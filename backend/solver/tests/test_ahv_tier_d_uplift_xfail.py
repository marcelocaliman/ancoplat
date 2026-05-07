"""
AHV Tier D + uplift — pendência F7.x.y (Sprint 7 / Commit 60).

Sprint 7 documenta o caminho mas NÃO implementa: combinar Tier D
(AHV operacional mid-line via ahv_work_wire) com uplift (anchor
suspenso, endpoint_grounded=False) requer extensão de
solve_suspended_endpoint para aceitar force injection F8 mid-line.

Implementação real fica como F7.x.y (pós-v1.4). Testes abaixo
servem como CONTRATO de comportamento esperado quando feature
existir, mas atualmente xfail (rejeitam com NotImplementedError
mensagem específica).
"""
from __future__ import annotations

import pytest

from backend.solver.solver import solve as facade_solve
from backend.solver.types import (
    BoundaryConditions,
    LineAttachment,
    LineSegment,
    SeabedConfig,
    SolutionMode,
    SolverConfig,
    WorkWireSpec,
)


def _make_uplift_tier_d_case():
    """Caso com anchor uplift + attachment AHV Tier D mid-line."""
    seg = LineSegment(
        length=1500.0, w=170.0, EA=5.5e8, MBL=6.5e6, category="Wire",
    )
    bc = BoundaryConditions(
        h=200.0,
        mode=SolutionMode.RANGE,
        input_value=1300.0,
        startpoint_depth=0.0,
        endpoint_grounded=False,  # uplift!
        endpoint_depth=100.0,     # anchor 100m abaixo da superfície
        # → 100m acima do fundo (h=200m)
    )
    att = LineAttachment(
        kind="ahv",
        position_s_from_anchor=750.0,
        ahv_bollard_pull=500_000.0,
        ahv_heading_deg=0.0,
        ahv_work_wire=WorkWireSpec(
            length=200.0, EA=5.5e8, w=170.0, MBL=6.5e6,
        ),
        ahv_deck_x=850.0,
        ahv_deck_level=10.0,
    )
    return [seg], bc, [att]


@pytest.mark.xfail(
    reason=(
        "Sprint 7 / pendência F7.x.y (v1.5+): combinar Tier D + uplift "
        "requer extensão de solve_suspended_endpoint para aceitar force "
        "injection F8 mid-line. Solver atual rejeita com mensagem "
        "específica citando o caminho de implementação."
    ),
    strict=True,  # quando feature for implementada, xfail vira pass automaticamente
)
def test_tier_d_com_uplift_converge_v1_5_plus() -> None:
    """
    Quando F7.x.y for implementada, este test passa: Tier D + uplift
    deve resolver via F7 catenária suspensa + F8 force injection
    iterativa.
    """
    segs, bc, atts = _make_uplift_tier_d_case()
    result = facade_solve(
        line_segments=segs, boundary=bc,
        seabed=SeabedConfig(), config=SolverConfig(),
        attachments=atts,
    )
    assert result.status.value == "converged"


def test_tier_d_com_uplift_rejeita_com_mensagem_clara_em_v1_4() -> None:
    """
    Sprint 7 / Commit 60: enquanto F7.x.y não existe, a rejeição é
    explícita citando o path de implementação ("F7.x.y", "Tier D",
    "v1.5+") para que o engenheiro entenda o porquê.
    """
    segs, bc, atts = _make_uplift_tier_d_case()
    result = facade_solve(
        line_segments=segs, boundary=bc,
        seabed=SeabedConfig(), config=SolverConfig(),
        attachments=atts,
    )
    assert result.status.value == "invalid_case"
    msg = (result.message or "").lower()
    # Mensagem deve citar uplift + caminho de implementação futura.
    # Aceita variações: "tier d" / "ahv_work_wire" / "f7.x" / "uplift"
    has_uplift_msg = "uplift" in msg or "endpoint_grounded" in msg
    has_path = "f7.x" in msg or "tier d" in msg or "v1.5" in msg
    assert has_uplift_msg, f"mensagem deveria citar uplift: {msg}"
    assert has_path, f"mensagem deveria citar path futuro (F7.x/Tier D): {msg}"
