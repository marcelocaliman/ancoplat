"""Testes dos endpoints de metadados (health, version, criteria-profiles)."""
from __future__ import annotations

from fastapi.testclient import TestClient


def test_health_retorna_200(client: TestClient) -> None:
    """Com banco sqlite vazio (mas criado), health responde 200."""
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["db"] == "ok"


def test_version_retorna_campos_esperados(client: TestClient) -> None:
    resp = client.get("/api/v1/version")
    assert resp.status_code == 200
    body = resp.json()
    assert "api" in body
    assert "schema_version" in body
    assert "solver" in body
    # Formatos simples (não regex exato para permitir bumps)
    assert isinstance(body["api"], str) and body["api"] != ""


def test_criteria_profiles_lista_quatro_perfis(client: TestClient) -> None:
    resp = client.get("/api/v1/criteria-profiles")
    assert resp.status_code == 200
    items = resp.json()
    assert isinstance(items, list)
    assert len(items) == 4
    names = {it["name"] for it in items}
    assert names == {
        "MVP_Preliminary", "API_RP_2SK", "DNV_placeholder", "UserDefined",
    }
    # Cada item tem todos os campos obrigatórios
    for it in items:
        for field in ("name", "yellow_ratio", "red_ratio", "broken_ratio", "description"):
            assert field in it, f"campo {field} faltando em {it['name']}"
        # Ordem matemática
        assert it["yellow_ratio"] < it["red_ratio"] < it["broken_ratio"]


def test_api_rp_2sk_tem_broken_0_80(client: TestClient) -> None:
    """Validação do perfil API RP 2SK: broken=0.80 (condição danificada)."""
    resp = client.get("/api/v1/criteria-profiles")
    items = {it["name"]: it for it in resp.json()}
    api = items["API_RP_2SK"]
    assert api["broken_ratio"] == 0.80


def test_rota_inexistente_retorna_404_padronizado(client: TestClient) -> None:
    """404 usa envelope ErrorResponse."""
    resp = client.get("/api/v1/nao-existe")
    assert resp.status_code == 404
    body = resp.json()
    assert "error" in body
    assert "code" in body["error"]
    assert "message" in body["error"]


def test_docs_openapi_acessivel(client: TestClient) -> None:
    """Swagger UI e OpenAPI JSON devem estar em /api/v1/docs e /openapi.json."""
    resp = client.get("/api/v1/openapi.json")
    assert resp.status_code == 200
    spec = resp.json()
    assert spec["info"]["title"] == "AncoPlat API"
    # Endpoints devem aparecer no spec
    paths = spec["paths"]
    assert "/api/v1/health" in paths
    assert "/api/v1/version" in paths
    assert "/api/v1/criteria-profiles" in paths
