"""Testes de geração de PDF (F2.7)."""
from __future__ import annotations

from fastapi.testclient import TestClient

from backend.api.tests._fixtures import BC01_LIKE_INPUT


def _create_and_solve(client: TestClient) -> int:
    """Cria caso BC-01 like e roda solve; retorna case_id."""
    created = client.post("/api/v1/cases", json=BC01_LIKE_INPUT).json()
    resp = client.post(f"/api/v1/cases/{created['id']}/solve")
    assert resp.status_code == 200
    return created["id"]


def test_exportar_pdf_retorna_200_application_pdf(client: TestClient) -> None:
    case_id = _create_and_solve(client)
    resp = client.get(f"/api/v1/cases/{case_id}/export/pdf")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert "qmoor_caso_" in resp.headers["content-disposition"]
    # Primeiro bytes do PDF devem ser magic number
    assert resp.content[:4] == b"%PDF"
    # PDF razoável de tamanho — pelo menos 5 KB
    assert len(resp.content) > 5_000


def test_exportar_pdf_caso_sem_execucao_200_parcial(client: TestClient) -> None:
    """Caso criado mas nunca resolvido: PDF parcial apenas com inputs."""
    created = client.post("/api/v1/cases", json=BC01_LIKE_INPUT).json()
    resp = client.get(f"/api/v1/cases/{created['id']}/export/pdf")
    assert resp.status_code == 200
    assert resp.content[:4] == b"%PDF"


def test_exportar_pdf_caso_inexistente_404(client: TestClient) -> None:
    resp = client.get("/api/v1/cases/99999/export/pdf")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "case_not_found"


def test_pdf_inclui_disclaimer_obrigatorio(client: TestClient) -> None:
    """
    O disclaimer da Seção 10 do Documento A v2.2 DEVE aparecer no PDF
    renderizado. Extrai o texto via pypdf e faz a checagem textual.
    """
    import io

    from pypdf import PdfReader

    case_id = _create_and_solve(client)
    resp = client.get(f"/api/v1/cases/{case_id}/export/pdf")
    reader = PdfReader(io.BytesIO(resp.content))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    # Trechos do disclaimer (robusto contra quebras de linha/encoding)
    assert "estimativas" in text.lower()
    assert "responsável técnico" in text.lower() or "responsavel tecnico" in text.lower()
    # Inclui nome do caso (BC-01 like)
    assert "BC-01" in text
    # Inclui menção ao solver e pelo menos uma métrica (T_fl em kN)
    assert "fairlead" in text.lower() or "785" in text
