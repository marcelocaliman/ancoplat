"""
Testes do endpoint POST /cases/{id}/solve (F2.4).

Inclui o marco de validação F2: rodar os 9 BCs via API e confirmar
concordância com o solver direto (backend.solver.solver.solve).
"""
from __future__ import annotations

import math
from copy import deepcopy
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.api.tests._fixtures import BC01_LIKE_INPUT, BC04_LIKE_INPUT
from backend.solver.solver import solve as direct_solve
from backend.solver.types import (
    BoundaryConditions,
    CriteriaProfile,
    LineSegment,
    SeabedConfig,
    SolutionMode,
)


LBF = 14.593903


def _create_case(client: TestClient, payload: dict) -> int:
    resp = client.post("/api/v1/cases", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


# ==============================================================================
# Happy path
# ==============================================================================


def test_solve_bc01_retorna_200_com_resultado(client: TestClient) -> None:
    case_id = _create_case(client, BC01_LIKE_INPUT)
    resp = client.post(f"/api/v1/cases/{case_id}/solve")
    assert resp.status_code == 200
    body = resp.json()
    assert body["case_id"] == case_id
    result = body["result"]
    assert result["status"] == "converged"
    assert result["alert_level"] in ("ok", "yellow", "red")
    # BC-01 com EA=34.25 MN (elástico): X ≈ 348 m, H ≈ 571 kN
    # (com EA rígido daria X≈335, H≈561)
    assert 340 < result["total_horz_distance"] < 360
    assert 560_000 < result["H"] < 580_000


def test_solve_persistido_no_historico(client: TestClient) -> None:
    """Após solve, GET /cases/{id} inclui latest_executions."""
    case_id = _create_case(client, BC01_LIKE_INPUT)
    client.post(f"/api/v1/cases/{case_id}/solve")
    resp = client.get(f"/api/v1/cases/{case_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["latest_executions"]) == 1
    assert body["latest_executions"][0]["result"]["status"] == "converged"


# ==============================================================================
# Casos de erro físico (422 com body rico)
# ==============================================================================


def test_solve_caso_rompido_retorna_422(client: TestClient) -> None:
    """MBL pequeno → utilization >= 1 → INVALID_CASE com alert=broken."""
    payload = deepcopy(BC01_LIKE_INPUT)
    payload["segments"][0]["MBL"] = 500_000.0  # T_fl=785kN / MBL=500kN = 1.57
    case_id = _create_case(client, payload)
    resp = client.post(f"/api/v1/cases/{case_id}/solve")
    assert resp.status_code == 422
    body = resp.json()
    assert body["error"]["code"] == "solver_invalid_case"
    assert "romp" in body["error"]["message"].lower()
    # Detail inclui snapshot do resultado
    assert body["error"]["detail"]["status"] == "invalid_case"
    assert body["error"]["detail"]["alert_level"] == "broken"


def test_solve_ancora_elevada_retorna_422(client: TestClient) -> None:
    """endpoint_grounded=false → INVALID_CASE."""
    payload = deepcopy(BC01_LIKE_INPUT)
    payload["boundary"]["endpoint_grounded"] = False
    case_id = _create_case(client, payload)
    resp = client.post(f"/api/v1/cases/{case_id}/solve")
    assert resp.status_code == 422
    body = resp.json()
    assert body["error"]["code"] == "solver_invalid_case"


def test_solve_caso_inexistente_retorna_404(client: TestClient) -> None:
    resp = client.post("/api/v1/cases/99999/solve")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "case_not_found"


# ==============================================================================
# Política de retenção
# ==============================================================================


def test_retencao_mantem_apenas_10_execucoes(client: TestClient) -> None:
    case_id = _create_case(client, BC01_LIKE_INPUT)
    # Faz 15 execuções
    for _ in range(15):
        r = client.post(f"/api/v1/cases/{case_id}/solve")
        assert r.status_code == 200
    # Agora GET /cases/{id} deve retornar apenas 10 últimas
    body = client.get(f"/api/v1/cases/{case_id}").json()
    assert len(body["latest_executions"]) == 10


# ==============================================================================
# Marco de validação F2: 9 BCs API-vs-direct devem coincidir
# ==============================================================================


def _bc_payload(
    L: float, h: float, w: float, EA: float, MBL: float, mu: float,
    mode: str, input_value: float, name: str,
) -> dict:
    return {
        "name": name,
        "segments": [{"length": L, "w": w, "EA": EA, "MBL": MBL}],
        "boundary": {"h": h, "mode": mode, "input_value": input_value},
        "seabed": {"mu": mu},
        "criteria_profile": "MVP_Preliminary",
    }


@pytest.mark.parametrize(
    "bc_name, params",
    [
        ("BC-01", {"L": 450, "h": 300, "w": 13.78 * LBF, "EA": 1e15, "MBL": 3.78e6,
                   "mu": 0.0, "mode": "Tension", "input_value": 785_000}),
        ("BC-02", {"L": 700, "h": 300, "w": 13.78 * LBF, "EA": 1e15, "MBL": 3.78e6,
                   "mu": 0.30, "mode": "Tension", "input_value": 150_000}),
        ("BC-03", {"L": 450, "h": 300, "w": 13.78 * LBF, "EA": 34.25e6, "MBL": 3.78e6,
                   "mu": 0.0, "mode": "Tension", "input_value": 785_000}),
        ("BC-04", {"L": 1800, "h": 1000, "w": 13.78 * LBF, "EA": 34.25e6, "MBL": 3.78e6,
                   "mu": 0.30, "mode": "Tension", "input_value": 150 * 9806.65}),
        ("BC-05", {"L": 1800, "h": 1000, "w": 13.78 * LBF, "EA": 34.25e6, "MBL": 3.78e6,
                   "mu": 0.30, "mode": "Range", "input_value": 1450}),
        ("BC-06", {"L": 530, "h": 500, "w": 13.78 * LBF, "EA": 34.25e6, "MBL": 3.78e6,
                   "mu": 0.0, "mode": "Range", "input_value": 170}),
        ("BC-07", {"L": 2000, "h": 100, "w": 13.78 * LBF, "EA": 34.25e6, "MBL": 3.78e6,
                   "mu": 0.30, "mode": "Tension", "input_value": 30_000}),
        ("BC-08", {"L": 700, "h": 300, "w": 13.78 * LBF, "EA": 1e15, "MBL": 3.78e6,
                   "mu": 1.0, "mode": "Tension", "input_value": 150_000}),
        ("BC-09", {"L": 700, "h": 300, "w": 13.78 * LBF, "EA": 1e15, "MBL": 3.78e6,
                   "mu": 0.0, "mode": "Tension", "input_value": 150_000}),
    ],
)
def test_bc_api_equivale_direct(client: TestClient, bc_name: str, params: dict) -> None:
    """
    Marco de validação F2: resolver cada BC via API e comparar com solver
    direto. Resultados devem ser numericamente idênticos (ambos invocam a
    mesma função solve()).
    """
    # Via API
    payload = _bc_payload(**params, name=bc_name)
    case_id = _create_case(client, payload)
    resp = client.post(f"/api/v1/cases/{case_id}/solve")
    assert resp.status_code == 200, (
        f"{bc_name} esperava 200, obteve {resp.status_code}: {resp.text}"
    )
    api_result = resp.json()["result"]

    # Direto
    seg = LineSegment(length=params["L"], w=params["w"], EA=params["EA"], MBL=params["MBL"])
    bc = BoundaryConditions(
        h=params["h"],
        mode=SolutionMode(params["mode"]),
        input_value=params["input_value"],
    )
    sb = SeabedConfig(mu=params["mu"])
    direct = direct_solve(
        line_segments=[seg], boundary=bc, seabed=sb,
        criteria_profile=CriteriaProfile.MVP_PRELIMINARY,
    )

    # Equivalência numérica (API serializa/deserializa, pode perder últimos bits).
    assert api_result["status"] == direct.status.value
    assert api_result["H"] == pytest.approx(direct.H, rel=1e-9)
    assert api_result["total_horz_distance"] == pytest.approx(
        direct.total_horz_distance, rel=1e-9
    )
    assert api_result["fairlead_tension"] == pytest.approx(
        direct.fairlead_tension, rel=1e-9
    )
