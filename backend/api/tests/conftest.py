"""Fixtures de teste para a API QMoor Web."""
from __future__ import annotations

from pathlib import Path
from typing import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.api.db import session as db_session_module
from backend.api.db.migrations import run_migrations
from backend.api.db.models import LineTypeRecord
from backend.api.main import app


@pytest.fixture()
def tmp_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """
    Isola cada teste em um banco SQLite temporário.

    Faz monkey-patch no engine/SessionLocal do módulo db.session para
    apontar para `tmp_path/qmoor_test.db`. A dependency get_db continua
    funcionando pois lê SessionLocal dinamicamente.
    """
    db_path = tmp_path / "qmoor_test.db"
    url = f"sqlite:///{db_path}"
    engine = create_engine(url, connect_args={"check_same_thread": False})
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    monkeypatch.setattr(db_session_module, "engine", engine)
    monkeypatch.setattr(db_session_module, "SessionLocal", SessionLocal)
    monkeypatch.setattr(db_session_module, "DB_PATH", db_path)

    # Aplica migrations no banco temporário (cria cases/executions/app_config).
    # line_types não é criada aqui — testes que precisam do catálogo devem
    # usar a fixture `seeded_catalog` (a ser adicionada em F2.5).
    run_migrations(engine)

    yield db_path

    engine.dispose()


@pytest.fixture()
def client(tmp_db: Path) -> Iterator[TestClient]:
    """TestClient do FastAPI com banco temporário já configurado."""
    del tmp_db
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def seeded_catalog(tmp_db: Path) -> Iterator[list[int]]:
    """
    Popula o banco temporário com algumas entradas de catálogo (mix
    legacy_qmoor e user_input). Retorna a lista de ids criados.

    Usado pelos testes que precisam validar o catálogo (F2.5, F2.6).
    """
    del tmp_db
    seeds = [
        dict(
            legacy_id=1, line_type="IWRCEIPS", category="Wire",
            base_unit_system="imperial",
            diameter=0.0254, dry_weight=27.0, wet_weight=22.4,
            break_strength=459_946.0, modulus=6.76e10,
            qmoor_ea=3.42e7, gmoor_ea=4.96e7,
            seabed_friction_cf=0.6, data_source="legacy_qmoor",
        ),
        dict(
            legacy_id=2, line_type="IWRCEIPS", category="Wire",
            base_unit_system="imperial",
            diameter=0.02858, dry_weight=34.2, wet_weight=28.3,
            break_strength=578_268.0, modulus=6.76e10,
            qmoor_ea=4.33e7, gmoor_ea=6.28e7,
            seabed_friction_cf=0.6, data_source="legacy_qmoor",
        ),
        dict(
            legacy_id=100, line_type="R4Studless", category="StudlessChain",
            base_unit_system="imperial",
            diameter=0.0762, dry_weight=1240.0, wet_weight=1058.0,
            break_strength=6_001_000.0, modulus=1.28e11,
            qmoor_ea=8.2e7, gmoor_ea=7.18e7,
            seabed_friction_cf=1.0, data_source="legacy_qmoor",
        ),
    ]
    from backend.api.db import session as ds
    ids: list[int] = []
    with ds.SessionLocal() as db:
        for s in seeds:
            rec = LineTypeRecord(**s)
            db.add(rec)
            db.commit()
            db.refresh(rec)
            ids.append(rec.id)
    yield ids
