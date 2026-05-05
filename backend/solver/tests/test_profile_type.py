"""
Testes unitários do classify_profile_type (Fase 4 / Q2).

Função pura: testes podem mockar SolverResult diretamente sem solver.
Cobre os 6 PTs atingíveis no AncoPlat MVP v1: PT_0, PT_1, PT_2, PT_3,
PT_6, PT_7, PT_8 (PT_4, PT_5, PT_U são forward-compat e nunca
retornados pelo classifier atual).

Testes de integração com BC-MOORPY estão em test_profile_type_moorpy.py
(Commit 3 da Fase 4).
"""
from __future__ import annotations

import pytest

from backend.solver.profile_type import classify_profile_type
from backend.solver.types import (
    ConvergenceStatus,
    LineSegment,
    ProfileType,
    SeabedConfig,
    SolverResult,
)


def _seg(L: float = 500.0, w: float = 200.0) -> LineSegment:
    return LineSegment(length=L, w=w, EA=7.5e9, MBL=3.0e6)


def _result(
    *,
    status: ConvergenceStatus = ConvergenceStatus.CONVERGED,
    grounded: float = 0.0,
    suspended: float = 500.0,
    anchor_tension: float = 50_000.0,
    X: float = 400.0,
) -> SolverResult:
    return SolverResult(
        status=status,
        total_grounded_length=grounded,
        total_suspended_length=suspended,
        anchor_tension=anchor_tension,
        total_horz_distance=X,
    )


# ─── Status sem geometria → None ────────────────────────────────────


def test_invalid_case_retorna_none():
    r = _result(status=ConvergenceStatus.INVALID_CASE)
    assert classify_profile_type(r, [_seg()]) is None


def test_numerical_error_retorna_none():
    r = _result(status=ConvergenceStatus.NUMERICAL_ERROR)
    assert classify_profile_type(r, [_seg()]) is None


def test_ill_conditioned_classifica_normalmente():
    """ILL_CONDITIONED ainda tem geometria — classifier opera."""
    r = _result(
        status=ConvergenceStatus.ILL_CONDITIONED,
        grounded=0.0, suspended=500.0, anchor_tension=50_000, X=400,
    )
    pt = classify_profile_type(r, [_seg()])
    assert pt == ProfileType.PT_1  # fully suspended


# ─── PT_0: linha inteira no seabed, plano ──────────────────────────


def test_PT_0_linha_inteira_grounded_sem_slope():
    r = _result(grounded=500.0, suspended=0.0, anchor_tension=10_000, X=500)
    pt = classify_profile_type(r, [_seg()], SeabedConfig(slope_rad=0.0))
    assert pt == ProfileType.PT_0


# ─── PT_1: catenária livre (fully suspended) ───────────────────────


def test_PT_1_fully_suspended_sem_seabed():
    r = _result(grounded=0.0, suspended=500.0, anchor_tension=80_000, X=400)
    pt = classify_profile_type(r, [_seg()])
    assert pt == ProfileType.PT_1


def test_PT_1_fully_suspended_com_slope_no_seabed_mas_linha_nao_toca():
    """Slope no seabed irrelevante quando linha não toca o fundo."""
    r = _result(grounded=0.0, suspended=500.0, X=400)
    pt = classify_profile_type(r, [_seg()], SeabedConfig(slope_rad=0.05))
    assert pt == ProfileType.PT_1


# ─── PT_2: touchdown plano com T_anchor != 0 ───────────────────────


def test_PT_2_touchdown_com_atrito_T_anchor_positivo():
    r = _result(grounded=200.0, suspended=300.0, anchor_tension=15_000, X=400)
    pt = classify_profile_type(r, [_seg()], SeabedConfig(slope_rad=0.0))
    assert pt == ProfileType.PT_2


# ─── PT_3: touchdown plano com T_anchor = 0 ────────────────────────


def test_PT_3_touchdown_T_anchor_zero():
    """Atrito alto saturou ou μ=0 e cabo lying — T_anc ≈ 0."""
    r = _result(grounded=200.0, suspended=300.0, anchor_tension=0.0, X=400)
    pt = classify_profile_type(r, [_seg()], SeabedConfig(slope_rad=0.0))
    assert pt == ProfileType.PT_3


def test_PT_3_T_anchor_ruido_numerico_clampado_a_zero():
    """T_anc < 1.0 N (= 0.1 kgf, ruído numérico) classifica como PT_3."""
    r = _result(grounded=200.0, suspended=300.0, anchor_tension=0.5, X=400)
    pt = classify_profile_type(r, [_seg()], SeabedConfig(slope_rad=0.0))
    assert pt == ProfileType.PT_3


# ─── PT_6: vertical (X ≈ 0) ────────────────────────────────────────


def test_PT_6_linha_vertical_X_zero():
    r = _result(grounded=0.0, suspended=500.0, X=0.0001)  # X muito pequeno
    pt = classify_profile_type(r, [_seg()])
    assert pt == ProfileType.PT_6


# ─── PT_7: touchdown em seabed inclinado ───────────────────────────


def test_PT_7_touchdown_com_slope():
    r = _result(grounded=200.0, suspended=300.0, anchor_tension=15_000, X=400)
    import math
    pt = classify_profile_type(
        r, [_seg()], SeabedConfig(slope_rad=math.radians(5)),
    )
    assert pt == ProfileType.PT_7


def test_PT_7_slope_negativo_tambem_e_PT_7():
    r = _result(grounded=200.0, suspended=300.0, anchor_tension=15_000, X=400)
    import math
    pt = classify_profile_type(
        r, [_seg()], SeabedConfig(slope_rad=math.radians(-3)),
    )
    assert pt == ProfileType.PT_7


# ─── PT_8: laid line em rampa ──────────────────────────────────────


def test_PT_8_laid_em_rampa():
    r = _result(grounded=500.0, suspended=0.0, anchor_tension=5_000, X=500)
    import math
    pt = classify_profile_type(
        r, [_seg()], SeabedConfig(slope_rad=math.radians(8)),
    )
    assert pt == ProfileType.PT_8


# ─── PTs reservados nunca são retornados pelo classifier MVP v1 ─────


def test_PT_4_5_nunca_retornado_no_MVP_v1():
    """PT_4 (boiante) e PT_5 (U-shape slack) reservados — classifier
    nunca atinge esses casos no MVP v1.

    Sanity: chamar com vários casos típicos e confirmar que nunca
    cai em PT_4 ou PT_5.
    """
    cases = [
        _result(grounded=0, suspended=500, X=400),    # PT_1
        _result(grounded=200, suspended=300, X=400),  # PT_2 ou PT_3
        _result(grounded=500, suspended=0, X=500),    # PT_0
    ]
    for r in cases:
        pt = classify_profile_type(r, [_seg()])
        assert pt not in (ProfileType.PT_4, ProfileType.PT_5)


# ─── Tolerâncias (boundary cases) ──────────────────────────────────


def test_grounded_minusculo_classifica_como_zero():
    """L_g = 1e-5 m em linha de 500m — < 1e-4 × 500 = 0.05m, é zero."""
    r = _result(grounded=1e-5, suspended=500.0, X=400)
    pt = classify_profile_type(r, [_seg()])
    assert pt == ProfileType.PT_1  # tratado como fully suspended


def test_grounded_relevante_classifica_como_touchdown():
    """L_g = 1m em linha de 500m — claramente touchdown."""
    r = _result(grounded=1.0, suspended=499.0, X=400)
    pt = classify_profile_type(r, [_seg()], SeabedConfig(slope_rad=0.0))
    assert pt in (ProfileType.PT_2, ProfileType.PT_3)


def test_classifier_e_funcao_pura_idempotente():
    """Múltiplas chamadas com mesmos args dão mesmo resultado."""
    r = _result(grounded=200, suspended=300, X=400)
    seg = [_seg()]
    pt1 = classify_profile_type(r, seg)
    pt2 = classify_profile_type(r, seg)
    assert pt1 == pt2
