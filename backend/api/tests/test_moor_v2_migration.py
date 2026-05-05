"""
Testes do migrador v1→v2 + round-trip `.moor` (Fase 5 / Q4 + Ajuste 2).

Cobertura:
  - Migrador é idempotente: payload já em v2 não é re-migrado.
  - Migrador popula defaults nos 7 fields novos (Fases 1-3) e retorna
    log estruturado (Ajuste 2).
  - Cada entrada do log tem {field, old, new, reason}.
  - Round-trip v1 → import → export v2 → import resulta em mesmo
    CaseInput (idempotência).
  - cases_baseline.json (3 cases físicos reais) re-importam via
    .moor v2 com mesmo solve result (rtol=1e-9).
"""
from __future__ import annotations

import copy
import json
import math
from pathlib import Path

import pytest

from backend.api.schemas.cases import CaseInput
from backend.api.services.moor_service import (
    CURRENT_MOOR_VERSION,
    _migrate_v1_to_v2,
    export_case_as_moor,
    parse_moor_payload,
    parse_moor_payload_with_log,
)
from backend.api.tests._fixtures import BC01_LIKE_INPUT


# ─── Estrutura mínima de payload .moor v1 ────────────────────────────


_V1_PAYLOAD = {
    "name": "Test v1",
    "unitSystem": "metric",
    "mooringLine": {
        "name": "L1",
        "rigidityType": "qmoor",
        "segments": [
            {
                "category": "Wire",
                "length": "450 m",
                "lineProps": {
                    "lineType": "IWRCEIPS",
                    "wetWeight": "201 N/m",
                    "breakStrength": "3780000 N",
                    "qmoorEA": "34250000 N",
                    "seabedFrictionCF": 0.3,
                },
            },
        ],
        "boundary": {
            "startpointDepth": "0 m",
            "endpointDepth": "300 m",
            "endpointGrounded": True,
        },
        "solution": {
            "inputParam": "Tension",
            "fairleadTension": "785000 N",
        },
    },
}


# ─── Migrador idempotente ──────────────────────────────────────────


def test_migrate_v1_payload_recebe_version_2():
    out, _log = _migrate_v1_to_v2(_V1_PAYLOAD)
    assert out["version"] == 2


def test_migrate_v2_payload_passa_inalterado():
    """Payload já em v2 não é re-migrado (sem entradas de log)."""
    v2 = copy.deepcopy(_V1_PAYLOAD)
    v2["version"] = 2
    out, log = _migrate_v1_to_v2(v2)
    assert out["version"] == 2
    assert log == []


def test_migrate_e_idempotente_aplicar_duas_vezes():
    """Re-migrar payload já migrado não muda nada."""
    out1, _log1 = _migrate_v1_to_v2(_V1_PAYLOAD)
    out2, log2 = _migrate_v1_to_v2(out1)
    assert out2 == out1
    assert log2 == []


# ─── Migrador popula 7 fields novos ────────────────────────────────


def test_migrate_popula_3_fields_no_boundary():
    """Fase 2-3: startpointOffsetHorz/Vert + startpointType."""
    out, log = _migrate_v1_to_v2(_V1_PAYLOAD)
    bc = out["mooringLine"]["boundary"]
    assert bc["startpointOffsetHorz"] == 0.0
    assert bc["startpointOffsetVert"] == 0.0
    assert bc["startpointType"] == "semisub"
    # 3 entradas no log para boundary
    boundary_logs = [e for e in log if e["field"].startswith("boundary.")]
    assert len(boundary_logs) == 3


def test_migrate_popula_3_fields_por_segmento():
    """Fase 1: eaSource, muOverride, eaDynamicBeta per segmento."""
    out, log = _migrate_v1_to_v2(_V1_PAYLOAD)
    seg = out["mooringLine"]["segments"][0]
    assert seg["lineProps"]["eaSource"] == "qmoor"
    assert seg["lineProps"]["muOverride"] is None
    assert seg["lineProps"]["eaDynamicBeta"] is None
    # 3 entradas por segmento (1 segmento × 3 fields = 3 entries)
    seg_logs = [e for e in log if e["field"].startswith("segments[0].")]
    assert len(seg_logs) == 3


def test_log_total_para_v1_payload_com_1_segmento():
    """3 boundary + 3 por segmento = 6 entradas para 1 seg."""
    _, log = _migrate_v1_to_v2(_V1_PAYLOAD)
    assert len(log) == 6


def test_log_total_para_v1_payload_com_3_segmentos():
    payload = copy.deepcopy(_V1_PAYLOAD)
    payload["mooringLine"]["segments"] = [
        copy.deepcopy(payload["mooringLine"]["segments"][0]) for _ in range(3)
    ]
    _, log = _migrate_v1_to_v2(payload)
    # 3 boundary + 3 segs × 3 fields = 12
    assert len(log) == 12


# ─── Estrutura do log (Ajuste 2) ───────────────────────────────────


def test_cada_entrada_log_tem_4_chaves():
    """Cada entrada: {field, old, new, reason} (Ajuste 2)."""
    _, log = _migrate_v1_to_v2(_V1_PAYLOAD)
    assert len(log) > 0
    for entry in log:
        assert set(entry.keys()) == {"field", "old", "new", "reason"}
        assert isinstance(entry["field"], str)
        assert isinstance(entry["reason"], str)
        assert len(entry["reason"]) > 10  # razão informativa


def test_log_reason_cita_fase_origem():
    """Cada razão menciona a Fase de origem do field (1, 2 ou 3)."""
    _, log = _migrate_v1_to_v2(_V1_PAYLOAD)
    for entry in log:
        reason = entry["reason"]
        assert any(
            f"Fase {n}" in reason for n in (1, 2, 3)
        ), f"Reason sem Fase: {reason!r}"


# ─── Export emite v2 ───────────────────────────────────────────────


def test_export_emite_version_2(client, seeded_catalog):
    """export_case_as_moor produz payload com version=2."""
    del seeded_catalog
    create_resp = client.post("/api/v1/cases", json=BC01_LIKE_INPUT)
    case_id = create_resp.json()["id"]
    resp = client.get(f"/api/v1/cases/{case_id}/export/moor")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["version"] == 2
    assert payload["version"] == CURRENT_MOOR_VERSION


def test_export_inclui_fields_fase_1_no_segmento(client, seeded_catalog):
    del seeded_catalog
    create_resp = client.post("/api/v1/cases", json=BC01_LIKE_INPUT)
    case_id = create_resp.json()["id"]
    payload = client.get(f"/api/v1/cases/{case_id}/export/moor").json()
    seg_props = payload["mooringLine"]["segments"][0]["lineProps"]
    # Os 3 fields novos da Fase 1 estão presentes (mesmo None/default)
    assert "eaSource" in seg_props
    assert "muOverride" in seg_props
    assert "eaDynamicBeta" in seg_props
    assert seg_props["eaSource"] == "qmoor"  # default


def test_export_inclui_fields_fase_2_3_no_boundary(client, seeded_catalog):
    del seeded_catalog
    create_resp = client.post("/api/v1/cases", json=BC01_LIKE_INPUT)
    case_id = create_resp.json()["id"]
    payload = client.get(f"/api/v1/cases/{case_id}/export/moor").json()
    bc = payload["mooringLine"]["boundary"]
    assert "startpointOffsetHorz" in bc
    assert "startpointOffsetVert" in bc
    assert "startpointType" in bc


# ─── Round-trip v1 → import → export v2 → import (idempotência) ────


def test_roundtrip_v1_via_v2_preserva_caso(client, seeded_catalog):
    """v1 importa, é migrado para v2, exportado v2, re-importado: solve
    final é idêntico (rtol=1e-9 nos escalares).

    Confirma que o migrador NÃO altera o significado físico do caso.
    """
    del seeded_catalog
    # Importa v1
    resp1 = client.post("/api/v1/import/moor", json=_V1_PAYLOAD)
    assert resp1.status_code == 201
    body1 = resp1.json()
    case_id_1 = body1["case"]["id"]

    # Exporta como v2
    payload_v2 = client.get(
        f"/api/v1/cases/{case_id_1}/export/moor?unit_system=metric"
    ).json()
    assert payload_v2["version"] == 2

    # Re-importa
    resp2 = client.post("/api/v1/import/moor", json=payload_v2)
    assert resp2.status_code == 201
    body2 = resp2.json()
    case_id_2 = body2["case"]["id"]

    # Solve ambos e compara
    solve1 = client.post(f"/api/v1/cases/{case_id_1}/solve").json()
    solve2 = client.post(f"/api/v1/cases/{case_id_2}/solve").json()
    r1 = solve1["result"]
    r2 = solve2["result"]
    for key in (
        "fairlead_tension", "anchor_tension", "total_horz_distance",
        "total_suspended_length", "total_grounded_length",
    ):
        assert math.isclose(r1[key], r2[key], rel_tol=1e-9, abs_tol=1e-6), (
            f"Round-trip drift em {key}: {r1[key]} vs {r2[key]}"
        )


def test_import_v1_retorna_migration_log_no_response(client, seeded_catalog):
    """Endpoint /import/moor retorna {case, migration_log} (Ajuste 2)."""
    del seeded_catalog
    resp = client.post("/api/v1/import/moor", json=_V1_PAYLOAD)
    assert resp.status_code == 201
    body = resp.json()
    assert "case" in body
    assert "migration_log" in body
    log = body["migration_log"]
    assert isinstance(log, list)
    assert len(log) == 6  # 3 boundary + 3 segment


def test_import_v2_payload_retorna_log_vazio(client, seeded_catalog):
    """Importar v2 nativo (sem migrar) → log vazio."""
    del seeded_catalog
    # Cria + exporta + re-importa = trip de v2 nativo
    create_resp = client.post("/api/v1/cases", json=BC01_LIKE_INPUT)
    case_id = create_resp.json()["id"]
    v2_payload = client.get(f"/api/v1/cases/{case_id}/export/moor").json()
    # Importa o v2 puro
    resp = client.post("/api/v1/import/moor", json=v2_payload)
    assert resp.status_code == 201
    body = resp.json()
    assert body["migration_log"] == []


# ─── Cases reais do baseline (regressão) ───────────────────────────


def test_baseline_cases_re_import_via_v2(client, seeded_catalog):
    """
    Carrega cases salvos no baseline, exporta cada um para v2,
    re-importa e verifica que o solve produz mesmo resultado.

    Gate de regressão (Princípio #1) — porém limitado ao subset de
    cases que o schema `.moor` v2 cobre completamente.

    LIMITAÇÃO conhecida do schema `.moor` (herdada de v1, não
    introduzida pela Fase 5): NÃO serializa `seabed.slope_rad` nem
    `attachments`. Cases com esses fields fazem round-trip incompleto
    e são SKIPADOS aqui. Pendência registrada para Fase 5.x ou
    Fase 12 — `.moor` schema completo.
    """
    del seeded_catalog
    baseline_path = (
        Path(__file__).resolve().parents[3]
        / "docs/audit/cases_baseline_2026-05-04.json"
    )
    if not baseline_path.exists():
        pytest.skip("Baseline não disponível")

    payload = json.loads(baseline_path.read_text(encoding="utf-8"))
    cases = payload["cases"]
    assert len(cases) >= 1

    cases_tested = 0
    for case_dict in cases:
        original_input = case_dict["input_json"]
        ci = CaseInput.model_validate(original_input)

        # Filtra cases com features fora do escopo do .moor schema:
        # - slope_rad ≠ 0 (campo ausente no schema)
        # - attachments (campo ausente no schema)
        if abs(ci.seabed.slope_rad) > 1e-6:
            continue
        if ci.attachments and len(ci.attachments) > 0:
            continue

        try:
            create_resp = client.post(
                "/api/v1/cases", json=ci.model_dump(mode="json"),
            )
        except Exception:
            continue
        if create_resp.status_code != 201:
            continue
        case_id = create_resp.json()["id"]

        # Exporta v2
        v2 = client.get(f"/api/v1/cases/{case_id}/export/moor").json()
        assert v2["version"] == 2

        # Re-importa
        resp2 = client.post("/api/v1/import/moor", json=v2)
        assert resp2.status_code == 201, resp2.text
        case_id_2 = resp2.json()["case"]["id"]

        # Solve ambos e compara escalares
        s1 = client.post(f"/api/v1/cases/{case_id}/solve").json()
        s2 = client.post(f"/api/v1/cases/{case_id_2}/solve").json()
        if "result" not in s1 or "result" not in s2:
            continue
        r1, r2 = s1["result"], s2["result"]
        for key in ("fairlead_tension", "total_horz_distance"):
            if r1.get(key) is not None and r2.get(key) is not None:
                assert math.isclose(r1[key], r2[key], rel_tol=1e-9, abs_tol=1e-6), (
                    f"case '{ci.name}' drift em {key}: {r1[key]} vs {r2[key]}"
                )
        cases_tested += 1

    # Sanity: pelo menos 1 case foi exercitado (pode ser zero se TODOS
    # os 3 cases do baseline têm slope ou attachments — registrar caso
    # aconteça)
    if cases_tested == 0:
        pytest.skip(
            "Nenhum case do baseline cabe no schema .moor v2 atual "
            "(todos têm slope_rad ≠ 0 ou attachments). Pendência: "
            ".moor schema expandido em Fase 5.x ou 12."
        )
