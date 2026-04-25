"""
Testes do endpoint POST /api/v1/solve/preview (F4.1).

Garantem três coisas:
  1. Não persiste — não cria CaseRecord nem ExecutionRecord.
  2. Tem mesmo mapeamento HTTP do solve normal (200/422 conforme status).
  3. Performance — < 500 ms para um caso típico (BC-01).

Os testes de validação física do solver (BC-01..09) já estão cobertos em
backend/solver/tests/. Aqui só validamos o contrato HTTP + isolamento de DB.
"""
from __future__ import annotations

import time
from copy import deepcopy

from fastapi.testclient import TestClient
from sqlalchemy import text

from backend.api.db import session as ds
from backend.api.tests._fixtures import BC01_LIKE_INPUT


def _count_rows(table: str) -> int:
    """Conta registros de uma tabela usando o engine atual (monkey-patched)."""
    with ds.engine.connect() as conn:
        return int(conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar() or 0)


# ==============================================================================
# Não-persistência
# ==============================================================================


def test_preview_nao_cria_case_nem_execution(client: TestClient) -> None:
    cases_before = _count_rows("cases")
    execs_before = _count_rows("executions")

    resp = client.post("/api/v1/solve/preview", json=BC01_LIKE_INPUT)
    assert resp.status_code == 200, resp.text

    assert _count_rows("cases") == cases_before, (
        "preview não deve criar CaseRecord"
    )
    assert _count_rows("executions") == execs_before, (
        "preview não deve criar ExecutionRecord"
    )


def test_preview_repetido_nao_acumula_no_db(client: TestClient) -> None:
    """Mesmo chamado N vezes, zero entradas no banco."""
    cases_before = _count_rows("cases")
    execs_before = _count_rows("executions")

    for _ in range(5):
        resp = client.post("/api/v1/solve/preview", json=BC01_LIKE_INPUT)
        assert resp.status_code == 200

    assert _count_rows("cases") == cases_before
    assert _count_rows("executions") == execs_before


def test_preview_caso_invalido_tambem_nao_persiste(client: TestClient) -> None:
    """422 (caso inviável) não pode deixar lixo no banco."""
    payload = deepcopy(BC01_LIKE_INPUT)
    # T_fl <= w·h derruba o solver com INVALID_CASE
    payload["boundary"]["input_value"] = 1.0  # T_fl = 1 N, claramente inviável
    cases_before = _count_rows("cases")
    execs_before = _count_rows("executions")

    resp = client.post("/api/v1/solve/preview", json=payload)
    assert resp.status_code == 422

    assert _count_rows("cases") == cases_before
    assert _count_rows("executions") == execs_before


# ==============================================================================
# Mapeamento HTTP — espelha o solve normal
# ==============================================================================


def test_preview_converged_retorna_200_com_solver_result(
    client: TestClient,
) -> None:
    resp = client.post("/api/v1/solve/preview", json=BC01_LIKE_INPUT)
    assert resp.status_code == 200
    body = resp.json()
    # Body é o SolverResult diretamente (não envelopado em ExecutionOutput)
    assert body["status"] == "converged"
    assert "fairlead_tension" in body
    assert "coords_x" in body and len(body["coords_x"]) > 1
    assert body["alert_level"] in ("ok", "yellow", "red")


def test_preview_invalid_case_retorna_422_com_detail(
    client: TestClient,
) -> None:
    payload = deepcopy(BC01_LIKE_INPUT)
    payload["boundary"]["input_value"] = 1.0
    resp = client.post("/api/v1/solve/preview", json=payload)
    assert resp.status_code == 422
    body = resp.json()
    assert "error" in body or "detail" in body
    # Estrutura do detail traz o SolverResult completo (frontend usa isso)
    raw = body.get("error") or body.get("detail")
    assert raw is not None
    detail = raw.get("detail") if isinstance(raw, dict) else None
    assert detail is not None
    assert detail["status"] == "invalid_case"


def test_preview_payload_invalido_retorna_422_pydantic(
    client: TestClient,
) -> None:
    """Validação Pydantic (estrutura) deve retornar 422 com erros de campo."""
    payload = {
        "name": "broken",
        "segments": [
            {"length": -1, "w": 100, "EA": 1e7, "MBL": 1e6, "category": "Wire"}
        ],
        "boundary": {"h": 300, "mode": "Tension", "input_value": 100_000},
        "seabed": {"mu": 0.0},
        "criteria_profile": "MVP_Preliminary",
    }
    resp = client.post("/api/v1/solve/preview", json=payload)
    assert resp.status_code == 422


# ==============================================================================
# Performance
# ==============================================================================


def test_preview_caso_tipico_responde_em_menos_500ms(client: TestClient) -> None:
    """BC-01 like: alvo 500 ms (geralmente fica abaixo de 100 ms)."""
    # Warm-up: primeira chamada paga import lazy de scipy/numpy.
    client.post("/api/v1/solve/preview", json=BC01_LIKE_INPUT)

    t0 = time.perf_counter()
    resp = client.post("/api/v1/solve/preview", json=BC01_LIKE_INPUT)
    elapsed_ms = (time.perf_counter() - t0) * 1000

    assert resp.status_code == 200
    assert elapsed_ms < 500, (
        f"preview demorou {elapsed_ms:.0f} ms (alvo: < 500 ms). "
        "Verifique se o solver não está fazendo I/O ou cálculos pesados."
    )


# ==============================================================================
# Não usa rota com case_id — endpoint é independente
# ==============================================================================


def test_preview_funciona_sem_case_existir_no_banco(client: TestClient) -> None:
    """Endpoint não consulta o banco, então funciona com DB vazio."""
    assert _count_rows("cases") == 0
    resp = client.post("/api/v1/solve/preview", json=BC01_LIKE_INPUT)
    assert resp.status_code == 200
