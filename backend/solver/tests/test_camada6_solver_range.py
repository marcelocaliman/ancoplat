"""
Testes da Camada 6 — Solver completo, modo Range.

Cobre BC-05 contra MoorPy e consistência Tension↔Range.
"""
from __future__ import annotations

import math

import pytest
from moorpy.Catenary import catenary as mp_catenary

from backend.solver.solver import solve
from backend.solver.types import (
    BoundaryConditions,
    ConvergenceStatus,
    LineSegment,
    SeabedConfig,
    SolutionMode,
)


TOL_FORCE_REL = 1e-2
TOL_GEOM_REL = 5e-3
LBF_FT_TO_N_M = 14.593903


def _bc04_inputs() -> tuple[LineSegment, SeabedConfig, float, float, float]:
    """Parâmetros compartilhados BC-04/BC-05: IWRCEIPS 3", h=1000, L=1800, EA=34.25 MN, μ=0.30."""
    L = 1800.0
    h = 1000.0
    w = 13.78 * LBF_FT_TO_N_M
    EA = 34.25e6
    MBL = 850e3 * 4.4482216
    mu = 0.30
    seg = LineSegment(length=L, w=w, EA=EA, MBL=MBL)
    seabed = SeabedConfig(mu=mu)
    return seg, seabed, h, EA, mu


# ==============================================================================
# BC-05 — Mode Range
# ==============================================================================


def test_BC05_contra_moorpy() -> None:
    """
    BC-05: Mesmos parâmetros de BC-04 mas em Mode Range com X=1450 m.
    Validação contra MoorPy no mesmo X.
    """
    seg, seabed, h, EA, mu = _bc04_inputs()
    L = seg.length
    w = seg.w
    X_input = 1450.0

    bc = BoundaryConditions(h=h, mode=SolutionMode.RANGE, input_value=X_input)
    r = solve([seg], bc, seabed=seabed)
    assert r.status == ConvergenceStatus.CONVERGED
    assert r.total_horz_distance == pytest.approx(X_input, rel=1e-5)

    # MoorPy validação: usando mesmo X
    fAH, fAV, fBH, fBV, info = mp_catenary(
        XF=X_input, ZF=h, L=L, EA=EA, W=w, CB=mu,
    )
    T_fl_mp = math.sqrt(fBH ** 2 + fBV ** 2)
    H_mp = abs(fBH)

    assert r.fairlead_tension == pytest.approx(T_fl_mp, rel=TOL_FORCE_REL)
    assert r.H == pytest.approx(H_mp, rel=TOL_FORCE_REL)

    print(
        f"\nBC-05 (Range, X={X_input:.0f} m, μ={mu}, EA={EA/1e6:.1f} MN):"
        f"\n  iters        : {r.iterations_used}"
        f"\n  T_fl         : my={r.fairlead_tension/1000:.2f} kN  MoorPy={T_fl_mp/1000:.2f} kN"
        f"\n  H            : my={r.H/1000:.2f} kN  MoorPy={H_mp/1000:.2f} kN"
        f"\n  L_grounded   : {r.total_grounded_length:.2f} m"
        f"\n  L_stretched  : {r.stretched_length:.2f} m (Δ={r.elongation:.2f} m)"
    )


def test_consistencia_BC04_BC05() -> None:
    """
    Consistência física: resolve BC-04 (Mode Tension, T_fl=150 t); pega X;
    resolve Mode Range com esse X; deve recuperar T_fl de entrada.
    """
    seg, seabed, h, _, _ = _bc04_inputs()
    T_fl_in = 150.0 * 9806.65

    bc_t = BoundaryConditions(h=h, mode=SolutionMode.TENSION, input_value=T_fl_in)
    r_t = solve([seg], bc_t, seabed=seabed)
    assert r_t.status == ConvergenceStatus.CONVERGED
    X_out = r_t.total_horz_distance

    bc_r = BoundaryConditions(h=h, mode=SolutionMode.RANGE, input_value=X_out)
    r_r = solve([seg], bc_r, seabed=seabed)
    assert r_r.status == ConvergenceStatus.CONVERGED

    # Recuperação de T_fl: tolerância de 1% (2·elastic_tolerance aproximadamente)
    assert r_r.fairlead_tension == pytest.approx(T_fl_in, rel=TOL_FORCE_REL)
    # Outros campos devem bater
    assert r_r.H == pytest.approx(r_t.H, rel=TOL_FORCE_REL)
    assert r_r.stretched_length == pytest.approx(r_t.stretched_length, rel=1e-3)
    assert r_r.total_grounded_length == pytest.approx(
        r_t.total_grounded_length, abs=1.0
    )


def test_range_mode_touchdown() -> None:
    """Mode Range no regime touchdown também converge."""
    # X pequeno comparado a L → touchdown
    L = 500.0
    h = 100.0
    w = 200.0
    seg = LineSegment(length=L, w=w, EA=5.0e7, MBL=2.0e6)
    bc = BoundaryConditions(h=h, mode=SolutionMode.RANGE, input_value=450.0)

    r = solve([seg], bc)
    assert r.status == ConvergenceStatus.CONVERGED
    assert r.total_grounded_length > 0
    assert r.total_horz_distance == pytest.approx(450.0, rel=1e-4)
