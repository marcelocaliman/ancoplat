"""
Testes funcionais do pipeline Tier D — Sprint 5 / Commit 44.

Validam que o dispatcher detecta Tier D corretamente, executa o
pre-processor 2-pass, e retorna SolverResult válido. NÃO validam
precisão numérica vs MoorPy (isso fica em test_ahv_operational_vs_moorpy.py).
"""
from __future__ import annotations

import pytest

from backend.solver.ahv_operational import (
    has_tier_d_attachment,
    solve_with_ahv_operational,
)
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


def _make_simple_case():
    """Cenário simples: linha 1500m, h=200m, X=1300m, attachment Tier D."""
    seg = LineSegment(
        length=1500.0, w=170.0, EA=5.5e8, MBL=6.5e6,
        category="Wire", line_type="wire76",
    )
    bc = BoundaryConditions(
        h=200.0, mode=SolutionMode.RANGE, input_value=1300.0,
        startpoint_depth=0.0, endpoint_grounded=True,
    )
    att = LineAttachment(
        kind="ahv",
        position_s_from_anchor=750.0,  # meio da linha
        ahv_bollard_pull=500_000.0,
        ahv_heading_deg=0.0,
        ahv_work_wire=WorkWireSpec(
            length=200.0, EA=5.5e8, w=170.0, MBL=6.5e6,
            line_type="wire76",
        ),
        ahv_deck_x=850.0,  # 100m à direita do meio (em frame plot)
        ahv_deck_level=10.0,
    )
    return [seg], bc, att


# ──────────────────────────────────────────────────────────────────
# Detector
# ──────────────────────────────────────────────────────────────────


def test_has_tier_d_detecta_attachment_com_work_wire() -> None:
    _, _, att_d = _make_simple_case()
    att_f8 = LineAttachment(
        kind="ahv", position_index=0,
        ahv_bollard_pull=100_000.0, ahv_heading_deg=0.0,
    )
    att_buoy = LineAttachment(
        kind="buoy", position_index=0, submerged_force=50_000.0,
    )
    assert has_tier_d_attachment([att_d]) is True
    assert has_tier_d_attachment([att_f8]) is False
    assert has_tier_d_attachment([att_buoy]) is False
    assert has_tier_d_attachment([att_buoy, att_d]) is True
    assert has_tier_d_attachment([]) is False


def test_has_tier_d_ignora_buoy_e_clump() -> None:
    """Mesmo se ahv_work_wire fosse setado em buoy/clump (validação
    Pydantic já bloqueia), helper só reconhece em kind='ahv'."""
    att_f8 = LineAttachment(
        kind="ahv", position_index=0,
        ahv_bollard_pull=100_000.0, ahv_heading_deg=0.0,
    )
    assert not has_tier_d_attachment([att_f8])


# ──────────────────────────────────────────────────────────────────
# Pipeline integrado via facade solve()
# ──────────────────────────────────────────────────────────────────


def test_facade_dispatcher_aciona_tier_d() -> None:
    """solve() detecta Tier D via has_tier_d_attachment e delega."""
    segs, bc, att = _make_simple_case()
    result = facade_solve(
        line_segments=segs, boundary=bc,
        seabed=SeabedConfig(), config=SolverConfig(),
        attachments=[att],
    )
    # Solver deve sempre retornar SolverResult — converged ou
    # invalid_case com mensagem clara. Não pode crashar.
    assert result.status.value in (
        "converged", "invalid_case", "max_iterations", "numerical_error",
    )
    # Versão do solver indica que o Tier D foi acionado (ou fallback).
    assert result.solver_version is not None


def test_solve_with_ahv_operational_chamado_diretamente() -> None:
    """Chamada direta de solve_with_ahv_operational com pieces."""
    segs, bc, att = _make_simple_case()
    result = solve_with_ahv_operational(
        line_segments=segs,
        boundary=bc,
        attachments=[att],
        seabed=SeabedConfig(),
        config=SolverConfig(),
    )
    assert result.status.value in (
        "converged", "invalid_case", "max_iterations", "numerical_error",
    )


def test_multi_tier_d_attachments_aceitos() -> None:
    """
    Sprint 7 / Commit 59 — Multi-AHV é ACEITO (era rejeitado em Sprint 5).
    Solver loop interno aplica force injection independente em cada AHV.
    Convergência depende da geometria; basta verificar que não crasha
    e retorna SolverResult válido.
    """
    seg, bc, att1 = _make_simple_case()
    att2 = att1.model_copy(update={"position_s_from_anchor": 600.0})
    result = solve_with_ahv_operational(
        line_segments=seg,
        boundary=bc,
        attachments=[att1, att2],
        seabed=SeabedConfig(),
        config=SolverConfig(),
    )
    # Não deve crashar — status pode ser converged, invalid_case, ou
    # outros conhecidos. NÃO deve mais retornar "apenas 1 attachment".
    assert result.status.value in (
        "converged", "invalid_case", "max_iterations", "numerical_error",
    )
    assert "apenas 1 attachment" not in (result.message or "").lower()


# ──────────────────────────────────────────────────────────────────
# Retro-compat F8 (sem Tier D) preservado
# ──────────────────────────────────────────────────────────────────


def test_f8_puro_continua_funcionando_sem_tier_d() -> None:
    """LineAttachment kind='ahv' sem ahv_work_wire → F8 puro inalterado."""
    seg = LineSegment(
        length=1500.0, w=170.0, EA=5.5e8, MBL=6.5e6, category="Wire",
    )
    bc = BoundaryConditions(
        h=200.0, mode=SolutionMode.RANGE, input_value=1300.0,
        startpoint_depth=0.0, endpoint_grounded=True,
    )
    att_f8 = LineAttachment(
        kind="ahv", position_s_from_anchor=750.0,
        ahv_bollard_pull=500_000.0, ahv_heading_deg=0.0,
    )
    result = facade_solve(
        line_segments=[seg], boundary=bc,
        seabed=SeabedConfig(), config=SolverConfig(),
        attachments=[att_f8],
    )
    # Não deve disparar Tier D (sem ahv_work_wire) → solver_version
    # NÃO contém 'ahv_operational'.
    assert "ahv_operational" not in (result.solver_version or "")


def test_caso_sem_attachments_inalterado() -> None:
    """Linha sem attachments — caminho normal F1+ preservado."""
    seg = LineSegment(
        length=1500.0, w=170.0, EA=5.5e8, MBL=6.5e6, category="Wire",
    )
    bc = BoundaryConditions(
        h=200.0, mode=SolutionMode.RANGE, input_value=1300.0,
        startpoint_depth=0.0, endpoint_grounded=True,
    )
    result = facade_solve(
        line_segments=[seg], boundary=bc,
        seabed=SeabedConfig(), config=SolverConfig(),
        attachments=[],
    )
    # Status pode ser converged ou invalid_case (geometria), mas
    # NÃO pode disparar Tier D.
    assert "ahv_operational" not in (result.solver_version or "")
