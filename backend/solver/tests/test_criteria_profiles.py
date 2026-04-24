"""
Testes dos perfis de critério de utilização e do alert_level no SolverResult.

Cobre A5 da auditoria: Seção 5 do Documento A v2.2 (alerta amarelo/vermelho),
resposta P-04 do Documento B (perfis MVP/API/DNV/UserDefined), e integração
com o facade solve().
"""
from __future__ import annotations

import pytest

from backend.solver.solver import solve
from backend.solver.types import (
    AlertLevel,
    BoundaryConditions,
    ConvergenceStatus,
    CriteriaProfile,
    LineSegment,
    PROFILE_LIMITS,
    SolutionMode,
    UtilizationLimits,
    classify_utilization,
)


LBF_FT_TO_N_M = 14.593903


# ==============================================================================
# classify_utilization — unidade
# ==============================================================================


def test_classify_utilization_ok_yellow_red_broken_mvp() -> None:
    """Perfil MVP: 0.50 yellow / 0.60 red / 1.00 broken."""
    classify = lambda u: classify_utilization(u, CriteriaProfile.MVP_PRELIMINARY)
    assert classify(0.30) == AlertLevel.OK
    assert classify(0.49) == AlertLevel.OK
    assert classify(0.50) == AlertLevel.YELLOW
    assert classify(0.55) == AlertLevel.YELLOW
    assert classify(0.60) == AlertLevel.RED
    assert classify(0.95) == AlertLevel.RED
    assert classify(1.00) == AlertLevel.BROKEN
    assert classify(1.50) == AlertLevel.BROKEN


def test_classify_api_rp_2sk_broken_em_0_80() -> None:
    """Perfil API RP 2SK: broken em 0.80 (condição danificada)."""
    classify = lambda u: classify_utilization(u, CriteriaProfile.API_RP_2SK)
    assert classify(0.75) == AlertLevel.RED
    assert classify(0.80) == AlertLevel.BROKEN
    assert classify(0.99) == AlertLevel.BROKEN


def test_classify_dnv_placeholder_igual_mvp_por_enquanto() -> None:
    """DNV placeholder tem mesmos limites do MVP até F4+ (comentário no schema)."""
    assert (
        classify_utilization(0.70, CriteriaProfile.DNV_PLACEHOLDER)
        == classify_utilization(0.70, CriteriaProfile.MVP_PRELIMINARY)
    )


def test_classify_user_defined_requer_limits() -> None:
    with pytest.raises(ValueError, match="USER_DEFINED"):
        classify_utilization(0.50, CriteriaProfile.USER_DEFINED)


def test_classify_user_defined_usa_limits_customizados() -> None:
    lims = UtilizationLimits(yellow_ratio=0.20, red_ratio=0.30, broken_ratio=0.50)
    f = lambda u: classify_utilization(u, CriteriaProfile.USER_DEFINED, lims)
    assert f(0.15) == AlertLevel.OK
    assert f(0.20) == AlertLevel.YELLOW
    assert f(0.30) == AlertLevel.RED
    assert f(0.50) == AlertLevel.BROKEN


def test_utilization_limits_valida_ordem() -> None:
    """yellow < red < broken."""
    with pytest.raises(ValueError, match="yellow.*red.*broken"):
        UtilizationLimits(yellow_ratio=0.60, red_ratio=0.50, broken_ratio=1.00)
    with pytest.raises(ValueError):
        UtilizationLimits(yellow_ratio=0.50, red_ratio=0.50, broken_ratio=1.00)


def test_profile_limits_contem_tres_perfis_built_in() -> None:
    """USER_DEFINED não tem entrada no dict — por design."""
    assert CriteriaProfile.MVP_PRELIMINARY in PROFILE_LIMITS
    assert CriteriaProfile.API_RP_2SK in PROFILE_LIMITS
    assert CriteriaProfile.DNV_PLACEHOLDER in PROFILE_LIMITS
    assert CriteriaProfile.USER_DEFINED not in PROFILE_LIMITS


# ==============================================================================
# Integração com solve() facade
# ==============================================================================


def _bc_padrao(T_fl: float, MBL: float) -> tuple:
    """Retorna (segmentos, boundary) para caso fully suspended conhecido."""
    seg = LineSegment(length=450.0, w=13.78 * LBF_FT_TO_N_M, EA=34.25e6, MBL=MBL)
    bc = BoundaryConditions(h=300, mode=SolutionMode.TENSION, input_value=T_fl)
    return [seg], bc


def test_solve_inclui_alert_level_default() -> None:
    """Sem especificar profile, usa MVP_Preliminary."""
    segs, bc = _bc_padrao(T_fl=200_000.0, MBL=1e6)  # utilization = 0.20 -> OK
    r = solve(segs, bc)
    assert r.status == ConvergenceStatus.CONVERGED
    assert r.alert_level == AlertLevel.OK


def test_solve_alert_yellow() -> None:
    """Utilization entre 0.50 e 0.60 no MVP → YELLOW."""
    segs, bc = _bc_padrao(T_fl=785_000.0, MBL=1.45e6)
    # utilization esperado ≈ 785k/1450k ≈ 0.541
    r = solve(segs, bc, criteria_profile=CriteriaProfile.MVP_PRELIMINARY)
    assert r.status == ConvergenceStatus.CONVERGED
    assert 0.50 <= r.utilization < 0.60
    assert r.alert_level == AlertLevel.YELLOW


def test_solve_alert_red() -> None:
    """Utilization entre 0.60 e 1.00 → RED."""
    segs, bc = _bc_padrao(T_fl=785_000.0, MBL=1.2e6)
    # utilization ≈ 785k/1200k ≈ 0.654
    r = solve(segs, bc)
    assert r.status == ConvergenceStatus.CONVERGED
    assert 0.60 <= r.utilization < 1.00
    assert r.alert_level == AlertLevel.RED


def test_solve_broken_vira_invalid_case() -> None:
    """Utilization >= 1.0 → INVALID_CASE + alert_level=BROKEN."""
    segs, bc = _bc_padrao(T_fl=785_000.0, MBL=500_000.0)  # util = 1.57
    r = solve(segs, bc)
    assert r.status == ConvergenceStatus.INVALID_CASE
    assert r.alert_level == AlertLevel.BROKEN
    assert "rompida" in r.message.lower()
    # Preserva os dados mesmo assim (utilization e geometria parcial)
    assert r.utilization > 1.0


def test_solve_api_rp_2sk_broken_mais_cedo_que_mvp() -> None:
    """Com API_RP_2SK, broken é 0.80 → mesmo caso que era RED no MVP vira BROKEN."""
    segs, bc = _bc_padrao(T_fl=785_000.0, MBL=900_000.0)
    # utilization ≈ 0.872

    # MVP: classifica como RED (< 1.0)
    r_mvp = solve(segs, bc, criteria_profile=CriteriaProfile.MVP_PRELIMINARY)
    assert r_mvp.status == ConvergenceStatus.CONVERGED
    assert r_mvp.alert_level == AlertLevel.RED

    # API RP 2SK: broken em 0.80 → invalidado
    r_api = solve(segs, bc, criteria_profile=CriteriaProfile.API_RP_2SK)
    assert r_api.status == ConvergenceStatus.INVALID_CASE
    assert r_api.alert_level == AlertLevel.BROKEN


def test_solve_user_defined_limites_customizados() -> None:
    """UserDefined permite critério conservador do cliente."""
    segs, bc = _bc_padrao(T_fl=300_000.0, MBL=1e6)  # util = 0.30
    lims = UtilizationLimits(yellow_ratio=0.15, red_ratio=0.25, broken_ratio=0.40)

    r = solve(
        segs, bc,
        criteria_profile=CriteriaProfile.USER_DEFINED,
        user_limits=lims,
    )
    # util 0.30 está entre red_ratio 0.25 e broken 0.40 → RED
    assert r.status == ConvergenceStatus.CONVERGED
    assert r.alert_level == AlertLevel.RED


def test_solve_user_defined_sem_limits_retorna_invalid() -> None:
    """USER_DEFINED sem user_limits: classify_utilization levanta,
    facade converte a INVALID_CASE (via NUMERICAL_ERROR catch-all)."""
    segs, bc = _bc_padrao(T_fl=300_000.0, MBL=1e6)
    r = solve(segs, bc, criteria_profile=CriteriaProfile.USER_DEFINED)
    # O facade captura ValueError de classify_utilization como NUMERICAL_ERROR
    # (cai no `except Exception`). Aceitável: sinaliza problema sem crashar.
    assert r.status in (
        ConvergenceStatus.NUMERICAL_ERROR,
        ConvergenceStatus.INVALID_CASE,
    )
