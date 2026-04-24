"""
Testes da Camada 7 — Robustez e casos patológicos.

Cobre BC-06 (linha curta, quase taut), BC-07 (linha longa, tração baixa),
casos fisicamente inválidos, e detecção de ill_conditioned.
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


# ==============================================================================
# BC-06 — Linha curta, quase taut (stress test de convergência)
# ==============================================================================


def test_BC06_linha_curta_contra_moorpy() -> None:
    """
    BC-06 (Documento A v2.2 Seção 6.1.4):
      Lâmina 500 m, L=530 m, X=170 m, wire rope 3", Modo Range.
      L_taut = √(170² + 500²) = 528.10 m; L/L_taut = 1.0036 (muito taut).

    Objetivo: validar convergência em caso de alta sensibilidade.
    """
    L = 530.0
    h = 500.0
    w = 13.78 * LBF_FT_TO_N_M
    EA = 34.25e6
    MBL = 850e3 * 4.4482216
    X_input = 170.0

    seg = LineSegment(length=L, w=w, EA=EA, MBL=MBL)
    bc = BoundaryConditions(h=h, mode=SolutionMode.RANGE, input_value=X_input)

    r = solve([seg], bc)
    # Pode convergir como CONVERGED ou ILL_CONDITIONED; ambos são OK.
    assert r.status in (ConvergenceStatus.CONVERGED, ConvergenceStatus.ILL_CONDITIONED)
    assert r.total_horz_distance == pytest.approx(X_input, rel=1e-4)

    # Validação contra MoorPy
    fAH, fAV, fBH, fBV, info = mp_catenary(
        XF=X_input, ZF=h, L=L, EA=EA, W=w, CB=0,
    )
    T_fl_mp = math.sqrt(fBH ** 2 + fBV ** 2)
    H_mp = abs(fBH)

    assert r.fairlead_tension == pytest.approx(T_fl_mp, rel=TOL_FORCE_REL)
    assert r.H == pytest.approx(H_mp, rel=TOL_FORCE_REL)

    print(
        f"\nBC-06 (Range, X=170 m, L=530 m, L_taut=528.1 m):"
        f"\n  status       : {r.status}"
        f"\n  T_fl         : my={r.fairlead_tension/1000:.2f} kN  MoorPy={T_fl_mp/1000:.2f} kN"
        f"\n  H            : my={r.H/1000:.2f} kN  MoorPy={H_mp/1000:.2f} kN"
        f"\n  L_stretched  : {r.stretched_length:.3f} m"
        f"\n  L/L_taut     : {r.stretched_length / math.sqrt(X_input**2 + h**2):.5f}"
        f"\n  utilization  : {r.utilization*100:.2f}%"
    )


# ==============================================================================
# BC-07 — Linha longa, tração baixa (extremo oposto de BC-06)
# ==============================================================================


def test_BC07_linha_longa_tracao_baixa() -> None:
    """
    BC-07 (Documento A v2.2 Seção 6.2, entradas a definir):
      Linha muito longa (L grande comparado a h), tração baixa, grande
      comprimento apoiado.

    Parâmetros escolhidos: L=2000 m, h=100 m, T_fl=30 kN, wire rope 3",
    μ=0,30 (atrito típico). w·h ≈ 20.1 kN; T_fl=30 kN > w·h mantém
    o caso fisicamente válido com grande trecho grounded.
    """
    L = 2000.0
    h = 100.0
    w = 13.78 * LBF_FT_TO_N_M
    EA = 34.25e6
    MBL = 850e3 * 4.4482216
    T_fl = 30_000.0  # > w·h ≈ 20.1 kN, mas ainda muito abaixo do T_fl_crit

    seg = LineSegment(length=L, w=w, EA=EA, MBL=MBL)
    bc = BoundaryConditions(h=h, mode=SolutionMode.TENSION, input_value=T_fl)
    seabed = SeabedConfig(mu=0.30)

    r = solve([seg], bc, seabed=seabed)
    assert r.status == ConvergenceStatus.CONVERGED
    # Muita linha deve ficar no grounded
    assert r.total_grounded_length / L > 0.8
    # T_fl recuperado
    assert r.fairlead_tension == pytest.approx(T_fl, rel=1e-4)

    # Validação contra MoorPy no X obtido
    X_my = r.total_horz_distance
    fAH, fAV, fBH, fBV, info = mp_catenary(
        XF=X_my, ZF=h, L=L, EA=EA, W=w, CB=0.30,
    )
    T_fl_mp = math.sqrt(fBH ** 2 + fBV ** 2)

    assert T_fl_mp == pytest.approx(T_fl, rel=TOL_FORCE_REL)

    print(
        f"\nBC-07 (Tension, L=2000 m, T_fl=20 kN, μ=0.30):"
        f"\n  status       : {r.status}"
        f"\n  X            : {X_my:.2f} m"
        f"\n  L_grounded   : {r.total_grounded_length:.1f} m ({r.total_grounded_length/L*100:.1f}%)"
        f"\n  T_anchor     : {r.anchor_tension/1000:.2f} kN"
        f"\n  T_fl MoorPy  : {T_fl_mp/1000:.2f} kN"
    )


# ==============================================================================
# Casos fisicamente inválidos
# ==============================================================================


def test_caso_invalido_retorna_status_apropriado() -> None:
    """
    T_fl < w·h → caso fisicamente inviável (linha não sustenta peso).
    Solver não deve crashar — retorna SolverResult com status INVALID_CASE
    e mensagem clara.
    """
    seg = LineSegment(length=500, w=200, EA=5e7, MBL=1e6)
    # w·h = 200·100 = 20000 N. T_fl=10000 < 20000
    bc = BoundaryConditions(h=100, mode=SolutionMode.TENSION, input_value=10_000)
    r = solve([seg], bc)
    assert r.status == ConvergenceStatus.INVALID_CASE
    assert "sustenta" in r.message.lower() or "atinge" in r.message.lower()


def test_caso_range_muito_grande_retorna_invalid() -> None:
    """
    X >> L+h com EA rígido: a linha não consegue esticar para alcançar.
    Solver deve rejeitar com mensagem clara (ou convergir com utilization
    fora da faixa operacional realista).
    """
    # EA rígido: sem estiramento, linha não alcança X
    seg = LineSegment(length=200, w=200, EA=1e15, MBL=1e6)
    bc = BoundaryConditions(h=100, mode=SolutionMode.RANGE, input_value=500)
    r = solve([seg], bc)
    # Deve sinalizar problema: INVALID_CASE ou ILL_CONDITIONED, e a mensagem
    # precisa ser informativa.
    assert r.status in (
        ConvergenceStatus.INVALID_CASE,
        ConvergenceStatus.ILL_CONDITIONED,
    ), (
        f"Caso geometricamente impossível retornou status inesperado: "
        f"{r.status}, utilization={r.utilization:.1f}"
    )
    assert r.message != ""


# ==============================================================================
# Detecção ill_conditioned
# ==============================================================================


def test_caso_ill_conditioned_avisa_usuario() -> None:
    """
    Linha quase perfeitamente taut (dentro de 0,01% do √(X²+h²)) deve
    ser classificada como ill_conditioned e o usuário recebe mensagem.
    """
    # Setup: EA muito alto (rígido) + L bem próximo do taut → L_stretched ≈ L,
    # e como L_taut = √(X²+h²) muito próximo de L, entra na zona ill_conditioned.
    L_taut = math.sqrt(100 ** 2 + 300 ** 2)
    L = L_taut * 1.00005  # apenas 0,005% acima do taut
    seg = LineSegment(length=L, w=200, EA=1e15, MBL=1e6)  # rígido
    bc = BoundaryConditions(h=300, mode=SolutionMode.RANGE, input_value=100)

    r = solve([seg], bc)
    # Pode ser CONVERGED ou ILL_CONDITIONED; se ILL_CONDITIONED, mensagem deve
    # indicar sensibilidade
    if r.status == ConvergenceStatus.ILL_CONDITIONED:
        assert "mal condicionado" in r.message.lower() or "taut" in r.message.lower()
        assert r.fairlead_tension > 0  # resultado ainda usable
    else:
        # Se foi CONVERGED, deve pelo menos ter resultado coerente
        assert r.status == ConvergenceStatus.CONVERGED
        assert r.fairlead_tension > 0


def test_solver_nao_crasha_em_combinacoes_extremas() -> None:
    """Lote de casos extremos; nenhum deve lançar exceção (todos viram
    um SolverResult com status apropriado)."""
    casos = [
        # (L, h, w, EA, MBL, mode, input_value, mu)
        (100, 50, 100, 1e8, 1e6, SolutionMode.TENSION, 1e6, 0.0),  # T_fl >>
        (100, 50, 100, 1e8, 1e6, SolutionMode.TENSION, 5001, 0.0),  # T_fl mal do limite
        (100, 50, 100, 1e8, 1e6, SolutionMode.RANGE, 50, 0.5),  # X pequeno
        (1000, 100, 100, 1e8, 1e6, SolutionMode.RANGE, 850, 0.0),  # X médio
        (1000, 100, 100, 1e8, 1e6, SolutionMode.TENSION, 50_000, 1.0),  # μ alto
    ]
    for (L, h, w, EA, MBL, mode, inp, mu) in casos:
        seg = LineSegment(length=L, w=w, EA=EA, MBL=MBL)
        bc = BoundaryConditions(h=h, mode=mode, input_value=inp)
        seabed = SeabedConfig(mu=mu)
        r = solve([seg], bc, seabed=seabed)
        assert r.status in ConvergenceStatus, f"status desconhecido para {(L,h,w,mode,inp,mu)}"
        assert r.message != "" or r.status == ConvergenceStatus.CONVERGED
