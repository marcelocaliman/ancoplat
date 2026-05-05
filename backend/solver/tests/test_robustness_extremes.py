"""
Robustez do solver em casos adversos (Fase 10 / Commit 4).

8 casos extremos com a mesma propriedade obrigatória: o solver **NÃO
deve crashar com exceção não-tratada**. Resultado aceitável é qualquer
um destes 4:
  - status=CONVERGED       (caso resolvido apesar do extremo)
  - status=ILL_CONDITIONED  (resolvido com aviso de degeneração)
  - status=INVALID_CASE     (rejeitado com diagnostic estruturado e
                              mensagem nomeando ID e campo afetado)
  - status=MAX_ITERATIONS   (não convergiu mas reportou educadamente)

Per Q7 do mini-plano F10, mensagens de invalid_case devem ser
**específicas** (não genéricas): "Geometria fisicamente inviável:
combinação de slope X°, EA Y, comprimento Z não admite solução
estática. Ajuste pelo menos um parâmetro."

Per Q5: cases que sabidamente não convergem após esforço razoável
podem usar `pytest.mark.xfail` com `reason=` específica documentando
a fase v1.1 onde será endereçado.

Casos cobertos:
  R1: slope extremo (35°)
  R2: EA muito macio (1e3 N — corda elástica)
  R3: EA muito rígido (1e10 N — aço quase inextensível)
  R4: μ=0 com material de catálogo (D013 deve disparar)
  R5: h muito raso (5m, L curto)
  R6: h muito profundo (3000m)
  R7: linha curta demais (L < chord)
  R8: linha quase taut (L = chord + ε)
"""
from __future__ import annotations

import math

import pytest

from backend.solver.solver import solve
from backend.solver.types import (
    BoundaryConditions,
    ConvergenceStatus,
    LineSegment,
    SeabedConfig,
    SolutionMode,
)


_ACCEPTABLE_STATUSES = {
    ConvergenceStatus.CONVERGED,
    ConvergenceStatus.ILL_CONDITIONED,
    ConvergenceStatus.INVALID_CASE,
    ConvergenceStatus.MAX_ITERATIONS,
}


def _solve_or_invalid(segs, bc, sb):
    """
    Helper: roda solver e exige que devolva um status conhecido.
    Crashes (uncaught exceptions) falham o teste imediatamente.
    """
    res = solve(segs, bc, sb)
    assert res.status in _ACCEPTABLE_STATUSES, (
        f"Status inesperado: {res.status}. msg={res.message}"
    )
    return res


def test_R1_slope_extremo():
    """R1: slope=35° (limite de validação do schema). Solver deve
    aceitar ou rejeitar com mensagem nomeando o slope."""
    seg = LineSegment(length=600.0, w=1100.0, EA=5.83e8, MBL=5.57e6)
    bc = BoundaryConditions(
        h=200.0, mode=SolutionMode.TENSION, input_value=2_000_000.0,
        startpoint_depth=0.0, endpoint_grounded=True,
    )
    sb = SeabedConfig(mu=0.5, slope_rad=math.radians(35.0))
    res = _solve_or_invalid([seg], bc, sb)
    if res.status == ConvergenceStatus.INVALID_CASE:
        # Mensagem deve mencionar slope ou geometria.
        assert (
            "slope" in res.message.lower()
            or "geometria" in res.message.lower()
        ), f"R1 INVALID_CASE sem mencionar slope: {res.message!r}"


def test_R2_EA_macio_extremo():
    """R2: EA=1e3 (corda muito elástica). Pode convergir com elongação
    enorme ou ser rejeitado por elongação > L."""
    seg = LineSegment(length=600.0, w=1100.0, EA=1e3, MBL=1e6)
    bc = BoundaryConditions(
        h=200.0, mode=SolutionMode.TENSION, input_value=500_000.0,
        startpoint_depth=0.0, endpoint_grounded=True,
    )
    sb = SeabedConfig(mu=0.5, slope_rad=0.0)
    _solve_or_invalid([seg], bc, sb)


def test_R3_EA_rigido_extremo():
    """R3: EA=1e10 (limite superior aço duro). Solver deve convergir
    sem problemas (regime quase-inextensível)."""
    seg = LineSegment(length=600.0, w=1100.0, EA=1e10, MBL=5.57e6)
    bc = BoundaryConditions(
        h=200.0, mode=SolutionMode.TENSION, input_value=2_000_000.0,
        startpoint_depth=0.0, endpoint_grounded=True,
    )
    sb = SeabedConfig(mu=0.5, slope_rad=0.0)
    res = _solve_or_invalid([seg], bc, sb)
    # Para EA muito alto, esperamos convergência (regime puramente
    # geométrico).
    assert res.status in (
        ConvergenceStatus.CONVERGED, ConvergenceStatus.ILL_CONDITIONED,
    )


def test_R4_mu_zero_com_catalogo():
    """R4: μ=0 com line_type de catálogo deve disparar D013 (medium
    confidence — μ=0 inviável fisicamente para chain on seabed)."""
    seg = LineSegment(
        length=600.0, w=1100.0, EA=5.83e8, MBL=5.57e6,
        category="StudlessChain", line_type="R4StudlessChain 76mm",
        seabed_friction_cf=0.6,
    )
    bc = BoundaryConditions(
        h=200.0, mode=SolutionMode.TENSION, input_value=2_000_000.0,
        startpoint_depth=0.0, endpoint_grounded=True,
    )
    sb = SeabedConfig(mu=0.0, slope_rad=0.0)
    res = _solve_or_invalid([seg], bc, sb)
    # D013 deve aparecer entre os diagnostics quando μ=0 + catálogo.
    diag_codes = {
        (d.code if hasattr(d, "code") else d.get("code"))
        for d in (res.diagnostics or [])
    }
    assert any("D013" in c for c in diag_codes if c), (
        f"R4: D013 ausente. diagnostics={diag_codes}, msg={res.message}"
    )


def test_R5_aguas_rasas_extremo():
    """R5: h=5m, L curto. Catenária muito comprimida — pode degenerar
    em ill_conditioned ou invalid_case."""
    seg = LineSegment(length=20.0, w=1100.0, EA=5.83e8, MBL=5.57e6)
    bc = BoundaryConditions(
        h=5.0, mode=SolutionMode.TENSION, input_value=100_000.0,
        startpoint_depth=0.0, endpoint_grounded=True,
    )
    sb = SeabedConfig(mu=0.5, slope_rad=0.0)
    _solve_or_invalid([seg], bc, sb)


def test_R6_aguas_profundas_extremo():
    """R6: h=3000m, linha longa. Convergência típica esperada."""
    seg = LineSegment(length=4000.0, w=400.0, EA=2.5e8, MBL=4.0e6)
    bc = BoundaryConditions(
        h=3000.0, mode=SolutionMode.TENSION, input_value=3_000_000.0,
        startpoint_depth=0.0, endpoint_grounded=True,
    )
    sb = SeabedConfig(mu=0.3, slope_rad=0.0)
    res = _solve_or_invalid([seg], bc, sb)
    assert res.status in (
        ConvergenceStatus.CONVERGED, ConvergenceStatus.ILL_CONDITIONED,
    )


def test_R7_linha_curta_invalida():
    """R7: L < chord (corda < distância em linha reta entre pontos).
    Geometria fisicamente impossível — solver DEVE rejeitar com
    mensagem específica per Q7."""
    seg = LineSegment(length=100.0, w=1100.0, EA=5.83e8, MBL=5.57e6)
    bc = BoundaryConditions(
        h=200.0, mode=SolutionMode.RANGE, input_value=400.0,
        startpoint_depth=0.0, endpoint_grounded=True,
    )
    sb = SeabedConfig(mu=0.5, slope_rad=0.0)
    res = _solve_or_invalid([seg], bc, sb)
    # L=100 e chord ≈ √(400²+200²) ≈ 447 → impossível.
    assert res.status == ConvergenceStatus.INVALID_CASE, (
        f"R7: esperava INVALID_CASE, recebeu {res.status}"
    )


def test_R8_quase_taut():
    """R8: L = chord + ε (linha esticada quase sem catenária).
    Numericamente delicado — pode ser ill_conditioned (BC-MOORPY-08
    é o exemplo canônico)."""
    chord = math.hypot(400.0, 200.0)  # ≈ 447.21
    L = chord * 1.0001
    seg = LineSegment(length=L, w=100.0, EA=5.83e8, MBL=5.57e6)
    bc = BoundaryConditions(
        h=200.0, mode=SolutionMode.RANGE, input_value=400.0,
        startpoint_depth=0.0, endpoint_grounded=True,
    )
    sb = SeabedConfig(mu=0.0, slope_rad=0.0)
    res = _solve_or_invalid([seg], bc, sb)
    # Ill-conditioned é resultado aceitável e esperado aqui.
    assert res.status in (
        ConvergenceStatus.CONVERGED,
        ConvergenceStatus.ILL_CONDITIONED,
        ConvergenceStatus.INVALID_CASE,
    )
