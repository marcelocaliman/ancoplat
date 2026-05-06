"""
End-to-end import QMoor 0.8.0 (Sprint 1 / v1.1.0 / Commit 9).

Exercita o pipeline completo:
  POST /import/qmoor-0_8/preview → POST /import/qmoor-0_8/commit →
  GET /cases/{id} → POST /cases/{id}/solve → GET /cases/{id}/export/json

Usa o fixture sintético `qmoor_v0_8_kar006_like` para garantir a
integração ponta-a-ponta. Quando o JSON KAR006 real estiver disponível
em `docs/audit/qmoor_kar006_sample.json` (path documentado no plano),
o teste `test_kar006_real_se_disponivel` o exercita também — caso
contrário ele faz `pytest.skip()` informando o usuário.
"""
from __future__ import annotations

import json
import os
import pathlib

import pytest
from fastapi.testclient import TestClient

from backend.api.tests.fixtures.qmoor_v0_8_synthetic import (
    synthetic_qmoor_v0_8_kar006_like,
)


REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
KAR006_REAL_PATHS = [
    REPO_ROOT / "docs" / "audit" / "qmoor_kar006_sample.json",
    REPO_ROOT / "docs" / "audit" / "kar006.json",
    REPO_ROOT / "docs" / "audit" / "7-PRA-2-SPS_Well_dbr.json",
]


def _maybe_kar006_real() -> dict | None:
    """Carrega o JSON real do KAR006 se algum dos paths esperados existir.

    Permite override via env var ANCOPLAT_KAR006_PATH para uso em CI ou
    em developer machines que tenham o arquivo num path não-padrão.
    """
    override = os.environ.get("ANCOPLAT_KAR006_PATH")
    candidates = (
        [pathlib.Path(override)] if override else []
    ) + KAR006_REAL_PATHS
    for p in candidates:
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    return None


# ──────────────────────────────────────────────────────────────────
# E2E pipeline com fixture sintético
# ──────────────────────────────────────────────────────────────────


def test_e2e_synthetic_pipeline_completo(client: TestClient) -> None:
    payload = synthetic_qmoor_v0_8_kar006_like()

    # 1. Preview
    preview = client.post("/api/v1/import/qmoor-0_8/preview", json=payload)
    assert preview.status_code == 200, preview.text
    preview_body = preview.json()
    assert preview_body["total"] == 3
    indices = [it["index"] for it in preview_body["items"]]

    # 2. Commit todos
    commit = client.post(
        "/api/v1/import/qmoor-0_8/commit",
        json={"payload": payload, "selected_indices": indices},
    )
    assert commit.status_code == 201, commit.text
    created = commit.json()["created"]
    assert len(created) == 3

    # 3. GET de cada case
    case_ids = [c["id"] for c in created]
    for cid in case_ids:
        resp = client.get(f"/api/v1/cases/{cid}")
        assert resp.status_code == 200
        case = resp.json()
        # Vessel propagado
        assert case["input"]["vessel"] is not None
        assert case["input"]["vessel"]["name"] == "P-77"
        # Metadata propagado
        md = case["input"]["metadata"]
        assert md["rig"] == "P-77"
        assert md["number"] == "KAR006"
        assert md["source_format"] == "qmoor_0_8"

    # 4. Solve do primeiro
    first_id = case_ids[0]
    solve = client.post(f"/api/v1/cases/{first_id}/solve")
    assert solve.status_code == 200, solve.text
    exec_out = solve.json()
    assert exec_out["case_id"] == first_id
    res = exec_out["result"]
    assert res["status"] in ("converged", "fully_grounded")
    assert res["fairlead_tension"] > 0

    # 5. Export JSON do primeiro
    export = client.get(f"/api/v1/cases/{first_id}/export/json")
    assert export.status_code == 200
    exported = export.json()
    # O JSON exportado preserva metadata e vessel
    assert exported["input"]["vessel"]["name"] == "P-77"
    assert exported["input"]["metadata"]["number"] == "KAR006"


def test_e2e_synthetic_solve_resultado_independente_de_metadata(
    client: TestClient,
) -> None:
    """Cases criados via QMoor import devem produzir o MESMO resultado
    de cases criados manualmente com mesmos parâmetros físicos. Vessel,
    current_profile e metadata não afetam o cálculo (invariante v1.0)."""
    from copy import deepcopy

    # 1. Import via QMoor → primeiro case (ML3 — Operational Profile 1)
    payload = synthetic_qmoor_v0_8_kar006_like()
    commit = client.post(
        "/api/v1/import/qmoor-0_8/commit",
        json={"payload": payload, "selected_indices": [0]},
    )
    assert commit.status_code == 201
    imported = commit.json()["created"][0]

    # 2. POST manual dos mesmos parâmetros físicos, sem vessel/current/metadata
    manual_input = deepcopy(imported["input"])
    manual_input["name"] = "manual sem metadata"
    manual_input["vessel"] = None
    manual_input["current_profile"] = None
    manual_input["metadata"] = None
    create = client.post("/api/v1/cases", json=manual_input)
    assert create.status_code == 201, create.text
    manual_id = create.json()["id"]

    # 3. Solve dos dois
    r1 = client.post(f"/api/v1/cases/{imported['id']}/solve").json()["result"]
    r2 = client.post(f"/api/v1/cases/{manual_id}/solve").json()["result"]
    assert r1["fairlead_tension"] == r2["fairlead_tension"]
    assert r1["anchor_tension"] == r2["anchor_tension"]
    assert r1["total_horz_distance"] == r2["total_horz_distance"]


# ──────────────────────────────────────────────────────────────────
# E2E com KAR006 real (skipa quando arquivo não está disponível)
# ──────────────────────────────────────────────────────────────────


def test_kar006_real_se_disponivel(client: TestClient) -> None:
    """Quando o JSON real do KAR006 está em disco, exercita o
    pipeline completo nele. Caso contrário, pula informando o
    usuário onde colocar o arquivo.
    """
    payload = _maybe_kar006_real()
    if payload is None:
        pytest.skip(
            "JSON real do KAR006 não disponível. Para habilitar este "
            "teste, salve o conteúdo do arquivo `7-PRA-2-SPS Well_dbr.moor` "
            "em um dos paths esperados:\n"
            "  - docs/audit/qmoor_kar006_sample.json\n"
            "  - docs/audit/kar006.json\n"
            "  - docs/audit/7-PRA-2-SPS_Well_dbr.json\n"
            "ou aponte ANCOPLAT_KAR006_PATH para outro caminho."
        )

    # Preview deve funcionar e retornar pelo menos 1 case
    preview = client.post("/api/v1/import/qmoor-0_8/preview", json=payload)
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert body["total"] >= 1, (
        f"Esperado ≥1 case do KAR006, recebido {body['total']}"
    )

    # Commit do primeiro
    commit = client.post(
        "/api/v1/import/qmoor-0_8/commit",
        json={"payload": payload, "selected_indices": [0]},
    )
    assert commit.status_code == 201, commit.text
    created = commit.json()["created"]
    assert len(created) == 1

    # Solve
    cid = created[0]["id"]
    solve = client.post(f"/api/v1/cases/{cid}/solve")
    assert solve.status_code == 200, (
        f"Solve falhou no caso real KAR006: {solve.text}"
    )
    res = solve.json()["result"]
    assert res["status"] in ("converged", "fully_grounded"), (
        f"Status inesperado: {res['status']}"
    )
    # Convergência: tensão positiva no fairlead
    assert res["fairlead_tension"] > 0
