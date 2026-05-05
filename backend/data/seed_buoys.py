"""
seed_buoys.py — Popula o catálogo de boias (F6).

Inicialmente o catálogo de boias não tinha fonte tabelada (ao contrário
do `line_types`, que vem de `QMoor_database_inventory.xlsx`). O Excel
`docs/Cópia de Buoy_Calculation_Imperial_English.xlsx` é apenas um
template de cálculo — não traz tabela de modelos comerciais. Usamos
ele como fonte de **fórmulas** (Formula Guide R4-R7) e completamos com:

  - 1 entrada `excel_buoy_calc_v1`: a única linha real do template
    (R7 da aba "Buoy Calculation"), convertida para SI.
  - ≥ 10 entradas `generic_offshore`: dimensões típicas de boias
    submergíveis offshore (lazy-S, wave attenuators, marker buoys),
    cobrindo os 4 end_types em pelo menos 2 dimensões cada (alinhado
    com os testes de empuxo).

Cada entrada tem `data_source` documentado (Q2 da F6). Entradas seed
são imutáveis pelo serviço (`buoy_service.IMMUTABLE_SOURCES`).

Idempotente: detecta entradas pré-existentes pela combinação
(name, data_source) e não duplica.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Permite executar como `python backend/data/seed_buoys.py` (script).
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy.orm import Session

from backend.api.db.migrations import run_migrations
from backend.api.db.models import BuoyRecord
from backend.api.db.session import SessionLocal, engine
from backend.api.services.buoyancy import compute_submerged_force


# ─────────────────────────────────────────────────────────────────
# Conversões imperial → SI usadas no item excel_buoy_calc_v1.
# ─────────────────────────────────────────────────────────────────
FT_TO_M = 0.3048
KIP_TO_N = 4448.2216152605  # 1 kip = 1000 lbf


def _buoy(
    name: str,
    buoy_type: str,
    end_type: str,
    diameter_m: float,
    length_m: float,
    weight_n: float,
    data_source: str,
    *,
    legacy_id: int | None = None,
    base_unit_system: str = "metric",
    manufacturer: str | None = None,
    serial_number: str | None = None,
    comments: str | None = None,
) -> dict:
    """
    Compõe o dict de uma entrada do seed. `submerged_force` é calculado
    a partir da função canônica para garantir consistência com a fórmula
    citada no `data_source`.
    """
    submerged_force = compute_submerged_force(
        end_type=end_type,
        outer_diameter=diameter_m,
        length=length_m,
        weight_in_air=weight_n,
    )
    return {
        "legacy_id": legacy_id,
        "name": name,
        "buoy_type": buoy_type,
        "end_type": end_type,
        "base_unit_system": base_unit_system,
        "outer_diameter": diameter_m,
        "length": length_m,
        "weight_in_air": weight_n,
        "submerged_force": submerged_force,
        "data_source": data_source,
        "manufacturer": manufacturer,
        "serial_number": serial_number,
        "comments": comments,
    }


def build_seed_payload() -> list[dict]:
    """
    Retorna a lista canônica de entradas do seed.

    Cada entrada cita explicitamente a origem:
    - `excel_buoy_calc_v1`  : Excel R7, imperial convertido para SI.
    - `generic_offshore`    : dimensões típicas de campo, fórmula de empuxo
                              ancorada em Excel Formula Guide R4-R7.
    """
    items: list[dict] = []

    # ─── 1) Entrada do template Excel "Buoy Calculation" R7 ────────
    # L=7 ft, D=4 ft, weight=22 kip, hemispherical.
    # Convertido para SI: L=2.1336 m, D=1.2192 m, weight=97860.88 N.
    items.append(_buoy(
        legacy_id=1,
        name="ExcelBuoyCalc-Hemi-7x4ft",
        buoy_type="submersible",
        end_type="hemispherical",
        diameter_m=4 * FT_TO_M,           # 1.2192 m
        length_m=7 * FT_TO_M,             # 2.1336 m
        weight_n=22 * KIP_TO_N,           # 97860.88 N
        data_source="excel_buoy_calc_v1",
        base_unit_system="imperial",
        comments=(
            "Convertido do Excel `Cópia de Buoy_Calculation_Imperial_"
            "English.xlsx`, sheet 'Buoy Calculation' R7 (L=7ft, D=4ft, "
            "weight=22 kip). Empuxo líquido fica negativo (peso > empuxo) "
            "— exemplo serve como referência didática, não como boia útil."
        ),
    ))

    # ─── 2..N) Genéricos offshore — 4 end_types × 2-3 dimensões ────
    # Faixa típica: D 1.0–3.0 m, L 2.0–4.5 m, weight ~5–15 kN.
    # Para a maioria dessas dimensões o empuxo líquido é positivo
    # (boia útil). Submerged_force calculado pela fórmula F6.
    generic_specs = [
        # (name, end_type, D, L, weight_in_air, comments)
        ("GEN-Flat-D1.0-L4.0",        "flat",          1.0, 4.0, 1500.0,
         "Boia cilíndrica reta — marker buoy genérica."),
        ("GEN-Flat-D2.0-L3.0",        "flat",          2.0, 3.0, 4900.0,
         "Boia cilíndrica reta — wave attenuator genérica."),
        ("GEN-Hemi-D1.5-L2.5",        "hemispherical", 1.5, 2.5, 3000.0,
         "Boia cilíndrica com tampas hemisféricas — submergível pequena."),
        ("GEN-Hemi-D3.0-L4.0",        "hemispherical", 3.0, 4.0, 15000.0,
         "Boia cilíndrica com tampas hemisféricas — lazy-S grande."),
        ("GEN-Ellip-D2.0-L3.0",       "elliptical",    2.0, 3.0, 4900.0,
         "Boia cilíndrica com tampas elípticas — submergível média."),
        ("GEN-Ellip-D2.5-L3.5",       "elliptical",    2.5, 3.5, 8000.0,
         "Boia cilíndrica com tampas elípticas — lazy-S intermediária."),
        ("GEN-Conic-D2.0-L2.5",       "semi_conical",  2.0, 2.5, 4900.0,
         "Boia cilíndrica com tampas cônicas — wave attenuator média."),
        ("GEN-Conic-D3.0-L4.0",       "semi_conical",  3.0, 4.0, 15000.0,
         "Boia cilíndrica com tampas cônicas — lazy-S grande."),
        ("GEN-Surf-Flat-D1.5-L2.0",   "flat",          1.5, 2.0, 2000.0,
         "Boia de superfície — marker simples."),
        ("GEN-Surf-Hemi-D2.0-L2.5",   "hemispherical", 2.0, 2.5, 5000.0,
         "Boia de superfície — marker hemisférica."),
    ]
    for legacy_id, (name, end_type, d, l, w, comm) in enumerate(generic_specs, start=2):
        items.append(_buoy(
            legacy_id=legacy_id,
            name=name,
            buoy_type=("surface" if "Surf" in name else "submersible"),
            end_type=end_type,
            diameter_m=d,
            length_m=l,
            weight_n=w,
            data_source="generic_offshore",
            comments=(
                f"{comm} Empuxo derivado via Excel Formula Guide "
                f"({end_type})."
            ),
        ))

    return items


def seed(db: Session, *, replace_existing: bool = False) -> dict[str, int]:
    """
    Insere entradas do seed em `buoys`. Idempotente:
    - Se entrada com mesmo `(name, data_source)` já existe, **pula**.
    - `replace_existing=True` deleta entradas seed antes de re-inserir
      (não toca em `user_input`).

    Retorna estatísticas: `inserted`, `skipped`, `replaced`.
    """
    payload = build_seed_payload()

    if replace_existing:
        # Apaga só entradas seed (preserva user_input)
        db.query(BuoyRecord).filter(
            BuoyRecord.data_source.in_(["excel_buoy_calc_v1", "generic_offshore"])
        ).delete(synchronize_session=False)
        db.commit()

    inserted = 0
    skipped = 0
    for item in payload:
        existing = (
            db.query(BuoyRecord)
            .filter_by(name=item["name"], data_source=item["data_source"])
            .first()
        )
        if existing is not None:
            skipped += 1
            continue
        rec = BuoyRecord(**item)
        db.add(rec)
        inserted += 1

    db.commit()
    return {
        "inserted": inserted,
        "skipped": skipped,
        "replaced": len(payload) if replace_existing else 0,
    }


def main() -> None:
    run_migrations(engine)
    with SessionLocal() as db:
        stats = seed(db)
        total = db.query(BuoyRecord).count()
    print(
        f"Seed buoys: inserted={stats['inserted']}, skipped={stats['skipped']}, "
        f"replaced={stats['replaced']}, total_no_db={total}"
    )


if __name__ == "__main__":
    main()
