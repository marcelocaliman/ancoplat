"""
BC-FR-01 — Validação física de atrito per-segmento (Fase 1 / B3).

Verifica que a precedência canônica do atrito implementada em
``_resolve_mu_per_seg`` produz resultados equivalentes ao comportamento
legado quando os campos novos são None, e que o solver respeita o
valor resolvido (mu_override → seabed_friction_cf → seabed.mu).

Validação contra cálculo manual: para linha grounded em seabed plano,
a redução de tensão na zona apoiada é ``ΔT = μ · w · L_grounded``
(equilíbrio quasi-estático de atrito Coulomb axial). Tolerância: ±2%
conforme AC do plano.
"""
from __future__ import annotations

import math

import pytest

from backend.solver.solver import solve
from backend.solver.types import (
    BoundaryConditions,
    LineSegment,
    SeabedConfig,
    SolutionMode,
)


# ─── BC-FR-01: validação contra cálculo manual de capstan plano ─────


def test_BC_FR_01_friction_matches_capstan_manual():
    """
    Linha mono-segmento com touchdown, μ=0.5 explícito por mu_override.
    ΔT (touchdown→anchor) = μ · w · L_grounded ± 2% (Coulomb axial).

    Pré-requisito do teste: T_anchor > 0 (não clampado a zero).
    Parâmetros escolhidos para garantir μ·w·L_g < H — assim a equação
    capstan é totalmente exercitada, sem cair no clamp T_anchor=0
    que o solver aplica quando o atrito disponível excede H.
    """
    L = 800.0
    h = 200.0
    w = 200.0  # chain leve
    EA = 82e9
    MBL = 6e6
    T_fl = 200_000.0
    mu = 0.5

    seg = LineSegment(
        length=L, w=w, EA=EA, MBL=MBL, mu_override=mu,
    )
    bc = BoundaryConditions(
        h=h, mode=SolutionMode.TENSION, input_value=T_fl,
        startpoint_depth=0.0, endpoint_grounded=True,
    )
    sb = SeabedConfig(mu=0.0)  # global zerado — todo atrito vem do per-seg

    r = solve([seg], bc, sb)
    assert r.status.value == "converged", r.message
    assert r.total_grounded_length > 0, "Caso precisa ter touchdown"

    # No seabed plano: tração no touchdown = H (horizontal puro)
    H = r.H
    T_anchor = math.hypot(r.tension_x[0], r.tension_y[0])
    delta_T_actual = H - T_anchor

    # Pré-requisito: T_anchor > 0 (caso contrário capstan está saturado)
    assert T_anchor > 1.0, (
        f"T_anchor={T_anchor:.2f} ≈ 0 — caso saturado, capstan não exercitado. "
        f"Aumente T_fl ou diminua μ/w/L_g."
    )

    # Capstan plano: ΔT = μ · w · L_g
    delta_T_predicted = mu * w * r.total_grounded_length

    rel_err = abs(delta_T_actual - delta_T_predicted) / abs(delta_T_predicted)
    assert rel_err < 0.02, (
        f"ΔT atual={delta_T_actual:.2f}, manual={delta_T_predicted:.2f}, "
        f"rel_err={rel_err:.4f} > 2%"
    )


# ─── Equivalência: mu_override == seabed.mu global (mesmo valor) ────


def test_per_seg_mu_equivalente_a_global_quando_mesmo_valor():
    """μ via mu_override produz mesmo SolverResult que μ via seabed.mu
    global, quando o valor é o mesmo. Garante que a substituição feita
    no facade não introduz erro numérico."""
    L = 800.0
    h = 200.0
    w = 1058.0
    EA = 82e9
    MBL = 6e6
    T_fl = 250_000.0
    mu = 0.5

    bc = BoundaryConditions(
        h=h, mode=SolutionMode.TENSION, input_value=T_fl,
    )

    # Caso A: μ via mu_override
    seg_a = LineSegment(length=L, w=w, EA=EA, MBL=MBL, mu_override=mu)
    r_a = solve([seg_a], bc, SeabedConfig(mu=0.0))

    # Caso B: μ via seabed.mu global
    seg_b = LineSegment(length=L, w=w, EA=EA, MBL=MBL)
    r_b = solve([seg_b], bc, SeabedConfig(mu=mu))

    # Resultados equivalentes
    assert r_a.tension_x[0] == pytest.approx(r_b.tension_x[0], rel=1e-9)
    assert r_a.tension_y[0] == pytest.approx(r_b.tension_y[0], rel=1e-9)
    assert r_a.total_grounded_length == pytest.approx(
        r_b.total_grounded_length, rel=1e-9,
    )
    assert r_a.fairlead_tension == pytest.approx(r_b.fairlead_tension, rel=1e-9)


# ─── seabed_friction_cf do catálogo tem mesma precedência ───────────


def test_seabed_friction_cf_equivalente_a_mu_override():
    """seabed_friction_cf (do catálogo) com mesmo valor produz mesmo
    SolverResult que mu_override (do usuário) — testa nível 2 da
    precedência."""
    L = 800.0
    h = 200.0
    w = 1058.0
    EA = 82e9
    MBL = 6e6
    T_fl = 250_000.0
    mu_val = 0.7

    bc = BoundaryConditions(
        h=h, mode=SolutionMode.TENSION, input_value=T_fl,
    )
    sb = SeabedConfig(mu=0.0)

    seg_override = LineSegment(
        length=L, w=w, EA=EA, MBL=MBL, mu_override=mu_val,
    )
    seg_catalog = LineSegment(
        length=L, w=w, EA=EA, MBL=MBL, seabed_friction_cf=mu_val,
    )

    r_o = solve([seg_override], bc, sb)
    r_c = solve([seg_catalog], bc, sb)

    assert r_o.tension_x[0] == pytest.approx(r_c.tension_x[0], rel=1e-12)
    assert r_o.total_grounded_length == pytest.approx(
        r_c.total_grounded_length, rel=1e-12,
    )


# ─── Precedência: mu_override vence sobre seabed_friction_cf ────────


def test_mu_override_vence_seabed_friction_cf():
    """Se ambos estão presentes com valores diferentes, mu_override domina.
    Verifica via ΔT contra cálculo manual usando mu_override (não cf).

    Mesma topologia do test_BC_FR_01_*: parâmetros escolhidos para evitar
    saturação (T_anchor > 0).
    """
    L = 800.0
    h = 200.0
    w = 200.0
    EA = 82e9
    MBL = 6e6
    T_fl = 200_000.0
    mu_override = 0.3
    cf_catalogo = 1.0  # diferente, não deveria ser usado

    seg = LineSegment(
        length=L, w=w, EA=EA, MBL=MBL,
        mu_override=mu_override,
        seabed_friction_cf=cf_catalogo,
    )
    bc = BoundaryConditions(
        h=h, mode=SolutionMode.TENSION, input_value=T_fl,
    )
    r = solve([seg], bc, SeabedConfig(mu=0.0))

    H = r.H
    T_anchor = math.hypot(r.tension_x[0], r.tension_y[0])
    delta_T_actual = H - T_anchor
    delta_T_with_override = mu_override * w * r.total_grounded_length

    # Confirma que o ΔT bate com mu_override (e NÃO com cf_catalogo)
    assert abs(delta_T_actual - delta_T_with_override) / delta_T_with_override < 0.02


# ─── Multi-segmento: μ do segmento 0 governa o atrito ───────────────


def test_multi_seg_friction_usa_mu_do_segmento_0():
    """Multi-seg (chain[μ=variável] + wire[μ_seg1] + chain[μ_seg2]):
    apenas o μ do segmento 0 (em contato com o seabed na arquitetura
    F5.7.1) é fisicamente usado. Testa que μ do segmento middle/last
    é IRRELEVANTE para o resultado."""
    bc = BoundaryConditions(
        h=200.0, mode=SolutionMode.TENSION, input_value=200_000.0,
    )
    sb = SeabedConfig(mu=0.0)

    def _line(mu_seg0: float, mu_seg1: float, mu_seg2: float):
        return [
            LineSegment(
                length=400.0, w=200.0, EA=82e9, MBL=6e6,
                mu_override=mu_seg0,
            ),
            LineSegment(
                length=200.0, w=22.4, EA=3.4e7, MBL=460e3,
                mu_override=mu_seg1,
            ),
            LineSegment(
                length=200.0, w=200.0, EA=82e9, MBL=6e6,
                mu_override=mu_seg2,
            ),
        ]

    # Mesmo seg0 mu, diferentes seg1/seg2 mu → resultado IDÊNTICO
    r_a = solve(_line(0.3, 0.3, 0.6), bc, sb)
    r_b = solve(_line(0.3, 1.0, 1.0), bc, sb)

    assert r_a.status.value == "converged"
    assert r_b.status.value == "converged"
    assert r_a.tension_x[0] == pytest.approx(r_b.tension_x[0], rel=1e-9)
    assert r_a.total_grounded_length == pytest.approx(
        r_b.total_grounded_length, rel=1e-9,
    )

    # E confirma que mudando seg0 mu, o resultado MUDA
    r_c = solve(_line(0.7, 0.3, 0.6), bc, sb)
    assert r_c.tension_x[0] != pytest.approx(r_a.tension_x[0], rel=1e-3)
