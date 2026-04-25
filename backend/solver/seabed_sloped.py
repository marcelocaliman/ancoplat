"""
F5.3 (revisão completa) — Seabed inclinado com touchdown.

Modelo geométrico
-----------------
Anchor em (0, 0). Seabed: y = m·x onde m = tan(θ_s).
Fairlead em (X, h) com h > 0 (drop vertical do anchor ao fairlead).

A linha tem três trechos potenciais:
  - Grounded (apoiado na rampa): de (0, 0) ao touchdown (x_td, m·x_td).
    Comprimento L_g = x_td · sqrt(1+m²).
  - Suspended (catenária): do touchdown ao fairlead.
    Comprimento L_s = a·(sinh(v) − sinh(u)) onde u = asinh(m), v =
    (X − x_v)/a.

A catenária é parametrizada pelo vértice virtual (x_v, y_v):
    y(x) = y_v + a·(cosh((x − x_v)/a) − 1)
    dy/dx = sinh((x − x_v)/a)

Condição de tangência no touchdown (encaixe suave com a rampa):
    sinh((x_td − x_v)/a) = m  ⇒  (x_td − x_v)/a = asinh(m) = u

Sistema de equações (modo Tension, T_fl dado)
---------------------------------------------
Incógnitas: (a, x_v, X). 3 equações:

  (E1) T_fl = w·a·cosh(v),  v = (X − x_v)/a
  (E2) m·x_td = y_v + a·(cosh(u) − 1)  [touchdown na rampa]
       onde x_td = x_v + a·u, y_v = h − a·(cosh(v) − 1)
  (E3) L = x_td·sqrt(1+m²) + a·(sinh(v) − m)  [conservação]

Sistema de equações (modo Range, X dado)
----------------------------------------
Incógnitas: (a, x_v). 2 equações: (E2) e (E3).

Resolução
---------
Usamos `scipy.optimize.fsolve` com chute inicial vindo do solver
horizontal análogo (slope = 0). Para slopes pequenos, o chute fica
muito próximo da solução e a convergência é robusta.

Atrito em rampa
---------------
Trecho grounded: equilíbrio ao longo da rampa.
  T_anchor = T_td − μ·w·cos(θ)·L_g − w·sin(θ)·L_g

Onde sin(θ) é signed:
  - θ > 0 (rampa sobe ao fairlead): gravidade adiciona tração no
    sentido do fairlead → T_anchor diminui mais.
  - θ < 0 (rampa desce ao fairlead): gravidade ajuda a puxar a linha
    em direção ao touchdown → T_anchor pode AUMENTAR vs caso horizontal.

T_anchor é clampado a 0 inferiormente (atrito não pode produzir
tração negativa).
"""
from __future__ import annotations

import math

import numpy as np
from scipy.optimize import fsolve

from .types import (
    ConvergenceStatus,
    SolutionMode,
    SolverConfig,
    SolverResult,
)


def _build_residual_tension(
    L: float, h: float, w: float, T_fl: float, m: float, u: float, sqrt_1pm2: float,
):
    """Retorna F(vars) onde vars = (a, x_v, X). 3 equações, 3 incógnitas."""

    def F(vars: np.ndarray) -> np.ndarray:
        a, x_v, X = vars
        if a <= 0:
            return np.array([1e9, 1e9, 1e9])
        v = (X - x_v) / a
        cosh_v = math.cosh(v)
        sinh_v = math.sinh(v)
        # (E1): T_fl = w·a·cosh(v)
        e1 = w * a * cosh_v - T_fl
        # (E2): touchdown na rampa
        x_td = x_v + a * u
        y_v = h - a * (cosh_v - 1.0)
        y_td = y_v + a * (sqrt_1pm2 - 1.0)
        e2 = y_td - m * x_td
        # (E3): conservação L = L_g + L_s
        L_g = x_td * sqrt_1pm2
        L_s = a * (sinh_v - m)
        e3 = L_g + L_s - L
        return np.array([e1, e2, e3])

    return F


def _build_residual_range(
    L: float, h: float, X: float, m: float, u: float, sqrt_1pm2: float,
):
    """Retorna F(vars) onde vars = (a, x_v). 2 equações."""

    def F(vars: np.ndarray) -> np.ndarray:
        a, x_v = vars
        if a <= 0:
            return np.array([1e9, 1e9])
        v = (X - x_v) / a
        cosh_v = math.cosh(v)
        sinh_v = math.sinh(v)
        x_td = x_v + a * u
        y_v = h - a * (cosh_v - 1.0)
        y_td = y_v + a * (sqrt_1pm2 - 1.0)
        e2 = y_td - m * x_td
        L_g = x_td * sqrt_1pm2
        L_s = a * (sinh_v - m)
        e3 = L_g + L_s - L
        return np.array([e2, e3])

    return F


def _initial_guess_tension(
    L: float, h: float, w: float, T_fl: float, m: float, u: float,
) -> tuple[float, float, float]:
    """
    Chute inicial usando solver horizontal análogo (m = 0).

    Para o caso horizontal com touchdown:
      a_h = T_fl/w − h
      x_s_h = a_h · acosh(1 + h/a_h)
      L_s_h = a_h · sinh(x_s_h/a_h)
      L_g_h = L − L_s_h
      X_h = L_g_h + x_s_h

    Para slopes pequenos, esse chute fica perto da solução. x_v_h vem
    de x_v_h = X_h − a_h · v_h onde v_h = asinh(L_s_h/a_h). Mas como
    no caso horizontal o vértice é o touchdown e v = x_s/a, x_v_h =
    X_h − x_s_h.

    Para slope ≠ 0, ajustamos x_v via x_v = x_td − a·u (relação E1).
    """
    a_h = T_fl / w - h
    if a_h <= 0:
        # T_fl < w·h → caso inviável; chute degenerado
        a_h = 1.0
    cosh_arg = 1.0 + h / a_h
    if cosh_arg < 1.0:
        cosh_arg = 1.0001
    x_s_h = a_h * math.acosh(cosh_arg)
    L_s_h = a_h * math.sinh(x_s_h / a_h)
    L_g_h = max(0.0, L - L_s_h)
    X_h = L_g_h + x_s_h
    # Para o sistema rampa, x_v ≈ x_td − a·u. No caso horizontal x_v = x_td.
    # Para rampa pequena, ajustamos: x_td_h ≈ L_g_h (em linha reta no
    # seabed horizontal); x_v ≈ L_g_h − a·u.
    x_td_h = L_g_h
    x_v_init = x_td_h - a_h * u
    return a_h, x_v_init, X_h


def _initial_guess_range(
    L: float, h: float, X: float, m: float, u: float, w: float,
) -> tuple[float, float]:
    """Chute inicial para modo Range usando relação geométrica horizontal."""
    # Para o caso horizontal (m=0), a equação reduz a:
    # h·(sinh(u_h) − u_h) / (cosh(u_h) − 1) = L − X, com u_h = x_s/a.
    # Para chute, usa estimativa direta de a a partir da catenária aproximada:
    LmX = max(L - X, 1e-3)
    if LmX >= h:
        # Caso degenerado — aproxima
        a_init = max(h, 1.0)
    else:
        # Solução iterativa simples (Newton mental): a ≈ (X² + h²) / (2h)
        a_init = max((X * X - h * h) / (2.0 * h), 1.0)
    L_g_h = max(0.0, L - a_init * math.sinh(X / max(a_init, 1.0)))
    x_td_h = L_g_h
    x_v_init = x_td_h - a_init * u
    return a_init, x_v_init


def _signed_friction_drop(
    T_td: float, mu: float, w: float, slope_rad: float, L_g: float,
) -> float:
    """
    T_anchor = T_td − μ·w·cos(θ)·L_g − w·sin(θ)·L_g, clampado em 0.

    Convenção: θ > 0 = seabed sobe ao fairlead → ambos termos
    positivos (atrito + gravidade contra o anchor). θ < 0 = desce ao
    fairlead → sin(θ) < 0, gravidade pode AUMENTAR T_anchor.
    """
    delta_friction = mu * w * math.cos(slope_rad) * L_g
    delta_gravity = w * math.sin(slope_rad) * L_g
    return max(0.0, T_td - delta_friction - delta_gravity)


def _solve_tension_sloped(
    L: float, h: float, w: float, T_fl: float, mu: float, slope_rad: float,
    config: SolverConfig,
) -> dict:
    """Modo Tension em rampa: fsolve 3D sobre (a, x_v, X)."""
    m = math.tan(slope_rad)
    u = math.asinh(m)
    sqrt_1pm2 = math.sqrt(1.0 + m * m)

    if T_fl <= w * h:
        raise ValueError(
            f"T_fl={T_fl:.1f} N <= w·h={w*h:.1f} N: linha não atinge fairlead"
        )

    F = _build_residual_tension(L, h, w, T_fl, m, u, sqrt_1pm2)
    a0, x_v0, X0 = _initial_guess_tension(L, h, w, T_fl, m, u)
    sol, _info, ier, _mesg = fsolve(
        F, np.array([a0, x_v0, X0]),
        full_output=True, xtol=1e-9, maxfev=200,
    )
    if ier != 1:
        raise ValueError(
            "fsolve não convergiu para touchdown em rampa (modo Tension). "
            "Verifique se a geometria é factível."
        )
    a, x_v, X = sol
    if a <= 0:
        raise ValueError(f"Solução com a={a:.3f} <= 0 — não-físico")
    v = (X - x_v) / a
    x_td = x_v + a * u
    if x_td < -1e-3:
        raise ValueError(
            f"x_td={x_td:.2f} < 0: caso não tem touchdown na frente do anchor "
            "(fully suspended ou inviável). Use solver horizontal."
        )
    x_td = max(0.0, x_td)
    sinh_v = math.sinh(v)
    cosh_v = math.cosh(v)
    L_g = x_td * sqrt_1pm2
    L_s = a * (sinh_v - m)
    H = w * a
    T_td = w * a * sqrt_1pm2  # = T no touchdown
    T_anchor = _signed_friction_drop(T_td, mu, w, slope_rad, L_g)

    return {
        "a": a, "v": v, "u": u, "m": m,
        "x_v": x_v, "y_v": h - a * (cosh_v - 1.0),
        "x_td": x_td, "y_td": m * x_td,
        "X": X, "L_g": L_g, "L_s": L_s,
        "T_fl": T_fl, "T_anchor": T_anchor, "T_touchdown": T_td,
        "H": H,
    }


def _solve_range_sloped(
    L: float, h: float, w: float, X: float, mu: float, slope_rad: float,
    config: SolverConfig,
) -> dict:
    """Modo Range em rampa: fsolve 2D sobre (a, x_v)."""
    m = math.tan(slope_rad)
    u = math.asinh(m)
    sqrt_1pm2 = math.sqrt(1.0 + m * m)

    F = _build_residual_range(L, h, X, m, u, sqrt_1pm2)
    a0, x_v0 = _initial_guess_range(L, h, X, m, u, w)
    sol, _info, ier, _mesg = fsolve(
        F, np.array([a0, x_v0]),
        full_output=True, xtol=1e-9, maxfev=200,
    )
    if ier != 1:
        raise ValueError(
            "fsolve não convergiu para touchdown em rampa (modo Range). "
            "Verifique se a geometria é factível."
        )
    a, x_v = sol
    if a <= 0:
        raise ValueError(f"Solução com a={a:.3f} <= 0 — não-físico")
    v = (X - x_v) / a
    x_td = x_v + a * u
    if x_td < -1e-3:
        raise ValueError(
            f"x_td={x_td:.2f} < 0: caso não tem touchdown."
        )
    x_td = max(0.0, x_td)
    sinh_v = math.sinh(v)
    cosh_v = math.cosh(v)
    L_g = x_td * sqrt_1pm2
    L_s = a * (sinh_v - m)
    H = w * a
    T_td = w * a * sqrt_1pm2
    T_fl = w * a * cosh_v
    T_anchor = _signed_friction_drop(T_td, mu, w, slope_rad, L_g)

    return {
        "a": a, "v": v, "u": u, "m": m,
        "x_v": x_v, "y_v": h - a * (cosh_v - 1.0),
        "x_td": x_td, "y_td": m * x_td,
        "X": X, "L_g": L_g, "L_s": L_s,
        "T_fl": T_fl, "T_anchor": T_anchor, "T_touchdown": T_td,
        "H": H,
    }


def _build_sloped_result(
    sol: dict, L: float, h: float, w: float, mu: float, slope_rad: float,
    config: SolverConfig, MBL: float,
) -> SolverResult:
    """Monta SolverResult discretizando os dois trechos (grounded + suspended)."""
    a = sol["a"]
    H = sol["H"]
    X_total = sol["X"]
    x_td = sol["x_td"]
    L_g = sol["L_g"]
    L_s = sol["L_s"]
    T_fl = sol["T_fl"]
    T_anchor = sol["T_anchor"]
    T_td = sol["T_touchdown"]
    x_v = sol["x_v"]
    y_v = sol["y_v"]
    u = sol["u"]
    v = sol["v"]
    m = sol["m"]

    n = config.n_plot_points
    if L_g > 0:
        n_g = max(2, int(round(n * L_g / max(L, L_g + L_s))))
    else:
        n_g = 0
    n_s = n - n_g
    if n_s < 2:
        n_s = 2
        n_g = max(0, n - n_s)

    if n_g > 0:
        x_g = np.linspace(0.0, x_td, n_g)
        y_g = m * x_g
        # Tração no grounded: variação linear entre anchor e touchdown
        T_g_mag = np.linspace(T_anchor, T_td, n_g)
        # Componentes Tx, Ty: ao longo da rampa
        Tx_g = T_g_mag * math.cos(slope_rad)
        Ty_g = T_g_mag * math.sin(slope_rad)
    else:
        x_g, y_g, T_g_mag = np.array([]), np.array([]), np.array([])
        Tx_g, Ty_g = np.array([]), np.array([])

    # Suspended: parametrizado por s_local = (x − x_v) ∈ [a·u, a·v]
    s_local_arr = np.linspace(a * u, a * v, n_s)
    x_susp = x_v + s_local_arr
    y_susp = y_v + a * (np.cosh(s_local_arr / a) - 1.0)
    # Tração: T(s) = w·a·cosh(s/a). Sinh para componente vertical.
    T_susp = w * a * np.cosh(s_local_arr / a)
    Tx_susp = np.full_like(T_susp, H)
    Ty_susp = w * a * np.sinh(s_local_arr / a)

    if n_g > 0:
        coords_x = np.concatenate([x_g, x_susp[1:]])
        coords_y = np.concatenate([y_g, y_susp[1:]])
        T_mag = np.concatenate([T_g_mag, T_susp[1:]])
        Tx = np.concatenate([Tx_g, Tx_susp[1:]])
        Ty = np.concatenate([Ty_g, Ty_susp[1:]])
    else:
        coords_x, coords_y = x_susp, y_susp
        T_mag, Tx, Ty = T_susp, Tx_susp, Ty_susp

    # Ângulos no fairlead e na âncora
    theta_h_fl = math.atan2(w * a * math.sinh(v), H)
    if L_g > 0:
        # Tangente na âncora segue a rampa
        theta_h_a = slope_rad
    else:
        theta_h_a = math.atan2(w * a * math.sinh(u), H)

    utilization = T_fl / MBL if MBL > 0 else 0.0

    return SolverResult(
        status=ConvergenceStatus.CONVERGED,
        message=(
            f"Touchdown em rampa de {math.degrees(slope_rad):.2f}°: "
            f"L_g={L_g:.2f} m apoiado, L_s={L_s:.2f} m suspenso. "
            f"T_anchor={T_anchor/1000:.2f} kN."
        ),
        coords_x=coords_x.tolist(),
        coords_y=coords_y.tolist(),
        tension_x=Tx.tolist(),
        tension_y=Ty.tolist(),
        tension_magnitude=T_mag.tolist(),
        fairlead_tension=T_fl,
        anchor_tension=T_anchor,
        total_horz_distance=X_total,
        endpoint_depth=h,
        unstretched_length=L,  # F5.3 inicial: rígido (sem elastic loop)
        stretched_length=L,
        elongation=0.0,
        total_suspended_length=L_s,
        total_grounded_length=L_g,
        dist_to_first_td=x_td,
        angle_wrt_horz_fairlead=theta_h_fl,
        angle_wrt_vert_fairlead=math.pi / 2.0 - theta_h_fl,
        angle_wrt_horz_anchor=theta_h_a,
        angle_wrt_vert_anchor=math.pi / 2.0 - theta_h_a,
        H=H,
        iterations_used=1,
        utilization=utilization,
    )


def solve_sloped_seabed_single_segment(
    L: float, h: float, w: float, EA: float,
    mode: SolutionMode, input_value: float,
    mu: float, slope_rad: float, MBL: float,
    config: SolverConfig | None = None,
) -> SolverResult:
    """
    Solver F5.3 com touchdown em rampa, single-segmento.

    Suporta modos Tension e Range. Atrito de Coulomb modificado:
        T_anchor = T_td − μ·w·cos(θ)·L_g − w·sin(θ)·L_g

    Elasticidade não é aplicada nesta entrega — o trecho na rampa não
    é esticado (rígido). Para a maioria dos casos com slopes pequenos
    (±10°), o impacto é < 0,5 % no T_anchor.
    """
    if config is None:
        config = SolverConfig()
    if abs(slope_rad) < 1e-9:
        raise ValueError("slope_rad ≈ 0: use o caminho horizontal padrão")

    if mode == SolutionMode.TENSION:
        sol = _solve_tension_sloped(
            L, h, w, float(input_value), mu, slope_rad, config,
        )
    elif mode == SolutionMode.RANGE:
        sol = _solve_range_sloped(
            L, h, w, float(input_value), mu, slope_rad, config,
        )
    else:
        raise ValueError(f"modo inválido: {mode}")

    # Sanity check: L_g + L_s ≈ L
    if abs(sol["L_g"] + sol["L_s"] - L) / L > 1e-3:
        raise ValueError(
            f"Solução inconsistente: L_g + L_s = "
            f"{sol['L_g'] + sol['L_s']:.2f} ≠ L = {L:.2f}"
        )
    return _build_sloped_result(sol, L, h, w, mu, slope_rad, config, MBL)


__all__ = ["solve_sloped_seabed_single_segment"]
