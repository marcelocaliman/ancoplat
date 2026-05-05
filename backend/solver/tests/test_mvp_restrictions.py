"""
Testes das restrições de contorno suportadas pelo solver.

Cobre:
- Âncora elevada do seabed (endpoint_grounded=False) → INVALID_CASE.
- Fairlead submerso (startpoint_depth ∈ (0, h)) → CONVERGED com drop reduzido.
- Fairlead no seabed (startpoint_depth == h) → CONVERGED via laid_line.
- Fairlead abaixo do seabed (startpoint_depth > h) → INVALID_CASE.
- Multi-segmento (len(line_segments) > 1) → INVALID_CASE.
"""
from __future__ import annotations

from backend.solver.solver import solve
from backend.solver.types import (
    BoundaryConditions,
    ConvergenceStatus,
    LineSegment,
    SeabedConfig,
    SolutionMode,
)


LBF_FT_TO_N_M = 14.593903


def _seg_padrao() -> LineSegment:
    return LineSegment(
        length=450.0, w=13.78 * LBF_FT_TO_N_M, EA=34.25e6, MBL=3.78e6,
    )


# ==============================================================================
# Âncora elevada — ainda não suportada
# ==============================================================================


def test_endpoint_grounded_false_sem_endpoint_depth_rejeitado_no_pydantic() -> None:
    """
    Fase 7: schema agora bloqueia endpoint_grounded=False sem endpoint_depth
    no Pydantic (falha rápido, antes do solver). Mensagem clara orienta
    o engenheiro a informar a profundidade do anchor.
    """
    import pytest
    from pydantic import ValidationError
    with pytest.raises(ValidationError, match="endpoint_depth é obrigatório"):
        BoundaryConditions(
            h=300, mode=SolutionMode.TENSION, input_value=785_000,
            endpoint_grounded=False,
        )


def test_endpoint_grounded_false_com_endpoint_depth_solver_pre_commit3_invalid() -> None:
    """
    Fase 7 / pré-Commit-3: solver ainda levanta NotImplementedError
    interno → INVALID_CASE. Pós-Commit-3 (dispatcher uplift), este
    teste será atualizado para expectar CONVERGED.
    """
    bc = BoundaryConditions(
        h=300, mode=SolutionMode.TENSION, input_value=785_000,
        endpoint_grounded=False, endpoint_depth=250.0,  # uplift=50m, BC-UP-01-like
    )
    r = solve([_seg_padrao()], bc)
    assert r.status == ConvergenceStatus.INVALID_CASE
    assert "endpoint_grounded" in r.message or "elevada" in r.message.lower()


# ==============================================================================
# Fairlead submerso — suportado desde que drop efetivo > 0
# ==============================================================================


def test_startpoint_depth_submerso_converge() -> None:
    """
    Fairlead submerso reduz o drop efetivo. Para drop de 200 m
    (h=300, startpoint_depth=100) com a mesma T_fl, a geometria
    acomoda mais linha no seabed → total_grounded_length > 0.
    """
    bc = BoundaryConditions(
        h=300, mode=SolutionMode.TENSION, input_value=785_000,
        startpoint_depth=100.0,
    )
    r = solve([_seg_padrao()], bc)
    assert r.status == ConvergenceStatus.CONVERGED
    # Campos geométricos globais devem ser propagados para o resultado
    assert r.water_depth == 300.0
    assert r.startpoint_depth == 100.0
    # endpoint_depth aqui vem do solver interno, que opera com drop=200
    assert abs(r.endpoint_depth - 200.0) < 1e-3


def test_fairlead_no_seabed_dispatches_para_laid_line() -> None:
    """
    Fairlead no mesmo nível da âncora: linha 100% horizontal no seabed.
    Tração varia linearmente por atrito, sem catenária.
    """
    seabed = SeabedConfig(mu=0.6)
    bc = BoundaryConditions(
        h=300, mode=SolutionMode.TENSION, input_value=600_000,
        startpoint_depth=300.0,
    )
    r = solve([_seg_padrao()], bc, seabed=seabed)
    assert r.status == ConvergenceStatus.CONVERGED
    # No caso horizontal não há trecho suspenso
    assert r.total_suspended_length == 0.0
    assert r.total_grounded_length > 0.0
    # Queda de tração = atrito total μ·w·L
    seg = _seg_padrao()
    expected_drop = 0.6 * seg.w * seg.length
    assert abs((r.fairlead_tension - r.anchor_tension) - expected_drop) < 1.0
    # Coords_y devem estar todas no seabed (drop=0 → y=0 no frame do solver)
    assert max(abs(y) for y in r.coords_y) < 1e-6


def test_fairlead_abaixo_do_seabed_invalid_case() -> None:
    """startpoint_depth > h: fairlead "enterrado" é fisicamente impossível."""
    bc = BoundaryConditions(
        h=300, mode=SolutionMode.TENSION, input_value=785_000,
        startpoint_depth=350.0,
    )
    r = solve([_seg_padrao()], bc)
    assert r.status == ConvergenceStatus.INVALID_CASE
    assert "startpoint_depth" in r.message or "inviável" in r.message.lower()


# ==============================================================================
# BC-FAIRLEAD-SLOPE-01: validação de fairlead em seabed inclinado (Fase 2 / Q7)
# ==============================================================================


def test_BC_FAIRLEAD_SLOPE_01_descendente_nao_rejeita_caso_valido() -> None:
    """
    Em seabed descendente (slope < 0 — anchor mais raso que ponto sob
    fairlead), a profundidade do seabed sob o fairlead é MAIOR que h.
    A validação Fase 2 (h_at_fairlead = h - tan(slope)·X) deve aceitar
    casos onde startpoint_depth > h mas startpoint_depth < h_at_fairlead.

    Cenário: h (anchor)=200m, slope=-5° (desce 5° p/ fairlead),
    X≈400m → h_at_fairlead = 200 - tan(-5°)·400 ≈ 235m.
    Fairlead a 30m de prof — OK (< 235m).
    """
    import math
    seg = LineSegment(
        length=600.0, w=13.78 * LBF_FT_TO_N_M, EA=34.25e6, MBL=3.78e6,
    )
    bc = BoundaryConditions(
        h=200, mode=SolutionMode.TENSION, input_value=785_000,
        startpoint_depth=30.0,
    )
    sb = SeabedConfig(slope_rad=math.radians(-5))  # descendente
    r = solve([seg], bc, sb)
    # Pré-Fase-2 isso teria rejeitado se startpoint_depth fosse > h plano —
    # mas startpoint_depth=30 < h=200 mesmo plano, logo o caso passaria.
    # Construímos um teste mais cirúrgico abaixo (startpoint_depth ENTRE h e h_at_fairlead).
    assert r.status == ConvergenceStatus.CONVERGED, r.message


def test_BC_FAIRLEAD_SLOPE_01_descendente_caso_que_falharia_pre_F2() -> None:
    """
    Caso que a validação plana pré-Fase-2 rejeitaria mas o relaxamento
    Q7 aceita: startpoint_depth > h mas ainda < h_at_fairlead.

    Setup escolhido: h=100m, slope=-30° (seabed cai forte), X (modo Range)
    de 500m → h_at_fairlead ≈ 100 - tan(-30°)·500 ≈ 100 + 289 = 389m.
    Fairlead a 150m de prof: 150 > h=100 (rejeitaria pré-F2) mas
    150 < h_at_fairlead=389 (aceita pós-F2).
    """
    import math
    seg = LineSegment(
        length=900.0, w=13.78 * LBF_FT_TO_N_M, EA=34.25e6, MBL=3.78e6,
    )
    bc = BoundaryConditions(
        h=100,
        mode=SolutionMode.RANGE,
        input_value=500.0,
        startpoint_depth=150.0,  # > h plano, mas < h_at_fairlead
    )
    sb = SeabedConfig(slope_rad=math.radians(-30))
    # Pré-F2 isto virava INVALID_CASE no _validate_inputs.
    # Pós-F2 deve passar a validação (e retornar CONVERGED ou INVALID_CASE
    # por outras razões físicas, mas NÃO pelo guard de startpoint_depth >= h).
    r = solve([seg], bc, sb)
    if r.status == ConvergenceStatus.INVALID_CASE:
        # Se ainda é INVALID, garante que é por outra razão (não startpoint_depth).
        assert "startpoint_depth" not in r.message, (
            f"Caso ainda rejeitado pelo guard de startpoint_depth: {r.message}"
        )


def test_BC_FAIRLEAD_SLOPE_01_descendente_excessivo_rejeita() -> None:
    """
    Caso que mesmo o relaxamento Q7 deve rejeitar: startpoint_depth >
    h_at_fairlead (geometria impossível).
    """
    import math
    seg = LineSegment(
        length=400.0, w=13.78 * LBF_FT_TO_N_M, EA=34.25e6, MBL=3.78e6,
    )
    # h=200, slope=+10° (sobe ao fairlead), X≈300 → h_at_fairlead ≈ 200 - 53 = 147
    # startpoint_depth=180 > h_at_fairlead=147 → rejeita.
    bc = BoundaryConditions(
        h=200,
        mode=SolutionMode.RANGE,
        input_value=300.0,
        startpoint_depth=180.0,
    )
    sb = SeabedConfig(slope_rad=math.radians(10))  # sobe ao fairlead
    r = solve([seg], bc, sb)
    assert r.status == ConvergenceStatus.INVALID_CASE
    assert "fairlead" in r.message.lower()


def test_default_endpoint_grounded_e_startpoint_depth() -> None:
    """Defaults preservados: endpoint_grounded=True, startpoint_depth=0."""
    bc = BoundaryConditions(h=300, mode=SolutionMode.TENSION, input_value=785_000)
    assert bc.endpoint_grounded is True
    assert bc.startpoint_depth == 0.0
    r = solve([_seg_padrao()], bc)
    assert r.status == ConvergenceStatus.CONVERGED
    assert r.water_depth == 300.0
    assert r.startpoint_depth == 0.0


# ==============================================================================
# Multi-segmento (F5.1)
# ==============================================================================


def test_multi_segmento_homogeneo_bate_com_single_segmento() -> None:
    """
    Linha composta de 2 segmentos IDÊNTICOS, somando o mesmo comprimento
    do caso single-segmento, deve produzir mesmo T_fl, X, geometria
    (dentro de tolerância numérica do bracket de brentq).
    """
    s_single = LineSegment(length=450.0, w=13.78 * LBF_FT_TO_N_M, EA=34.25e6, MBL=3.78e6)
    s_a = LineSegment(length=200.0, w=13.78 * LBF_FT_TO_N_M, EA=34.25e6, MBL=3.78e6)
    s_b = LineSegment(length=250.0, w=13.78 * LBF_FT_TO_N_M, EA=34.25e6, MBL=3.78e6)
    bc = BoundaryConditions(h=300, mode=SolutionMode.TENSION, input_value=785_000)

    r_single = solve([s_single], bc)
    r_multi = solve([s_a, s_b], bc)

    assert r_single.status == ConvergenceStatus.CONVERGED
    assert r_multi.status == ConvergenceStatus.CONVERGED
    # Tolerância 0,3 % — vem do bracket de brentq na busca por H
    assert abs(r_multi.fairlead_tension - r_single.fairlead_tension) / r_single.fairlead_tension < 3e-3
    assert abs(r_multi.total_horz_distance - r_single.total_horz_distance) / r_single.total_horz_distance < 3e-3
    assert abs(r_multi.H - r_single.H) / r_single.H < 3e-3


def test_lista_vazia_de_segmentos_retorna_invalid_case() -> None:
    bc = BoundaryConditions(h=300, mode=SolutionMode.TENSION, input_value=785_000)
    r = solve([], bc)
    assert r.status == ConvergenceStatus.INVALID_CASE
    assert "segmento" in r.message.lower()
