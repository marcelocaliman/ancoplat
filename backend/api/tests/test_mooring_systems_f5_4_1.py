"""
Testes da F5.4.1 — schemas + persistência de mooring systems.

Cobre:
  - Migração cria tabela `mooring_systems` com constraints corretas.
  - Pydantic `MooringSystemInput` valida obrigatoriedade, faixas e
    duplicidade de nomes de linha.
  - CRUD via service: create / get / list / update / delete; round-trip
    do `config_json` preserva todos os campos.
"""
from __future__ import annotations

import copy
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError

from backend.api.db.migrations import run_migrations
from backend.api.db.models import MooringSystemRecord
from backend.api.schemas.mooring_systems import (
    MooringSystemInput,
    MooringSystemOutput,
    MooringSystemSummary,
)
from backend.api.services.mooring_system_service import (
    create_mooring_system,
    delete_mooring_system,
    get_mooring_system,
    list_mooring_systems,
    mooring_system_record_to_output,
    mooring_system_record_to_summary,
    update_mooring_system,
)
from backend.api.tests._fixtures import BC01_LIKE_INPUT


# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────


def _line_dict(name: str, az_deg: float, radius: float = 30.0) -> dict:
    """Constrói uma definição de SystemLineSpec a partir do BC-01."""
    case = copy.deepcopy(BC01_LIKE_INPUT)
    return {
        "name": name,
        "fairlead_azimuth_deg": az_deg,
        "fairlead_radius": radius,
        "segments": case["segments"],
        "boundary": case["boundary"],
        "seabed": case["seabed"],
        "criteria_profile": case["criteria_profile"],
    }


def _msys_payload(name: str = "Spread 4x simétrico") -> dict:
    return {
        "name": name,
        "description": "FPSO 60 m raio, 4 linhas a 90°.",
        "platform_radius": 30.0,
        "lines": [
            _line_dict("L1", 45.0),
            _line_dict("L2", 135.0),
            _line_dict("L3", 225.0),
            _line_dict("L4", 315.0),
        ],
    }


# ──────────────────────────────────────────────────────────────────────
# Migrações
# ──────────────────────────────────────────────────────────────────────


def test_migration_cria_tabela_mooring_systems(tmp_path: Path) -> None:
    """run_migrations cria `mooring_systems` num banco vazio."""
    db = tmp_path / "fresh.db"
    engine = create_engine(f"sqlite:///{db}")
    created = run_migrations(engine)
    assert "mooring_systems" in created
    cols = {c["name"] for c in inspect(engine).get_columns("mooring_systems")}
    assert {
        "id", "name", "description", "platform_radius", "line_count",
        "config_json", "created_at", "updated_at",
    }.issubset(cols)


def test_migration_idempotente_nao_recria(tmp_path: Path) -> None:
    db = tmp_path / "twice.db"
    engine = create_engine(f"sqlite:///{db}")
    run_migrations(engine)
    assert run_migrations(engine) == []


def test_check_constraints_recusam_dados_invalidos(tmp_db: Path) -> None:
    """name vazio, raio ≤ 0, line_count < 1 violam CHECK constraints."""
    from backend.api.db import session as ds
    cases = [
        dict(name="", description=None, platform_radius=30.0, line_count=4,
             config_json="{}"),
        dict(name="x", description=None, platform_radius=0.0, line_count=4,
             config_json="{}"),
        dict(name="x", description=None, platform_radius=30.0, line_count=0,
             config_json="{}"),
    ]
    for params in cases:
        with ds.SessionLocal() as db:
            db.add(MooringSystemRecord(**params))
            with pytest.raises(IntegrityError):
                db.commit()
            db.rollback()


# ──────────────────────────────────────────────────────────────────────
# Validação Pydantic
# ──────────────────────────────────────────────────────────────────────


def test_pydantic_aceita_payload_valido() -> None:
    msys = MooringSystemInput.model_validate(_msys_payload())
    assert msys.name == "Spread 4x simétrico"
    assert len(msys.lines) == 4
    assert msys.lines[0].fairlead_azimuth_deg == 45.0


def test_pydantic_rejeita_nomes_de_linha_duplicados() -> None:
    payload = _msys_payload()
    payload["lines"][1]["name"] = "L1"  # duplicada com lines[0]
    with pytest.raises(ValueError, match="duplicado"):
        MooringSystemInput.model_validate(payload)


def test_pydantic_rejeita_azimuth_fora_de_faixa() -> None:
    payload = _msys_payload()
    payload["lines"][0]["fairlead_azimuth_deg"] = 360.0
    with pytest.raises(Exception):
        MooringSystemInput.model_validate(payload)


def test_pydantic_rejeita_raio_zero_ou_negativo() -> None:
    payload = _msys_payload()
    payload["lines"][0]["fairlead_radius"] = 0.0
    with pytest.raises(Exception):
        MooringSystemInput.model_validate(payload)


def test_pydantic_rejeita_lista_de_linhas_vazia() -> None:
    payload = _msys_payload()
    payload["lines"] = []
    with pytest.raises(Exception):
        MooringSystemInput.model_validate(payload)


def test_pydantic_user_defined_exige_limites() -> None:
    payload = _msys_payload()
    payload["lines"][0]["criteria_profile"] = "UserDefined"
    with pytest.raises(ValueError, match="user_defined_limits"):
        MooringSystemInput.model_validate(payload)


# ──────────────────────────────────────────────────────────────────────
# CRUD via service
# ──────────────────────────────────────────────────────────────────────


def test_crud_round_trip(tmp_db: Path) -> None:
    """create → get → output round-trip preserva todos os campos."""
    from backend.api.db import session as ds
    msys = MooringSystemInput.model_validate(_msys_payload())
    with ds.SessionLocal() as db:
        rec = create_mooring_system(db, msys)
        assert rec.id is not None
        assert rec.line_count == 4

        fetched = get_mooring_system(db, rec.id)
        assert fetched is not None

        out = mooring_system_record_to_output(fetched)
        assert isinstance(out, MooringSystemOutput)
        # Round-trip do JSON: input preservado integralmente
        assert out.input == msys
        assert out.input.lines[2].name == "L3"
        assert out.input.lines[2].fairlead_azimuth_deg == 225.0


def test_summary_omite_config_json(tmp_db: Path) -> None:
    from backend.api.db import session as ds
    msys = MooringSystemInput.model_validate(_msys_payload())
    with ds.SessionLocal() as db:
        rec = create_mooring_system(db, msys)
        summary = mooring_system_record_to_summary(rec)
        assert isinstance(summary, MooringSystemSummary)
        assert summary.line_count == 4
        assert summary.platform_radius == 30.0
        # Pydantic do summary não tem `input` — confirma que é a versão enxuta.
        assert "input" not in summary.model_dump()


def test_list_paginacao_e_busca(tmp_db: Path) -> None:
    from backend.api.db import session as ds
    with ds.SessionLocal() as db:
        for n in ["Alpha 4x", "Beta 8x", "Alpha legacy"]:
            create_mooring_system(
                db, MooringSystemInput.model_validate(_msys_payload(name=n))
            )

        items, total = list_mooring_systems(db, page=1, page_size=10)
        assert total == 3
        assert len(items) == 3

        items, total = list_mooring_systems(db, page=1, page_size=2)
        assert total == 3
        assert len(items) == 2  # paginado

        items, total = list_mooring_systems(db, search="Alpha")
        assert total == 2
        assert all("Alpha" in r.name for r in items)


def test_update_substitui_config_e_recalcula_line_count(tmp_db: Path) -> None:
    from backend.api.db import session as ds
    msys = MooringSystemInput.model_validate(_msys_payload())
    with ds.SessionLocal() as db:
        rec = create_mooring_system(db, msys)

        # Atualiza para apenas 2 linhas
        new_payload = _msys_payload(name="Reduzido 2x")
        new_payload["lines"] = new_payload["lines"][:2]
        new_msys = MooringSystemInput.model_validate(new_payload)

        updated = update_mooring_system(db, rec.id, new_msys)
        assert updated is not None
        assert updated.line_count == 2
        assert updated.name == "Reduzido 2x"

        roundtrip = mooring_system_record_to_output(updated)
        assert len(roundtrip.input.lines) == 2


def test_update_de_id_inexistente_retorna_none(tmp_db: Path) -> None:
    from backend.api.db import session as ds
    msys = MooringSystemInput.model_validate(_msys_payload())
    with ds.SessionLocal() as db:
        assert update_mooring_system(db, 9999, msys) is None


def test_delete_remove_record(tmp_db: Path) -> None:
    from backend.api.db import session as ds
    msys = MooringSystemInput.model_validate(_msys_payload())
    with ds.SessionLocal() as db:
        rec = create_mooring_system(db, msys)
        assert delete_mooring_system(db, rec.id) is True
        assert get_mooring_system(db, rec.id) is None
        # Deletar duas vezes: segunda chamada retorna False.
        assert delete_mooring_system(db, rec.id) is False
