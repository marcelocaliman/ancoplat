"""Testes de import/export .moor (F2.6)."""
from __future__ import annotations

from copy import deepcopy

from fastapi.testclient import TestClient

from backend.api.tests._fixtures import BC01_LIKE_INPUT


# Exemplo do MVP v2 PDF Seção 5.2, adaptado para ser válido
_MOOR_JSON_IMPERIAL = {
    "name": "Test .moor imperial",
    "unitSystem": "imperial",
    "mooringLine": {
        "name": "ML1",
        "rigidityType": "qmoor",
        "segments": [
            {
                "category": "Wire",
                "length": "1476.4 ft",  # ~450 m
                "lineProps": {
                    "lineType": "IWRCEIPS",
                    "diameter": "3 in",
                    "breakStrength": "850 kip",
                    "wetWeight": "13.78 lbf/ft",
                    "dryWeight": "16.6 lbf/ft",
                    "modulus": "9804 kip/in^2",
                    "seabedFrictionCF": 0.6,
                },
            }
        ],
        "boundary": {
            "startpointDepth": "0 ft",
            "endpointDepth": "984 ft",  # ~300 m
            "endpointGrounded": True,
        },
        "solution": {
            "inputParam": "Tension",
            "fairleadTension": "150 kip",
        },
    },
}


# ==============================================================================
# POST /import/moor
# ==============================================================================


def test_import_moor_imperial_cria_caso(client: TestClient) -> None:
    resp = client.post("/api/v1/import/moor", json=_MOOR_JSON_IMPERIAL)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["case"]["id"] > 0
    assert body["case"]["name"] == "Test .moor imperial"
    # Valores devem ter sido convertidos para SI
    seg = body["case"]["input"]["segments"][0]
    # 1476.4 ft → ~450.04 m
    assert 449 < seg["length"] < 451
    # 13.78 lbf/ft → ~201.1 N/m
    assert 200 < seg["w"] < 202
    # 850 kip → ~3.78e6 N
    assert 3.77e6 < seg["MBL"] < 3.79e6
    assert seg["category"] == "Wire"
    assert seg["line_type"] == "IWRCEIPS"
    # Boundary: 984 ft → ~299.9 m
    assert 299 < body["case"]["input"]["boundary"]["h"] < 301


def test_import_moor_metric_com_numeros_puros(client: TestClient) -> None:
    """Campos sem unidade em unitSystem=metric → usa default (m, N/m, N, Pa)."""
    payload = {
        "name": "Metric puro",
        "unitSystem": "metric",
        "mooringLine": {
            "segments": [{
                "category": "Wire",
                "length": 450.0,
                "lineProps": {
                    "lineType": "CustomSI",
                    "diameter": 0.076,
                    "breakStrength": 3.78e6,
                    "wetWeight": 201.1,
                    "dryWeight": 240.0,
                    "qmoorEA": 3.425e7,
                    "seabedFrictionCF": 0.3,
                },
            }],
            "boundary": {
                "startpointDepth": 0,
                "endpointDepth": 300,
                "endpointGrounded": True,
            },
            "solution": {
                "inputParam": "Tension",
                "fairleadTension": 785000,
            },
        },
    }
    resp = client.post("/api/v1/import/moor", json=payload)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    seg = body["case"]["input"]["segments"][0]
    assert seg["length"] == 450.0
    assert seg["w"] == 201.1
    assert body["case"]["input"]["boundary"]["h"] == 300.0


def test_import_moor_sem_name_400(client: TestClient) -> None:
    payload = deepcopy(_MOOR_JSON_IMPERIAL)
    del payload["name"]
    del payload["mooringLine"]["name"]
    resp = client.post("/api/v1/import/moor", json=payload)
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "moor_format_error"


def test_import_moor_mode_invalido_400(client: TestClient) -> None:
    payload = deepcopy(_MOOR_JSON_IMPERIAL)
    payload["mooringLine"]["solution"]["inputParam"] = "NonExistent"
    resp = client.post("/api/v1/import/moor", json=payload)
    assert resp.status_code == 400


def test_import_moor_multi_segmento_aceito(client: TestClient) -> None:
    """F5.1: parser aceita .moor com múltiplos segmentos por linha."""
    payload = deepcopy(_MOOR_JSON_IMPERIAL)
    payload["mooringLine"]["segments"].append(payload["mooringLine"]["segments"][0])
    resp = client.post("/api/v1/import/moor", json=payload)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert len(body["case"]["input"]["segments"]) == 2


def test_import_moor_acima_de_10_segmentos_400(client: TestClient) -> None:
    payload = deepcopy(_MOOR_JSON_IMPERIAL)
    payload["mooringLine"]["segments"] = [
        payload["mooringLine"]["segments"][0] for _ in range(11)
    ]
    resp = client.post("/api/v1/import/moor", json=payload)
    assert resp.status_code == 400


def test_import_moor_unitsystem_invalido_400(client: TestClient) -> None:
    payload = deepcopy(_MOOR_JSON_IMPERIAL)
    payload["unitSystem"] = "chinese"
    resp = client.post("/api/v1/import/moor", json=payload)
    assert resp.status_code == 400


def test_import_moor_categoria_invalida_400(client: TestClient) -> None:
    payload = deepcopy(_MOOR_JSON_IMPERIAL)
    payload["mooringLine"]["segments"][0]["category"] = "Nylon"
    resp = client.post("/api/v1/import/moor", json=payload)
    assert resp.status_code == 400


# ==============================================================================
# GET /cases/{id}/export/moor
# ==============================================================================


def test_export_moor_metric_200(client: TestClient) -> None:
    created = client.post("/api/v1/cases", json=BC01_LIKE_INPUT).json()
    resp = client.get(f"/api/v1/cases/{created['id']}/export/moor?unit_system=metric")
    assert resp.status_code == 200
    body = resp.json()
    assert body["unitSystem"] == "metric"
    assert body["mooringLine"]["segments"][0]["lineProps"]["seabedFrictionCF"] == 0.0
    # Comprimento deve estar em m
    length_str = body["mooringLine"]["segments"][0]["length"]
    assert "m" in length_str
    assert "ft" not in length_str


def test_export_moor_imperial_200(client: TestClient) -> None:
    created = client.post("/api/v1/cases", json=BC01_LIKE_INPUT).json()
    resp = client.get(
        f"/api/v1/cases/{created['id']}/export/moor?unit_system=imperial"
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["unitSystem"] == "imperial"
    # length deve estar em ft
    length_str = body["mooringLine"]["segments"][0]["length"]
    assert "ft" in length_str
    # 450 m ≈ 1476 ft
    length_num = float(length_str.split()[0])
    assert 1475 < length_num < 1478


def test_export_moor_caso_inexistente_404(client: TestClient) -> None:
    resp = client.get("/api/v1/cases/9999/export/moor")
    assert resp.status_code == 404


def test_export_moor_unit_system_invalido_422(client: TestClient) -> None:
    created = client.post("/api/v1/cases", json=BC01_LIKE_INPUT).json()
    resp = client.get(
        f"/api/v1/cases/{created['id']}/export/moor?unit_system=chinese"
    )
    assert resp.status_code == 422


# ==============================================================================
# Round-trip import → export
# ==============================================================================


def test_roundtrip_import_export_metric(client: TestClient) -> None:
    """
    Import .moor metric → export .moor metric deve preservar valores
    principais dentro de precisão razoável.
    """
    imported = client.post("/api/v1/import/moor", json=_MOOR_JSON_IMPERIAL).json()
    case_id = imported["case"]["id"]  # Fase 5: response wrap {case, migration_log}
    exported = client.get(
        f"/api/v1/cases/{case_id}/export/moor?unit_system=imperial"
    ).json()
    # Re-extrai length e breakStrength do exported
    seg = exported["mooringLine"]["segments"][0]
    length_ft = float(seg["length"].split()[0])
    mbl_kip = float(seg["lineProps"]["breakStrength"].split()[0])
    assert 1475 < length_ft < 1478  # original: 1476.4
    assert 849 < mbl_kip < 851  # original: 850


# ==============================================================================
# GET /cases/{id}/export/json
# ==============================================================================


def test_export_json_200(client: TestClient) -> None:
    created = client.post("/api/v1/cases", json=BC01_LIKE_INPUT).json()
    resp = client.get(f"/api/v1/cases/{created['id']}/export/json")
    assert resp.status_code == 200
    body = resp.json()
    # GET /export/json retorna CaseOutput direto (sem wrapper {case, ...})
    assert body["id"] == created["id"]
    assert "input" in body
    assert "latest_executions" in body


def test_export_json_404(client: TestClient) -> None:
    resp = client.get("/api/v1/cases/9999/export/json")
    assert resp.status_code == 404
