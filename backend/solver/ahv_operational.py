"""
Solver AHV Operacional Mid-Line (Tier D) — Sprint 5 / Commit 44.

Modela cenário onde uma linha de ancoragem **instalada** (plataforma →
fairlead → mooring → anchor) é puxada lateralmente por um AHV via
Work Wire conectado num ponto intermediário da linha.

Diferença vs as 3 modalidades AHV existentes:

  ┌─────────────────────────────────────────────────────────────────┐
  │ SPRINT 2 (instalação simples):                                  │
  │   [AHV-fairlead] ─── linha ─── [ANCHOR]                         │
  │   bollard = T_fl direto                                         │
  ├─────────────────────────────────────────────────────────────────┤
  │ SPRINT 4 (Tier C — instalação ww endpoint):                     │
  │   [AHV-deck] ── ww ── [pega] ── linha ── [ANCHOR]               │
  │   AHV virtual no convés, ww elástico no endpoint                │
  ├─────────────────────────────────────────────────────────────────┤
  │ FASE 8 (AHV pontual mid-line):                                  │
  │   [PLAT] ── linha ─── [pega] ─── linha ── [ANCHOR]              │
  │              (carga estática F8 no pega, sem ww)                │
  ├─────────────────────────────────────────────────────────────────┤
  │ SPRINT 5 / TIER D (este módulo — operacional mid-line):         │
  │   [PLAT] ── linha ─── [pega] ─── linha ── [ANCHOR]              │
  │                          │                                       │
  │                       ww elástico                               │
  │                          │                                       │
  │                     [AHV deck na superfície]                    │
  └─────────────────────────────────────────────────────────────────┘

Pré-condições (Sprint 5):
  - LineAttachment.kind == "ahv"
  - LineAttachment.ahv_work_wire is not None
  - LineAttachment.ahv_deck_x is not None
  - position_index OR position_s_from_anchor set
  - Apenas 1 attachment com Tier D ativo (multi-AHV é v1.3+)

Algoritmo (pre-processor 2-pass com refinamento):

  1. Pass 1: resolve linha SEM ww (F8 puro com bollard/heading do
     attachment original). Obtém (X_pega, Z_pega) no array coords.
  2. Compute ww: catenária Work Wire entre (X_pega, Z_pega) e
     (X_AHV, deck_z) com mode=Range. Output: H_ww, V_ww_at_pega, T_AHV.
  3. Pass 2: substitui (bollard, heading) do attachment por
     (magnitude_resultante, angle_resultante) derivados de
     (H_ww, V_ww_at_pega). Re-roda solver com força atualizada.
  4. Converge em 1-3 iterações (Banach contraction típica).

Fallback automático para F8 puro com D025 quando:
  - Catenária ww não tem solução geométrica (chord > L_ww com strain
    inviável).
  - Iteração não converge em 5 ciclos.

Validação: 6 BC-AHV-OP-01..06 vs MoorPy Subsystem (gate rtol < 1e-2).
"""
from __future__ import annotations

import math
from typing import Optional, Sequence

from .elastic import solve_elastic_iterative
from .types import (
    BoundaryConditions,
    ConvergenceStatus,
    CriteriaProfile,
    LineAttachment,
    LineSegment,
    SeabedConfig,
    SolutionMode,
    SolverConfig,
    SolverResult,
    UtilizationLimits,
)

SOLVER_VERSION = "ahv_operational_v1.0_sprint5"

# Tolerância da iteração outer Tier D (em metros — convergência da
# posição da pega entre passes consecutivos).
PEGA_CONVERGENCE_TOL = 0.5  # m
MAX_OUTER_ITERS = 5


def has_tier_d_attachment(attachments: Sequence[LineAttachment]) -> bool:
    """True se há ≥1 attachment com Tier D ativo (ahv_work_wire set)."""
    for att in attachments:
        if att.kind == "ahv" and att.ahv_work_wire is not None:
            return True
    return False


def _find_pega_indices(
    result: SolverResult,
    att: LineAttachment,
    segments: Sequence[LineSegment],
) -> Optional[int]:
    """
    Localiza o índice do array coords_x/y onde está o ponto de pega
    do attachment AHV.

    Para attachments com `position_index` (junção entre segmentos),
    o índice no array é dado por `segment_boundaries[position_index+1]`.
    Para `position_s_from_anchor`, calcula o índice via arc length
    cumulativo nos pontos do array.
    """
    coords_x = result.coords_x or []
    coords_y = result.coords_y or []
    if len(coords_x) < 2:
        return None

    # Caso 1: position_index — junção entre segmentos.
    if att.position_index is not None:
        seg_bounds = result.segment_boundaries or []
        idx = att.position_index + 1
        if 0 < idx < len(seg_bounds):
            return seg_bounds[idx]
        # Fallback: estimar via arc length acumulado.

    # Caso 2: position_s_from_anchor — busca por arc length.
    s_target: Optional[float] = att.position_s_from_anchor
    if s_target is None and att.position_index is not None:
        # Junção entre segs[position_index] e segs[position_index+1]:
        # s = sum(L_0..L_position_index)
        s_target = sum(s.length for s in segments[: att.position_index + 1])
    if s_target is None:
        return None

    arc_cum = 0.0
    for k in range(1, len(coords_x)):
        dx = coords_x[k] - coords_x[k - 1]
        dy = coords_y[k] - coords_y[k - 1]
        arc_cum += math.hypot(dx, dy)
        if arc_cum >= s_target:
            return k
    return len(coords_x) - 1


def _compute_ww_force_at_pega(
    att: LineAttachment,
    pega_x_global: float,
    pega_z_global: float,
    config: SolverConfig,
) -> Optional[dict]:
    """
    Resolve catenária do Work Wire entre o pega (X_pega, Z_pega) e o
    convés do AHV (ahv_deck_x, ahv_deck_level) em frame plot global.

    Retorna dict com:
      H_ww: magnitude horizontal da força do ww no pega (N).
      V_ww_at_pega: componente vertical (N, positivo = puxando pra cima).
      T_AHV: tração no end B do ww (= bollard pull resultante).
      sign_x: +1 se ww puxa pega no sentido +X, -1 caso contrário.

    None se geometria do ww é inviável (chord >> L_ww com strain insano).
    """
    ww = att.ahv_work_wire
    if ww is None:
        return None
    deck_x = att.ahv_deck_x
    if deck_x is None:
        return None
    deck_z = att.ahv_deck_level or 0.0

    chord_x = deck_x - pega_x_global
    chord_z = deck_z - pega_z_global  # > 0 (deck acima do pega)
    if chord_z <= 0:
        # AHV abaixo do pega — fisicamente inválido para ww.
        return None
    abs_chord_x = abs(chord_x)
    sign_x = 1.0 if chord_x >= 0 else -1.0

    try:
        r_ww = solve_elastic_iterative(
            L=ww.length,
            h=chord_z,
            w=ww.w,
            EA=ww.EA,
            mode=SolutionMode.RANGE,
            input_value=abs_chord_x if abs_chord_x > 0.01 else 0.01,
            config=config,
            mu=0.0,
            MBL=ww.MBL,
        )
    except (ValueError, RuntimeError):
        return None
    if r_ww.status != ConvergenceStatus.CONVERGED:
        return None

    H_ww_mag = r_ww.H or 0.0
    T_pega_ww = r_ww.anchor_tension  # T no end A (pega)
    T_AHV = r_ww.fairlead_tension    # T no end B (AHV deck)
    # V_ww no end A (pega) — sempre positivo (puxando pra cima)
    v_sq = T_pega_ww * T_pega_ww - H_ww_mag * H_ww_mag
    V_ww_at_pega = math.sqrt(max(0.0, v_sq))

    # Ângulo do ww com a horizontal — usado por D026.
    angle_deg = math.degrees(math.atan2(chord_z, abs_chord_x or 0.001))

    return {
        "H_ww": H_ww_mag,
        "V_ww_at_pega": V_ww_at_pega,
        "T_AHV": T_AHV,
        "sign_x": sign_x,
        "angle_deg": angle_deg,
    }


def _att_with_replaced_force(
    original: LineAttachment,
    H_ww_signed: float,
    V_ww_at_pega: float,
) -> LineAttachment:
    """
    Cria cópia do attachment com (ahv_bollard_pull, ahv_heading_deg)
    substituídos pela resultante da força do Work Wire no pega.

    Mantém ahv_work_wire/ahv_deck_x originais para auditoria mas o
    solver downstream agora usa a força INJETADA (que reflete o
    equilíbrio físico do ww). O fluxo F8 normal (`_signed_force_2d`)
    pega esses 2 campos.

    Convenção: o ww puxa o pega COM a força resultante. Se ww está
    à direita do pega (sign_x>0), a força puxa pega na direção +X.
    Vertical: ww sempre puxa pega pra cima.
    Para o F8: ahv_heading_deg = ângulo da força no plano horizontal
    (eixo X global). Em modelo 2D plano vertical, a "componente
    horizontal" da força AHV é H_ww_signed; a vertical (V_ww) entra
    via diferente caminho. Para F8 atual ela compõe apenas o plano
    horizontal — em 2D plano vertical, modelamos V_ww como soma à
    sustentação local do pega.
    """
    bollard_eq = math.hypot(H_ww_signed, V_ww_at_pega)
    # heading_deg = ângulo no plano horizontal X-Y. No modelo 2D
    # vertical do AncoPlat, usamos heading=0 (puxando +X) ou 180
    # (puxando -X) — sem componente Y. O ângulo vertical (V_ww
    # sustentando o pega) é absorvido como uplift no equilíbrio.
    if H_ww_signed >= 0:
        heading_eq = 0.0  # +X
    else:
        heading_eq = 180.0  # -X
    return original.model_copy(update={
        "ahv_bollard_pull": max(bollard_eq, 1.0),
        "ahv_heading_deg": heading_eq,
        # Zera work_wire e deck_x para que o próximo passe pelo facade
        # solve() NÃO re-dispare Tier D (evita recursão infinita).
        "ahv_work_wire": None,
        "ahv_deck_x": None,
    })


def solve_with_ahv_operational(
    line_segments: Sequence[LineSegment],
    boundary: BoundaryConditions,
    attachments: Sequence[LineAttachment],
    seabed: SeabedConfig,
    config: Optional[SolverConfig] = None,
    criteria_profile: CriteriaProfile = CriteriaProfile.MVP_PRELIMINARY,
    user_limits: Optional[UtilizationLimits] = None,
) -> SolverResult:
    """
    Solver Tier D — AHV Operacional Mid-Line.

    Pre-processor 2-pass com refinamento iterativo. Detalhes na
    docstring do módulo.
    """
    from .solver import solve as facade_solve

    if config is None:
        config = SolverConfig()

    # Sprint 7 / Commit 59 — Localiza TODOS os attachments Tier D
    # (multi-AHV simultâneos). Loop sobre cada um na iteração outer,
    # cada um calcula sua própria força ww e injeta independentemente.
    tier_d_indices: list[int] = [
        i for i, att in enumerate(attachments)
        if att.kind == "ahv" and att.ahv_work_wire is not None
    ]
    if not tier_d_indices:
        # Não tem Tier D — não deveria ter sido chamado, mas executar
        # facade normal por safety.
        return facade_solve(
            line_segments=line_segments,
            boundary=boundary,
            seabed=seabed,
            config=config,
            criteria_profile=criteria_profile,
            user_limits=user_limits,
            attachments=attachments,
        )

    # Originais (com ww populado) usados para computar força ww em cada pass.
    original_atts: dict[int, LineAttachment] = {
        i: attachments[i] for i in tier_d_indices
    }

    # Iteração outer: pass 1 todos AHVs como F8 puro; pass 2+ cada um
    # com força ww atualizada. Convergência: max de |ΔX| + |ΔZ| de
    # TODOS os pegas < tolerância.
    prev_pegas: dict[int, tuple[float, float]] = {}
    current_attachments: list[LineAttachment] = list(attachments)
    # Limpa ww/deck_x em todos os Tier D para o pass 1 (sem recursão).
    for i in tier_d_indices:
        current_attachments[i] = original_atts[i].model_copy(update={
            "ahv_work_wire": None, "ahv_deck_x": None,
        })
    last_result: Optional[SolverResult] = None
    last_ww_data: dict[int, dict] = {}
    last_pegas: dict[int, tuple[float, float]] = {}
    fallback_reason: Optional[str] = None

    for outer in range(MAX_OUTER_ITERS):
        result = facade_solve(
            line_segments=line_segments,
            boundary=boundary,
            seabed=seabed,
            config=config,
            criteria_profile=criteria_profile,
            user_limits=user_limits,
            attachments=current_attachments,
        )
        last_result = result
        if result.status != ConvergenceStatus.CONVERGED:
            fallback_reason = (
                f"linha não converge no pass {outer + 1} "
                f"({result.message[:80]})"
            )
            break

        # Para CADA AHV Tier D: localiza pega + computa ww_data.
        coords_x = result.coords_x or []
        coords_y = result.coords_y or []
        X_total = result.total_horz_distance
        endpoint_depth = result.endpoint_depth or boundary.h

        new_pegas: dict[int, tuple[float, float]] = {}
        ww_per_ahv: dict[int, dict] = {}
        had_failure = False
        for i in tier_d_indices:
            tier_d_att = original_atts[i]
            pega_idx = _find_pega_indices(result, tier_d_att, line_segments)
            if pega_idx is None:
                fallback_reason = (
                    f"não foi possível localizar pega do AHV idx={i}"
                )
                had_failure = True
                break
            sx_pega = coords_x[pega_idx]
            sy_pega = coords_y[pega_idx]
            pega_x_global = X_total - sx_pega
            pega_z_global = sy_pega - endpoint_depth
            ww_data = _compute_ww_force_at_pega(
                tier_d_att, pega_x_global, pega_z_global, config,
            )
            if ww_data is None:
                fallback_reason = (
                    f"catenária ww (AHV idx={i}) não converge: chord "
                    f"({tier_d_att.ahv_deck_x - pega_x_global:.1f}, "
                    f"{(tier_d_att.ahv_deck_level or 0.0) - pega_z_global:.1f}) "
                    f"L_ww={tier_d_att.ahv_work_wire.length}m"
                )
                had_failure = True
                break
            new_pegas[i] = (pega_x_global, pega_z_global)
            ww_per_ahv[i] = ww_data
        if had_failure:
            break
        last_pegas = new_pegas
        last_ww_data = ww_per_ahv

        # Verifica convergência (todos os pegas) — só após 1ª iter.
        if prev_pegas:
            max_dx = max(
                abs(new_pegas[i][0] - prev_pegas[i][0]) for i in tier_d_indices
            )
            max_dz = max(
                abs(new_pegas[i][1] - prev_pegas[i][1]) for i in tier_d_indices
            )
            if max_dx < PEGA_CONVERGENCE_TOL and max_dz < PEGA_CONVERGENCE_TOL:
                # Convergiu! Anexa metadados de TODOS os AHVs.
                # Para retro-compat, _attach_ww_metadata recebe o
                # primeiro como representativo + lista completa.
                primary_idx = tier_d_indices[0]
                return _attach_ww_metadata_multi(
                    result, original_atts, ww_per_ahv,
                    new_pegas, outer + 1,
                )
        prev_pegas = new_pegas

        # Aplica força resultante em CADA AHV.
        for i in tier_d_indices:
            ww_data = ww_per_ahv[i]
            H_ww_signed = ww_data["H_ww"] * ww_data["sign_x"]
            base_clean = original_atts[i].model_copy(update={
                "ahv_work_wire": None, "ahv_deck_x": None,
            })
            current_attachments[i] = _att_with_replaced_force(
                base_clean, H_ww_signed, ww_data["V_ww_at_pega"],
            )
    # Se chegou aqui, não convergiu em MAX_OUTER_ITERS — fallback F8.
    if fallback_reason is None:
        fallback_reason = (
            f"iteração outer Tier D não convergiu em {MAX_OUTER_ITERS} ciclos"
        )
    return _build_fallback_f8(
        line_segments, boundary, attachments, seabed, config,
        criteria_profile, user_limits, fallback_reason,
    )


def _attach_ww_metadata_multi(
    result: SolverResult,
    original_atts: dict[int, LineAttachment],
    ww_per_ahv: dict[int, dict],
    pegas: dict[int, tuple[float, float]],
    iters: int,
) -> SolverResult:
    """
    Sprint 7 / Commit 59 — versão multi-AHV.

    Anexa info de TODOS os AHVs Tier D ao SolverResult. Para cada
    AHV, cita seu T_AHV e ângulo do ww. Adiciona D018 (sempre,
    com tier_d_active=True) + D026 (se algum ww raso).
    """
    n = len(ww_per_ahv)
    parts = []
    for i, ww_data in ww_per_ahv.items():
        pega_x, pega_z = pegas[i]
        parts.append(
            f"AHV idx={i}: pega=({pega_x:.1f}, {pega_z:.1f}), "
            f"T_AHV={ww_data['T_AHV']/1e3:.1f} kN, "
            f"H_ww={ww_data['H_ww']/1e3:.1f} kN, "
            f"angle={ww_data.get('angle_deg', 0):.1f}°"
        )
    msg_extra = (
        f" | Tier D operacional ({n} AHV{'s' if n > 1 else ''}) "
        f"convergiu em {iters} pass(es). " + " | ".join(parts) + "."
    )
    msg = (result.message or "") + msg_extra
    r_dict = result.model_dump()
    r_dict["message"] = msg
    r_dict["solver_version"] = SOLVER_VERSION

    diags = list(r_dict.get("diagnostics") or [])

    # Sprint 5/7 — D018 com tier_d_active=True (sempre dispara em Tier D).
    from .diagnostics import (
        D018_ahv_static_idealization,
        D026_work_wire_too_horizontal,
    )
    diags.append(
        D018_ahv_static_idealization(
            n_ahv=n, tier_d_active=True,
        ).model_dump()
    )

    # D026 para cada AHV com ww raso.
    for i, ww_data in ww_per_ahv.items():
        angle_deg = ww_data.get("angle_deg", 90.0)
        if angle_deg < 10.0:
            diags.append(
                D026_work_wire_too_horizontal(angle_deg=angle_deg).model_dump()
            )

    r_dict["diagnostics"] = diags
    return SolverResult(**r_dict)


def _attach_ww_metadata(
    result: SolverResult,
    tier_d_att: LineAttachment,
    ww_data: dict,
    pega_x: float,
    pega_z: float,
    iters: int,
) -> SolverResult:
    """
    Anexa info do Work Wire ao SolverResult para downstream + D026
    se ww estiver muito horizontal (geometria operacional incomum).
    """
    msg_extra = (
        f" | Tier D operacional convergiu em {iters} pass(es). "
        f"Pega global=({pega_x:.1f}, {pega_z:.1f}). "
        f"T_AHV={ww_data['T_AHV']/1e3:.1f} kN. "
        f"H_ww={ww_data['H_ww']/1e3:.1f} kN, "
        f"V_ww_pega={ww_data['V_ww_at_pega']/1e3:.1f} kN. "
        f"ww_angle={ww_data.get('angle_deg', 0):.1f}°."
    )
    msg = (result.message or "") + msg_extra
    r_dict = result.model_dump()
    r_dict["message"] = msg
    r_dict["solver_version"] = SOLVER_VERSION

    diags = list(r_dict.get("diagnostics") or [])

    # Sprint 5 / D018 update — tier_d_active=True (sempre dispara em
    # Tier D, mesmo padrão F8/Tier C). Decisão Q6 da Fase 8 reforçada.
    from .diagnostics import (
        D018_ahv_static_idealization,
        D026_work_wire_too_horizontal,
    )
    diags.append(
        D018_ahv_static_idealization(
            n_ahv=1, tier_d_active=True,
        ).model_dump()
    )

    # Sprint 5 / D026 — ww muito horizontal (< 10° vertical).
    angle_deg = ww_data.get("angle_deg", 90.0)
    if angle_deg < 10.0:
        diags.append(
            D026_work_wire_too_horizontal(angle_deg=angle_deg).model_dump()
        )
    r_dict["diagnostics"] = diags
    return SolverResult(**r_dict)


def _build_fallback_f8(
    line_segments: Sequence[LineSegment],
    boundary: BoundaryConditions,
    attachments: Sequence[LineAttachment],
    seabed: SeabedConfig,
    config: SolverConfig,
    criteria_profile: CriteriaProfile,
    user_limits: Optional[UtilizationLimits],
    reason: str,
) -> SolverResult:
    """
    Fallback Tier D → F8 puro. Roda solver com ahv_work_wire/ahv_deck_x
    zerados e injeta D025 (info, high) explicando.
    """
    from .solver import solve as facade_solve
    # Limpa ahv_work_wire em todos os attachments para evitar recursão.
    cleaned: list[LineAttachment] = []
    for att in attachments:
        if att.kind == "ahv" and att.ahv_work_wire is not None:
            cleaned.append(att.model_copy(update={
                "ahv_work_wire": None, "ahv_deck_x": None,
            }))
        else:
            cleaned.append(att)
    result = facade_solve(
        line_segments=line_segments,
        boundary=boundary,
        seabed=seabed,
        config=config,
        criteria_profile=criteria_profile,
        user_limits=user_limits,
        attachments=cleaned,
    )
    if result.status != ConvergenceStatus.CONVERGED:
        return result  # já tem mensagem de erro
    r_dict = result.model_dump()
    r_dict["message"] = (
        (result.message or "")
        + f" | Tier D → fallback F8 puro: {reason}. "
          "Bollard pull aplicado direto como F8 force pontual."
    )
    r_dict["solver_version"] = SOLVER_VERSION
    diags = list(r_dict.get("diagnostics") or [])
    # D025 (info, high) — fallback Tier D → F8 (helper canônico).
    from .diagnostics import D025_tier_d_fallback_f8
    diags.append(D025_tier_d_fallback_f8(fallback_reason=reason).model_dump())
    r_dict["diagnostics"] = diags
    return SolverResult(**r_dict)


__all__ = [
    "solve_with_ahv_operational",
    "has_tier_d_attachment",
    "SOLVER_VERSION",
]
