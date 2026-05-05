"""
Testes do dispatcher de anchor uplift no facade `solve()` (Fase 7 / Q3).

AC:
  - Single-segment + sem attachments + endpoint_grounded=False → CONVERGED
    via solve_suspended_endpoint.
  - Multi-segmento + uplift → INVALID_CASE com mensagem clara
    ("multi-segmento + uplift fica para F7.x"). Cobre Q3=b.
  - Attachments + uplift → INVALID_CASE com mensagem clara
    ("attachments + uplift fica para F7.x"). Cobre Q3=b.
  - Cases grounded continuam intactos (regression).
"""
from __future__ import annotations

import pytest

from backend.solver.solver import solve
from backend.solver.types import (
    BoundaryConditions,
    ConvergenceStatus,
    LineAttachment,
    LineSegment,
    SolutionMode,
)


def _seg(L: float = 500.0) -> LineSegment:
    return LineSegment(length=L, w=200.0, EA=3.4e7, MBL=3.78e6)


def _bc(
    endpoint_depth: float | None = None,
    endpoint_grounded: bool = True,
) -> BoundaryConditions:
    return BoundaryConditions(
        h=300.0, mode=SolutionMode.TENSION, input_value=850_000.0,
        endpoint_grounded=endpoint_grounded,
        endpoint_depth=endpoint_depth,
    )


# ─── Single-segment uplift ──────────────────────────────────────────


def test_single_seg_uplift_converge_via_dispatcher():
    """Caminho válido principal — dispatch para suspended_endpoint."""
    r = solve([_seg()], _bc(endpoint_depth=250.0, endpoint_grounded=False))
    assert r.status == ConvergenceStatus.CONVERGED
    assert "uplift" in r.message.lower() or "suspended endpoint" in r.message.lower()


def test_single_seg_grounded_continua_funcionando():
    """Regressão: cases grounded inalterados."""
    r = solve([_seg()], _bc())  # grounded default
    assert r.status == ConvergenceStatus.CONVERGED


# ─── Multi-segmento + uplift → barrado (Q3=b) ───────────────────────


def test_multi_seg_uplift_levanta_NotImplementedError_invalid_case():
    """Q3=b: multi-seg + uplift fica para F7.x. Mensagem clara."""
    segs = [_seg(L=200.0), _seg(L=300.0)]
    bc = _bc(endpoint_depth=250.0, endpoint_grounded=False)
    r = solve(segs, bc)
    assert r.status == ConvergenceStatus.INVALID_CASE
    assert (
        "multi-segmento + uplift" in r.message.lower()
        or "f7.x" in r.message.lower()
        or "1 segmento" in r.message.lower()
    )


# ─── Attachments + uplift → barrado (Q3=b) ──────────────────────────


def test_attachments_buoy_uplift_levanta_invalid_case():
    """Q3=b: boia + uplift fica para F7.x."""
    segs = [_seg()]
    att = LineAttachment(
        kind="buoy",
        submerged_force=50_000,
        position_s_from_anchor=200.0,
    )
    bc = _bc(endpoint_depth=250.0, endpoint_grounded=False)
    r = solve(segs, bc, attachments=[att])
    assert r.status == ConvergenceStatus.INVALID_CASE
    assert (
        "attachments + uplift" in r.message.lower()
        or "f7.x" in r.message.lower()
        or "remova attachments" in r.message.lower()
    )


def test_attachments_clump_uplift_levanta_invalid_case():
    """Q3=b: clump + uplift fica para F7.x."""
    segs = [_seg()]
    att = LineAttachment(
        kind="clump_weight",
        submerged_force=80_000,
        position_s_from_anchor=300.0,
    )
    bc = _bc(endpoint_depth=250.0, endpoint_grounded=False)
    r = solve(segs, bc, attachments=[att])
    assert r.status == ConvergenceStatus.INVALID_CASE
    assert (
        "attachments + uplift" in r.message.lower()
        or "f7.x" in r.message.lower()
    )


# ─── Comparação com caso grounded equivalente ───────────────────────


def test_uplift_50m_vs_grounded_X_diferente():
    """
    Smoke comparativo: anchor 50m elevado em h=300 dá X menor que
    anchor grounded em h=300 com mesma T_fl/L (intuição: linha tem
    menos drop a sustentar, geometria mais "compacta").
    """
    bc_g = _bc()  # grounded, h=300, drop_eff=300
    bc_u = _bc(endpoint_depth=250.0, endpoint_grounded=False)  # uplift=50m, drop_eff=250

    r_g = solve([_seg()], bc_g)
    r_u = solve([_seg()], bc_u)

    assert r_g.status == ConvergenceStatus.CONVERGED
    assert r_u.status == ConvergenceStatus.CONVERGED
    # Anchor uplift → drop menor → X levemente diferente.
    # Não impomos direção forte (depende da T_fl); só que NÃO sejam
    # idênticos (sanity de que o dispatcher não está retornando o
    # mesmo solver para os dois casos).
    assert abs(r_g.total_horz_distance - r_u.total_horz_distance) > 1.0
