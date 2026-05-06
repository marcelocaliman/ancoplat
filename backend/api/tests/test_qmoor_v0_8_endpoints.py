"""
Testes dos endpoints REST QMoor 0.8.0 (Sprint 1 / v1.1.0 / Commit 7).

Cobre:
  • POST /import/qmoor-0_8/preview — retorna lista preview, NÃO persiste.
  • POST /import/qmoor-0_8/commit  — cria casos selecionados.
  • Validação de payload (400 quando inválido).
  • Selected indices fora de range são logados, não derrubam o batch.
"""
from __future__ import annotations

from copy import deepcopy

from fastapi.testclient import TestClient

from backend.api.tests.fixtures.qmoor_v0_8_synthetic import (
    synthetic_qmoor_v0_8_kar006_like,
    synthetic_qmoor_v0_8_minimal,
)


# ──────────────────────────────────────────────────────────────────
# /preview
# ──────────────────────────────────────────────────────────────────


def test_preview_minimal(client: TestClient) -> None:
    payload = synthetic_qmoor_v0_8_minimal()
    resp = client.post("/api/v1/import/qmoor-0_8/preview", json=payload)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] == 1
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert item["index"] == 0
    assert item["name"] == "ML1 — Operational"
    assert item["n_segments"] == 1
    assert item["has_vessel"] is False


def test_preview_kar006_like(client: TestClient) -> None:
    payload = synthetic_qmoor_v0_8_kar006_like()
    resp = client.post("/api/v1/import/qmoor-0_8/preview", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3
    names = [it["name"] for it in body["items"]]
    assert "ML3 — Operational Profile 1" in names
    assert "ML3 — Preset Profile" in names
    assert "ML4 — Operational Profile 1" in names
    # Todos os 3 cases compartilham o vessel + têm current_profile
    assert all(it["has_vessel"] for it in body["items"])
    assert all(it["has_current_profile"] for it in body["items"])


def test_preview_payload_invalido_400(client: TestClient) -> None:
    payload = synthetic_qmoor_v0_8_minimal()
    payload["version"] = "0.7.0"  # versão não suportada
    resp = client.post("/api/v1/import/qmoor-0_8/preview", json=payload)
    assert resp.status_code == 400
    body = resp.json()
    assert body["error"]["code"] == "qmoor_v0_8_parse_error"


def test_preview_nao_persiste(client: TestClient) -> None:
    """/preview NÃO cria casos no DB."""
    # Garantir DB começa vazio
    list_resp = client.get("/api/v1/cases")
    assert list_resp.json()["total"] == 0

    payload = synthetic_qmoor_v0_8_minimal()
    client.post("/api/v1/import/qmoor-0_8/preview", json=payload)

    list_resp_2 = client.get("/api/v1/cases")
    assert list_resp_2.json()["total"] == 0


# ──────────────────────────────────────────────────────────────────
# /commit
# ──────────────────────────────────────────────────────────────────


def test_commit_seleciona_subset(client: TestClient) -> None:
    payload = synthetic_qmoor_v0_8_kar006_like()
    body = {"payload": payload, "selected_indices": [0, 2]}
    resp = client.post("/api/v1/import/qmoor-0_8/commit", json=body)
    assert resp.status_code == 201, resp.text
    out = resp.json()
    assert out["n_created"] == 2
    assert len(out["created"]) == 2
    # Cases criados foram persistidos
    list_resp = client.get("/api/v1/cases")
    assert list_resp.json()["total"] == 2


def test_commit_todos_indices(client: TestClient) -> None:
    payload = synthetic_qmoor_v0_8_kar006_like()
    body = {"payload": payload, "selected_indices": [0, 1, 2]}
    resp = client.post("/api/v1/import/qmoor-0_8/commit", json=body)
    assert resp.status_code == 201
    out = resp.json()
    assert out["n_created"] == 3


def test_commit_indice_fora_de_range_logado(client: TestClient) -> None:
    payload = synthetic_qmoor_v0_8_kar006_like()
    body = {"payload": payload, "selected_indices": [0, 99, 1]}
    resp = client.post("/api/v1/import/qmoor-0_8/commit", json=body)
    assert resp.status_code == 201
    out = resp.json()
    assert out["n_created"] == 2  # 99 pulado
    fora = [e for e in out["migration_log"]
            if "fora do range" in e.get("reason", "")]
    assert len(fora) == 1


def test_commit_payload_ausente_400(client: TestClient) -> None:
    resp = client.post("/api/v1/import/qmoor-0_8/commit",
                       json={"selected_indices": [0]})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "missing_payload"


def test_commit_indices_invalidos_400(client: TestClient) -> None:
    payload = synthetic_qmoor_v0_8_minimal()
    resp = client.post(
        "/api/v1/import/qmoor-0_8/commit",
        json={"payload": payload, "selected_indices": "abc"},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_indices"


def test_commit_payload_qmoor_invalido_400(client: TestClient) -> None:
    payload = synthetic_qmoor_v0_8_minimal()
    payload["version"] = "1.0.0"
    resp = client.post(
        "/api/v1/import/qmoor-0_8/commit",
        json={"payload": payload, "selected_indices": [0]},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "qmoor_v0_8_parse_error"


def test_commit_preserva_metadata_no_caso_criado(client: TestClient) -> None:
    payload = synthetic_qmoor_v0_8_kar006_like()
    body = {"payload": payload, "selected_indices": [0]}
    resp = client.post("/api/v1/import/qmoor-0_8/commit", json=body)
    assert resp.status_code == 201
    case = resp.json()["created"][0]
    md = case["input"]["metadata"]
    assert md["rig"] == "P-77"
    assert md["number"] == "KAR006"
    assert md["source_format"] == "qmoor_0_8"
