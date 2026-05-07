"""
Testes do catálogo `vessel_types` — Sprint 6 / Commit 50.
"""
from __future__ import annotations

import pytest

from backend.api.db.models import VesselTypeRecord
from backend.data.seed_vessels import seed_vessels


@pytest.fixture()
def seeded_vessels(tmp_db):
    del tmp_db
    from backend.api.db import session as ds
    with ds.SessionLocal() as db:
        seed_vessels(db)
        yield db


def test_seed_insere_9_vessels_canonicos(seeded_vessels) -> None:
    total = seeded_vessels.query(VesselTypeRecord).count()
    assert total == 9


def test_seed_idempotente(tmp_db) -> None:
    del tmp_db
    from backend.api.db import session as ds
    with ds.SessionLocal() as db:
        n1 = seed_vessels(db)
        n2 = seed_vessels(db)
        assert n1 == 9
        assert n2 == 0
        assert db.query(VesselTypeRecord).count() == 9


def test_seed_cobre_categorias_principais(seeded_vessels) -> None:
    types = {v.vessel_type for v in seeded_vessels.query(VesselTypeRecord).all()}
    for required in ("FPSO", "Semisubmersible", "Spar", "AHV", "Drillship", "Barge"):
        assert required in types, f"categoria {required} ausente do seed"


def test_seed_p77_tem_dados_realistas(seeded_vessels) -> None:
    """P-77 (FPSO Petrobras-tipo) é o vessel-âncora dos exemplos QMoor."""
    p77 = (
        seeded_vessels.query(VesselTypeRecord)
        .filter(VesselTypeRecord.name == "P-77 (FPSO)")
        .first()
    )
    assert p77 is not None
    assert p77.vessel_type == "FPSO"
    assert p77.loa == 320.0
    assert p77.breadth == 58.0
    assert p77.draft == 21.0
    assert p77.operator == "Petrobras"
    assert p77.data_source == "legacy_qmoor"
    assert p77.legacy_id == 1


def test_seed_dimensoes_positivas(seeded_vessels) -> None:
    for v in seeded_vessels.query(VesselTypeRecord).all():
        assert v.loa > 0
        assert v.breadth > 0
        assert v.draft > 0


def test_constraint_loa_positiva_rejeita_zero(tmp_db) -> None:
    """CheckConstraint do schema rejeita loa <= 0 a nível de DB."""
    from sqlalchemy.exc import IntegrityError
    from backend.api.db import session as ds
    del tmp_db
    with ds.SessionLocal() as db:
        bad = VesselTypeRecord(
            name="Bad LOA",
            vessel_type="FPSO",
            base_unit_system="metric",
            loa=0.0,
            breadth=10.0,
            draft=5.0,
            data_source="user_input",
        )
        db.add(bad)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
