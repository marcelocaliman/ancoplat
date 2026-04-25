"""
seed_catalog.py — Importa o catálogo QMoor (legacy) para SQLite.

Lê docs/QMoor_database_inventory.xlsx (aba 'All Lines') e popula a tabela
line_types em backend/data/ancoplat.db. Todos os valores imperiais do catálogo
são convertidos para SI via Pint no momento da inserção.

Nota sobre nomenclatura: "QMoor" aqui se refere ao software LEGADO 0.8.5 do
qual o catálogo foi exportado (xlsx é arquivo de terceiros). O app que
estamos construindo se chama AncoPlat — não confundir.

Unidades armazenadas (SI):
  diameter           → m
  dry_weight         → N/m
  wet_weight         → N/m
  break_strength     → N
  modulus            → Pa
  qmoor_ea, gmoor_ea → N
  seabed_friction_cf → adimensional

PENDÊNCIAS DE VALIDAÇÃO (a levar ao engenheiro revisor):

  [R5Studless-friction] As 41 entradas de R5Studless trazem
  seabed_friction_cf = 0,6, enquanto as demais correntes (ORQChain,
  ORQ10, ORQ20, R4Chain, R5Chain, R4Studless) trazem 1,0. Valor
  preservado conforme decisão "Atrito de seabed — anomalia R5Studless"
  registrada em CLAUDE.md. O seed emite warning ao detectar.

Uso:
    python backend/data/seed_catalog.py

Idempotente: DROP + CREATE da tabela em cada execução.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pandas as pd
from pint import UnitRegistry

ROOT = Path(__file__).resolve().parents[2]
XLSX_PATH = ROOT / "docs" / "QMoor_database_inventory.xlsx"
DB_PATH = ROOT / "backend" / "data" / "ancoplat.db"

_ureg = UnitRegistry()
IN_TO_M: float = (1 * _ureg.inch).to("meter").magnitude
LBF_FT_TO_N_M: float = (1 * _ureg("lbf/ft")).to("N/m").magnitude
KIP_TO_N: float = (1 * _ureg.kip).to("newton").magnitude
KIP_IN2_TO_PA: float = (1 * _ureg("kip/inch**2")).to("pascal").magnitude

SCHEMA_SQL = """
CREATE TABLE line_types (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    legacy_id          INTEGER,
    line_type          TEXT    NOT NULL,
    category           TEXT    NOT NULL,
    base_unit_system   TEXT    NOT NULL,
    diameter           REAL    NOT NULL,
    dry_weight         REAL    NOT NULL,
    wet_weight         REAL    NOT NULL,
    break_strength     REAL    NOT NULL,
    modulus            REAL,
    qmoor_ea           REAL,
    gmoor_ea           REAL,
    seabed_friction_cf REAL    NOT NULL,
    data_source        TEXT    NOT NULL,
    manufacturer       TEXT,
    serial_number      TEXT,
    comments           TEXT,
    created_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_line_types_type_diameter
    ON line_types(line_type, diameter);
"""

INSERT_SQL = """
INSERT INTO line_types (
    legacy_id, line_type, category, base_unit_system,
    diameter, dry_weight, wet_weight, break_strength,
    modulus, qmoor_ea, gmoor_ea, seabed_friction_cf,
    data_source, manufacturer, serial_number, comments
) VALUES (
    :legacy_id, :line_type, :category, :base_unit_system,
    :diameter, :dry_weight, :wet_weight, :break_strength,
    :modulus, :qmoor_ea, :gmoor_ea, :seabed_friction_cf,
    :data_source, :manufacturer, :serial_number, :comments
);
"""


def load_catalog(xlsx_path: Path) -> pd.DataFrame:
    """Lê a aba 'All Lines' e descarta colunas fantasma e linhas vazias."""
    df = pd.read_excel(xlsx_path, sheet_name="All Lines")
    real_cols = [c for c in df.columns if not str(c).startswith("Unnamed")]
    return df[real_cols].dropna(subset=["line_type"]).reset_index(drop=True)


def _f(v) -> float | None:
    return None if pd.isna(v) else float(v)


def _s(v) -> str | None:
    return None if pd.isna(v) else str(v)


def convert_row_to_si(row: pd.Series) -> dict:
    """Converte uma entrada imperial para representação SI de inserção."""
    modulus = _f(row.get("modulus"))
    qmoor_ea = _f(row.get("qmoor_ea"))
    gmoor_ea = _f(row.get("gmoor_ea"))
    return {
        "legacy_id": int(row["id"]),
        "line_type": str(row["line_type"]),
        "category": str(row["category"]),
        "base_unit_system": str(row["base_unit_system"]),
        "diameter": float(row["diameter"]) * IN_TO_M,
        "dry_weight": float(row["dry_weight"]) * LBF_FT_TO_N_M,
        "wet_weight": float(row["wet_weight"]) * LBF_FT_TO_N_M,
        "break_strength": float(row["break_strength"]) * KIP_TO_N,
        "modulus": modulus * KIP_IN2_TO_PA if modulus is not None else None,
        "qmoor_ea": qmoor_ea * KIP_TO_N if qmoor_ea is not None else None,
        "gmoor_ea": gmoor_ea * KIP_TO_N if gmoor_ea is not None else None,
        "seabed_friction_cf": float(row["seabed_friction_cf"]),
        "data_source": str(row["data_source"]),
        "manufacturer": _s(row.get("manufacturer")),
        "serial_number": _s(row.get("serial_number")),
        "comments": _s(row.get("comments")),
    }


def detect_anomalies(df: pd.DataFrame) -> list[str]:
    """Detecta anomalias conhecidas no catálogo legado."""
    warnings: list[str] = []
    r5 = df.loc[df["line_type"] == "R5Studless", "seabed_friction_cf"].unique()
    r4 = df.loc[df["line_type"] == "R4Studless", "seabed_friction_cf"].unique()
    if len(r5) == 1 and len(r4) == 1 and r5[0] != r4[0]:
        warnings.append(
            f"[R5Studless-friction] μ={r5[0]:.2f} (41 entradas) difere do "
            f"R4Studless μ={r4[0]:.2f} (63 entradas) e das demais correntes "
            "(ORQ*, R4Chain, R5Chain — todas 1,0). Valor preservado por "
            "decisão técnica (CLAUDE.md). Pendência de validação."
        )
    return warnings


def main() -> int:
    if not XLSX_PATH.exists():
        print(f"ERRO: catálogo não encontrado em {XLSX_PATH}", file=sys.stderr)
        return 1

    print("=== AncoPlat — Seed do catálogo (QMoor legacy xlsx) ===")
    print(f"Origem:  {XLSX_PATH.relative_to(ROOT)}")
    print(f"Destino: {DB_PATH.relative_to(ROOT)}")
    print()

    df = load_catalog(XLSX_PATH)
    n_rows = len(df)
    n_types = df["line_type"].nunique()
    n_cats = df["category"].nunique()
    print(f"[1/4] Catálogo carregado: {n_rows} entradas, {n_types} tipos em {n_cats} categorias")

    warnings = detect_anomalies(df)
    if warnings:
        print(f"[2/4] Anomalias detectadas: {len(warnings)}")
        for w in warnings:
            print(f"  ⚠  {w}")
    else:
        print("[2/4] Nenhuma anomalia detectada")

    print(f"[3/4] Criando tabela line_types e inserindo {n_rows} registros (valores em SI)…")
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    rows = [convert_row_to_si(r) for _, r in df.iterrows()]
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("DROP TABLE IF EXISTS line_types")
        conn.executescript(SCHEMA_SQL)
        conn.executemany(INSERT_SQL, rows)
        conn.commit()
    finally:
        conn.close()

    print("[4/4] Verificação pós-seed:")
    conn = sqlite3.connect(DB_PATH)
    try:
        total = conn.execute("SELECT COUNT(*) FROM line_types").fetchone()[0]
        legacy_min, legacy_max = conn.execute(
            "SELECT MIN(legacy_id), MAX(legacy_id) FROM line_types"
        ).fetchone()
        by_cat = conn.execute(
            "SELECT category, COUNT(*) FROM line_types GROUP BY category ORDER BY category"
        ).fetchall()
        by_type = conn.execute(
            "SELECT category, line_type, COUNT(*) FROM line_types "
            "GROUP BY category, line_type ORDER BY category, line_type"
        ).fetchall()
    finally:
        conn.close()

    print(f"  Total de registros: {total}")
    print(f"  Range legacy_id:    {legacy_min}–{legacy_max}")
    print("  Distribuição por categoria:")
    for cat, n in by_cat:
        print(f"    {cat:15s} {n:4d}")
    print("  Distribuição por tipo:")
    for cat, lt, n in by_type:
        print(f"    {cat:15s} {lt:15s} {n:4d}")

    print()
    print(f"✓ Seed concluído. Banco: {DB_PATH}")
    if warnings:
        print(
            f"⚠ {len(warnings)} pendência(s) registrada(s). "
            "Ver cabeçalho PENDÊNCIAS DE VALIDAÇÃO em backend/data/seed_catalog.py."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
