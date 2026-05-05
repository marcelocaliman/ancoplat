"""
Classificador de regime catenário (Fase 4 / Q2 do plano de
profissionalização).

Espelha o vocabulário de `MoorPy/Catenary.py:147-163` (NREL,
MIT-licensed) — taxonomia adotada para cross-comparação numérica e
diagnostics estruturados (D015 ProfileType raro).

A função `classify_profile_type` é PURA — não chama o solver,
apenas inspeciona o `SolverResult` já produzido + entradas de
contorno. Mora em módulo isolado para ser testável sem fixtures
de solver.

Decisões caso-a-caso e divergências documentadas em
`docs/relatorio_F4_diagnostics.md` §3 (tabela de classificação
1/2/3 das divergências classifier vs MoorPy):

  Categoria 1 — bug do classifier (corrigir).
  Categoria 2 — diferença legítima de modelo (multi-segmento vs
                MoorPy single-segment, ou regime que AncoPlat trata
                diferente por razão física).
  Categoria 3 — edge case de tolerância numérica (caso na fronteira
                entre PTs, classifier escolhe diferente do MoorPy mas
                ambas escolhas são defensáveis).

PTs não-atingíveis no AncoPlat MVP v1 (PT_4 boiante, PT_5 U-shape
slack) ficam no enum mas o classifier nunca os retorna em runtime —
serão habilitados em Fase 7+ (uplift) e Fase 12 (linhas boiantes).
"""
from __future__ import annotations

from typing import Optional, Sequence

from .types import (
    ConvergenceStatus,
    LineSegment,
    ProfileType,
    SeabedConfig,
    SolverResult,
)


# Tolerâncias para classificação. Calibradas para evitar falsos
# positivos em casos no limite (p.ex., touchdown iminente onde L_g
# é numericamente >0 mas <1mm — não vale chamar PT_2).
_EPS_LENGTH_REL = 1e-4   # razão L/L_total — abaixo disso é "zero"
_EPS_LENGTH_ABS = 1e-3   # m — bound absoluto
_EPS_X_ABS = 1e-3        # m — caso degenerado X ≈ 0 (vertical)
_EPS_SLOPE_RAD = 1e-6    # rad — slope efetivamente zero
_EPS_TENSION_N = 1.0     # N — T_anchor "essencialmente zero"


def _is_zero_length(L: float, L_total: float) -> bool:
    """Comprimento é numericamente zero se < 1e-4 do total OU < 1mm absoluto."""
    if L_total <= 0:
        return L < _EPS_LENGTH_ABS
    return L < max(_EPS_LENGTH_ABS, _EPS_LENGTH_REL * L_total)


def classify_profile_type(
    result: SolverResult,
    segments: Sequence[LineSegment],
    seabed: Optional[SeabedConfig] = None,
) -> Optional[ProfileType]:
    """
    Classifica o regime catenário do `SolverResult` em um ProfileType.

    Retorna `None` quando:
      - status != CONVERGED nem ILL_CONDITIONED (sem geometria útil).
      - case degenerado que não cai em nenhum dos 10 PTs definidos
        (geralmente significa bug no solver ou input inválido).

    Política das tolerâncias:
      - Comprimento "zero" se < max(1e-3 m, 1e-4 × L_total).
      - Tração "zero" no anchor se < 1.0 N (= 0.1 kgf — ruído numérico).
      - Slope "zero" se |slope_rad| < 1e-6.

    Args:
      result: SolverResult já populado pelo solver.
      segments: lista de LineSegment (para obter L_total).
      seabed: SeabedConfig (para obter slope_rad). Se None, assume slope=0.

    Returns:
      ProfileType ou None.
    """
    # Sanity: status must indicate a solve that produced geometry.
    if result.status not in (
        ConvergenceStatus.CONVERGED,
        ConvergenceStatus.ILL_CONDITIONED,
    ):
        return None

    L_total = sum(s.length for s in segments) if segments else 0.0
    L_g = result.total_grounded_length
    L_s = result.total_suspended_length
    T_anc = result.anchor_tension
    X = result.total_horz_distance
    slope_rad = seabed.slope_rad if seabed is not None else 0.0
    has_slope = abs(slope_rad) > _EPS_SLOPE_RAD

    g_zero = _is_zero_length(L_g, L_total)
    s_zero = _is_zero_length(L_s, L_total)

    # ─── PT_6: linha completamente vertical (X ≈ 0) ──────────────────
    # Caso degenerado onde fairlead está praticamente em cima da
    # âncora. MoorPy classifica como PT_6.
    if X < _EPS_X_ABS and not s_zero:
        return ProfileType.PT_6

    # ─── PT_0 / PT_8: linha inteira no seabed (laid line) ────────────
    # Toda a linha apoiada — fairlead também está no seabed
    # (startpoint_depth ≈ h). PT_0 plano, PT_8 com slope.
    if s_zero and not g_zero:
        return ProfileType.PT_8 if has_slope else ProfileType.PT_0

    # ─── PT_1: catenária livre, sem seabed ───────────────────────────
    # Fully suspended — nenhuma porção tocando o fundo. Independe de
    # slope (seabed inclinado mas linha não toca = mesmo regime).
    if g_zero and not s_zero:
        return ProfileType.PT_1

    # ─── Mistura: parte grounded + parte suspended (touchdown) ───────
    if has_slope:
        # PT_7: touchdown em rampa (caso F5.3 do AncoPlat).
        return ProfileType.PT_7

    # Plano: distinguir PT_2 (T_anchor != 0) de PT_3 (T_anchor = 0).
    if T_anc > _EPS_TENSION_N:
        return ProfileType.PT_2
    return ProfileType.PT_3
