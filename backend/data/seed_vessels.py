"""
seed_vessels.py — Popula o catálogo de vessels (Sprint 6 / Commit 50).

Análogo a `seed_buoys.py` (F6) e à seed do catálogo de line_types
(F1a). Não há fonte tabelada externa para vessels — usamos vessels
canônicos representativos das classes principais offshore:

  - 1× FPSO Petrobras-tipo (P-77): vessel real do KAR006/exemplos QMoor.
  - 1× FPSO Tipo 1 genérico: dimensões médias de FPSO Suezmax-class.
  - 1× Atlanta-class (Semisub): plataforma típica em águas brasileiras.
  - 1× Semisub genérico: dimensões médias para projetos preliminares.
  - 1× Spar genérico: cilíndrico vertical (tipo Aera/Genesis).
  - 1× AHV 200 te: Anchor Handler Vessel high-end (DP3).
  - 1× AHV 100 te: AHV intermediário.
  - 1× Drillship genérico.
  - 1× Barge MODU: barcaça transportadora pesada.

Cada entrada tem `data_source` documentado (mesmo padrão Q2 da F6).
Entradas seed são imutáveis pelo serviço (vessel_service.IMMUTABLE_SOURCES).

Idempotente: detecta entradas pré-existentes pela combinação
(name, data_source) e não duplica.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy.orm import Session

from backend.api.db.migrations import run_migrations
from backend.api.db.models import VesselTypeRecord
from backend.api.db.session import SessionLocal, engine


def _vessel(
    name: str,
    vessel_type: str,
    *,
    loa: float,
    breadth: float,
    draft: float,
    displacement: float | None = None,
    default_heading_deg: float = 0.0,
    operator: str | None = None,
    data_source: str = "generic_offshore",
    legacy_id: int | None = None,
    comments: str | None = None,
) -> dict:
    return {
        "name": name,
        "vessel_type": vessel_type,
        "base_unit_system": "metric",
        "loa": loa,
        "breadth": breadth,
        "draft": draft,
        "displacement": displacement,
        "default_heading_deg": default_heading_deg,
        "data_source": data_source,
        "legacy_id": legacy_id,
        "operator": operator,
        "comments": comments,
    }


# ─────────────────────────────────────────────────────────────────
# 9 vessels canônicos — cobertura representativa das classes principais.
# Dimensões em SI (m) e displacement em N (peso, não massa).
# ─────────────────────────────────────────────────────────────────
SEED_VESSELS = [
    # FPSOs
    _vessel(
        "P-77 (FPSO)", "FPSO",
        loa=320.0, breadth=58.0, draft=21.0,
        displacement=2_400_000_000.0,  # ~245 kt × 9.81
        operator="Petrobras",
        data_source="legacy_qmoor",
        legacy_id=1,
        comments="FPSO classe P-77 — Bacia de Santos. Dimensões típicas.",
    ),
    _vessel(
        "FPSO Tipo Suezmax", "FPSO",
        loa=274.0, breadth=48.0, draft=17.0,
        displacement=1_700_000_000.0,
        data_source="generic_offshore",
        comments="FPSO Suezmax-class (genérico) para projetos preliminares.",
    ),
    # Semisubs
    _vessel(
        "Atlanta (Semisub)", "Semisubmersible",
        loa=110.0, breadth=85.0, draft=22.0,
        displacement=420_000_000.0,
        operator="Petrobras",
        data_source="generic_offshore",
        comments="Semisub classe Atlanta — Bacia de Campos.",
    ),
    _vessel(
        "Semisub Genérico", "Semisubmersible",
        loa=105.0, breadth=80.0, draft=20.0,
        displacement=400_000_000.0,
        data_source="generic_offshore",
        comments="Semisub deepwater (genérico).",
    ),
    # Spar
    _vessel(
        "Spar Genérico", "Spar",
        loa=215.0, breadth=37.0, draft=200.0,
        displacement=1_200_000_000.0,
        data_source="generic_offshore",
        comments="Spar cilíndrico vertical (tipo Aera/Genesis).",
    ),
    # AHVs (Anchor Handler Vessels)
    _vessel(
        "AHV 200 te", "AHV",
        loa=92.0, breadth=22.0, draft=8.0,
        displacement=80_000_000.0,
        default_heading_deg=180.0,  # popa para a plataforma
        data_source="generic_offshore",
        comments="AHV high-end 200 te bollard (DP3).",
    ),
    _vessel(
        "AHV 100 te", "AHV",
        loa=82.0, breadth=20.0, draft=7.0,
        displacement=55_000_000.0,
        default_heading_deg=180.0,
        data_source="generic_offshore",
        comments="AHV intermediário 100 te bollard.",
    ),
    # Drillship
    _vessel(
        "Drillship Genérico", "Drillship",
        loa=230.0, breadth=42.0, draft=12.0,
        displacement=900_000_000.0,
        data_source="generic_offshore",
        comments="Drillship deepwater genérico.",
    ),
    # Barge
    _vessel(
        "Barge MODU", "Barge",
        loa=140.0, breadth=42.0, draft=6.0,
        displacement=300_000_000.0,
        data_source="generic_offshore",
        comments="Barcaça MODU (Mobile Offshore Drilling Unit).",
    ),
]


def seed_vessels(session: Session) -> int:
    """
    Insere os 9 vessels canônicos no DB se não existirem.

    Idempotente: identifica duplicatas pela combinação (name, data_source).
    Retorna número de novas entradas inseridas.
    """
    inserted = 0
    for entry in SEED_VESSELS:
        existing = (
            session.query(VesselTypeRecord)
            .filter(
                VesselTypeRecord.name == entry["name"],
                VesselTypeRecord.data_source == entry["data_source"],
            )
            .first()
        )
        if existing is not None:
            continue
        rec = VesselTypeRecord(**entry)
        session.add(rec)
        inserted += 1
    session.commit()
    return inserted


def main() -> None:
    print("Seed de vessels (Sprint 6 / Commit 50)…")
    run_migrations(engine)
    with SessionLocal() as session:
        n = seed_vessels(session)
        print(f"Inseridas {n} novas entradas no catálogo vessel_types.")
        total = session.query(VesselTypeRecord).count()
        print(f"Total de entradas no catálogo: {total}")


if __name__ == "__main__":
    main()
