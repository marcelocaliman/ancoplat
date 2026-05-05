"""
Solver de catenária livre nas duas pontas — Anchor uplift / suspended endpoint.

Fase 7 do plano de profissionalização. Habilita âncoras elevadas do
seabed (`endpoint_grounded=False`). O modelo físico é catenária livre
clássica (PT_1 fully suspended na taxonomia MoorPy/F4) — anchor é fixo
num ponto não-grounded, linha não toca seabed por hipótese (não há
touchdown).

Convenções de coordenadas:

- Frame "solver interno" (compatível com `catenary.py`): anchor em
  (0, 0), fairlead em (X, h_drop). `h_drop` é o drop vertical
  efetivo anchor → fairlead = `endpoint_depth - startpoint_depth`.

- Frame "físico" (frame do plot e do SolverResult final): superfície
  em y=0, seabed em y=-`water_depth`, anchor em y=-`endpoint_depth`,
  fairlead em y=-`startpoint_depth`. Após resolver no frame interno,
  os coords_y são transladados subtraindo `endpoint_depth` (anchor
  fica em y=-endpoint_depth, fairlead fica em y=-endpoint_depth +
  h_drop = -startpoint_depth).

Decisões fechadas (Fase 7 / Q1, Q2, Q3, Q5):

- **Q1**: Modelo físico = catenária livre PT_1. Sem mass-spring (modelo
  dinâmico fora do escopo estático).
- **Q2**: `endpoint_depth` é Optional[float] em `BoundaryConditions`,
  required quando `endpoint_grounded=False` (validação Pydantic).
- **Q3**: MVP single-segment + sem attachments. Multi-segmento OU
  attachments + uplift levanta `NotImplementedError` específico
  registrado pelo dispatcher em `solver.py`. F7.x cobre essa extensão.
- **Q5**: Tolerância vs MoorPy = rtol=1e-2 (BC-UP-01..05).

Referências matemáticas:
- Catenária paramétrica clássica: ver `backend/solver/catenary.py`.
- Loop elástico: ver `backend/solver/elastic.py`.
- MoorPy `Catenary.py`: comparação direta — quando z (drop) é igual a
  `endpoint_depth - startpoint_depth`, AncoPlat e MoorPy resolvem o
  mesmo problema (anchor não toca seabed por hipótese estrutural,
  parametrizada em ambos pelo drop, não pela coluna d'água total).
"""
from __future__ import annotations

import math

import numpy as np
from scipy.optimize import brentq  # type: ignore[import-untyped]

from .catenary import (
    _solve_suspended_range_mode,
    _solve_suspended_tension_mode,
)


def _solve_uplift_tension_mode(
    L: float, h_drop: float, w: float, T_fl: float
) -> dict:
    """
    Variante do `_solve_suspended_tension_mode` (catenary.py) que ACEITA
    s_a < 0 para uplift fully-suspended.

    Em uplift sem touchdown disponível, o vértice virtual da catenária
    pode ficar ENTRE anchor e fairlead (linha forma "U" levemente
    descendente do anchor antes de subir ao fairlead). A versão upstream
    em catenary.py rejeita s_a < 0 com mensagem "demanda touchdown" —
    correto para grounded, mas overly restritivo em uplift onde
    touchdown é fisicamente impossível.

    Mesma matemática do upstream, sem o guard de s_a >= 0:
      R_f = T_fl/w; R_a = R_f − h_drop
      s_a = (R_f² − R_a² − L²) / (2·L)        [pode ser < 0]
      a² = R_a² − s_a²                        [precisa ser > 0]
      s_f = s_a + L; X = a·[asinh(s_f/a) − asinh(s_a/a)]
    """
    if T_fl <= w * h_drop:
        raise ValueError(
            f"T_fl={T_fl:.1f} N insuficiente para sustentar peso suspenso "
            f"w·h_drop={w * h_drop:.1f} N (caso inválido em uplift)."
        )
    R_f = T_fl / w
    R_a = R_f - h_drop  # > 0 garantido pelo teste acima
    s_a = (R_f * R_f - R_a * R_a - L * L) / (2.0 * L)
    # NOTA — sem guard `s_a >= 0`. Em uplift, s_a pode ser negativo:
    # vértice virtual entre anchor e fairlead (catenária em "U").
    a_sq = R_a * R_a - s_a * s_a
    if a_sq <= 0:
        raise ValueError(
            f"a²={a_sq:.3e} <= 0: caso degenerado (linha taut ou "
            "dados inconsistentes)."
        )
    a = math.sqrt(a_sq)
    s_f = s_a + L
    H = a * w
    # Distância horizontal: X = x(s_f) − x(s_a)
    # = a·[asinh(s_f/a) − asinh(s_a/a)]
    X = a * (math.asinh(s_f / a) - math.asinh(s_a / a))
    return {
        "a": a,
        "H": H,
        "s_a": s_a,
        "s_f": s_f,
        "X": X,
        "T_fl": T_fl,
        "T_anchor": w * R_a,
        "V_anchor": w * s_a,  # pode ser negativo
        "V_fairlead": w * s_f,
    }
from .types import (
    BoundaryConditions,
    ConvergenceStatus,
    LineSegment,
    SeabedConfig,
    SolutionMode,
    SolverConfig,
    SolverResult,
)


def solve_suspended_endpoint(
    segment: LineSegment,
    boundary: BoundaryConditions,
    seabed: SeabedConfig | None = None,
    config: SolverConfig | None = None,
) -> SolverResult:
    """
    Resolve catenária livre com anchor elevado (suspended endpoint).

    Parameters
    ----------
    segment : LineSegment
        Single-segment apenas (Q3=b). Multi-seg disparado pelo dispatcher.
    boundary : BoundaryConditions
        Deve ter `endpoint_grounded=False` e `endpoint_depth` informado
        (Pydantic já valida).
    seabed : SeabedConfig | None
        Atrito é ignorado (anchor não toca seabed). Slope é ignorado
        para o cálculo, mas reportado em `depth_at_fairlead`.
    config : SolverConfig | None
        Tolerâncias e n_plot_points.

    Returns
    -------
    SolverResult
        Status CONVERGED em casos válidos, INVALID_CASE com mensagem
        clara em casos de domínio violado pós-Pydantic (raros — Pydantic
        cobre maioria).
    """
    if config is None:
        config = SolverConfig()
    if seabed is None:
        seabed = SeabedConfig()

    # ─── Validações específicas de uplift ────────────────────────────
    if boundary.endpoint_grounded:
        return _invalid_case(
            "solve_suspended_endpoint requer endpoint_grounded=False. "
            "Use solve() facade que faz dispatch correto.",
            boundary,
        )
    if boundary.endpoint_depth is None:
        # Defesa em profundidade — Pydantic já cobre.
        return _invalid_case(
            "endpoint_depth é obrigatório quando endpoint_grounded=False.",
            boundary,
        )
    if boundary.endpoint_depth <= 0:
        return _invalid_case(
            f"endpoint_depth ({boundary.endpoint_depth}) deve ser > 0 "
            "(anchor não pode estar acima ou na superfície).",
            boundary,
        )
    if boundary.endpoint_depth > boundary.h + 1e-6:
        return _invalid_case(
            f"endpoint_depth ({boundary.endpoint_depth}) > h ({boundary.h}): "
            "anchor estaria abaixo do seabed (geometria impossível).",
            boundary,
        )

    h_drop = boundary.endpoint_depth - boundary.startpoint_depth
    if h_drop <= 1e-6:
        return _invalid_case(
            f"Drop efetivo (endpoint_depth - startpoint_depth = "
            f"{h_drop:.4f}) deve ser > 0 — anchor abaixo do fairlead.",
            boundary,
        )

    # ─── Resolve catenária livre com loop elástico ───────────────────
    L = segment.length
    w = segment.w
    EA = segment.EA

    # Pre-check: linha precisa sustentar a coluna d'água efetiva.
    if boundary.mode == SolutionMode.TENSION:
        T_fl_in = float(boundary.input_value)
        if T_fl_in <= w * h_drop:
            return _invalid_case(
                f"T_fl ({T_fl_in:.0f} N) ≤ w·h_drop ({w * h_drop:.0f} N): "
                "linha não sustenta peso até o fairlead em uplift.",
                boundary,
            )

    try:
        result_internal = _solve_with_elastic(
            L=L, h_drop=h_drop, w=w, EA=EA,
            mode=boundary.mode, input_value=boundary.input_value,
            config=config,
        )
    except (ValueError, RuntimeError) as exc:
        return _invalid_case(
            f"Solver de catenária livre não convergiu (uplift): {exc}",
            boundary,
        )

    # ─── Translada coords_y do frame solver para frame físico ────────
    # No frame interno, anchor=(0,0) e fairlead=(X, h_drop).
    # No frame físico, anchor=(0, -endpoint_depth) e fairlead=(X, -startpoint_depth).
    # → translation: y_phys = y_internal - endpoint_depth.
    coords_y_phys = [y - boundary.endpoint_depth for y in result_internal.coords_y]

    # ─── Monta SolverResult final com campos preenchidos para uplift ─
    depth_at_fairlead = boundary.h - math.tan(seabed.slope_rad) * result_internal.total_horz_distance

    # ─── D017 — uplift desprezível (Fase 7 / Q8) ────────────────────
    diagnostics_list = list(result_internal.diagnostics or [])
    uplift = boundary.h - boundary.endpoint_depth
    if 0 < uplift < 1.0:
        from .diagnostics import D017_anchor_uplift_negligible
        d017 = D017_anchor_uplift_negligible(
            endpoint_depth=boundary.endpoint_depth,
            h=boundary.h,
        )
        diagnostics_list.append(d017.model_dump())

    return result_internal.model_copy(update={
        "coords_y": coords_y_phys,
        # Campos de auditoria/UI:
        "water_depth": boundary.h,
        "startpoint_depth": boundary.startpoint_depth,
        "endpoint_depth": boundary.endpoint_depth,
        "depth_at_fairlead": depth_at_fairlead,
        "message": (
            f"Anchor uplift (Fase 7): suspended endpoint a "
            f"{boundary.endpoint_depth:.1f} m de profundidade, "
            f"uplift = {uplift:.1f} m. "
            "Catenária livre nas duas pontas (PT_1)."
        ),
        # `total_grounded_length` = 0 por hipótese (anchor não no seabed).
        "total_grounded_length": 0.0,
        # `dist_to_first_td` = None (não há touchdown).
        "dist_to_first_td": None,
        "diagnostics": diagnostics_list,
    })


def _solve_with_elastic(
    L: float,
    h_drop: float,
    w: float,
    EA: float,
    mode: SolutionMode,
    input_value: float,
    config: SolverConfig,
) -> SolverResult:
    """
    Loop elástico análogo a `elastic.solve_elastic_iterative`, mas força
    o caminho fully-suspended (sem dispatch para touchdown).

    A presença de `endpoint_grounded=False` significa anchor fixo num
    ponto elevado por hipótese — não há touchdown disponível mesmo se
    T_fl < T_fl_crit. Usar `_solve_suspended_*_mode` direto evita o
    fallback automático para `solve_with_seabed` que faria touchdown
    impossível neste caso.
    """
    if EA <= 0:
        raise ValueError("EA deve ser > 0 no modo elástico")

    # Construção do bracket para brentq.
    #
    # Em uplift fully-suspended, o L_eff válido é estreito quando drop é
    # pequeno + T_fl alto (catenária quase taut, vértice virtual passa o
    # anchor rapidamente — `_solve_suspended_tension_mode` rejeita s_a<0).
    # Por isso o teto L_hi_cap aqui é mais conservador que em
    # `solve_elastic_iterative` (que usa L*100 — adequado para grounded
    # com touchdown). Estimativa: para T_fl conhecido, L_eff ideal é
    # L * (1 + T_fl/EA) com fator de segurança 5×.
    if mode == SolutionMode.RANGE:
        X_target = float(input_value)
        L_taut = math.sqrt(X_target * X_target + h_drop * h_drop)
        L_lo = max(L, L_taut) * 1.0001
        L_hi_cap = (X_target + h_drop) * 0.9999
    else:
        L_lo = L
        T_fl_in = float(input_value)
        # L_eff_estim ≈ L * (1 + T_fl/EA). Margem 5× absorve T_mean > T_fl
        # em casos com w·L significativo.
        L_hi_cap = L * (1.0 + 5.0 * T_fl_in / EA)
        # Em qualquer caso, pelo menos L*1.001 (linha praticamente rígida)
        L_hi_cap = max(L_hi_cap, L * 1.001)

    _cache: dict = {"L_eff": None, "result": None, "T_mean": None}
    _call_count = [0]

    def _rigid_suspended(L_eff: float) -> SolverResult | None:
        try:
            if mode == SolutionMode.TENSION:
                # Usa variante uplift (aceita s_a < 0 → catenária em "U")
                sol = _solve_uplift_tension_mode(
                    L_eff, h_drop, w, float(input_value),
                )
            else:
                # Modo Range — variante upstream OK (parametrização
                # sobre `a` direto, não tem guard s_a >= 0 problemático).
                sol = _solve_suspended_range_mode(
                    L_eff, h_drop, w, float(input_value), config,
                )
        except Exception:
            return None
        return _build_internal_result(sol, L_eff, h_drop, w, config)

    def _mean_tension(r: SolverResult) -> float:
        if r.tension_magnitude:
            return float(np.mean(r.tension_magnitude))
        return r.fairlead_tension

    def F(L_eff: float) -> float:
        _call_count[0] += 1
        r = _rigid_suspended(L_eff)
        if r is None:
            return -1e12
        T_mean = _mean_tension(r)
        _cache["L_eff"] = L_eff
        _cache["result"] = r
        _cache["T_mean"] = T_mean
        return L_eff - L * (1.0 + T_mean / EA)

    f_lo = F(L_lo)
    if f_lo <= -1e11:
        raise ValueError(
            f"Caso geometricamente inviável: solver rígido falha mesmo "
            f"no L_eff mínimo ({L_lo:.1f} m)."
        )

    if f_lo > 0:
        L_eff_final = L_lo
    else:
        L_hi = min(L_hi_cap, max(L_lo, L) * 2.0)
        f_hi = F(L_hi)
        # Expansão: se F(L_hi) ainda < 0, aumenta até virar de sinal.
        expand_iter = 0
        while f_hi < 0 and L_hi < L_hi_cap and expand_iter < 20:
            L_hi = min(L_hi * 1.5, L_hi_cap)
            f_hi = F(L_hi)
            expand_iter += 1
        if f_hi < 0:
            raise ValueError(
                f"Bracket elástico não fecha em [{L_lo:.1f}, {L_hi:.1f}]. "
                "EA muito baixo para a geometria, ou caso fora do domínio."
            )
        L_eff_final = brentq(
            F, L_lo, L_hi,
            xtol=config.elastic_tolerance * L,
            maxiter=config.max_brent_iter,
        )

    # Reusa cache se L_eff_final já foi avaliado
    if _cache["L_eff"] is not None and abs(_cache["L_eff"] - L_eff_final) < 1e-9:
        result_rigid = _cache["result"]
    else:
        result_rigid = _rigid_suspended(L_eff_final)
        if result_rigid is None:
            raise ValueError(
                "Solver rígido falhou em L_eff_final apesar de bracket válido."
            )

    # Atualiza campos elásticos: stretched=L_eff_final, unstretched=L,
    # elongation=L_eff_final-L, iterations=_call_count.
    elongation = L_eff_final - L
    return result_rigid.model_copy(update={
        "stretched_length": L_eff_final,
        "unstretched_length": L,
        "elongation": elongation,
        "iterations_used": _call_count[0],
    })


def _build_internal_result(
    sol: dict,
    L: float,
    h_drop: float,
    w: float,
    config: SolverConfig,
) -> SolverResult:
    """
    Espelha `_build_result` em catenary.py mas sem mexer em campos do
    frame físico (water_depth, endpoint_depth, etc.) — esses são
    preenchidos no facade `solve_suspended_endpoint`.
    """
    a: float = sol["a"]
    s_a: float = sol["s_a"]
    s_f: float = sol["s_f"]
    H: float = sol["H"]
    X: float = sol["X"]
    T_fl: float = sol["T_fl"]
    T_anchor: float = sol["T_anchor"]

    n = config.n_plot_points
    s_phys = np.linspace(0.0, L, n)
    s_cat = s_a + s_phys

    coords_x = a * (np.arcsinh(s_cat / a) - math.asinh(s_a / a))
    coords_y = np.sqrt(a * a + s_cat * s_cat) - math.sqrt(a * a + s_a * s_a)

    tension_x = np.full(n, H)
    # Em uplift com s_a < 0 (vértice virtual entre anchor e fairlead),
    # `w·s_cat` pode ser negativo no início da linha — `tension_y` é
    # MAGNITUDE da componente vertical da força (sempre >= 0). Magnitude
    # da tração total = sqrt(H² + V²) também sempre >= 0.
    tension_y = np.abs(w * s_cat)
    tension_mag = np.sqrt(tension_x * tension_x + (w * s_cat) ** 2)

    theta_h_fl = math.atan2(w * s_f, H)
    theta_v_fl = math.pi / 2.0 - theta_h_fl
    theta_h_a = math.atan2(w * s_a, H)
    theta_v_a = math.pi / 2.0 - theta_h_a

    return SolverResult(
        status=ConvergenceStatus.CONVERGED,
        message="Anchor uplift — catenária livre fully suspended.",
        coords_x=coords_x.tolist(),
        coords_y=coords_y.tolist(),  # frame interno; translação no facade
        tension_x=tension_x.tolist(),
        tension_y=tension_y.tolist(),
        tension_magnitude=tension_mag.tolist(),
        fairlead_tension=T_fl,
        anchor_tension=T_anchor,
        total_horz_distance=X,
        endpoint_depth=h_drop,  # placeholder; facade reescreve com endpoint_depth real
        unstretched_length=L,
        stretched_length=L,
        elongation=0.0,
        total_suspended_length=L,
        total_grounded_length=0.0,
        dist_to_first_td=None,
        angle_wrt_horz_fairlead=theta_h_fl,
        angle_wrt_vert_fairlead=theta_v_fl,
        angle_wrt_horz_anchor=theta_h_a,
        angle_wrt_vert_anchor=theta_v_a,
        H=H,
        iterations_used=0,
        utilization=0.0,
    )


def _invalid_case(message: str, boundary: BoundaryConditions) -> SolverResult:
    """SolverResult INVALID_CASE preservando metadados geométricos do input."""
    return SolverResult(
        status=ConvergenceStatus.INVALID_CASE,
        message=message,
        water_depth=boundary.h,
        startpoint_depth=boundary.startpoint_depth,
        endpoint_depth=boundary.endpoint_depth or boundary.h,
    )


__all__ = ["solve_suspended_endpoint"]
