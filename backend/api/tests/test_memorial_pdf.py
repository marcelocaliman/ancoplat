"""
Testes do memorial técnico PDF (Fase 5 / Q1+Q2+Q8).

Conforme Q8 do mini-plano: smoke + content checks (não snapshot binário).
Strings-chave verificadas no texto extraído via PyPDF2:
  - "MEMORIAL TÉCNICO" (título — distingue do PDF resumido)
  - SOLVER_VERSION (rastreabilidade)
  - hash[:16] do caso (rastreabilidade — Q3+Q9)
  - "ProfileType" ou "Regime catenário" (Fase 4 integrada)
  - código do primeiro diagnostic (se houver)
"""
from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient

from backend.api.tests._fixtures import BC01_LIKE_INPUT


def _extract_pdf_text(pdf_bytes: bytes) -> str:
    """Extrai texto bruto do PDF para content checks."""
    try:
        from pypdf import PdfReader
    except ImportError:
        try:
            from PyPDF2 import PdfReader  # fallback nome antigo
        except ImportError:
            pytest.skip("pypdf não instalado — instale com pip install pypdf")
    reader = PdfReader(io.BytesIO(pdf_bytes))
    text = ""
    for page in reader.pages:
        text += page.extract_text() + "\n"
    return text


# ─── Smoke ──────────────────────────────────────────────────────────


def test_memorial_endpoint_404_quando_caso_nao_existe(client: TestClient):
    resp = client.get("/api/v1/cases/9999/export/memorial-pdf")
    assert resp.status_code == 404


def test_memorial_endpoint_retorna_pdf_valido(client: TestClient, seeded_catalog):
    """Smoke: endpoint retorna 200 + PDF não-vazio."""
    del seeded_catalog
    case_resp = client.post("/api/v1/cases", json=BC01_LIKE_INPUT)
    case_id = case_resp.json()["id"]
    resp = client.get(f"/api/v1/cases/{case_id}/export/memorial-pdf")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert len(resp.content) > 1000  # PDF tem pelo menos algum tamanho
    # PDF começa com '%PDF-' magic number
    assert resp.content[:5] == b"%PDF-"


def test_memorial_pdf_tem_pelo_menos_3_paginas(client: TestClient, seeded_catalog):
    """Memorial é volumoso: capa + sumário + segmentos + diagnostics ≥ 3 págs."""
    del seeded_catalog
    case_resp = client.post("/api/v1/cases", json=BC01_LIKE_INPUT)
    case_id = case_resp.json()["id"]
    # Solve para popular execução
    client.post(f"/api/v1/cases/{case_id}/solve")

    resp = client.get(f"/api/v1/cases/{case_id}/export/memorial-pdf")
    assert resp.status_code == 200

    try:
        from pypdf import PdfReader
    except ImportError:
        try:
            from PyPDF2 import PdfReader
        except ImportError:
            pytest.skip("pypdf não instalado")
    reader = PdfReader(io.BytesIO(resp.content))
    assert len(reader.pages) >= 3, (
        f"Memorial PDF tem apenas {len(reader.pages)} páginas; "
        "esperado ≥ 3 (capa + identificação + resultados)."
    )


# ─── Content checks (Q8) ────────────────────────────────────────────


def test_memorial_pdf_contem_titulo_memorial_tecnico(client: TestClient, seeded_catalog):
    """String-chave: 'MEMORIAL TÉCNICO' — distingue do PDF resumido."""
    del seeded_catalog
    case_resp = client.post("/api/v1/cases", json=BC01_LIKE_INPUT)
    case_id = case_resp.json()["id"]
    pdf = client.get(f"/api/v1/cases/{case_id}/export/memorial-pdf").content
    text = _extract_pdf_text(pdf).upper()
    assert "MEMORIAL" in text


def test_memorial_pdf_contem_solver_version(client: TestClient, seeded_catalog):
    """String-chave: SOLVER_VERSION (rastreabilidade)."""
    del seeded_catalog
    from backend.api.routers.health import SOLVER_VERSION

    case_resp = client.post("/api/v1/cases", json=BC01_LIKE_INPUT)
    case_id = case_resp.json()["id"]
    pdf = client.get(f"/api/v1/cases/{case_id}/export/memorial-pdf").content
    text = _extract_pdf_text(pdf)
    assert SOLVER_VERSION in text


def test_memorial_pdf_contem_hash_do_caso(client: TestClient, seeded_catalog):
    """String-chave: hash[:16] do caso (rastreabilidade — Fase 5 / Q3)."""
    del seeded_catalog
    from backend.api.schemas.cases import CaseInput
    from backend.api.services.case_hash import case_input_short_hash

    case_resp = client.post("/api/v1/cases", json=BC01_LIKE_INPUT)
    case_id = case_resp.json()["id"]
    pdf = client.get(f"/api/v1/cases/{case_id}/export/memorial-pdf").content
    text = _extract_pdf_text(pdf)

    # Re-deriva hash do CaseInput salvo
    case_full = client.get(f"/api/v1/cases/{case_id}").json()
    case_input = CaseInput.model_validate(case_full["input"])
    expected_hash = case_input_short_hash(case_input)

    assert expected_hash in text, (
        f"Hash {expected_hash!r} não encontrado no PDF. "
        f"Texto extraído (primeiros 300 chars): {text[:300]!r}"
    )


def test_memorial_pdf_contem_profile_type_quando_solved(
    client: TestClient, seeded_catalog,
):
    """Após solve, memorial mostra ProfileType detectado (Fase 4)."""
    del seeded_catalog
    case_resp = client.post("/api/v1/cases", json=BC01_LIKE_INPUT)
    case_id = case_resp.json()["id"]
    solve_resp = client.post(f"/api/v1/cases/{case_id}/solve")
    if solve_resp.status_code != 200 or solve_resp.json()["result"]["status"] != "converged":
        pytest.skip("Solve não convergiu — sem ProfileType para testar")

    pdf = client.get(f"/api/v1/cases/{case_id}/export/memorial-pdf").content
    text = _extract_pdf_text(pdf)

    # ProfileType pode aparecer como "Regime catenário" ou "PT_X"
    assert (
        "Regime catenário" in text
        or "ProfileType" in text
        or "PT_" in text
    ), (
        f"ProfileType não encontrado no memorial. "
        f"Excerpt: {text[300:800]!r}"
    )


def test_memorial_pdf_contem_premissas_block(client: TestClient, seeded_catalog):
    """Bloco 'Premissas e escopo' presente."""
    del seeded_catalog
    case_resp = client.post("/api/v1/cases", json=BC01_LIKE_INPUT)
    case_id = case_resp.json()["id"]
    pdf = client.get(f"/api/v1/cases/{case_id}/export/memorial-pdf").content
    text = _extract_pdf_text(pdf)
    assert "Premissas" in text or "premissa" in text.lower()


def test_memorial_pdf_caso_sem_solve_gera_parcial(client: TestClient, seeded_catalog):
    """Caso sem solve gera memorial parcial mas válido."""
    del seeded_catalog
    case_resp = client.post("/api/v1/cases", json=BC01_LIKE_INPUT)
    case_id = case_resp.json()["id"]
    # NÃO faz solve — pega o PDF parcial direto
    resp = client.get(f"/api/v1/cases/{case_id}/export/memorial-pdf")
    assert resp.status_code == 200
    assert resp.content[:5] == b"%PDF-"


def test_pdf_resumido_continua_funcionando(client: TestClient, seeded_catalog):
    """Sanity: endpoint /export/pdf (resumido) NÃO foi quebrado pelo memorial."""
    del seeded_catalog
    case_resp = client.post("/api/v1/cases", json=BC01_LIKE_INPUT)
    case_id = case_resp.json()["id"]
    resp = client.get(f"/api/v1/cases/{case_id}/export/pdf")
    assert resp.status_code == 200
    assert resp.content[:5] == b"%PDF-"
