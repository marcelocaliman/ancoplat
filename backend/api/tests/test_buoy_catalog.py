"""
Testes dos endpoints REST de boias (F6).

Cobre paginação, busca, filtros, criação, edição, remoção, e proteção
de entradas seed (data_source canônico não pode ser modificado).
"""
from __future__ import annotations

from fastapi.testclient import TestClient


# ─── Smoke ──────────────────────────────────────────────────────────


def test_list_buoys_vazio_quando_sem_seed(client: TestClient):
    """DB temp sem seed retorna lista vazia."""
    resp = client.get("/api/v1/buoys")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 0
    assert body["items"] == []


def test_list_buoys_retorna_seed_canonico(
    client: TestClient, seeded_buoys: list[int],
):
    """Com seed aplicado, lista paginada traz ≥10 entradas."""
    resp = client.get("/api/v1/buoys")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 10
    assert len(body["items"]) == body["total"]  # ≤ 50 = page_size default
    # Cada item tem campos canônicos
    item = body["items"][0]
    for k in ("id", "name", "buoy_type", "end_type",
              "outer_diameter", "length", "weight_in_air",
              "submerged_force", "data_source"):
        assert k in item, f"campo {k!r} ausente"
    assert seeded_buoys  # noqa: usado pelo fixture


# ─── Paginação ──────────────────────────────────────────────────────


def test_paginacao_respeita_page_size(
    client: TestClient, seeded_buoys: list[int],
):
    del seeded_buoys
    resp = client.get("/api/v1/buoys", params={"page": 1, "page_size": 3})
    body = resp.json()
    assert resp.status_code == 200
    assert len(body["items"]) == 3
    assert body["page"] == 1
    assert body["page_size"] == 3


def test_paginacao_pagina_2_traz_diferentes(
    client: TestClient, seeded_buoys: list[int],
):
    del seeded_buoys
    page1 = client.get("/api/v1/buoys", params={"page": 1, "page_size": 5}).json()
    page2 = client.get("/api/v1/buoys", params={"page": 2, "page_size": 5}).json()
    ids1 = {i["id"] for i in page1["items"]}
    ids2 = {i["id"] for i in page2["items"]}
    assert not (ids1 & ids2), "Páginas 1 e 2 não podem ter overlap"


# ─── Filtros ────────────────────────────────────────────────────────


def test_filtro_por_end_type(client: TestClient, seeded_buoys: list[int]):
    del seeded_buoys
    resp = client.get("/api/v1/buoys", params={"end_type": "elliptical"})
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert all(i["end_type"] == "elliptical" for i in items)
    assert len(items) >= 1


def test_filtro_por_buoy_type(client: TestClient, seeded_buoys: list[int]):
    del seeded_buoys
    resp = client.get("/api/v1/buoys", params={"buoy_type": "surface"})
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert all(i["buoy_type"] == "surface" for i in items)


def test_busca_por_nome_ilike(client: TestClient, seeded_buoys: list[int]):
    del seeded_buoys
    resp = client.get("/api/v1/buoys", params={"search": "Hemi"})
    body = resp.json()
    assert resp.status_code == 200
    assert all("hemi" in i["name"].lower() for i in body["items"])


# ─── GET por id ─────────────────────────────────────────────────────


def test_get_buoy_by_id(client: TestClient, seeded_buoys: list[int]):
    buoy_id = seeded_buoys[0]
    resp = client.get(f"/api/v1/buoys/{buoy_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == buoy_id


def test_get_buoy_404_quando_inexistente(
    client: TestClient, seeded_buoys: list[int],
):
    del seeded_buoys
    resp = client.get("/api/v1/buoys/99999")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "buoy_not_found"


# ─── POST (create user_input) ──────────────────────────────────────


def _custom_payload() -> dict:
    return {
        "name": "MyTestBuoy",
        "buoy_type": "submersible",
        "end_type": "flat",
        "outer_diameter": 1.5,
        "length": 2.5,
        "weight_in_air": 2500.0,
        "submerged_force": 40000.0,
        "manufacturer": "Acme",
    }


def test_create_buoy_user_input(client: TestClient):
    resp = client.post("/api/v1/buoys", json=_custom_payload())
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["name"] == "MyTestBuoy"
    assert body["data_source"] == "user_input"
    assert "id" in body


def test_create_buoy_invalid_422(client: TestClient):
    """diâmetro negativo → 422 Pydantic."""
    payload = _custom_payload()
    payload["outer_diameter"] = -1.0
    resp = client.post("/api/v1/buoys", json=payload)
    assert resp.status_code == 422


# ─── PUT ────────────────────────────────────────────────────────────


def test_update_buoy_user_input_ok(client: TestClient):
    created = client.post("/api/v1/buoys", json=_custom_payload()).json()
    new_payload = {**_custom_payload(), "name": "MyTestBuoy-Updated"}
    resp = client.put(f"/api/v1/buoys/{created['id']}", json=new_payload)
    assert resp.status_code == 200
    assert resp.json()["name"] == "MyTestBuoy-Updated"


def test_update_buoy_seed_403(client: TestClient, seeded_buoys: list[int]):
    """Tentativa de editar entrada seed retorna 403."""
    seed_id = seeded_buoys[0]
    payload = _custom_payload()
    resp = client.put(f"/api/v1/buoys/{seed_id}", json=payload)
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "buoy_immutable"


def test_update_buoy_404(client: TestClient):
    resp = client.put("/api/v1/buoys/9999", json=_custom_payload())
    assert resp.status_code == 404


# ─── DELETE ─────────────────────────────────────────────────────────


def test_delete_buoy_user_input_ok(client: TestClient):
    created = client.post("/api/v1/buoys", json=_custom_payload()).json()
    resp = client.delete(f"/api/v1/buoys/{created['id']}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "deleted"
    # confirmacao: GET subsequente é 404
    assert client.get(f"/api/v1/buoys/{created['id']}").status_code == 404


def test_delete_buoy_seed_403(client: TestClient, seeded_buoys: list[int]):
    seed_id = seeded_buoys[0]
    resp = client.delete(f"/api/v1/buoys/{seed_id}")
    assert resp.status_code == 403


def test_delete_buoy_404(client: TestClient):
    resp = client.delete("/api/v1/buoys/9999")
    assert resp.status_code == 404
