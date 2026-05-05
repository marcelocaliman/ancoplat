"""
BC-EA-01 — Toggle EA QMoor/GMoor por segmento (Fase 1 / A1.4+B4).

Verifica que mudar entre EA estático (`qmoor_ea`) e EA dinâmico
(`gmoor_ea` ≡ termo α do modelo NREL/MoorPy) muda a elongação na
proporção esperada.

Modelo físico (CLAUDE.md, Fase 0 / B0.2):
    EA_estatico  = EA_MBL × MBL                   [QMoor — default]
    EA_dinamico  = EAd  × MBL  +  EAd_Lm × T_mean [GMoor — opcional]
                 = α + β·T_mean
β (`ea_dynamic_beta`) NÃO é implementado em v1.0 — solver usa α
constante. BC-EA-01 testa a substituição de EA per-segmento (A1.4)
e a propagação correta para o solver.
"""
from __future__ import annotations

import pytest

from backend.solver.solver import solve
from backend.solver.types import (
    BoundaryConditions,
    LineSegment,
    SeabedConfig,
    SolutionMode,
)


def test_BC_EA_01_gmoor_ratio_aumenta_elongation_proporcionalmente():
    """
    Poliéster: gmoor_ea ≈ 12× qmoor_ea (CLAUDE.md, observação do
    catálogo legacy_qmoor). Para mesma carga, segmento com EA 12× maior
    deve ter elongação 12× MENOR (Hooke: ε = T_mean / EA).
    """
    L = 2000.0
    h = 1500.0  # taut o suficiente p/ exercitar elasticidade
    w = 50.0    # poliéster (peso submerso baixo)
    MBL = 5e6
    T_fl = 2_500_000.0  # alto, induz strain mensurável
    qmoor_ea = 1e8
    gmoor_ea = 12 * qmoor_ea

    bc = BoundaryConditions(
        h=h, mode=SolutionMode.TENSION, input_value=T_fl,
    )
    sb = SeabedConfig(mu=0.0)

    seg_q = LineSegment(
        length=L, w=w, EA=qmoor_ea, MBL=MBL, ea_source="qmoor",
    )
    seg_g = LineSegment(
        length=L, w=w, EA=gmoor_ea, MBL=MBL, ea_source="gmoor",
    )

    r_q = solve([seg_q], bc, sb)
    r_g = solve([seg_g], bc, sb)

    # Aceita CONVERGED ou ILL_CONDITIONED (caso taut)
    assert r_q.status.value in ("converged", "ill_conditioned"), r_q.message
    assert r_g.status.value in ("converged", "ill_conditioned"), r_g.message

    # Para EA muito alto (gmoor), elongation tende a zero. Para qmoor,
    # elongation é mensurável. Razão deve ser ~12× (com tolerância
    # generosa porque T_mean é levemente diferente nos dois casos por
    # mudança de geometria).
    assert r_q.elongation > 0
    assert r_g.elongation > 0
    ratio = r_q.elongation / r_g.elongation
    assert 10.0 < ratio < 14.0, (
        f"elongation_qmoor / elongation_gmoor = {ratio:.2f}, "
        f"esperado ~12× (entre 10 e 14)"
    )


def test_BC_EA_01_ea_source_metadata_persistida_no_segmento():
    """ea_source não afeta o solver em v1.0 mas é persistido no schema
    (rastreabilidade). Confirmação de que LineSegment retém o valor."""
    seg_q = LineSegment(length=500, w=200, EA=1e8, MBL=5e6, ea_source="qmoor")
    seg_g = LineSegment(length=500, w=200, EA=1e8, MBL=5e6, ea_source="gmoor")
    assert seg_q.ea_source == "qmoor"
    assert seg_g.ea_source == "gmoor"


def test_BC_EA_01_ea_dynamic_beta_reservado_nao_afeta_solver_v1():
    """β (ea_dynamic_beta) é campo reservado em v1.0. Solver NÃO usa
    ainda — modelo simplificado a α constante. Confirmação de que
    fornecer β não muda resultado."""
    L = 1000.0
    bc = BoundaryConditions(
        h=500.0, mode=SolutionMode.TENSION, input_value=1_000_000.0,
    )
    sb = SeabedConfig()

    seg_no_beta = LineSegment(
        length=L, w=100, EA=1.2e9, MBL=5e6,
        ea_source="gmoor", ea_dynamic_beta=None,
    )
    seg_with_beta = LineSegment(
        length=L, w=100, EA=1.2e9, MBL=5e6,
        ea_source="gmoor", ea_dynamic_beta=2_500_000.0,
    )

    r_no = solve([seg_no_beta], bc, sb)
    r_with = solve([seg_with_beta], bc, sb)

    # β não usado em v1 → resultados idênticos
    assert r_no.fairlead_tension == pytest.approx(r_with.fairlead_tension, rel=1e-12)
    assert r_no.elongation == pytest.approx(r_with.elongation, rel=1e-12)
    assert r_no.total_horz_distance == pytest.approx(
        r_with.total_horz_distance, rel=1e-12,
    )
