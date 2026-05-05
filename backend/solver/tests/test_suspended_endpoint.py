"""
Testes do módulo `suspended_endpoint.py` (Fase 7 / Q1+Q3).

Cobre:
  - BC-UP-01..05 cenários (smoke do solver puro, sem regressão MoorPy
    — esta vem em test_uplift_moorpy.py).
  - Translação de coordenadas para frame físico.
  - Validações de domínio (defesa em profundidade pós-Pydantic).
  - Equilíbrio físico: T_anchor = T_fl − w·h_drop em catenária livre
    (relação fundamental da catenária — vertical na âncora ≠ vertical
    no fairlead pelo peso suspenso entre os dois pontos).
"""
from __future__ import annotations

import pytest

from backend.solver.suspended_endpoint import solve_suspended_endpoint
from backend.solver.types import (
    BoundaryConditions,
    ConvergenceStatus,
    LineSegment,
    SeabedConfig,
    SolutionMode,
)


def _seg(L: float = 500.0, w: float = 200.0, EA: float = 3.4e7) -> LineSegment:
    return LineSegment(length=L, w=w, EA=EA, MBL=3.78e6)


def _bc_uplift(h: float, endpoint_depth: float, T_fl: float = 850_000.0) -> BoundaryConditions:
    return BoundaryConditions(
        h=h, mode=SolutionMode.TENSION, input_value=T_fl,
        endpoint_grounded=False, endpoint_depth=endpoint_depth,
    )


# ─── BC-UP-01..05 smokes (sem comparação MoorPy ainda) ──────────────


def test_BC_UP_01_moderado_50m_uplift_converge():
    """h=300, endpoint_depth=250 (uplift=50m), T_fl=850 kN."""
    r = solve_suspended_endpoint(_seg(), _bc_uplift(300.0, 250.0))
    assert r.status == ConvergenceStatus.CONVERGED
    assert r.endpoint_depth == 250.0
    assert r.water_depth == 300.0
    assert r.total_grounded_length == 0.0  # fully suspended


def test_BC_UP_02_severo_100m_uplift_converge():
    """h=300, endpoint_depth=200 (uplift=100m)."""
    r = solve_suspended_endpoint(_seg(), _bc_uplift(300.0, 200.0))
    assert r.status == ConvergenceStatus.CONVERGED
    assert r.total_grounded_length == 0.0


def test_BC_UP_03_quase_grounded_5m_uplift_converge():
    """h=300, endpoint_depth=295 (uplift=5m). Próximo ao limite grounded."""
    r = solve_suspended_endpoint(_seg(), _bc_uplift(300.0, 295.0))
    assert r.status == ConvergenceStatus.CONVERGED
    # uplift desprezível — solver converge mas pode disparar D017 (medium)
    # quando integrado ao facade. Aqui teste só do módulo puro.


def test_BC_UP_04_proximo_surface_anchor_alto_converge():
    """
    h=250, endpoint_depth=50 (uplift=200m). Anchor a 50m da superfície.
    Drop pequeno (50m) força catenária quase taut com s_a > 0 → linha
    curta (L=200m) e T_fl moderado convergem. Parâmetros finais para
    BC-UP-04 vêm do baseline MoorPy (Commit 4); aqui é smoke do regime.
    """
    r = solve_suspended_endpoint(
        _seg(L=200.0), _bc_uplift(h=250.0, endpoint_depth=50.0, T_fl=200_000.0),
    )
    assert r.status == ConvergenceStatus.CONVERGED


def test_BC_UP_05_taut_uplift_EA_grande():
    """EA grande + uplift moderado — caso numericamente difícil."""
    seg = LineSegment(length=400.0, w=200.0, EA=1.0e9, MBL=3.78e6)
    r = solve_suspended_endpoint(seg, _bc_uplift(300.0, 200.0, T_fl=950_000.0))
    assert r.status == ConvergenceStatus.CONVERGED
    # EA grande → elongation pequeno
    assert r.elongation < 5.0


# ─── Equilíbrio físico ──────────────────────────────────────────────


def test_T_anchor_iguais_T_fl_menos_w_h_drop():
    """
    Catenária livre: V_fl - V_anchor = w·L (peso da linha suspensa).
    Em fully-suspended sem touchdown, a relação T_fl² - T_anchor² é
    aproximadamente proporcional a (w·h_drop)² para anchor não
    elevado tradicional, mas em uplift (V_anchor > 0) a relação
    é diferente.

    Verificação: H é constante ao longo da linha (não há atrito).
    Componentes verticais: V_fl = sqrt(T_fl² - H²); V_anchor =
    sqrt(T_anchor² - H²); V_fl - V_anchor = w · L_stretched (peso
    suspenso). Por isto T_anchor < T_fl em uplift fully suspended.
    """
    import math
    h, ed, T_fl = 300.0, 250.0, 850_000.0
    seg = _seg()
    r = solve_suspended_endpoint(seg, _bc_uplift(h, ed, T_fl=T_fl))

    # Verificação: V_fl - V_anchor ≈ w · L_stretched.
    H = r.H
    V_fl = math.sqrt(r.fairlead_tension ** 2 - H ** 2)
    V_anchor = math.sqrt(r.anchor_tension ** 2 - H ** 2) if r.anchor_tension > H else 0.0
    expected_w_L = seg.w * r.stretched_length
    rel_err = abs((V_fl - V_anchor) - expected_w_L) / expected_w_L
    assert rel_err < 1e-2, (
        f"V_fl - V_anchor = {V_fl - V_anchor:.0f}, esperado w·L = {expected_w_L:.0f}, "
        f"erro relativo = {rel_err*100:.3f}%"
    )


# ─── Translação de coordenadas para frame físico ────────────────────


def test_coordenadas_y_anchor_em_minus_endpoint_depth():
    """coords_y[0] (anchor) = -endpoint_depth no frame físico."""
    r = solve_suspended_endpoint(_seg(), _bc_uplift(300.0, 250.0))
    assert abs(r.coords_y[0] - (-250.0)) < 1e-6


def test_coordenadas_y_fairlead_em_minus_startpoint_depth():
    """coords_y[-1] (fairlead) = -startpoint_depth (default 0) no frame físico."""
    r = solve_suspended_endpoint(_seg(), _bc_uplift(300.0, 250.0))
    assert abs(r.coords_y[-1] - 0.0) < 1e-6  # startpoint_depth=0 default


def test_translacao_com_startpoint_depth_nao_zero():
    """Fairlead submerso + uplift: ambos transladados consistentemente."""
    bc = BoundaryConditions(
        h=300.0, mode=SolutionMode.TENSION, input_value=850_000.0,
        endpoint_grounded=False, endpoint_depth=250.0,
        startpoint_depth=20.0,  # fairlead submerso 20m
    )
    r = solve_suspended_endpoint(_seg(), bc)
    assert r.status == ConvergenceStatus.CONVERGED
    assert abs(r.coords_y[0] - (-250.0)) < 1e-6  # anchor
    assert abs(r.coords_y[-1] - (-20.0)) < 1e-6  # fairlead


# ─── Validações de domínio (defesa em profundidade) ─────────────────


def test_chamado_com_endpoint_grounded_True_retorna_invalid():
    """Defesa: caller não deveria chamar com grounded=True; retorna INVALID."""
    bc = BoundaryConditions(
        h=300.0, mode=SolutionMode.TENSION, input_value=850_000.0,
        endpoint_grounded=True,
    )
    r = solve_suspended_endpoint(_seg(), bc)
    assert r.status == ConvergenceStatus.INVALID_CASE
    assert "endpoint_grounded=False" in r.message


def test_T_fl_insuficiente_para_sustentar_h_drop():
    """T_fl ≤ w·h_drop é geometria impossível mesmo em uplift."""
    bc = BoundaryConditions(
        h=300.0, mode=SolutionMode.TENSION,
        input_value=10_000.0,  # ridículo
        endpoint_grounded=False, endpoint_depth=250.0,
    )
    r = solve_suspended_endpoint(_seg(), bc)
    assert r.status == ConvergenceStatus.INVALID_CASE
    assert "linha não sustenta" in r.message.lower() or "≤ w·h_drop" in r.message.lower()


# ─── Mode RANGE ─────────────────────────────────────────────────────


def test_modo_range_uplift_converge():
    """Modo RANGE com anchor elevado também resolve."""
    bc = BoundaryConditions(
        h=300.0, mode=SolutionMode.RANGE, input_value=400.0,
        endpoint_grounded=False, endpoint_depth=250.0,
    )
    r = solve_suspended_endpoint(_seg(), bc)
    assert r.status == ConvergenceStatus.CONVERGED
    # Range output ≈ input (X_total ≈ 400)
    assert abs(r.total_horz_distance - 400.0) / 400.0 < 1e-2


# ─── Diagnostics tag — water_depth vs endpoint_depth ────────────────


def test_solverresult_distingue_water_depth_de_endpoint_depth():
    """Em uplift, water_depth ≠ endpoint_depth (este último < primeiro)."""
    r = solve_suspended_endpoint(_seg(), _bc_uplift(300.0, 250.0))
    assert r.water_depth == 300.0
    assert r.endpoint_depth == 250.0
    assert r.water_depth > r.endpoint_depth  # uplift = 50m
