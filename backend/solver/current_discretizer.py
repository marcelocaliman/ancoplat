"""
Discretização de `CurrentProfile` em `LineAttachment(kind='ahv')` pontuais.

Sprint 1 / v1.1.0 / Commit 5.

Esta é uma **função pura, opt-in**, NÃO auto-invocada pelo `solve()`. O
caller (UI ou endpoint dedicado) decide quando converter um perfil de
corrente em forças pontuais distribuídas. O solver continua tratando os
AHVs gerados pela mesma rotina de F8 — nenhuma mudança no core.

Modelo físico
─────────────
Arrasto estático tipo Morison na linha cilíndrica:

    F_i = 0.5 · ρ · Cd · D · Δs · V(z_i)²

onde:
    ρ   = densidade da água (kg/m³)         — default 1025
    Cd  = coeficiente de arrasto (adim.)    — default 1.2
    D   = diâmetro nominal da linha (m)
    Δs  = comprimento do trecho i (m)
    V_i = velocidade interpolada na profundidade z_i (m/s)

Idealizações registradas (a serem cobertas por D020 no Commit 9 quando
houver UI dedicada):
  • Mapeamento depth ↔ arc length aproximado linearmente
    (`z_i = h · s_i / L_total`). Realista para linhas predominantemente
    verticais (taut wire); pode subestimar correntes superficiais em
    catenárias slack onde grande parte do comprimento está perto da
    superfície.
  • V_i² assume fluxo perpendicular à linha — não corrige por ângulo
    de incidência. Para linhas alinhadas ao fluxo, isso superestima.
  • Heading interpolado por nearest-neighbor (não por SLERP) — escolha
    consciente para evitar artefatos angulares.
  • Modelagem ESTÁTICA — não captura VIV, lock-in, fadiga.

Para casos onde a aproximação é forte (slack catenária, corrente
horizontal violenta), recomenda-se análise dinâmica (OrcaFlex/MoorPy
Subsystem) — D020 documenta esse limite.
"""
from __future__ import annotations

import math
from typing import Optional

from backend.solver.types import CurrentLayer, CurrentProfile, LineAttachment


DEFAULT_DRAG_COEFFICIENT: float = 1.2
DEFAULT_WATER_DENSITY: float = 1025.0  # kg/m³, salt water


def _interp_speed(layers: list[CurrentLayer], z: float) -> float:
    """Interpolação linear de speed em função de depth.

    `layers` é assumido pré-ordenado por depth crescente (garantido pelo
    `CurrentProfile._validate_layers_sorted`).
    """
    if z <= layers[0].depth:
        return layers[0].speed
    if z >= layers[-1].depth:
        return layers[-1].speed
    for i in range(len(layers) - 1):
        z0, z1 = layers[i].depth, layers[i + 1].depth
        if z0 <= z <= z1:
            if z1 == z0:
                return layers[i].speed
            t = (z - z0) / (z1 - z0)
            return layers[i].speed + t * (layers[i + 1].speed - layers[i].speed)
    return layers[-1].speed  # fallback (não alcançado em entradas válidas)


def _nearest_heading(layers: list[CurrentLayer], z: float) -> float:
    """Heading da layer mais próxima de `z` em depth."""
    best = layers[0]
    best_dist = abs(layers[0].depth - z)
    for lyr in layers[1:]:
        d = abs(lyr.depth - z)
        if d < best_dist:
            best = lyr
            best_dist = d
    return best.heading_deg


def discretize_current_profile(
    profile: CurrentProfile,
    *,
    line_diameter: float,
    total_arc_length: float,
    water_depth: float,
    n_slices: int = 10,
    cd_override: Optional[float] = None,
    rho_override: Optional[float] = None,
    name_prefix: str = "current",
) -> list[LineAttachment]:
    """
    Converte um `CurrentProfile` em `n_slices` AHVs pontuais ao longo
    da linha.

    Parameters
    ----------
    profile : CurrentProfile
        Perfil V(z) com layers ordenadas (validado pelo schema).
    line_diameter : float
        Diâmetro nominal da linha sob arrasto (m). Tipicamente o do
        primeiro segmento ou média ponderada se a linha for heterogênea
        — caller decide.
    total_arc_length : float
        Comprimento total não-esticado da linha (m). É a soma de todos
        os `segment.length`.
    water_depth : float
        Profundidade do seabed (m) — usada para mapear `s` em `z`.
    n_slices : int, default 10
        Número de fatias / AHVs gerados. Quanto maior, mais fiel ao
        perfil contínuo; quanto menor, mais barato no solver.
    cd_override, rho_override : float, opcional
        Sobrescreve defaults físicos. Quando None:
          • Cd = profile.drag_coefficient se presente, senão 1.2.
          • ρ  = profile.water_density   se presente, senão 1025.
    name_prefix : str
        Prefixo para `LineAttachment.name` — facilita identificar
        quais AHVs vieram da discretização vs criados manualmente.

    Returns
    -------
    list[LineAttachment]
        Lista ordenada por `position_s_from_anchor` crescente. AHVs com
        `ahv_bollard_pull = 0` são DESCARTADOS (slice em zona de speed=0).

    Raises
    ------
    ValueError
        Quando `n_slices < 1`, `line_diameter ≤ 0`, ou parâmetros
        físicos inválidos.

    Notas
    -----
    Esta função NÃO modifica o perfil de corrente nem o caso. Cabe ao
    caller anexar os AHVs retornados ao `attachments` antes de chamar
    `solve()`.

    Não há side-effect global: rho/Cd dos overrides são lidos e
    consumidos in-loco; defaults (1025 / 1.2) viram constantes do
    módulo, expostas para teste.
    """
    if n_slices < 1:
        raise ValueError(f"n_slices deve ser ≥ 1, recebido {n_slices}")
    if line_diameter <= 0:
        raise ValueError(f"line_diameter deve ser > 0, recebido {line_diameter}")
    if total_arc_length <= 0:
        raise ValueError(
            f"total_arc_length deve ser > 0, recebido {total_arc_length}"
        )
    if water_depth <= 0:
        raise ValueError(f"water_depth deve ser > 0, recebido {water_depth}")

    cd = cd_override if cd_override is not None else (
        profile.drag_coefficient if profile.drag_coefficient is not None
        else DEFAULT_DRAG_COEFFICIENT
    )
    rho = rho_override if rho_override is not None else (
        profile.water_density if profile.water_density is not None
        else DEFAULT_WATER_DENSITY
    )
    if cd <= 0:
        raise ValueError(f"cd deve ser > 0, recebido {cd}")
    if rho <= 0:
        raise ValueError(f"rho deve ser > 0, recebido {rho}")

    delta_s = total_arc_length / n_slices
    layers = list(profile.layers)
    out: list[LineAttachment] = []

    for i in range(n_slices):
        # midpoint do trecho ao longo do arco — referência da força pontual
        s_mid = (i + 0.5) * delta_s
        # mapeamento simples s ↔ z (linhas predominantemente verticais)
        z_mid = water_depth * (s_mid / total_arc_length)
        v_mid = _interp_speed(layers, z_mid)
        h_mid = _nearest_heading(layers, z_mid)
        # F = 0.5 · ρ · Cd · D · Δs · V²
        force_n = 0.5 * rho * cd * line_diameter * delta_s * v_mid * v_mid

        if force_n <= 0:
            continue  # zona de speed=0 → não cria AHV vazio

        out.append(
            LineAttachment(
                kind="ahv",
                position_s_from_anchor=s_mid,
                ahv_bollard_pull=force_n,
                ahv_heading_deg=h_mid % 360.0,
                name=f"{name_prefix}[{i}]",
            )
        )

    return out


def total_drag_force(
    profile: CurrentProfile,
    *,
    line_diameter: float,
    total_arc_length: float,
    water_depth: float,
    n_slices: int = 10,
    cd_override: Optional[float] = None,
    rho_override: Optional[float] = None,
) -> float:
    """
    Soma escalar dos `ahv_bollard_pull` que `discretize_current_profile`
    produziria — útil para sanity check "essa corrente vai mexer a
    catenária?" sem chamar o solver.

    Note: soma de magnitudes, não soma vetorial — quando layers têm
    headings diferentes, o resultado superestima a resultante.
    """
    ahvs = discretize_current_profile(
        profile,
        line_diameter=line_diameter,
        total_arc_length=total_arc_length,
        water_depth=water_depth,
        n_slices=n_slices,
        cd_override=cd_override,
        rho_override=rho_override,
    )
    return math.fsum(a.ahv_bollard_pull or 0.0 for a in ahvs)


__all__ = [
    "DEFAULT_DRAG_COEFFICIENT",
    "DEFAULT_WATER_DENSITY",
    "discretize_current_profile",
    "total_drag_force",
]
