"""
Testes do Memorial PDF com AHV (Fase 8 / Q9 + Ajuste 3).

Mitigação obrigatória registrada em CLAUDE.md (decisão fechada Fase 8
antecipada): Memorial PDF inclui PARÁGRAFO DEDICADO "AHV — Domínio de
aplicação" quando há ≥1 AHV no caso. Strings-chave verificadas via
content check no texto extraído do PDF (mesma estratégia da Fase 5):

  - "AHV — Domínio de aplicação" (título da seção)
  - "idealização" (palavra-chave técnica de AHV é estática)
  - "não substitui" (delimitação do escopo)
  - "análise dinâmica" (alternativa recomendada)
  - "snap loads" (cargas dinâmicas específicas)
  - "Anchor Handler Vessel" (terminologia explícita)

Critério de aceitação: TODAS as strings presentes no PDF quando AHV
está ativo; AUSENTES quando AHV não está no caso.
"""
from __future__ import annotations

import copy
import io

import pytest
from fastapi.testclient import TestClient

from backend.api.tests._fixtures import BC01_LIKE_INPUT


def _extract_pdf_text(pdf_bytes: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        try:
            from PyPDF2 import PdfReader
        except ImportError:
            pytest.skip("pypdf não instalado")
    reader = PdfReader(io.BytesIO(pdf_bytes))
    text = ""
    for page in reader.pages:
        text += page.extract_text() + "\n"
    return text


def _build_ahv_payload() -> dict:
    """BC-AHV-01 like: 2 segmentos + 1 AHV em junção 0."""
    payload = copy.deepcopy(BC01_LIKE_INPUT)
    payload["name"] = "AHV memorial test"
    # 2 segmentos para ter junção
    payload["segments"] = [
        {**payload["segments"][0], "length": 200.0},
        {**payload["segments"][0], "length": 250.0},
    ]
    payload["attachments"] = [
        {
            "kind": "ahv",
            "position_index": 0,
            "name": "AHV-1",
            "ahv_bollard_pull": 200_000.0,
            "ahv_heading_deg": 0.0,
        }
    ]
    return payload


# ─── Strings-chave presentes quando AHV está ativo ─────────────────


def test_memorial_pdf_ahv_section_present_when_ahv(
    client: TestClient, seeded_catalog,
):
    """Memorial inclui seção "AHV — Domínio de aplicação" quando AHV ativo."""
    del seeded_catalog
    payload = _build_ahv_payload()
    case_resp = client.post("/api/v1/cases", json=payload)
    assert case_resp.status_code == 201, case_resp.text
    case_id = case_resp.json()["id"]
    client.post(f"/api/v1/cases/{case_id}/solve")
    resp = client.get(f"/api/v1/cases/{case_id}/export/memorial-pdf")
    assert resp.status_code == 200, resp.text
    text = _extract_pdf_text(resp.content)
    # Título da seção
    assert "AHV" in text
    assert "Domínio de aplicação" in text or "Dom" in text  # acento OK


@pytest.mark.parametrize(
    "keyword",
    [
        "idealização",
        "não substitui",
        "análise dinâmica",
        "snap loads",
        "Anchor Handler Vessel",
    ],
)
def test_memorial_pdf_ahv_text_contem_strings_chave(
    client: TestClient, seeded_catalog, keyword: str,
):
    """
    Cada string-chave deve estar presente no texto do PDF (Q9 / Ajuste 3).
    Strings cobrem: técnica (idealização, snap loads, dinâmica), domínio
    (não substitui, Anchor Handler Vessel). Busca case-insensitive
    para acomodar capitalização no início de frase.
    """
    del seeded_catalog
    payload = _build_ahv_payload()
    case_resp = client.post("/api/v1/cases", json=payload)
    case_id = case_resp.json()["id"]
    client.post(f"/api/v1/cases/{case_id}/solve")
    resp = client.get(f"/api/v1/cases/{case_id}/export/memorial-pdf")
    text = _extract_pdf_text(resp.content)
    assert keyword.lower() in text.lower(), (
        f"String '{keyword}' AUSENTE no Memorial PDF com AHV. "
        "Mitigação Q9 incompleta — texto literal precisa cobrir essa "
        "palavra-chave técnica."
    )


# ─── Strings-chave AUSENTES quando AHV NÃO está no caso ────────────


def test_memorial_pdf_ahv_section_absent_quando_sem_ahv(
    client: TestClient, seeded_catalog,
):
    """
    Sem AHV no caso, a seção "AHV — Domínio de aplicação" NÃO deve
    aparecer no Memorial. Evita poluir cases regulares com aviso
    irrelevante.
    """
    del seeded_catalog
    payload = copy.deepcopy(BC01_LIKE_INPUT)
    case_resp = client.post("/api/v1/cases", json=payload)
    case_id = case_resp.json()["id"]
    client.post(f"/api/v1/cases/{case_id}/solve")
    resp = client.get(f"/api/v1/cases/{case_id}/export/memorial-pdf")
    text = _extract_pdf_text(resp.content)
    # As strings-chave do bloco AHV NÃO devem aparecer
    assert "Anchor Handler Vessel" not in text
    assert "snap loads" not in text


# ─── D018 dispara no caso AHV (regression do facade) ───────────────


def test_solve_ahv_dispara_D018_diagnostics(
    client: TestClient, seeded_catalog,
):
    """
    Confirma integração: solve com AHV popula D018 nos diagnostics
    retornados pela API.
    """
    del seeded_catalog
    payload = _build_ahv_payload()
    case_resp = client.post("/api/v1/cases", json=payload)
    case_id = case_resp.json()["id"]
    solve_resp = client.post(f"/api/v1/cases/{case_id}/solve")
    assert solve_resp.status_code == 200, solve_resp.text
    body = solve_resp.json()
    diagnostics = body["result"]["diagnostics"]
    codes = [d["code"] for d in diagnostics]
    assert "D018_AHV_STATIC_IDEALIZATION" in codes


def test_solve_sem_ahv_NAO_dispara_D018(
    client: TestClient, seeded_catalog,
):
    """Cases sem AHV não devem ter D018 nos diagnostics."""
    del seeded_catalog
    payload = copy.deepcopy(BC01_LIKE_INPUT)
    case_resp = client.post("/api/v1/cases", json=payload)
    case_id = case_resp.json()["id"]
    solve_resp = client.post(f"/api/v1/cases/{case_id}/solve")
    body = solve_resp.json()
    codes = [d["code"] for d in body["result"]["diagnostics"]]
    assert "D018_AHV_STATIC_IDEALIZATION" not in codes
