"""
Testes da validação Fase 1 — `ea_source="gmoor"` contra o catálogo.

Defesa em profundidade: a UI já desabilita a opção GMoor visualmente
quando o catálogo não tem `gmoor_ea`, mas chamadas via API direta
precisam rejeitar com 422 + mensagem nominal (citando o `line_type`).
"""
from __future__ import annotations

import copy
from typing import Iterator

import pytest
from fastapi.testclient import TestClient

from backend.api.db import session as db_session_module
from backend.api.db.models import LineTypeRecord
from backend.api.tests._fixtures import BC01_LIKE_INPUT


@pytest.fixture()
def catalog_with_chain_no_gmoor(seeded_catalog: list[int]) -> Iterator[None]:
    """
    Adiciona ao catálogo uma corrente sem `gmoor_ea` populado, para
    exercitar o caminho de rejeição. Usa nome único para não colidir
    com o `seeded_catalog` base.
    """
    del seeded_catalog
    with db_session_module.SessionLocal() as db:
        rec = LineTypeRecord(
            legacy_id=999,
            line_type="ChainNoGmoor",
            category="StuddedChain",
            base_unit_system="metric",
            diameter=0.10,
            dry_weight=200.0,
            wet_weight=170.0,
            break_strength=10_000_000.0,
            modulus=None,
            qmoor_ea=8.0e8,
            gmoor_ea=None,  # ← cenário do teste
            seabed_friction_cf=1.0,
            data_source="legacy_qmoor",
        )
        db.add(rec)
        db.commit()
    yield


# ─── Caminho feliz: ea_source default qmoor passa ────────────────────


def test_create_case_default_qmoor_passa(client: TestClient, seeded_catalog: list[int]):
    """Sem ea_source explícito, default 'qmoor' — não valida catálogo."""
    del seeded_catalog
    payload = copy.deepcopy(BC01_LIKE_INPUT)
    resp = client.post("/api/v1/cases", json=payload)
    assert resp.status_code == 201, resp.text


def test_create_case_qmoor_explicito_passa(client: TestClient, seeded_catalog):
    """Mesmo sem gmoor_ea no catálogo, qmoor passa porque não é validado."""
    del seeded_catalog
    payload = copy.deepcopy(BC01_LIKE_INPUT)
    payload["segments"][0]["ea_source"] = "qmoor"
    resp = client.post("/api/v1/cases", json=payload)
    assert resp.status_code == 201


# ─── ea_source=gmoor com catálogo populado: passa ────────────────────


def test_create_case_gmoor_com_catalogo_populado_passa(
    client: TestClient, seeded_catalog
):
    """IWRCEIPS no seeded_catalog tem gmoor_ea. Aceita gmoor."""
    del seeded_catalog
    payload = copy.deepcopy(BC01_LIKE_INPUT)
    payload["segments"][0]["ea_source"] = "gmoor"
    resp = client.post("/api/v1/cases", json=payload)
    assert resp.status_code == 201, resp.text


# ─── ea_source=gmoor com catálogo vazio para esse line_type: rejeita ─


def test_create_case_gmoor_sem_no_catalogo_rejeita_com_422(
    client: TestClient, catalog_with_chain_no_gmoor
):
    del catalog_with_chain_no_gmoor
    payload = copy.deepcopy(BC01_LIKE_INPUT)
    payload["segments"][0]["line_type"] = "ChainNoGmoor"
    payload["segments"][0]["ea_source"] = "gmoor"
    resp = client.post("/api/v1/cases", json=payload)
    assert resp.status_code == 422, resp.text
    body = resp.json()
    err = body["error"]
    assert err["code"] == "gmoor_not_available"
    # Mensagem precisa nomear o line_type específico (Q4 detail)
    assert "ChainNoGmoor" in err["message"]
    assert err["detail"]["line_type"] == "ChainNoGmoor"
    assert err["detail"]["segment_index"] == 0


def test_create_case_gmoor_em_segmento_2_rejeita_com_indice_correto(
    client: TestClient, catalog_with_chain_no_gmoor, seeded_catalog
):
    """Segundo segmento sem gmoor_ea — erro deve apontar segmento #2 (idx=1)."""
    del catalog_with_chain_no_gmoor, seeded_catalog
    payload = copy.deepcopy(BC01_LIKE_INPUT)
    payload["segments"] = [
        {**payload["segments"][0], "ea_source": "qmoor"},
        {
            "length": 200.0,
            "w": 200.0,
            "EA": 8.0e8,
            "MBL": 10_000_000.0,
            "category": "StuddedChain",
            "line_type": "ChainNoGmoor",
            "ea_source": "gmoor",
        },
    ]
    resp = client.post("/api/v1/cases", json=payload)
    assert resp.status_code == 422
    err = resp.json()["error"]
    assert err["detail"]["segment_index"] == 1
    assert err["detail"]["line_type"] == "ChainNoGmoor"


# ─── line_type custom (não no catálogo): aceita ──────────────────────


def test_create_case_gmoor_com_line_type_custom_aceita(
    client: TestClient, seeded_catalog
):
    """
    Quando o usuário fornece um line_type que não está no catálogo
    (entrada custom), a validação confia no EA fornecido. Não
    deveríamos rejeitar — usuário sabe o que está fazendo.
    """
    del seeded_catalog
    payload = copy.deepcopy(BC01_LIKE_INPUT)
    payload["segments"][0]["line_type"] = "MyCustomLineType"
    payload["segments"][0]["ea_source"] = "gmoor"
    resp = client.post("/api/v1/cases", json=payload)
    assert resp.status_code == 201, resp.text


# ─── update_case também valida ──────────────────────────────────────


def test_update_case_gmoor_sem_catalogo_rejeita_com_422(
    client: TestClient, catalog_with_chain_no_gmoor, seeded_catalog
):
    del catalog_with_chain_no_gmoor, seeded_catalog
    # cria limpo
    payload = copy.deepcopy(BC01_LIKE_INPUT)
    create = client.post("/api/v1/cases", json=payload)
    assert create.status_code == 201
    case_id = create.json()["id"]

    # tenta update inválido
    bad_payload = copy.deepcopy(payload)
    bad_payload["segments"][0]["line_type"] = "ChainNoGmoor"
    bad_payload["segments"][0]["ea_source"] = "gmoor"
    resp = client.put(f"/api/v1/cases/{case_id}", json=bad_payload)
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "gmoor_not_available"
