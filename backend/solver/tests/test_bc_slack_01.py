"""
BC-SLACK-01 — Regressão para o regime SLACK (multi-seg + slope + L_g
atravessa múltiplos segmentos sem boia/clump na zona grounded).

Sprint 2 / Commit 21: garantir que o caso KAR006 ML3 (que motivou o
fix do `_integrate_with_extended_grounded`) continua convergindo em
PRs futuros.

Caso fonte: arquivo real `7-PRA-2-SPS Well_dbr.moor` do projeto KAR006
da Karoon Energy (Maersk Developer / Bauna Field). Variante ML3:
  • 5 segments: chain 488m + wire 305m + chain 6m + wire 609m + chain 475m
    (anchor → fairlead, convenção AncoPlat).
  • h = 311 m (anchor depth), startpoint na superfície.
  • Slope = atan2(311 − 284, 1829) ≈ 0.846° (bathymetry derivada).
  • mu = 0.6 (catálogo wire EIPS20; usado conservadoramente).
  • T_fl = 150 te (ML3 spec). Modo Tension.

Antes do Commit 21: solver retornava `invalid_case` com mensagem
"fsolve não convergiu para multi-segmento + slope" porque o
integrador `_integrate_segments_with_grounded` rejeitava
`L_g_0 > L_effs[0]` (488 m), mas o L_g real está em ~700 m.
"""
from __future__ import annotations

import pytest

from backend.api.schemas.cases import CaseInput
from backend.solver.solver import solve


# ──────────────────────────────────────────────────────────────────
# Configuração canônica do BC-SLACK-01
# ──────────────────────────────────────────────────────────────────


def _bc_slack_01_input() -> CaseInput:
    G = 9.80665
    G_KN = 9806.65  # kN per te
    return CaseInput.model_validate({
        "name": "BC-SLACK-01: KAR006 ML3 (regime slack)",
        "description": (
            "Caso real do KAR006 (Maersk Developer / Bauna Field) com "
            "L_g real > L_effs[0]. Antes Sprint 2/Commit 21 não convergia."
        ),
        "segments": [
            {"length": 488.0, "w": 134.51 * G,
             "EA": 72333.87 * G_KN, "MBL": 735.56 * G_KN,
             "category": "StuddedChain", "line_type": "R4Chain",
             "diameter": 0.084},
            {"length": 305.0, "w": 28.04 * G,
             "EA": 42785.34 * G_KN, "MBL": 710.01 * G_KN,
             "category": "Wire", "line_type": "EIPS20",
             "diameter": 0.0889},
            {"length": 6.0, "w": 134.51 * G,
             "EA": 72333.87 * G_KN, "MBL": 735.56 * G_KN,
             "category": "StuddedChain", "line_type": "R4Chain",
             "diameter": 0.084},
            {"length": 609.0, "w": 33.97 * G,
             "EA": 51992.85 * G_KN, "MBL": 732.58 * G_KN,
             "category": "Wire", "line_type": "EIPS20",
             "diameter": 0.098},
            {"length": 475.0, "w": 150.66 * G,
             "EA": 81018.96 * G_KN, "MBL": 815.16 * G_KN,
             "category": "StuddedChain", "line_type": "R4Chain",
             "diameter": 0.0889},
        ],
        "boundary": {
            "h": 311.0, "mode": "Tension",
            "input_value": 150.0 * G_KN,
            "startpoint_depth": 0.0, "endpoint_grounded": True,
        },
        "seabed": {"mu": 0.6, "slope_rad": 0.0146935},  # atan2(27, 1829)
        "criteria_profile": "MVP_Preliminary",
    })


# ──────────────────────────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────────────────────────


def test_bc_slack_01_converge() -> None:
    """KAR006 ML3 com T_fl=150te converge (status=converged)."""
    ci = _bc_slack_01_input()
    res = solve(
        line_segments=ci.segments,
        boundary=ci.boundary,
        seabed=ci.seabed,
        criteria_profile=ci.criteria_profile,
    )
    assert res.status.value == "converged", (
        f"BC-SLACK-01 falhou: status={res.status.value}, "
        f"msg={res.message[:200]}"
    )


def test_bc_slack_01_geometria_plausivel() -> None:
    """Resultado vs QMoor (X≈1797m): nossa estimativa deve estar
    dentro de ±5% (tolerância para diferenças de catálogo µ/EA)."""
    ci = _bc_slack_01_input()
    res = solve(
        line_segments=ci.segments,
        boundary=ci.boundary,
        seabed=ci.seabed,
        criteria_profile=ci.criteria_profile,
    )
    # QMoor reportou X = 1796.88 m
    assert res.total_horz_distance == pytest.approx(1797, rel=0.05), (
        f"X={res.total_horz_distance:.1f} fora de QMoor 1797m ±5%"
    )
    # T_fl deve ser exatamente o input (modo Tension fixa)
    assert res.fairlead_tension == pytest.approx(150.0 * 9806.65, rel=1e-9)
    # T_anchor > 0 e < T_fl (consistência física)
    assert 0 < res.anchor_tension < res.fairlead_tension


def test_bc_slack_01_l_grounded_atravessa_multiplos_segmentos() -> None:
    """L_g real do KAR006 ML3 deve ser > L_effs[0]=488m, comprovando
    que o caminho `_integrate_with_extended_grounded` foi exercitado."""
    ci = _bc_slack_01_input()
    res = solve(
        line_segments=ci.segments,
        boundary=ci.boundary,
        seabed=ci.seabed,
        criteria_profile=ci.criteria_profile,
    )
    L_seg_0 = ci.segments[0].length  # 488 m
    assert res.total_grounded_length > L_seg_0, (
        f"L_g={res.total_grounded_length:.1f} ≤ L_seg_0={L_seg_0} — "
        "extended-grounded NÃO foi acionado, fix pode ter regredido."
    )
    # Total da linha não-esticada deve ser preservado (sanity)
    L_total = sum(s.length for s in ci.segments)
    assert (
        res.total_grounded_length + res.total_suspended_length
        == pytest.approx(L_total + res.elongation, rel=1e-4)
    )


@pytest.mark.parametrize("tfl_te", [80, 100, 120, 150, 180, 200, 300, 500])
def test_bc_slack_01_sweep_tfl_converge(tfl_te: float) -> None:
    """Em TODA a faixa T_fl ∈ [80, 500] te o caso deve convergir.
    Antes do Commit 21, T_fl < 180te falhava."""
    ci = _bc_slack_01_input()
    bd = ci.boundary.model_copy(update={"input_value": tfl_te * 9806.65})
    res = solve(
        line_segments=ci.segments,
        boundary=bd,
        seabed=ci.seabed,
        criteria_profile=ci.criteria_profile,
    )
    # Em T_fl muito alto (>~700te) pode dar broken por T/MBL > 1.0;
    # aceitar broken como resultado "convergido fisicamente".
    assert res.status.value in ("converged",), (
        f"T_fl={tfl_te}te: status={res.status.value} msg={res.message[:120]}"
    )
