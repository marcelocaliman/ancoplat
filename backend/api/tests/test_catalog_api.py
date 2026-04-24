"""Testes do catálogo de tipos de linha (F2.5)."""
from __future__ import annotations

from fastapi.testclient import TestClient


# Payload válido para POST
_NEW_USER_INPUT = {
    "line_type": "CustomWire",
    "category": "Wire",
    "diameter": 0.076,
    "dry_weight": 200.0,
    "wet_weight": 170.0,
    "break_strength": 5.0e6,
    "modulus": 1.0e11,
    "qmoor_ea": 8.0e7,
    "seabed_friction_cf": 0.3,
    "manufacturer": "Acme",
}


# ==============================================================================
# GET /line-types — listagem com filtros
# ==============================================================================


def test_listar_line_types_vazio(client: TestClient) -> None:
    resp = client.get("/api/v1/line-types")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 0
    assert body["items"] == []


def test_listar_line_types_com_seed(
    client: TestClient, seeded_catalog: list[int]
) -> None:
    resp = client.get("/api/v1/line-types")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == len(seeded_catalog)
    # Itens vêm em SI
    for it in body["items"]:
        assert it["diameter"] < 1.0  # metros, não polegadas
        assert it["data_source"] == "legacy_qmoor"


def test_filtro_por_category(client: TestClient, seeded_catalog: list[int]) -> None:
    resp = client.get("/api/v1/line-types?category=Wire")
    body = resp.json()
    assert body["total"] == 2
    assert all(it["category"] == "Wire" for it in body["items"])


def test_filtro_por_diameter(client: TestClient, seeded_catalog: list[int]) -> None:
    # Pega só o maior (R4Studless d=0.0762)
    resp = client.get("/api/v1/line-types?diameter_min=0.05")
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["line_type"] == "R4Studless"


def test_filtro_search_por_nome(
    client: TestClient, seeded_catalog: list[int]
) -> None:
    resp = client.get("/api/v1/line-types?search=iwrc")
    body = resp.json()
    assert body["total"] == 2


def test_category_invalida_422(client: TestClient) -> None:
    resp = client.get("/api/v1/line-types?category=Nylon")
    assert resp.status_code == 422


# ==============================================================================
# GET /line-types/{id}
# ==============================================================================


def test_get_line_type_by_id(client: TestClient, seeded_catalog: list[int]) -> None:
    lt_id = seeded_catalog[0]
    resp = client.get(f"/api/v1/line-types/{lt_id}")
    assert resp.status_code == 200
    assert resp.json()["line_type"] == "IWRCEIPS"


def test_get_line_type_404(client: TestClient) -> None:
    resp = client.get("/api/v1/line-types/99999")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "line_type_not_found"


# ==============================================================================
# GET /line-types/lookup
# ==============================================================================


def test_lookup_line_type(client: TestClient, seeded_catalog: list[int]) -> None:
    resp = client.get(
        "/api/v1/line-types/lookup?line_type=IWRCEIPS&diameter=0.0254"
    )
    assert resp.status_code == 200
    assert resp.json()["line_type"] == "IWRCEIPS"
    assert resp.json()["diameter"] == 0.0254


def test_lookup_line_type_404(client: TestClient, seeded_catalog: list[int]) -> None:
    resp = client.get(
        "/api/v1/line-types/lookup?line_type=IWRCEIPS&diameter=0.99"
    )
    assert resp.status_code == 404


def test_lookup_line_type_missing_params_422(client: TestClient) -> None:
    resp = client.get("/api/v1/line-types/lookup?line_type=IWRCEIPS")
    assert resp.status_code == 422  # diameter obrigatório


# ==============================================================================
# POST /line-types (user_input)
# ==============================================================================


def test_criar_line_type_201(client: TestClient) -> None:
    resp = client.post("/api/v1/line-types", json=_NEW_USER_INPUT)
    assert resp.status_code == 201
    body = resp.json()
    assert body["data_source"] == "user_input"
    assert body["legacy_id"] is None
    assert body["id"] > 0


def test_criar_line_type_422_payload_invalido(client: TestClient) -> None:
    from copy import deepcopy
    payload = deepcopy(_NEW_USER_INPUT)
    payload["diameter"] = -1.0
    resp = client.post("/api/v1/line-types", json=payload)
    assert resp.status_code == 422


# ==============================================================================
# PUT /line-types/{id} — edição
# ==============================================================================


def test_editar_user_input_200(client: TestClient) -> None:
    created = client.post("/api/v1/line-types", json=_NEW_USER_INPUT).json()
    from copy import deepcopy
    patch = deepcopy(_NEW_USER_INPUT)
    patch["comments"] = "Editado"
    patch["break_strength"] = 6.0e6
    resp = client.put(f"/api/v1/line-types/{created['id']}", json=patch)
    assert resp.status_code == 200
    assert resp.json()["comments"] == "Editado"
    assert resp.json()["break_strength"] == 6.0e6


def test_editar_legacy_qmoor_403(
    client: TestClient, seeded_catalog: list[int]
) -> None:
    """Entradas legacy_qmoor são imutáveis."""
    lt_id = seeded_catalog[0]
    resp = client.put(f"/api/v1/line-types/{lt_id}", json=_NEW_USER_INPUT)
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "line_type_immutable"


def test_editar_inexistente_404(client: TestClient) -> None:
    resp = client.put("/api/v1/line-types/99999", json=_NEW_USER_INPUT)
    assert resp.status_code == 404


# ==============================================================================
# DELETE /line-types/{id}
# ==============================================================================


def test_deletar_user_input_200(client: TestClient) -> None:
    created = client.post("/api/v1/line-types", json=_NEW_USER_INPUT).json()
    resp = client.delete(f"/api/v1/line-types/{created['id']}")
    assert resp.status_code == 200
    # Segundo DELETE: 404
    resp2 = client.delete(f"/api/v1/line-types/{created['id']}")
    assert resp2.status_code == 404


def test_deletar_legacy_qmoor_403(
    client: TestClient, seeded_catalog: list[int]
) -> None:
    """Entradas legacy_qmoor não podem ser removidas."""
    lt_id = seeded_catalog[0]
    resp = client.delete(f"/api/v1/line-types/{lt_id}")
    assert resp.status_code == 403


def test_deletar_inexistente_404(client: TestClient) -> None:
    resp = client.delete("/api/v1/line-types/99999")
    assert resp.status_code == 404
