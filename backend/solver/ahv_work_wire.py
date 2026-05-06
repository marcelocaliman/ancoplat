"""
Solver Tier C — AHV Install com Work Wire elástico físico.

Sprint 4 / Commit 35. Validado vs MoorPy Subsystem
(BC-AHV-MOORPY-01..08).

Modelagem física
─────────────────────────────────────────────────────────────────
Sistema 2D plano vertical com 3 pontos significativos:

    [AHV deck]   (X_AHV, deck_z)              ← endpoint B (bollard pull)
        |
        |  Work Wire (L_ww, EA_ww, w_ww — wire elástico)
        |
    [pega]       (X_p, Z_p)  — junção interna
         \\
          \\ Mooring (L_moor, EA_moor, w_moor — pode ter touchdown)
           \\
            v Anchor    (0, -h)               ← endpoint A

Formulação adotada (Sprint 4)
─────────────────────────────────────────────────────────────────
1. Modo TENSION para o Work Wire: bollard_pull = T no end B (input).
   Solver retorna T_pega_ww (= T no end A), H_ww, X_resultante_ww.
   Eq. de continuidade vertical garante T_pega_moor = T_pega_ww.

2. Modo TENSION para o Mooring: T_pega_moor = T no end B (= pega).
   Solver retorna H_moor, X_resultante_moor.

3. Variável livre única: Z_p (profundidade da pega). 1 equação:
        H_moor(Z_p) = H_ww(Z_p)
   → fsolve 1D, scipy.optimize.brentq quando bracket é detectável.

4. X_AHV resultante = X_resultante_moor + X_resultante_ww (output).

Cenários de fallback automático
─────────────────────────────────────────────────────────────────
Mooring com touchdown ≥ 95% do comprimento ou T_pega abaixo de
w_moor·(h+Z_p) representa o caso "mooring totalmente apoiado".
Nesse regime, o solver elastic_iterative do mooring REJEITA. Tier C
detecta e cai em Sprint 2 effective:
  - bollard_pull aplicado direto como T_fl (sem Work Wire elástico).
  - X_AHV = target_horz_distance (informativo).
  - D024 (info) informa que Tier C reduziu para Sprint 2 nesta solução.
  - Resultado preserva validade física (ww quasi-vertical é uma
    aproximação razoável quando mooring está deitado).

Pré-condições (Sprint 4)
─────────────────────────────────────────────────────────────────
  - boundary.ahv_install.work_wire is not None
  - boundary.ahv_install.target_horz_distance is not None
  - len(line_segments) == 1 (single-seg mooring; multi-seg = v1.2+)
  - boundary.endpoint_grounded == True (uplift = Commit 36)
  - len(attachments) == 0
"""
from __future__ import annotations

import math
from typing import Optional, Sequence

import numpy as np
from scipy.optimize import brentq, fsolve

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
)

SOLVER_VERSION = "ahv_work_wire_v1.0_sprint4"

# Limiar para acionar fallback Sprint 2 (mooring deitado).
# Calibrado contra MoorPy: lay ≥ 90% indica regime degenerado onde
# o sistema é frouxo no eixo X (múltiplas soluções compatíveis com
# o mesmo bollard_pull). Tier C nesse regime não acrescenta info
# sobre Sprint 2 — tanto o engenheiro quanto MoorPy não "decidem"
# X_AHV diferente para o mesmo bollard. Manter Tier C ativo nesta
# zona produziria respostas tecnicamente válidas mas divergentes
# do MoorPy (que decide via heurística de energia mínima).
GROUNDED_FALLBACK_THRESHOLD = 0.90


def _validate_tier_c_preconditions(
    line_segments: Sequence[LineSegment],
    boundary: BoundaryConditions,
    attachments: Sequence[LineAttachment],
) -> None:
    ahv = boundary.ahv_install
    if ahv is None or ahv.work_wire is None:
        raise NotImplementedError(
            "solve_with_work_wire chamado sem AHVInstall.work_wire."
        )
    if ahv.target_horz_distance is None:
        raise NotImplementedError(
            "AHVInstall.work_wire requer target_horz_distance set."
        )
    if len(line_segments) != 1:
        raise NotImplementedError(
            f"Tier C com mooring multi-segmento (n={len(line_segments)}) "
            "fica para v1.2+ — use single-segment ou aguarde."
        )
    if not boundary.endpoint_grounded:
        # Sprint 4 / Commit 36: AHV + uplift single-seg suportado.
        # Anchor virtual em (0, -endpoint_depth) com endpoint_depth < h.
        if boundary.endpoint_depth is None:
            raise NotImplementedError(
                "AHV + uplift requer boundary.endpoint_depth set "
                "(profundidade do anchor abaixo da superfície). "
                "Sem isso o solver não tem onde posicionar o anchor."
            )
        if boundary.endpoint_depth >= boundary.h:
            raise NotImplementedError(
                f"AHV + uplift: endpoint_depth ({boundary.endpoint_depth}m) "
                f"deve ser < h ({boundary.h}m). Para anchor no fundo, "
                "use endpoint_grounded=True."
            )
    if len(attachments) > 0:
        raise NotImplementedError(
            "Tier C com attachments fica para v1.2+."
        )


def _try_solve_ww(
    Z_p: float,
    deck_z: float,
    bollard_pull: float,
    ww,  # WorkWireSpec
    config: SolverConfig,
) -> Optional[dict]:
    """ww em mode TENSION com bollard_pull como input."""
    h_ww = deck_z - Z_p
    if h_ww <= 0:
        return None
    if bollard_pull <= ww.w * h_ww:
        return None  # tração insuficiente para suportar coluna
    try:
        r = solve_elastic_iterative(
            L=ww.length,
            h=h_ww,
            w=ww.w,
            EA=ww.EA,
            mode=SolutionMode.TENSION,
            input_value=bollard_pull,
            config=config,
            mu=0.0,
            MBL=ww.MBL,
        )
    except (ValueError, RuntimeError):
        return None
    if r.status != ConvergenceStatus.CONVERGED:
        return None
    return {
        "result": r,
        "T_pega": r.anchor_tension,
        "H": r.H or 0.0,
        "X_resultante": r.total_horz_distance,
    }


def _try_solve_moor(
    Z_p: float,
    h_anchor_below_surface: float,
    T_pega: float,
    seg_moor: LineSegment,
    mu_moor: float,
    config: SolverConfig,
) -> Optional[dict]:
    """
    mooring em mode TENSION com T_pega como input.

    `h_anchor_below_surface` é a profundidade do anchor abaixo da
    superfície da água — para anchor no fundo isso é `boundary.h`,
    para uplift isso é `boundary.endpoint_depth` (Commit 36).
    """
    h_moor = h_anchor_below_surface + Z_p  # Z_p < 0 → h_moor < h_anchor
    if h_moor <= 0:
        return None
    # Solver elastic_iterative valida T > w·h. Aqui tornamos a falha
    # explícita devolvendo None (em vez de propagar ValueError).
    if T_pega <= seg_moor.w * h_moor:
        return None
    try:
        r = solve_elastic_iterative(
            L=seg_moor.length,
            h=h_moor,
            w=seg_moor.w,
            EA=seg_moor.EA,
            mode=SolutionMode.TENSION,
            input_value=T_pega,
            config=config,
            mu=mu_moor,
            MBL=seg_moor.MBL,
        )
    except (ValueError, RuntimeError):
        return None
    if r.status != ConvergenceStatus.CONVERGED:
        return None
    return {
        "result": r,
        "T_anchor": r.anchor_tension,
        "H": r.H or 0.0,
        "X_resultante": r.total_horz_distance,
    }


def _build_fallback_sprint2(
    seg_moor: LineSegment,
    boundary: BoundaryConditions,
    seabed: SeabedConfig,
    config: SolverConfig,
    mu_moor: float,
    fallback_reason: str,
) -> SolverResult:
    """
    Fallback automático: trata bollard_pull como T_fl direto (Sprint 2
    effective). Útil quando mooring está totalmente apoiado e a
    catenária do work_wire não pode ser resolvida fisicamente.
    """
    ahv = boundary.ahv_install
    assert ahv is not None
    bollard_pull = ahv.bollard_pull
    h = boundary.h
    # Uplift-aware: anchor pode estar suspenso (Commit 36).
    h_anchor = (
        boundary.endpoint_depth
        if (not boundary.endpoint_grounded and boundary.endpoint_depth is not None)
        else h
    )

    # Resolve mooring SEM Work Wire — solver Sprint 2 efetivo.
    # Em uplift, fallback delega para solve_suspended_endpoint (F7).
    try:
        if boundary.endpoint_grounded:
            r = solve_elastic_iterative(
                L=seg_moor.length,
                h=h,
                w=seg_moor.w,
                EA=seg_moor.EA,
                mode=SolutionMode.TENSION,
                input_value=bollard_pull,
                config=config,
                mu=mu_moor,
                MBL=seg_moor.MBL,
            )
        else:
            from .suspended_endpoint import solve_suspended_endpoint
            r = solve_suspended_endpoint(
                segment=seg_moor,
                boundary=boundary,
                seabed=seabed,
                config=config,
            )
    except (ValueError, RuntimeError) as exc:
        return SolverResult(
            status=ConvergenceStatus.INVALID_CASE,
            message=(
                f"Tier C: fallback Sprint 2 também falhou — {exc}. "
                "Caso fisicamente inviável."
            ),
            water_depth=h,
            startpoint_depth=boundary.startpoint_depth,
            solver_version=SOLVER_VERSION,
        )
    # Anota mensagem com o motivo do fallback.
    r_dict = r.model_dump()
    r_dict["message"] = (
        f"Tier C → fallback Sprint 2: {fallback_reason}. "
        "Bollard pull aplicado direto como T_fl (Work Wire ignorado "
        "fisicamente porque mooring está deitado e ww não tem suspensão "
        "viável). D024 (info) informa o engenheiro."
    )
    r_dict["solver_version"] = SOLVER_VERSION
    # Adiciona D024 explícito (info, high confidence — fato determinístico).
    diags = list(r_dict.get("diagnostics") or [])
    diags.append({
        "code": "D024",
        "severity": "info",
        "confidence": "high",
        "title": "Tier C reduzido a Sprint 2 (mooring totalmente apoiado)",
        "message": (
            f"Tier C detectou {fallback_reason} e usou modelo Sprint 2 "
            "efetivo. Resultado equivalente: bollard pull aplicado "
            "diretamente como T_fl. Para validar Tier C completo, "
            "use cenário com mooring parcialmente suspenso."
        ),
        "suggested_changes": [],
    })
    r_dict["diagnostics"] = diags
    return SolverResult(**r_dict)


def solve_with_work_wire(
    line_segments: Sequence[LineSegment],
    boundary: BoundaryConditions,
    seabed: Optional[SeabedConfig] = None,
    config: Optional[SolverConfig] = None,
    criteria_profile: CriteriaProfile = CriteriaProfile.MVP_PRELIMINARY,
    user_limits=None,  # type: ignore[no-untyped-def]
    attachments: Sequence[LineAttachment] = (),
) -> SolverResult:
    """Solver Tier C — ver docstring do módulo."""
    if seabed is None:
        seabed = SeabedConfig()
    if config is None:
        config = SolverConfig()

    try:
        _validate_tier_c_preconditions(line_segments, boundary, attachments)
    except NotImplementedError as exc:
        return SolverResult(
            status=ConvergenceStatus.INVALID_CASE,
            message=f"Tier C: {exc}",
            water_depth=boundary.h,
            startpoint_depth=boundary.startpoint_depth,
            solver_version=SOLVER_VERSION,
        )

    seg_moor = line_segments[0]
    ahv = boundary.ahv_install
    assert ahv is not None and ahv.work_wire is not None
    ww = ahv.work_wire
    h = boundary.h
    # Profundidade do anchor abaixo da superfície (uplift se < h).
    # Quando endpoint_grounded=True (default), anchor está no fundo: h.
    # Quando False (Commit 36), anchor está em endpoint_depth.
    h_anchor = (
        boundary.endpoint_depth
        if (not boundary.endpoint_grounded and boundary.endpoint_depth is not None)
        else h
    )
    deck_z = ahv.deck_level_above_swl
    bollard_pull = ahv.bollard_pull

    mu_moor = (
        seg_moor.mu_override
        if seg_moor.mu_override is not None
        else (
            seg_moor.seabed_friction_cf
            if seg_moor.seabed_friction_cf is not None
            else seabed.mu
        )
    )

    # Cache de soluções para evitar re-solve no fsolve.
    _cache: dict = {"Z_p": None, "ww": None, "moor": None}

    def _evaluate(Z_p: float) -> Optional[tuple]:
        ww_sol = _try_solve_ww(Z_p, deck_z, bollard_pull, ww, config)
        if ww_sol is None:
            return None
        T_pega = ww_sol["T_pega"]
        moor_sol = _try_solve_moor(
            Z_p, h_anchor, T_pega, seg_moor, mu_moor, config,
        )
        if moor_sol is None:
            return None
        return ww_sol, moor_sol

    def _residual(Z_p: float) -> float:
        evald = _evaluate(Z_p)
        if evald is None:
            return 1e9  # penalidade
        ww_sol, moor_sol = evald
        _cache["Z_p"] = Z_p
        _cache["ww"] = ww_sol
        _cache["moor"] = moor_sol
        return ww_sol["H"] - moor_sol["H"]

    # ─── Tentativa de bracket-based brentq ─────────────────────────────
    # Z_p físico ∈ [-h_anchor+1, deck_z-h_ww_min]. Procuramos Z_p tal que
    # H_moor(Z_p) - H_ww(Z_p) muda de sinal. Sample ~24 pontos e detecta
    # bracket. Em uplift: pega não pode ficar abaixo do anchor virtual.
    Z_p_min = -h_anchor + 1.0
    Z_p_max = -1.0  # pega não pode estar acima da água
    samples = np.linspace(Z_p_min, Z_p_max, 24)
    bracket_found: Optional[tuple[float, float]] = None
    last_valid: Optional[tuple[float, float]] = None  # (Z_p, residual)

    for Z_p_sample in samples:
        res = _residual(float(Z_p_sample))
        if abs(res) >= 1e8:  # invalid — penalty
            last_valid = None
            continue
        if last_valid is None:
            last_valid = (float(Z_p_sample), res)
            continue
        if last_valid[1] * res < 0.0:
            bracket_found = (last_valid[0], float(Z_p_sample))
            break
        last_valid = (float(Z_p_sample), res)

    Z_p_solution: Optional[float] = None
    if bracket_found is not None:
        try:
            Z_p_solution = brentq(
                _residual, bracket_found[0], bracket_found[1],
                xtol=1e-4, rtol=1e-9, maxiter=80,
            )
        except (ValueError, RuntimeError):
            Z_p_solution = None

    # Fallback fsolve sem bracket se brentq falhar.
    if Z_p_solution is None:
        Z_p_0 = -h_anchor * 0.7
        try:
            sol_vars, info, ier, _msg = fsolve(
                lambda v: [_residual(v[0])],
                [Z_p_0], full_output=True, xtol=1e-7, maxfev=200,
            )
            if ier == 1 and abs(_residual(sol_vars[0])) < 1e3:
                Z_p_solution = float(sol_vars[0])
        except (ValueError, RuntimeError):
            pass

    # Se nada convergiu, fallback Sprint 2.
    if Z_p_solution is None:
        return _build_fallback_sprint2(
            seg_moor, boundary, seabed, config, mu_moor,
            fallback_reason=(
                "fsolve Tier C não encontrou solução válida — "
                "mooring possivelmente está totalmente apoiado em todos "
                "os Z_p candidatos"
            ),
        )

    # Re-evalua na solução para ter resultados detalhados.
    final_eval = _evaluate(Z_p_solution)
    if final_eval is None:
        return _build_fallback_sprint2(
            seg_moor, boundary, seabed, config, mu_moor,
            fallback_reason=(
                f"Tier C convergiu Z_p={Z_p_solution:.2f}m mas reavaliação "
                "produziu solução inválida"
            ),
        )
    ww_sol, moor_sol = final_eval
    r_moor = moor_sol["result"]
    r_ww = ww_sol["result"]
    Z_p = Z_p_solution
    X_p = moor_sol["X_resultante"]
    X_AHV = X_p + ww_sol["X_resultante"]

    # Detecção de fallback Sprint 2: mooring com lay_length ≥ 95% L.
    lay_pct = (
        (r_moor.total_grounded_length or 0.0) / seg_moor.length
        if seg_moor.length > 0 else 0.0
    )
    if lay_pct >= GROUNDED_FALLBACK_THRESHOLD:
        return _build_fallback_sprint2(
            seg_moor, boundary, seabed, config, mu_moor,
            fallback_reason=(
                f"mooring com touchdown {lay_pct:.0%} ≥ "
                f"{GROUNDED_FALLBACK_THRESHOLD:.0%} (linha praticamente "
                "toda apoiada — Tier C físico não diferente de Sprint 2)"
            ),
        )

    # ─── Concatenação geométrica ───────────────────────────────────────
    coords_x_moor = np.array(r_moor.coords_x or [])
    coords_y_moor = np.array(r_moor.coords_y or []) - h
    coords_x_ww = np.array(r_ww.coords_x or []) + X_p
    coords_y_ww = np.array(r_ww.coords_y or []) + Z_p

    full_x = np.concatenate([coords_x_moor, coords_x_ww]).tolist()
    full_y = np.concatenate([coords_y_moor, coords_y_ww]).tolist()
    full_tension = np.concatenate([
        np.array(r_moor.tension_magnitude or []),
        np.array(r_ww.tension_magnitude or []),
    ]).tolist()

    L_total_unstretched = seg_moor.length + ww.length
    L_total_stretched = (r_moor.stretched_length or seg_moor.length) + (
        r_ww.stretched_length or ww.length
    )
    grounded_total = r_moor.total_grounded_length or 0.0
    suspended_total = (r_moor.total_suspended_length or 0.0) + ww.length
    utilization_moor = (
        (r_moor.fairlead_tension / seg_moor.MBL) if seg_moor.MBL > 0 else 0.0
    )
    utilization_ww = (bollard_pull / ww.MBL) if ww.MBL > 0 else 0.0
    utilization = max(utilization_moor, utilization_ww)

    return SolverResult(
        status=ConvergenceStatus.CONVERGED,
        message=(
            "Tier C / AHV Work Wire físico — convergido. "
            f"Z_pega={Z_p:.1f}m, X_pega={X_p:.1f}m, X_AHV={X_AHV:.1f}m. "
            "ATENÇÃO: análise estática — não substitui análise dinâmica "
            "de instalação (snap loads, AHV motion)."
        ),
        coords_x=full_x,
        coords_y=full_y,
        tension_magnitude=full_tension,
        fairlead_tension=bollard_pull,
        anchor_tension=r_moor.anchor_tension,
        total_horz_distance=X_AHV,
        endpoint_depth=h,
        unstretched_length=L_total_unstretched,
        stretched_length=L_total_stretched,
        elongation=L_total_stretched - L_total_unstretched,
        total_suspended_length=suspended_total,
        total_grounded_length=grounded_total,
        dist_to_first_td=r_moor.dist_to_first_td,
        angle_wrt_horz_fairlead=r_ww.angle_wrt_horz_fairlead,
        angle_wrt_vert_fairlead=r_ww.angle_wrt_vert_fairlead,
        angle_wrt_horz_anchor=r_moor.angle_wrt_horz_anchor,
        angle_wrt_vert_anchor=r_moor.angle_wrt_vert_anchor,
        H=r_moor.H,
        iterations_used=0,
        utilization=utilization,
        water_depth=h,
        startpoint_depth=boundary.startpoint_depth,
        solver_version=SOLVER_VERSION,
    )


__all__ = ["solve_with_work_wire", "SOLVER_VERSION"]
