"""
Testes do seed de boias (F6 / Q2 + Q9).

AC:
  - ≥ 10 entradas no seed final.
  - Cada entrada tem `data_source` documentado (não vazio, não user_input).
  - Idempotência: rodar o seed duas vezes não duplica entradas.
  - submerged_force consistente com fórmula de empuxo (F = V·ρ·g − w).
"""
from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from backend.api.db.models import BuoyRecord
from backend.api.services.buoyancy import compute_submerged_force
from backend.data.seed_buoys import build_seed_payload, seed


# ─── Fixture local: roda seed em DB temporário ─────────────────


@pytest.fixture()
def seeded_db(tmp_db) -> Session:
    """Aplica o seed canônico em DB temp e retorna a sessão."""
    del tmp_db
    from backend.api.db import session as ds

    with ds.SessionLocal() as db:
        seed(db)
        yield db


# ─── AC do plano ────────────────────────────────────────────────


def test_seed_tem_ao_menos_10_entradas():
    """AC F6 / Q9 (ajuste do usuário): mínimo 10 boias no seed."""
    payload = build_seed_payload()
    assert len(payload) >= 10, (
        f"Seed deve ter ≥ 10 entradas (Q9 ajustado), tem {len(payload)}"
    )


def test_seed_cobre_4_end_types():
    """Q3: 4 end_types canônicos representados no seed."""
    payload = build_seed_payload()
    end_types = {p["end_type"] for p in payload}
    assert end_types == {"flat", "hemispherical", "elliptical", "semi_conical"}, (
        f"Seed deve cobrir os 4 end_types; cobre {end_types}"
    )


def test_cada_entrada_tem_data_source_documentado():
    """Q2: cada entrada cita explicitamente origem (não vazio, não user_input)."""
    payload = build_seed_payload()
    valid_sources = {"excel_buoy_calc_v1", "generic_offshore"}
    for item in payload:
        assert item["data_source"], f"{item['name']} sem data_source"
        assert item["data_source"] in valid_sources or item["data_source"].startswith(
            "manufacturer"
        ), (
            f"{item['name']} com data_source desconhecido: "
            f"{item['data_source']!r}"
        )
        assert item["data_source"] != "user_input", (
            f"{item['name']} marcado como user_input no seed — viola Q2"
        )


def test_seed_inclui_excel_buoy_calc_v1():
    """Q2: ao menos 1 entrada cita o Excel R7 como origem."""
    payload = build_seed_payload()
    excel_sourced = [p for p in payload if p["data_source"] == "excel_buoy_calc_v1"]
    assert len(excel_sourced) >= 1, "Seed deve incluir ≥ 1 entrada Excel R7"


def test_seed_idempotente(tmp_db):
    """Rodar duas vezes não duplica entradas."""
    del tmp_db
    from backend.api.db import session as ds

    with ds.SessionLocal() as db:
        stats1 = seed(db)
        n_after_first = db.query(BuoyRecord).count()
        stats2 = seed(db)
        n_after_second = db.query(BuoyRecord).count()

    assert stats1["inserted"] >= 10
    assert stats2["inserted"] == 0, "Segunda execução não deveria inserir"
    assert stats2["skipped"] == stats1["inserted"]
    assert n_after_first == n_after_second


def test_submerged_force_consistente_com_formula(seeded_db: Session):
    """submerged_force armazenado bate com compute_submerged_force()."""
    for rec in seeded_db.query(BuoyRecord).all():
        expected = compute_submerged_force(
            end_type=rec.end_type,
            outer_diameter=rec.outer_diameter,
            length=rec.length,
            weight_in_air=rec.weight_in_air,
        )
        # tolerância 0.01% só para evitar artefato de float roundtrip
        assert abs(rec.submerged_force - expected) <= 1e-6 * max(
            abs(expected), 1.0
        ), f"{rec.name}: stored={rec.submerged_force}, expected={expected}"


def test_replace_existing_remove_seed_existente(tmp_db):
    """`replace_existing=True` reseta entradas seed (não user_input)."""
    del tmp_db
    from backend.api.db import session as ds

    with ds.SessionLocal() as db:
        seed(db)
        n_seed_first = db.query(BuoyRecord).count()
        # Adiciona 1 user_input "manualmente"
        custom = BuoyRecord(
            name="UserCustom",
            buoy_type="submersible",
            end_type="flat",
            base_unit_system="metric",
            outer_diameter=1.0,
            length=2.0,
            weight_in_air=500.0,
            submerged_force=15000.0,
            data_source="user_input",
        )
        db.add(custom)
        db.commit()

        stats = seed(db, replace_existing=True)
        n_after_replace = db.query(BuoyRecord).count()
        # n_after_replace = entradas seed novas + 1 user_input preservada
        assert stats["replaced"] == n_seed_first
        assert n_after_replace == n_seed_first + 1
        # user_input preservado
        kept = db.query(BuoyRecord).filter_by(data_source="user_input").all()
        assert len(kept) == 1 and kept[0].name == "UserCustom"


def test_seed_combina_excel_e_generic(seeded_db: Session):
    """Q2 (c): seed final combina ambas as fontes (Excel + generic)."""
    sources = {
        rec.data_source
        for rec in seeded_db.query(BuoyRecord).all()
    }
    assert "excel_buoy_calc_v1" in sources
    assert "generic_offshore" in sources
