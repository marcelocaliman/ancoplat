"""
Testes do parser QMoor 0.8.0 (Sprint 1 / v1.1.0 / Commit 6).

Cobre:
  • Versão: aceita 0.8.x; rejeita ausente, 0.7.x, 1.0.0.
  • Unit system: aceita metric|imperial; rejeita outros.
  • Mínimo (1 line × 1 profile): produz 1 CaseInput válido.
  • Estrutura rica KAR006-like: produz N CaseInputs (cartesiano
    line × profile), preserva metadata top-level, vessel, current_profile.
  • Pendant multi-segmento round-trip.
  • profile_filter pula profiles não-selecionados.
  • Log de migração: registra trunc, fallbacks, skipados.
  • Erros: mooringLines vazio; profile sem segments; segment incompleto.

⚠ Fixtures sintéticos. Round-trip do KAR006 real é Commit 11.
"""
from __future__ import annotations

import pytest

from backend.api.services.moor_qmoor_v0_8 import (
    QMoorV08ParseError,
    parse_qmoor_v0_8,
)
from backend.api.tests.fixtures.qmoor_v0_8_synthetic import (
    synthetic_qmoor_v0_8_kar006_like,
    synthetic_qmoor_v0_8_minimal,
)


# ──────────────────────────────────────────────────────────────────
# Versão / unit system / sanity
# ──────────────────────────────────────────────────────────────────


def test_version_ausente_rejeitada() -> None:
    payload = synthetic_qmoor_v0_8_minimal()
    del payload["version"]
    with pytest.raises(QMoorV08ParseError, match="version"):
        parse_qmoor_v0_8(payload)


@pytest.mark.parametrize("v", ["0.7.5", "1.0.0", "2.0", "abc"])
def test_version_nao_0_8_rejeitada(v: str) -> None:
    payload = synthetic_qmoor_v0_8_minimal()
    payload["version"] = v
    with pytest.raises(QMoorV08ParseError, match="0.8"):
        parse_qmoor_v0_8(payload)


@pytest.mark.parametrize("v", ["0.8.0", "0.8.1", "0.8.10"])
def test_version_0_8_aceita(v: str) -> None:
    payload = synthetic_qmoor_v0_8_minimal()
    payload["version"] = v
    cases, _ = parse_qmoor_v0_8(payload)
    assert len(cases) == 1


def test_unit_system_invalido_rejeitado() -> None:
    payload = synthetic_qmoor_v0_8_minimal()
    payload["unitSystem"] = "feet"
    with pytest.raises(QMoorV08ParseError, match="unitSystem"):
        parse_qmoor_v0_8(payload)


def test_mooring_lines_vazio_rejeitado() -> None:
    payload = synthetic_qmoor_v0_8_minimal()
    payload["mooringLines"] = []
    with pytest.raises(QMoorV08ParseError, match="mooringLines"):
        parse_qmoor_v0_8(payload)


# ──────────────────────────────────────────────────────────────────
# Mínimo: 1 line × 1 profile
# ──────────────────────────────────────────────────────────────────


def test_minimal_produz_um_case() -> None:
    payload = synthetic_qmoor_v0_8_minimal()
    cases, log = parse_qmoor_v0_8(payload)
    assert len(cases) == 1
    case = cases[0]
    assert case.name == "ML1 — Operational"
    assert len(case.segments) == 1
    assert case.segments[0].length == 600.0
    assert case.boundary.h == 300.0
    assert case.boundary.input_value == 800_000.0
    assert case.metadata is not None
    assert case.metadata["source_format"] == "qmoor_0_8"
    assert case.metadata["source_unit_system"] == "metric"


# ──────────────────────────────────────────────────────────────────
# KAR006-like: 2 lines × 2 profiles → 3 cases (ML3 tem 2, ML4 tem 1)
# ──────────────────────────────────────────────────────────────────


def test_kar006_like_produz_3_cases() -> None:
    payload = synthetic_qmoor_v0_8_kar006_like()
    cases, log = parse_qmoor_v0_8(payload)
    # ML3 com 2 profiles + ML4 com 1 profile = 3 cases
    assert len(cases) == 3
    names = [c.name for c in cases]
    assert "ML3 — Operational Profile 1" in names
    assert "ML3 — Preset Profile" in names
    assert "ML4 — Operational Profile 1" in names


def test_kar006_top_metadata_propagado_para_todos_os_cases() -> None:
    payload = synthetic_qmoor_v0_8_kar006_like()
    cases, _ = parse_qmoor_v0_8(payload)
    for case in cases:
        md = case.metadata or {}
        assert md["rig"] == "P-77"
        assert md["location"] == "Bacia de Santos"
        assert md["region"] == "BR-Sul"
        assert md["engineer"] == "F. Silva"
        assert md["number"] == "KAR006"
        assert md["source_format"] == "qmoor_0_8"


def test_kar006_vessel_compartilhado() -> None:
    payload = synthetic_qmoor_v0_8_kar006_like()
    cases, _ = parse_qmoor_v0_8(payload)
    vessels = {c.vessel for c in cases}
    assert len(vessels) == 1  # mesmo vessel em todos
    v = cases[0].vessel
    assert v is not None
    assert v.name == "P-77"
    assert v.vessel_type == "Semisubmersible"
    assert v.loa == 120.0


def test_kar006_current_profile_extraido() -> None:
    payload = synthetic_qmoor_v0_8_kar006_like()
    cases, _ = parse_qmoor_v0_8(payload)
    op = next(c for c in cases if "Operational Profile 1" in c.name
              and c.name.startswith("ML3"))
    cp = op.current_profile
    assert cp is not None
    assert len(cp.layers) == 3
    assert cp.layers[0].depth == 0.0
    assert cp.layers[0].speed == 1.5
    assert cp.layers[-1].depth == 300.0


def test_kar006_pendant_segments_round_trip() -> None:
    payload = synthetic_qmoor_v0_8_kar006_like()
    cases, _ = parse_qmoor_v0_8(payload)
    op_ml3 = next(c for c in cases
                  if c.name == "ML3 — Operational Profile 1")
    assert len(op_ml3.attachments) == 1
    att = op_ml3.attachments[0]
    assert att.name == "Buoy A"
    assert att.kind == "buoy"
    assert att.submerged_force == 50_000.0
    assert att.position_s_from_anchor == 250.0
    assert att.pendant_segments is not None
    assert len(att.pendant_segments) == 2
    assert att.pendant_segments[0].length == 12.0
    assert att.pendant_segments[1].diameter == 0.080


def test_kar006_segments_multi_categoria() -> None:
    payload = synthetic_qmoor_v0_8_kar006_like()
    cases, _ = parse_qmoor_v0_8(payload)
    op_ml3 = next(c for c in cases
                  if c.name == "ML3 — Operational Profile 1")
    assert len(op_ml3.segments) == 3
    assert op_ml3.segments[0].category is not None
    assert op_ml3.segments[1].category is not None


# ──────────────────────────────────────────────────────────────────
# profile_filter
# ──────────────────────────────────────────────────────────────────


def test_profile_filter_so_operational() -> None:
    payload = synthetic_qmoor_v0_8_kar006_like()
    cases, _ = parse_qmoor_v0_8(
        payload,
        profile_filter=lambda p: p.get("type") == "operational",
    )
    assert len(cases) == 2  # ML3 op + ML4 op
    assert all("Operational" in c.name for c in cases)


def test_profile_filter_zero_match_rejeitado() -> None:
    payload = synthetic_qmoor_v0_8_kar006_like()
    with pytest.raises(QMoorV08ParseError, match="Nenhum CaseInput"):
        parse_qmoor_v0_8(payload, profile_filter=lambda p: False)


# ──────────────────────────────────────────────────────────────────
# Truncamento e log de migração
# ──────────────────────────────────────────────────────────────────


def test_segments_acima_de_10_truncado_com_log() -> None:
    payload = synthetic_qmoor_v0_8_minimal()
    seg_template = payload["mooringLines"][0]["profiles"][0]["segments"][0]
    payload["mooringLines"][0]["profiles"][0]["segments"] = [
        dict(seg_template) for _ in range(15)
    ]
    cases, log = parse_qmoor_v0_8(payload)
    case = cases[0]
    assert len(case.segments) == 10
    trunc_entries = [e for e in log if "trunca" in e.get("reason", "")]
    assert len(trunc_entries) >= 1


def test_horz_forces_acima_de_20_truncado_com_log() -> None:
    payload = synthetic_qmoor_v0_8_minimal()
    layers = [
        {"depth": float(i * 5), "speed": 1.0} for i in range(25)
    ]
    payload["mooringLines"][0]["profiles"][0]["horzForces"] = layers
    cases, log = parse_qmoor_v0_8(payload)
    cp = cases[0].current_profile
    assert cp is not None
    assert len(cp.layers) == 20
    trunc_entries = [e for e in log if "trunca" in e.get("reason", "")]
    assert len(trunc_entries) >= 1


def test_horz_forces_duplicate_depths_dedup() -> None:
    payload = synthetic_qmoor_v0_8_minimal()
    payload["mooringLines"][0]["profiles"][0]["horzForces"] = [
        {"depth": 0.0, "speed": 1.5},
        {"depth": 0.0, "speed": 0.5},   # duplicado — descartado
        {"depth": 100.0, "speed": 0.5},
    ]
    cases, _ = parse_qmoor_v0_8(payload)
    cp = cases[0].current_profile
    assert cp is not None
    depths = [l.depth for l in cp.layers]
    assert depths == [0.0, 100.0]


def test_horz_forces_invalida_em_lista_pula_entry() -> None:
    payload = synthetic_qmoor_v0_8_minimal()
    payload["mooringLines"][0]["profiles"][0]["horzForces"] = [
        {"depth": 0.0, "speed": 1.0},
        {"depth": "not-a-number", "speed": 0.5},  # inválido
        {"depth": 100.0, "speed": 0.5},
    ]
    cases, _ = parse_qmoor_v0_8(payload)
    cp = cases[0].current_profile
    assert cp is not None
    assert len(cp.layers) == 2  # entry inválida pulada


# ──────────────────────────────────────────────────────────────────
# Erros estruturais
# ──────────────────────────────────────────────────────────────────


def test_profile_sem_segments_loga_e_pula() -> None:
    payload = synthetic_qmoor_v0_8_kar006_like()
    payload["mooringLines"][0]["profiles"][0]["segments"] = []
    cases, log = parse_qmoor_v0_8(payload)
    # Pula só esse profile; ML3 fica com Preset; ML4 op continua → 2 cases
    assert len(cases) == 2
    skipped = [e for e in log if e.get("new") == "skipped"]
    assert any("erro de parse" in s.get("reason", "") for s in skipped)


def test_segment_incompleto_skipa_o_profile() -> None:
    payload = synthetic_qmoor_v0_8_minimal()
    # Remove EA do único segmento
    payload["mooringLines"][0]["profiles"][0]["segments"][0].pop("EA")
    with pytest.raises(QMoorV08ParseError, match="Nenhum CaseInput"):
        parse_qmoor_v0_8(payload)


def test_attachment_sem_position_e_logado() -> None:
    payload = synthetic_qmoor_v0_8_minimal()
    payload["mooringLines"][0]["profiles"][0]["attachments"] = [
        {"name": "Boia órfã", "kind": "buoy", "submergedForce": 1000.0},
    ]
    cases, log = parse_qmoor_v0_8(payload)
    assert cases[0].attachments == []
    skipped = [e for e in log if "position" in e.get("reason", "")]
    assert len(skipped) == 1


def test_attachment_kind_desconhecido_fallback_buoy() -> None:
    payload = synthetic_qmoor_v0_8_minimal()
    payload["mooringLines"][0]["profiles"][0]["attachments"] = [
        {
            "name": "Strange",
            "kind": "tugboat",
            "submergedForce": 1000.0,
            "positionFromAnchor": 200.0,
        },
    ]
    cases, log = parse_qmoor_v0_8(payload)
    att = cases[0].attachments[0]
    assert att.kind == "buoy"
    fallback = [e for e in log if "fallback" in e.get("reason", "")]
    assert len(fallback) == 1


# ──────────────────────────────────────────────────────────────────
# CaseInput é válido + round-trip JSON
# ──────────────────────────────────────────────────────────────────


def test_kar006_cases_round_trip_json() -> None:
    """Cada CaseInput produzido deve sobreviver model_dump → model_validate."""
    from backend.api.schemas.cases import CaseInput

    payload = synthetic_qmoor_v0_8_kar006_like()
    cases, _ = parse_qmoor_v0_8(payload)
    for c in cases:
        c2 = CaseInput.model_validate(c.model_dump())
        assert c2 == c
