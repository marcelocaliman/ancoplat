"""
Testes do CSV de geometria (Fase 5 / Q5 + Commit 4).

Conforme Q5 do mini-plano (international format: decimal `.`,
separator `,`). AC do plano: ≥ 5000 pontos.
"""
from __future__ import annotations

import csv
import io

import pytest
from fastapi.testclient import TestClient

from backend.api.tests._fixtures import BC01_LIKE_INPUT


def _solve_case(client: TestClient) -> int:
    """Cria + solve case BC01 like e retorna case_id."""
    case_resp = client.post("/api/v1/cases", json=BC01_LIKE_INPUT)
    case_id = case_resp.json()["id"]
    solve_resp = client.post(f"/api/v1/cases/{case_id}/solve")
    assert solve_resp.status_code == 200
    return case_id


# ─── Smoke ──────────────────────────────────────────────────────────


def test_csv_endpoint_404_quando_caso_nao_existe(client: TestClient):
    resp = client.get("/api/v1/cases/9999/export/csv")
    assert resp.status_code == 404


def test_csv_endpoint_409_quando_sem_solve(client: TestClient, seeded_catalog):
    """Caso sem solve → 409 Conflict (sem geometria para exportar)."""
    del seeded_catalog
    case_resp = client.post("/api/v1/cases", json=BC01_LIKE_INPUT)
    case_id = case_resp.json()["id"]
    # NÃO faz solve
    resp = client.get(f"/api/v1/cases/{case_id}/export/csv")
    assert resp.status_code == 409
    body = resp.json()
    assert body["error"]["code"] == "no_execution"


def test_csv_endpoint_retorna_csv_valido(client: TestClient, seeded_catalog):
    """Smoke: retorna 200 + Content-Type CSV."""
    del seeded_catalog
    case_id = _solve_case(client)
    resp = client.get(f"/api/v1/cases/{case_id}/export/csv")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    assert "Content-Disposition" in resp.headers


# ─── AC: ≥ 5000 pontos ──────────────────────────────────────────────


def test_csv_tem_pelo_menos_5000_pontos(client: TestClient, seeded_catalog):
    """AC do plano Fase 5: CSV exporta ≥ 5000 pontos de geometria."""
    del seeded_catalog
    case_id = _solve_case(client)
    csv_content = client.get(f"/api/v1/cases/{case_id}/export/csv").text

    # Conta linhas de dados (excluindo comentários iniciados em '#' e header)
    data_lines = [
        line for line in csv_content.splitlines()
        if line and not line.startswith("#") and not line.startswith("x_m,")
    ]
    assert len(data_lines) >= 5000, (
        f"CSV tem apenas {len(data_lines)} pontos; AC F5 requer ≥ 5000."
    )


# ─── Estrutura: header correto ──────────────────────────────────────


def test_csv_header_correto(client: TestClient, seeded_catalog):
    """Header obrigatório: x_m,y_m,tension_x_n,tension_y_n,tension_magnitude_n."""
    del seeded_catalog
    case_id = _solve_case(client)
    csv_content = client.get(f"/api/v1/cases/{case_id}/export/csv").text

    # Skip comentários iniciados em '#'
    lines = [line for line in csv_content.splitlines() if not line.startswith("#")]
    header = lines[0]
    assert header == "x_m,y_m,tension_x_n,tension_y_n,tension_magnitude_n"


# ─── Formato international: decimal point + comma separator ────────


def test_csv_usa_decimal_ponto_e_separador_virgula(client: TestClient, seeded_catalog):
    """Q5: international format. Verifica .  e , consistentes."""
    del seeded_catalog
    case_id = _solve_case(client)
    csv_content = client.get(f"/api/v1/cases/{case_id}/export/csv").text

    # Pega primeira linha de dados (após header)
    lines = [line for line in csv_content.splitlines() if not line.startswith("#")]
    first_data = lines[1]  # 0=header, 1=primeiro dado

    # 5 campos separados por vírgula
    fields = first_data.split(",")
    assert len(fields) == 5, f"Esperava 5 campos, recebeu {len(fields)}: {first_data!r}"
    # Cada campo é parseável como float (decimal point)
    for field in fields:
        try:
            float(field)
        except ValueError:
            pytest.fail(f"Campo não parseável como float (decimal point): {field!r}")


# ─── Rastreabilidade: comentários metadata ──────────────────────────


def test_csv_comentarios_metadata(client: TestClient, seeded_catalog):
    """CSV inclui comentários # com case_name, timestamp, solver_version."""
    del seeded_catalog
    case_id = _solve_case(client)
    csv_content = client.get(f"/api/v1/cases/{case_id}/export/csv").text

    comment_lines = [
        line for line in csv_content.splitlines() if line.startswith("#")
    ]
    assert any("AncoPlat" in line or "geometry export" in line for line in comment_lines)
    assert any("generated" in line for line in comment_lines)
    assert any("solver_version" in line for line in comment_lines)
    assert any("n_points" in line for line in comment_lines)


# ─── CSV é parseável por Python csv.reader ──────────────────────────


def test_csv_parseavel_via_csv_reader_padrao(client: TestClient, seeded_catalog):
    """CSV abre limpo no csv.reader padrão (validação de formato)."""
    del seeded_catalog
    case_id = _solve_case(client)
    csv_content = client.get(f"/api/v1/cases/{case_id}/export/csv").text

    # Pula comentários
    data = "\n".join(
        line for line in csv_content.splitlines() if not line.startswith("#")
    )
    reader = csv.reader(io.StringIO(data))
    rows = list(reader)
    assert len(rows) >= 5001  # 1 header + ≥ 5000 dados
    # Primeira linha de dados — todos floats
    first_data_row = rows[1]
    assert len(first_data_row) == 5
    for v in first_data_row:
        float(v)  # não levanta
