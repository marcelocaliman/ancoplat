"""
Testes da Camada 4 — Correção elástica.

Cobre: apply_elastic_correction, EA-infinito ≡ rígido,
alongamento > 0 para EA finito, e BC-03 contra MoorPy (elástica
totalmente suspensa).
"""
from __future__ import annotations

import math

import pytest
from moorpy.Catenary import catenary as mp_catenary

from backend.solver.catenary import solve_rigid_suspended
from backend.solver.elastic import (
    apply_elastic_correction,
    solve_elastic_iterative,
)
from backend.solver.types import (
    ConvergenceStatus,
    SolutionMode,
)


TOL_GEOM_REL = 5e-3
TOL_FORCE_REL = 1e-2
LBF_FT_TO_N_M = 14.593903


# ==============================================================================
# apply_elastic_correction — helper
# ==============================================================================


def test_apply_elastic_correction_formula() -> None:
    """L_stretched = L · (1 + T_mean/EA)."""
    assert apply_elastic_correction(100.0, 1.0e8, 1.0e6) == pytest.approx(101.0)
    # EA = ∞ (muito grande): alongamento desprezível (T/EA ~ 1e-12)
    assert apply_elastic_correction(100.0, 1.0e18, 1.0e6) == pytest.approx(100.0, rel=1e-9)


def test_apply_elastic_correction_recusa_EA_invalido() -> None:
    with pytest.raises(ValueError):
        apply_elastic_correction(100.0, 0.0, 1000.0)
    with pytest.raises(ValueError):
        apply_elastic_correction(100.0, -1.0, 1000.0)


# ==============================================================================
# EA muito grande ≡ rígido
# ==============================================================================


def test_EA_infinito_equivale_rigido() -> None:
    """Para EA gigantesco, resultado elástico deve bater com rígido nos campos
    geométricos e de força (Camada 3)."""
    L = 450.0
    h = 300.0
    w = 13.78 * LBF_FT_TO_N_M
    T_fl = 785_000.0

    r_rig = solve_rigid_suspended(
        L=L, h=h, w=w, mode=SolutionMode.TENSION, input_value=T_fl,
    )
    r_el = solve_elastic_iterative(
        L=L, h=h, w=w, EA=1.0e18, mode=SolutionMode.TENSION, input_value=T_fl,
    )

    assert r_el.status == ConvergenceStatus.CONVERGED
    assert r_el.total_horz_distance == pytest.approx(r_rig.total_horz_distance, rel=1e-9)
    assert r_el.H == pytest.approx(r_rig.H, rel=1e-9)
    assert r_el.fairlead_tension == pytest.approx(r_rig.fairlead_tension, rel=1e-9)
    assert r_el.elongation == pytest.approx(0.0, abs=1e-6)


def test_correcao_elastica_aumenta_comprimento_esticado() -> None:
    """
    Sanity: para EA finito, a linha estica → stretched_length > unstretched_length,
    elongation > 0, e X é ligeiramente maior (linha estica sob tração).
    """
    L = 450.0
    h = 300.0
    w = 13.78 * LBF_FT_TO_N_M
    T_fl = 785_000.0
    EA_finite = 3.42e7  # IWRCEIPS 3" qmoor_ea (~34 MN)

    r_rig = solve_rigid_suspended(
        L=L, h=h, w=w, mode=SolutionMode.TENSION, input_value=T_fl,
    )
    r_el = solve_elastic_iterative(
        L=L, h=h, w=w, EA=EA_finite, mode=SolutionMode.TENSION, input_value=T_fl,
    )

    assert r_el.status == ConvergenceStatus.CONVERGED
    assert r_el.stretched_length > L
    assert r_el.elongation > 0
    # Para T_mean ~700 kN e EA 34 MN, alongamento esperado ~2%. Checa ordem.
    assert 0.01 < r_el.elongation / L < 0.05
    # X aumentou (linha mais longa → fairlead mais longe)
    assert r_el.total_horz_distance > r_rig.total_horz_distance


# ==============================================================================
# BC-03 — Elástica totalmente suspensa contra MoorPy
# ==============================================================================


def test_BC03_contra_moorpy() -> None:
    """
    BC-03 (conforme Documento A v2.2 Seção 6.2, entradas a definir):
    Catenária elástica totalmente suspensa com EA finito.

    Parâmetros: IWRCEIPS 3" com qmoor_ea=34.25 MN (do catálogo),
    h=300 m, L=450 m, T_fl=785 kN — mesma geometria de BC-01.
    Sem touchdown, com elasticidade.
    """
    L = 450.0
    h = 300.0
    w = 13.78 * LBF_FT_TO_N_M
    EA = 34.25e6  # qmoor_ea ~ 34.25 MN para IWRCEIPS 3"
    T_fl_input = 785_000.0

    my = solve_elastic_iterative(
        L=L, h=h, w=w, EA=EA, mode=SolutionMode.TENSION, input_value=T_fl_input,
    )
    assert my.status == ConvergenceStatus.CONVERGED
    assert my.iterations_used >= 1
    assert my.total_grounded_length == 0.0  # fully suspended
    X_my = my.total_horz_distance

    # MoorPy com mesmo EA
    fAH, fAV, fBH, fBV, info = mp_catenary(
        XF=X_my, ZF=h, L=L, EA=EA, W=w, CB=0,
    )
    T_fl_mp = math.sqrt(fBH ** 2 + fBV ** 2)
    H_mp = abs(fBH)
    # MoorPy também reporta L_stretched via info dict
    L_stretched_mp = info.get("Sextreme", None)
    # or:
    stretched_len_key = "Ltot" if "Ltot" in info else None

    assert T_fl_mp == pytest.approx(T_fl_input, rel=TOL_FORCE_REL)
    assert H_mp == pytest.approx(my.H, rel=TOL_FORCE_REL)

    print(
        f"\nBC-03 (EA={EA/1e6:.1f} MN):"
        f"\n  iters        : {my.iterations_used}"
        f"\n  X            : {X_my:.3f} m"
        f"\n  H            : my={my.H/1000:.2f} kN  MoorPy={H_mp/1000:.2f} kN"
        f"\n  T_fl         : my={my.fairlead_tension/1000:.2f} kN  MoorPy={T_fl_mp/1000:.2f} kN"
        f"\n  elongation   : my={my.elongation:.3f} m ({my.elongation/L*100:.2f}%)"
        f"\n  L_stretched  : my={my.stretched_length:.3f} m"
    )
