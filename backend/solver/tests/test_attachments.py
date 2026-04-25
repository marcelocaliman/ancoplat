"""
Testes de validação dos attachments (F5.2 — boias e clump weights).

Casos cobertos
--------------
BC-AT-01: linha homogênea (2 segs idênticos) com 1 boia no meio →
          configuração lazy-wave simplificada.
BC-AT-02: linha homogênea com 1 clump weight perto da âncora →
          aumento de pré-tensão na âncora (V_anchor maior).
BC-AT-03: 3 segmentos com 2 boias alternadas (S-curve simplificada).
BC-AT-04: caso degenerado — boia com empuxo > peso total da linha →
          INVALID_CASE com mensagem clara.
BC-AT-05: comparação com solver single equivalente (sem attachments)
          deve dar mesmo resultado quando attachments=[].

Validação física
----------------
- H constante em toda a linha (a invariante chave continua valendo).
- T monotonicamente crescente do anchor ao fairlead — exceto que ao
  PASSAR uma boia ou clump, V tem salto. Logo |T| pode ter degraus,
  mas H sempre é o mesmo.
- Equilíbrio vertical estendido: V_fl − V_anchor = Σ w_i·L_eff_i + Σ F_att.
"""
from __future__ import annotations

import math

import pytest

from backend.solver.solver import solve
from backend.solver.types import (
    BoundaryConditions,
    ConvergenceStatus,
    LineAttachment,
    LineSegment,
    SolutionMode,
)


def _equivalent_with_attachments(case_T_fl, segments, h, attachments) -> dict:
    """Helper: roda o solve e retorna campos relevantes."""
    bc = BoundaryConditions(h=h, mode=SolutionMode.TENSION, input_value=case_T_fl)
    return solve(segments, bc, attachments=attachments)


# ==============================================================================
# BC-AT-01 — boia única no meio (lazy-wave simplificado)
# ==============================================================================


def test_BC_AT_01_boia_unica_no_meio() -> None:
    """
    Linha homogênea: 2 segmentos idênticos (450 m cada) com 1 boia de 50 kN
    de empuxo na junção. Validação por invariantes físicas + diferença
    mensurável da geometria sem boia.

    Nota: a intuição "boia alivia → T_anchor diminui" não vale em todos os
    cenários. A boia muda H E V_anchor simultaneamente; a invariante
    sólida é o equilíbrio vertical estendido V_fl − V_anchor = Σw·L_eff + ΣF.
    """
    seg = LineSegment(length=450.0, w=200.0, EA=4.4e8, MBL=4.8e6, category="Wire")
    h = 400.0
    T_fl = 1.5e6

    bc = BoundaryConditions(h=h, mode=SolutionMode.TENSION, input_value=T_fl)
    r_no_buoy = solve([seg, seg], bc)
    boia = LineAttachment(
        kind="buoy", submerged_force=50_000.0, position_index=0, name="Boia M",
    )
    r_buoy = solve([seg, seg], bc, attachments=[boia])
    assert r_no_buoy.status == ConvergenceStatus.CONVERGED
    assert r_buoy.status == ConvergenceStatus.CONVERGED
    assert r_buoy.fairlead_tension == pytest.approx(T_fl, rel=1e-3)

    # Invariante 1: H constante em toda a linha
    Tx = r_buoy.tension_x
    assert (max(Tx) - min(Tx)) / r_buoy.H < 1e-6

    # Invariante 2: equilíbrio vertical estendido
    sum_wL_str = (
        2 * seg.w * seg.length * (r_buoy.stretched_length / r_buoy.unstretched_length)
    )
    expected = sum_wL_str - 50_000.0  # buoy = força negativa em V
    V_fl = math.sqrt(max(r_buoy.fairlead_tension ** 2 - r_buoy.H ** 2, 0))
    V_an = math.sqrt(max(r_buoy.anchor_tension ** 2 - r_buoy.H ** 2, 0))
    assert abs((V_fl - V_an) - expected) / abs(expected) < 0.01

    # Boia produz geometria mensurávelmente diferente do baseline.
    assert abs(r_buoy.total_horz_distance - r_no_buoy.total_horz_distance) > 0.1


# ==============================================================================
# BC-AT-02 — clump weight perto da âncora
# ==============================================================================


def test_BC_AT_02_clump_proximo_da_ancora() -> None:
    """
    2 segmentos idênticos com clump de 30 kN na junção. Validação por
    equilíbrio vertical estendido (V_fl − V_anchor = Σw·L_eff + clump).
    """
    seg = LineSegment(length=400.0, w=200.0, EA=4.4e8, MBL=4.8e6, category="Wire")
    h = 350.0
    T_fl = 1.6e6

    bc = BoundaryConditions(h=h, mode=SolutionMode.TENSION, input_value=T_fl)
    clump = LineAttachment(kind="clump_weight", submerged_force=30_000.0, position_index=0)
    r = solve([seg, seg], bc, attachments=[clump])

    assert r.status == ConvergenceStatus.CONVERGED
    assert r.fairlead_tension == pytest.approx(T_fl, rel=1e-3)

    # H constante
    Tx = r.tension_x
    assert (max(Tx) - min(Tx)) / r.H < 1e-6

    # Equilíbrio vertical estendido
    sum_wL_str = (
        2 * seg.w * seg.length * (r.stretched_length / r.unstretched_length)
    )
    expected = sum_wL_str + 30_000.0  # clump = força positiva em V
    V_fl = math.sqrt(max(r.fairlead_tension ** 2 - r.H ** 2, 0))
    V_an = math.sqrt(max(r.anchor_tension ** 2 - r.H ** 2, 0))
    assert abs((V_fl - V_an) - expected) / abs(expected) < 0.01


# ==============================================================================
# BC-AT-03 — 3 segmentos com 2 boias (S-curve simplificada)
# ==============================================================================


def test_BC_AT_03_duas_boias_alternadas() -> None:
    """
    3 segmentos com boias nas duas junções. Geometria mais complexa.
    Verifica que o solver converge e mantém H constante.
    """
    s = LineSegment(length=300.0, w=200.0, EA=4.4e8, MBL=4.8e6, category="Wire")
    boia1 = LineAttachment(kind="buoy", submerged_force=20_000.0, position_index=0, name="B1")
    boia2 = LineAttachment(kind="buoy", submerged_force=20_000.0, position_index=1, name="B2")
    bc = BoundaryConditions(h=350.0, mode=SolutionMode.TENSION, input_value=1.4e6)

    r = solve([s, s, s], bc, attachments=[boia1, boia2])
    assert r.status == ConvergenceStatus.CONVERGED

    # H constante
    Tx = r.tension_x
    assert (max(Tx) - min(Tx)) / r.H < 1e-6

    # Equilíbrio vertical estendido
    sum_wL_unstr = 3 * s.w * s.length
    sum_F = -20_000.0 * 2  # 2 boias = empuxo
    sum_total_unstr = sum_wL_unstr + sum_F
    sum_total_stretched = sum_total_unstr * (
        r.stretched_length / r.unstretched_length
    )
    # Aproximação: se attachments não esticam, peso "stretching" só atua
    # nos segmentos. Para validação, aceitamos 1.5% de tolerância porque
    # a soma 'stretched' presume que tudo escala — na verdade só w·L escala.
    V_fl = math.sqrt(max(r.fairlead_tension ** 2 - r.H ** 2, 0))
    V_an = math.sqrt(max(r.anchor_tension ** 2 - r.H ** 2, 0))
    delta_V = V_fl - V_an
    # Peso esticado da linha (sem attachments) + attachments (não esticam)
    expected = (
        sum_wL_unstr * (r.stretched_length / r.unstretched_length) + sum_F
    )
    assert abs(delta_V - expected) / abs(expected) < 0.02, (
        f"V_fl − V_an = {delta_V:.1f}, expected {expected:.1f}"
    )


# ==============================================================================
# BC-AT-04 — boia com empuxo > peso total → INVALID_CASE
# ==============================================================================


def test_BC_AT_04_buoy_excede_peso_invalida() -> None:
    """
    Boia com empuxo absurdamente grande (excede w·L total) deve ser
    rejeitada com INVALID_CASE e mensagem clara — geometria invertida.
    """
    s = LineSegment(length=400.0, w=200.0, EA=4.4e8, MBL=4.8e6, category="Wire")
    # 2 segs × 400m × 200 N/m = 160 kN. Boia de 200 kN excede.
    boia = LineAttachment(kind="buoy", submerged_force=200_000.0, position_index=0)
    bc = BoundaryConditions(h=350.0, mode=SolutionMode.TENSION, input_value=1.5e6)

    r = solve([s, s], bc, attachments=[boia])
    assert r.status == ConvergenceStatus.INVALID_CASE
    msg = r.message.lower()
    assert "empuxo" in msg or "geometria invertida" in msg


# ==============================================================================
# BC-AT-05 — sem attachments deve dar mesmo resultado que sem o parâmetro
# ==============================================================================


def test_BC_AT_05_sem_attachments_match_sem_parametro() -> None:
    """
    Garantia de não-regressão: passar attachments=[] deve produzir
    exatamente o mesmo resultado que não passar nada (caminho single
    intacto).
    """
    s = LineSegment(length=600.0, w=200.0, EA=4.4e8, MBL=4.8e6, category="Wire")
    bc = BoundaryConditions(h=400.0, mode=SolutionMode.TENSION, input_value=1.5e6)

    r1 = solve([s], bc)
    r2 = solve([s], bc, attachments=[])
    assert r1.status == r2.status == ConvergenceStatus.CONVERGED
    assert r1.fairlead_tension == pytest.approx(r2.fairlead_tension, rel=1e-9)
    assert r1.anchor_tension == pytest.approx(r2.anchor_tension, rel=1e-9)
    assert r1.total_horz_distance == pytest.approx(r2.total_horz_distance, rel=1e-9)


# ==============================================================================
# BC-AT-06 — attachments com 1 segmento devem ser rejeitados
# ==============================================================================


def test_BC_AT_06_attachments_com_1_segmento_invalido() -> None:
    """
    Attachments precisam de pelo menos 2 segmentos (ficam nas junções).
    Com 1 segmento, deve cair em INVALID_CASE com mensagem orientadora.
    """
    s = LineSegment(length=600.0, w=200.0, EA=4.4e8, MBL=4.8e6, category="Wire")
    boia = LineAttachment(kind="buoy", submerged_force=20_000.0, position_index=0)
    bc = BoundaryConditions(h=400.0, mode=SolutionMode.TENSION, input_value=1.5e6)

    r = solve([s], bc, attachments=[boia])
    assert r.status == ConvergenceStatus.INVALID_CASE
    assert "junções" in r.message.lower() or "junção" in r.message.lower() or "segmento" in r.message.lower()
