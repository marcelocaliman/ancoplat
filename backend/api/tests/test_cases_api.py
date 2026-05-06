"""Testes dos endpoints de casos (F2.3)."""
from __future__ import annotations

from copy import deepcopy

from fastapi.testclient import TestClient

from backend.api.tests._fixtures import BC01_LIKE_INPUT


# ==============================================================================
# POST /cases — criar
# ==============================================================================


def test_criar_caso_201(client: TestClient) -> None:
    resp = client.post("/api/v1/cases", json=BC01_LIKE_INPUT)
    assert resp.status_code == 201
    body = resp.json()
    assert body["id"] > 0
    assert body["name"] == BC01_LIKE_INPUT["name"]
    assert body["input"]["boundary"]["h"] == 300.0
    assert body["latest_executions"] == []
    assert "created_at" in body and "updated_at" in body


def test_criar_caso_com_multi_segmento_aceito(client: TestClient) -> None:
    """F5.1: schema agora aceita até 10 segmentos por linha."""
    payload = deepcopy(BC01_LIKE_INPUT)
    payload["segments"].append(payload["segments"][0])  # 2 segmentos idênticos
    resp = client.post("/api/v1/cases", json=payload)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert len(body["input"]["segments"]) == 2


def test_criar_caso_com_mais_de_10_segmentos_422(client: TestClient) -> None:
    """Limite superior de 10 segmentos preserva sanidade do MVP."""
    payload = deepcopy(BC01_LIKE_INPUT)
    payload["segments"] = [payload["segments"][0] for _ in range(11)]
    resp = client.post("/api/v1/cases", json=payload)
    assert resp.status_code == 422
    body = resp.json()
    assert body["error"]["code"] == "validation_error"


def test_criar_caso_sem_name_422(client: TestClient) -> None:
    payload = deepcopy(BC01_LIKE_INPUT)
    del payload["name"]
    resp = client.post("/api/v1/cases", json=payload)
    assert resp.status_code == 422


def test_criar_caso_length_negativo_422(client: TestClient) -> None:
    payload = deepcopy(BC01_LIKE_INPUT)
    payload["segments"][0]["length"] = -10.0
    resp = client.post("/api/v1/cases", json=payload)
    assert resp.status_code == 422


def test_criar_caso_mode_invalido_422(client: TestClient) -> None:
    payload = deepcopy(BC01_LIKE_INPUT)
    payload["boundary"]["mode"] = "Parabolic"  # não existe
    resp = client.post("/api/v1/cases", json=payload)
    assert resp.status_code == 422


# ==============================================================================
# GET /cases/{id}
# ==============================================================================


def test_get_case_200(client: TestClient) -> None:
    created = client.post("/api/v1/cases", json=BC01_LIKE_INPUT).json()
    resp = client.get(f"/api/v1/cases/{created['id']}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == created["id"]
    # Input é round-trip: dump → load → re-dump deve bater nos campos chave
    assert body["input"]["boundary"]["input_value"] == 785000.0
    assert body["input"]["segments"][0]["length"] == 450.0


def test_get_case_404(client: TestClient) -> None:
    resp = client.get("/api/v1/cases/99999")
    assert resp.status_code == 404
    body = resp.json()
    assert body["error"]["code"] == "case_not_found"
    assert "99999" in body["error"]["message"]


# ==============================================================================
# PUT /cases/{id}
# ==============================================================================


def test_update_case_200(client: TestClient) -> None:
    created = client.post("/api/v1/cases", json=BC01_LIKE_INPUT).json()
    updated_payload = deepcopy(BC01_LIKE_INPUT)
    updated_payload["name"] = "BC-01 editado"
    updated_payload["description"] = "descrição alterada"
    updated_payload["boundary"]["input_value"] = 800000.0
    resp = client.put(f"/api/v1/cases/{created['id']}", json=updated_payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "BC-01 editado"
    assert body["input"]["boundary"]["input_value"] == 800000.0
    # updated_at > created_at
    assert body["updated_at"] >= body["created_at"]


def test_update_case_404(client: TestClient) -> None:
    resp = client.put("/api/v1/cases/99999", json=BC01_LIKE_INPUT)
    assert resp.status_code == 404


def test_update_case_422_para_payload_invalido(client: TestClient) -> None:
    created = client.post("/api/v1/cases", json=BC01_LIKE_INPUT).json()
    payload = deepcopy(BC01_LIKE_INPUT)
    payload["segments"][0]["EA"] = 0  # violada validator do solver
    resp = client.put(f"/api/v1/cases/{created['id']}", json=payload)
    assert resp.status_code == 422


# ==============================================================================
# DELETE /cases/{id}
# ==============================================================================


def test_delete_case_200(client: TestClient) -> None:
    created = client.post("/api/v1/cases", json=BC01_LIKE_INPUT).json()
    resp = client.delete(f"/api/v1/cases/{created['id']}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "deleted"
    # Segundo DELETE deve dar 404
    resp2 = client.delete(f"/api/v1/cases/{created['id']}")
    assert resp2.status_code == 404


def test_delete_case_404(client: TestClient) -> None:
    resp = client.delete("/api/v1/cases/99999")
    assert resp.status_code == 404


# ==============================================================================
# GET /cases (lista, paginação, search)
# ==============================================================================


def test_list_cases_vazio(client: TestClient) -> None:
    resp = client.get("/api/v1/cases")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 0
    assert body["items"] == []
    assert body["page"] == 1
    assert body["page_size"] == 20


def test_list_cases_paginacao(client: TestClient) -> None:
    # Cria 5 casos
    for i in range(5):
        payload = deepcopy(BC01_LIKE_INPUT)
        payload["name"] = f"Case {i}"
        client.post("/api/v1/cases", json=payload)
    resp = client.get("/api/v1/cases?page=1&page_size=2")
    body = resp.json()
    assert body["total"] == 5
    assert len(body["items"]) == 2
    # Página 3 deve ter o restante (5 - 2*2 = 1)
    resp3 = client.get("/api/v1/cases?page=3&page_size=2")
    body3 = resp3.json()
    assert len(body3["items"]) == 1


def test_list_cases_search(client: TestClient) -> None:
    for name in ["Taut wire", "Slack chain", "Taut polyester"]:
        payload = deepcopy(BC01_LIKE_INPUT)
        payload["name"] = name
        client.post("/api/v1/cases", json=payload)
    resp = client.get("/api/v1/cases?search=taut")
    body = resp.json()
    assert body["total"] == 2
    assert all("taut" in item["name"].lower() for item in body["items"])


def test_list_cases_pagesize_invalido_422(client: TestClient) -> None:
    resp = client.get("/api/v1/cases?page_size=999")
    assert resp.status_code == 422


# ==============================================================================
# metadata operacional (Sprint 1 / v1.1.0) — preserva info QMoor (rig, region…)
# ==============================================================================


def test_criar_caso_sem_metadata_default_none(client: TestClient) -> None:
    resp = client.post("/api/v1/cases", json=BC01_LIKE_INPUT)
    assert resp.status_code == 201
    body = resp.json()
    assert body["input"]["metadata"] is None


def test_criar_caso_com_metadata_round_trip(client: TestClient) -> None:
    payload = deepcopy(BC01_LIKE_INPUT)
    payload["metadata"] = {
        "rig": "P-XX",
        "location": "Bacia de Santos",
        "engineer": "F. Silva",
        "source_version": "QMoor 0.8.0",
    }
    resp = client.post("/api/v1/cases", json=payload)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["input"]["metadata"] == payload["metadata"]


def test_criar_caso_metadata_excede_20_chaves_422(client: TestClient) -> None:
    payload = deepcopy(BC01_LIKE_INPUT)
    payload["metadata"] = {f"k{i}": f"v{i}" for i in range(21)}
    resp = client.post("/api/v1/cases", json=payload)
    assert resp.status_code == 422
    body = resp.json()
    assert body["error"]["code"] == "validation_error"


def test_criar_caso_metadata_chave_muito_longa_422(client: TestClient) -> None:
    payload = deepcopy(BC01_LIKE_INPUT)
    payload["metadata"] = {"k" * 81: "valor"}
    resp = client.post("/api/v1/cases", json=payload)
    assert resp.status_code == 422


def test_criar_caso_metadata_valor_muito_longo_422(client: TestClient) -> None:
    payload = deepcopy(BC01_LIKE_INPUT)
    payload["metadata"] = {"rig": "x" * 501}
    resp = client.post("/api/v1/cases", json=payload)
    assert resp.status_code == 422


def test_criar_caso_metadata_valor_nao_string_422(client: TestClient) -> None:
    """metadata deve ser dict[str, str] — int não passa."""
    payload = deepcopy(BC01_LIKE_INPUT)
    payload["metadata"] = {"line_count": 8}  # int em vez de "8"
    resp = client.post("/api/v1/cases", json=payload)
    assert resp.status_code == 422
