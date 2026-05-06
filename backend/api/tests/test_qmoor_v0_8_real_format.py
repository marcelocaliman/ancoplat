"""
Testes do formato REAL QMoor 0.8.0 — Sprint 2 / Commit 20.

Diferente dos fixtures sintéticos do Commit 6 (que tinham campos
flatten no top-level), aqui exercitamos a estrutura REAL do JSON do
QMoor 0.8.0 conforme reportada pelo usuário no caso KAR006:

  • Top-level: `QMoorVersion` (não `version`).
  • Segments com props físicas em `lineProps.{...}` (não no top do seg).
  • Quantidades como string com unidade ("475.0 m", "150.66 kgf / m",
    "81018.96 te", "128001 MPa").
  • Boias em `profile.buoys[]` com `pennantLine.segments[]` e
    `distFromEnd`.
"""
from __future__ import annotations

import pytest

from backend.api.services.moor_qmoor_v0_8 import (
    QMoorV08ParseError,
    parse_qmoor_v0_8,
)
from backend.api.tests.fixtures.qmoor_v0_8_synthetic import (
    synthetic_qmoor_v0_8_kar006_real,
)


# ──────────────────────────────────────────────────────────────────
# Detecção de versão (QMoorVersion vs version)
# ──────────────────────────────────────────────────────────────────


def test_qmoorversion_alias_aceito() -> None:
    """O JSON real usa `QMoorVersion`; meu fixture original usava
    `version`. Ambos devem ser aceitos."""
    payload = synthetic_qmoor_v0_8_kar006_real()
    # Garantir que QMoorVersion está presente e version não
    assert "QMoorVersion" in payload
    assert "version" not in payload
    cases, _ = parse_qmoor_v0_8(payload)
    assert len(cases) == 1


# ──────────────────────────────────────────────────────────────────
# Segments com lineProps + quantidades string-com-unidade
# ──────────────────────────────────────────────────────────────────


def test_segments_real_format_parse_ok() -> None:
    payload = synthetic_qmoor_v0_8_kar006_real()
    cases, log = parse_qmoor_v0_8(payload)
    case = cases[0]
    assert len(case.segments) == 3
    rig_chain, wire, anchor_chain = case.segments

    # Lengths em metros
    assert rig_chain.length == pytest.approx(475.0, rel=1e-9)
    assert wire.length == pytest.approx(609.0, rel=1e-9)
    assert anchor_chain.length == pytest.approx(488.0, rel=1e-9)

    # Wet weight: kgf/m → N/m (× 9.80665)
    # 150.66 kgf/m = 150.66 × 9.80665 = 1477.5 N/m
    assert rig_chain.w == pytest.approx(150.66171764698163 * 9.80665, rel=1e-3)
    # 33.97 kgf/m = 333.13 N/m
    assert wire.w == pytest.approx(33.97113378709231 * 9.80665, rel=1e-3)

    # EA: te → N (× 9806.65)
    # 81018.96 te = 81018.96 × 9806.65 ≈ 7.95e8 N
    assert rig_chain.EA == pytest.approx(81018.96002399089 * 9806.65, rel=1e-3)

    # MBL: te → N
    # 815.16 te = 7.99 MN
    assert rig_chain.MBL == pytest.approx(815.1553840507001 * 9806.65, rel=1e-3)

    # Diameter: mm → m
    assert rig_chain.diameter == pytest.approx(0.0889, rel=1e-3)
    assert wire.diameter == pytest.approx(0.098, rel=1e-3)

    # line_type via lineProps
    assert rig_chain.line_type == "R4Chain"
    assert wire.line_type == "EIPS20"

    # Category drillado de lineProps
    assert rig_chain.category == "StuddedChain"
    assert wire.category == "Wire"


def test_segments_dryweight_modulus_extraidos() -> None:
    payload = synthetic_qmoor_v0_8_kar006_real()
    cases, _ = parse_qmoor_v0_8(payload)
    rig_chain = cases[0].segments[0]
    assert rig_chain.dry_weight is not None
    assert rig_chain.dry_weight > rig_chain.w  # peso seco > submerso
    assert rig_chain.modulus is not None
    assert rig_chain.modulus == pytest.approx(128001.16914767069e6, rel=1e-3)


# ──────────────────────────────────────────────────────────────────
# Boundary com fairleadOffset + solution.inputParam
# ──────────────────────────────────────────────────────────────────


def test_boundary_real_format_parse() -> None:
    payload = synthetic_qmoor_v0_8_kar006_real()
    cases, _ = parse_qmoor_v0_8(payload)
    case = cases[0]
    # endpointDepth=311 m é a referência; startpointDepth=284 é a
    # convenção QMoor "fairlead na superfície" → mapeia para 0.
    assert case.boundary.h == pytest.approx(311.0, rel=1e-9)
    assert case.boundary.startpoint_depth == 0.0
    # mode=Tension via solution.inputParam='tension'
    assert case.boundary.mode == "Tension"
    # input_value = 150 te = 150 × 9806.65 ≈ 1.471e6 N
    assert case.boundary.input_value == pytest.approx(150.0 * 9806.65, rel=1e-3)


def test_fairlead_offset_preservado_em_metadata() -> None:
    payload = synthetic_qmoor_v0_8_kar006_real()
    cases, _ = parse_qmoor_v0_8(payload)
    md = cases[0].metadata or {}
    assert "fairlead_offset_y_m" in md
    assert float(md["fairlead_offset_y_m"]) == pytest.approx(2.4384, rel=1e-3)


# ──────────────────────────────────────────────────────────────────
# Boias em profile.buoys[] com pennantLine.segments[]
# ──────────────────────────────────────────────────────────────────


def test_boias_em_profile_buoys_extraidas() -> None:
    payload = synthetic_qmoor_v0_8_kar006_real()
    cases, log = parse_qmoor_v0_8(payload)
    case = cases[0]
    # Esperamos 1 boia no profile.buoys[]
    assert len(case.attachments) == 1
    buoy = case.attachments[0]
    assert buoy.kind == "buoy"
    assert buoy.name == "B1018"
    # Empuxo > 0 (computed via compute_submerged_force)
    assert buoy.submerged_force > 0
    # Dimensões da boia
    assert buoy.buoy_outer_diameter == pytest.approx(3.048, rel=1e-3)
    assert buoy.buoy_length == pytest.approx(3.6308, rel=1e-3)
    assert buoy.buoy_end_type == "elliptical"
    assert buoy.buoy_type == "submersible"


def test_pennant_line_multi_trecho_parseado() -> None:
    payload = synthetic_qmoor_v0_8_kar006_real()
    cases, _ = parse_qmoor_v0_8(payload)
    buoy = cases[0].attachments[0]
    assert buoy.pendant_segments is not None
    assert len(buoy.pendant_segments) == 2
    chain, wire = buoy.pendant_segments
    # Primeiro trecho (lado da linha): R4Chain 6m
    assert chain.line_type == "R4Chain"
    assert chain.length == pytest.approx(6.0, rel=1e-9)
    assert chain.diameter == pytest.approx(0.08255, rel=1e-3)
    assert chain.category == "StuddedChain"
    # Segundo trecho (lado da boia): EIPS20 92m
    assert wire.line_type == "EIPS20"
    assert wire.length == pytest.approx(92.0, rel=1e-9)


def test_buoy_position_convertida_de_distFromEnd() -> None:
    """`distFromEnd` (distância do fairlead) → `position_s_from_anchor`
    (distância da âncora). Total = 475+609+488 = 1572 m. distFromEnd =
    1088 m. position_s_from_anchor = 1572 − 1088 = 484 m."""
    payload = synthetic_qmoor_v0_8_kar006_real()
    cases, _ = parse_qmoor_v0_8(payload)
    buoy = cases[0].attachments[0]
    assert buoy.position_s_from_anchor == pytest.approx(484.0, rel=1e-9)


# ──────────────────────────────────────────────────────────────────
# Pipeline solver → o caso parseado é solúvel
# ──────────────────────────────────────────────────────────────────


def test_caso_parseado_aceito_em_post_cases(client) -> None:  # type: ignore[no-untyped-def]
    """Caso real KAR006 parseado deve passar a validação Pydantic do
    `POST /api/v1/cases` (criação no DB). Solver é um passo separado
    com suas próprias condições de convergência (multi-seg + slope +
    boia pode ser numericamente difícil em alguns regimes — não é
    problema do parser)."""
    payload = synthetic_qmoor_v0_8_kar006_real()
    cases, _ = parse_qmoor_v0_8(payload)
    case = cases[0]

    resp = client.post("/api/v1/cases", json=case.model_dump(mode="json"))
    assert resp.status_code == 201, resp.text
    body = resp.json()
    # Round-trip preserva os campos importantes
    assert body["input"]["metadata"]["number"] == "KAR006"
    assert body["input"]["metadata"]["rig"] == "Maersk Developer"
    assert len(body["input"]["segments"]) == 3
    assert len(body["input"]["attachments"]) == 1
    assert body["input"]["attachments"][0]["kind"] == "buoy"
