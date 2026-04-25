"""
F5.4 — Solver dispatcher de mooring system multi-linha.

Resolve cada linha independentemente (sem equilíbrio de plataforma) e
agrega o resultante horizontal das forças no plano do casco. Cada
linha é tratada como um caso isolado pelo solver canônico
(`backend.solver.solver.solve`).

Convenção do plano horizontal (mesma da Seção F5.4 das schemas):

  - Origem no centro da plataforma.
  - +X aponta para a proa (azimuth 0°).
  - Sentido anti-horário.
  - Fairlead em `(R cos θ, R sin θ)`; linha sai radialmente.
  - Anchor em `((R + X_solver) cos θ, (R + X_solver) sin θ)`.

Força horizontal sobre a plataforma vinda da linha i:
  `F_i = H_i · (cos θ_i, sin θ_i)`
Aponta radialmente para fora (do fairlead em direção à âncora) — em
spread simétrico balanceado, Σ F_i ≈ 0.
"""
from __future__ import annotations

import math
from typing import Iterable, TYPE_CHECKING

from . import SOLVER_VERSION
from .solver import solve as solve_single_line
from .types import (
    AlertLevel,
    ConvergenceStatus,
    MooringLineResult,
    MooringSystemResult,
)

if TYPE_CHECKING:
    from backend.api.schemas.mooring_systems import (
        MooringSystemInput,
        SystemLineSpec,
    )


# Hierarquia de severidade — usada para `worst_alert_level`.
_ALERT_SEVERITY: dict[AlertLevel, int] = {
    AlertLevel.OK: 0,
    AlertLevel.YELLOW: 1,
    AlertLevel.RED: 2,
    AlertLevel.BROKEN: 3,
}


def _solve_single_line_in_system(
    line: "SystemLineSpec",
) -> MooringLineResult:
    """Resolve uma linha individual e a transforma para o frame da plataforma."""
    res = solve_single_line(
        line_segments=list(line.segments),
        boundary=line.boundary,
        seabed=line.seabed,
        criteria_profile=line.criteria_profile,
        user_limits=line.user_defined_limits,
        attachments=tuple(line.attachments),
    )

    theta = math.radians(line.fairlead_azimuth_deg)
    cos_t = math.cos(theta)
    sin_t = math.sin(theta)

    fairlead_xy = (line.fairlead_radius * cos_t, line.fairlead_radius * sin_t)

    # Quando o solver não converge, X (total_horz_distance) pode ser 0.
    # A âncora "cai" sobre o fairlead na plan view — visualmente sinaliza
    # que aquela linha falhou; código consumidor checa `solver_result.status`.
    x_total = res.total_horz_distance
    anchor_radius = line.fairlead_radius + x_total
    anchor_xy = (anchor_radius * cos_t, anchor_radius * sin_t)

    # Força horizontal sobre a plataforma. Convenção: positiva radialmente
    # para fora (linha puxa a plataforma na direção do anchor). Quando
    # status != converged, zera a força para não contaminar o agregado.
    if res.status == ConvergenceStatus.CONVERGED:
        h = res.H
    else:
        h = 0.0
    horz_force_xy = (h * cos_t, h * sin_t)

    return MooringLineResult(
        line_name=line.name,
        fairlead_azimuth_deg=line.fairlead_azimuth_deg,
        fairlead_radius=line.fairlead_radius,
        fairlead_xy=fairlead_xy,
        anchor_xy=anchor_xy,
        horz_force_xy=horz_force_xy,
        solver_result=res,
    )


def _aggregate(line_results: Iterable[MooringLineResult]) -> dict:
    """Agrega forças e métricas de severidade entre linhas convergidas."""
    fx = 0.0
    fy = 0.0
    n_converged = 0
    n_invalid = 0
    max_util = 0.0
    worst = AlertLevel.OK

    for lr in line_results:
        sr = lr.solver_result
        if sr.status == ConvergenceStatus.CONVERGED:
            fx += lr.horz_force_xy[0]
            fy += lr.horz_force_xy[1]
            n_converged += 1
            if sr.utilization > max_util:
                max_util = sr.utilization
            if sr.alert_level is not None:
                if _ALERT_SEVERITY[sr.alert_level] > _ALERT_SEVERITY[worst]:
                    worst = sr.alert_level
        else:
            n_invalid += 1

    mag = math.hypot(fx, fy)
    # azimuth do resultante: 0 quando magnitude ~ 0 (sem direção definida).
    if mag > 1e-6:
        az_rad = math.atan2(fy, fx)
        az_deg = math.degrees(az_rad)
        # Normaliza para [0, 360)
        if az_deg < 0:
            az_deg += 360.0
        if az_deg >= 360.0:
            az_deg -= 360.0
    else:
        az_deg = 0.0

    return dict(
        aggregate_force_xy=(fx, fy),
        aggregate_force_magnitude=mag,
        aggregate_force_azimuth_deg=az_deg,
        max_utilization=max_util,
        worst_alert_level=worst,
        n_converged=n_converged,
        n_invalid=n_invalid,
    )


def solve_mooring_system(msys_input: "MooringSystemInput") -> MooringSystemResult:
    """
    Resolve todas as linhas de um mooring system e devolve o agregado.

    Cada linha é resolvida independentemente. Linhas que falham
    (status != CONVERGED) entram no resultado com `solver_result` cheio
    da exceção, mas ficam de fora do agregado de forças.
    """
    line_results: list[MooringLineResult] = [
        _solve_single_line_in_system(line) for line in msys_input.lines
    ]
    agg = _aggregate(line_results)

    return MooringSystemResult(
        lines=line_results,
        solver_version=SOLVER_VERSION,
        **agg,
    )


__all__ = ["solve_mooring_system"]
