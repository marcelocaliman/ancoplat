"""
Endpoints REST /vessel-types — Sprint 6 / Commit 51.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def seeded_client(client: TestClient, tmp_db) -> TestClient:
    """Aplica seed de vessels antes de chamar endpoints."""
    del tmp_db
    from backend.api.db import session as ds
    from backend.data.seed_vessels import seed_vessels
    with ds.SessionLocal() as db:
        seed_vessels(db)
    return client


def test_list_vessels_retorna_seed(seeded_client: TestClient) -> None:
    r = seeded_client.get("/api/v1/vessel-types")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 9
    assert len(data["items"]) == 9


def test_list_vessels_filtro_por_type(seeded_client: TestClient) -> None:
    r = seeded_client.get("/api/v1/vessel-types?vessel_type=AHV")
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 2  # 2 AHVs no seed
    for it in items:
        assert it["vessel_type"] == "AHV"


def test_list_vessels_search(seeded_client: TestClient) -> None:
    r = seeded_client.get("/api/v1/vessel-types?search=P-77")
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["name"] == "P-77 (FPSO)"


def test_get_vessel_por_id(seeded_client: TestClient) -> None:
    list_r = seeded_client.get("/api/v1/vessel-types?search=Spar")
    spar_id = list_r.json()["items"][0]["id"]
    r = seeded_client.get(f"/api/v1/vessel-types/{spar_id}")
    assert r.status_code == 200
    assert r.json()["vessel_type"] == "Spar"


def test_get_vessel_404(seeded_client: TestClient) -> None:
    r = seeded_client.get("/api/v1/vessel-types/99999")
    assert r.status_code == 404


def test_create_vessel_user_input(seeded_client: TestClient) -> None:
    payload = {
        "name": "MyCustomFPSO",
        "vessel_type": "FPSO",
        "loa": 280.0,
        "breadth": 50.0,
        "draft": 18.0,
        "displacement": 1_800_000_000.0,
        "operator": "MyCompany",
    }
    r = seeded_client.post("/api/v1/vessel-types", json=payload)
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "MyCustomFPSO"
    assert body["data_source"] == "user_input"


def test_update_vessel_seed_canonico_403(seeded_client: TestClient) -> None:
    """Vessels com data_source legacy_qmoor/generic_offshore são imutáveis."""
    list_r = seeded_client.get("/api/v1/vessel-types?search=P-77")
    p77_id = list_r.json()["items"][0]["id"]
    r = seeded_client.put(
        f"/api/v1/vessel-types/{p77_id}",
        json={
            "name": "Hacked",
            "vessel_type": "FPSO",
            "loa": 100.0,
            "breadth": 20.0,
            "draft": 5.0,
        },
    )
    assert r.status_code == 403
    body = r.json()
    # FastAPI pode ou não wrappar em {"detail": ...}; aceita ambos.
    detail = body.get("detail") if isinstance(body.get("detail"), dict) else body
    assert "immutable" in str(detail).lower() or "imutável" in str(detail).lower()


def test_delete_vessel_seed_canonico_403(seeded_client: TestClient) -> None:
    list_r = seeded_client.get("/api/v1/vessel-types?search=P-77")
    p77_id = list_r.json()["items"][0]["id"]
    r = seeded_client.delete(f"/api/v1/vessel-types/{p77_id}")
    assert r.status_code == 403


def test_update_user_input_funciona(seeded_client: TestClient) -> None:
    """user_input pode ser editado."""
    create_r = seeded_client.post("/api/v1/vessel-types", json={
        "name": "Editable",
        "vessel_type": "FPSO",
        "loa": 200.0, "breadth": 40.0, "draft": 15.0,
    })
    new_id = create_r.json()["id"]
    r = seeded_client.put(f"/api/v1/vessel-types/{new_id}", json={
        "name": "Edited",
        "vessel_type": "FPSO",
        "loa": 250.0, "breadth": 45.0, "draft": 16.0,
    })
    assert r.status_code == 200
    assert r.json()["loa"] == 250.0


def test_delete_user_input_funciona(seeded_client: TestClient) -> None:
    create_r = seeded_client.post("/api/v1/vessel-types", json={
        "name": "ToDelete",
        "vessel_type": "FPSO",
        "loa": 200.0, "breadth": 40.0, "draft": 15.0,
    })
    new_id = create_r.json()["id"]
    r = seeded_client.delete(f"/api/v1/vessel-types/{new_id}")
    assert r.status_code == 200
    # Confirma que sumiu
    g = seeded_client.get(f"/api/v1/vessel-types/{new_id}")
    assert g.status_code == 404


def test_create_vessel_loa_zero_422(seeded_client: TestClient) -> None:
    r = seeded_client.post("/api/v1/vessel-types", json={
        "name": "Bad",
        "vessel_type": "FPSO",
        "loa": 0.0, "breadth": 40.0, "draft": 15.0,
    })
    assert r.status_code == 422
