"""
Testes do `current_discretizer` (Sprint 1 / v1.1.0 / Commit 5).

Função pura, opt-in. Solver não a chama. Tests garantem:
  • Discretização uniforme (V constante) → forças iguais.
  • Discretização linear → forças crescem com V².
  • Total drag bate com cálculo manual (rtol < 1e-9).
  • n_slices respeitado; AHVs ordenados por position_s.
  • Edge cases: speed=0 zona descartada; n=1 funciona.
  • Validação dos args (ValueError em cada branch).
  • Interpolação V(z) e nearest_heading: testes unitários.
"""
from __future__ import annotations

import math

import pytest
from pydantic import ValidationError

from backend.solver.current_discretizer import (
    DEFAULT_DRAG_COEFFICIENT,
    DEFAULT_WATER_DENSITY,
    _interp_speed,
    _nearest_heading,
    discretize_current_profile,
    total_drag_force,
)
from backend.solver.types import CurrentLayer, CurrentProfile


def _uniform_profile(speed: float = 1.0) -> CurrentProfile:
    return CurrentProfile(layers=[CurrentLayer(depth=0.0, speed=speed)])


def _linear_profile(v_top: float = 1.5, v_bot: float = 0.0) -> CurrentProfile:
    return CurrentProfile(
        layers=[
            CurrentLayer(depth=0.0, speed=v_top),
            CurrentLayer(depth=300.0, speed=v_bot),
        ],
    )


# ──────────────────────────────────────────────────────────────────
# _interp_speed
# ──────────────────────────────────────────────────────────────────


def test_interp_speed_em_layer_exato() -> None:
    layers = [CurrentLayer(depth=0.0, speed=1.5),
              CurrentLayer(depth=300.0, speed=0.5)]
    assert _interp_speed(layers, 0.0) == 1.5
    assert _interp_speed(layers, 300.0) == 0.5


def test_interp_speed_linear() -> None:
    layers = [CurrentLayer(depth=0.0, speed=1.0),
              CurrentLayer(depth=100.0, speed=0.0)]
    assert _interp_speed(layers, 50.0) == pytest.approx(0.5)


def test_interp_speed_clamp_acima_e_abaixo() -> None:
    layers = [CurrentLayer(depth=10.0, speed=2.0),
              CurrentLayer(depth=20.0, speed=1.0)]
    assert _interp_speed(layers, 0.0) == 2.0   # acima do topo → clamp
    assert _interp_speed(layers, 999.0) == 1.0  # abaixo do fundo → clamp


def test_interp_speed_uniforme_1_layer() -> None:
    layers = [CurrentLayer(depth=0.0, speed=0.7)]
    assert _interp_speed(layers, 0.0) == 0.7
    assert _interp_speed(layers, 100.0) == 0.7


# ──────────────────────────────────────────────────────────────────
# _nearest_heading
# ──────────────────────────────────────────────────────────────────


def test_nearest_heading_pega_layer_mais_proxima() -> None:
    layers = [
        CurrentLayer(depth=0.0, speed=1.0, heading_deg=0.0),
        CurrentLayer(depth=100.0, speed=0.5, heading_deg=90.0),
        CurrentLayer(depth=300.0, speed=0.1, heading_deg=180.0),
    ]
    assert _nearest_heading(layers, 0.0) == 0.0
    assert _nearest_heading(layers, 50.0) == 0.0  # mais próximo do topo
    assert _nearest_heading(layers, 60.0) == 90.0  # mais próximo do meio
    assert _nearest_heading(layers, 200.0) == 90.0  # mais próximo do meio
    assert _nearest_heading(layers, 250.0) == 180.0  # mais próximo do fundo


# ──────────────────────────────────────────────────────────────────
# discretize_current_profile — comportamento físico
# ──────────────────────────────────────────────────────────────────


def test_discretize_uniforme_forcas_iguais() -> None:
    p = _uniform_profile(speed=1.0)
    ahvs = discretize_current_profile(
        p, line_diameter=0.1, total_arc_length=600.0,
        water_depth=300.0, n_slices=10,
    )
    assert len(ahvs) == 10
    forces = [a.ahv_bollard_pull for a in ahvs]
    assert all(f == pytest.approx(forces[0], rel=1e-12) for f in forces)


def test_discretize_total_bate_calculo_manual() -> None:
    """∑ F_i = 0.5 · ρ · Cd · D · L · V² para perfil uniforme."""
    rho = DEFAULT_WATER_DENSITY
    cd = DEFAULT_DRAG_COEFFICIENT
    D = 0.1
    L = 600.0
    V = 1.0
    expected = 0.5 * rho * cd * D * L * V * V

    actual = total_drag_force(
        _uniform_profile(V),
        line_diameter=D, total_arc_length=L, water_depth=300.0,
        n_slices=10,
    )
    assert actual == pytest.approx(expected, rel=1e-12)


def test_discretize_linear_top_maior_que_fundo() -> None:
    """Perfil linear com V_top > V_bot → AHVs do topo têm força maior."""
    p = _linear_profile(v_top=2.0, v_bot=0.5)
    ahvs = discretize_current_profile(
        p, line_diameter=0.1, total_arc_length=600.0,
        water_depth=300.0, n_slices=4,
    )
    assert len(ahvs) == 4
    # Ordem: AHV[0] está perto da âncora (s pequeno → z pequeno → topo
    # superior — note que o mapping s→z é s_arc / L · h, então s=0
    # mapeia para z=0 (superfície) — slice mais perto da âncora
    # NÃO é o do topo. AHV[0].force > AHV[3].force porque z[0]<z[3].
    forces = [a.ahv_bollard_pull for a in ahvs]
    assert forces[0] > forces[1] > forces[2] > forces[3]


def test_discretize_position_s_monotonica() -> None:
    p = _uniform_profile(1.0)
    ahvs = discretize_current_profile(
        p, line_diameter=0.1, total_arc_length=600.0,
        water_depth=300.0, n_slices=8,
    )
    positions = [a.position_s_from_anchor for a in ahvs]
    assert positions == sorted(positions)


def test_discretize_speed_zero_zona_descartada() -> None:
    """Layers com speed=0 não geram AHVs (slice retorna F=0)."""
    p = CurrentProfile(layers=[
        CurrentLayer(depth=0.0, speed=1.0),
        CurrentLayer(depth=300.0, speed=0.0),
    ])
    ahvs = discretize_current_profile(
        p, line_diameter=0.1, total_arc_length=600.0,
        water_depth=300.0, n_slices=2,
    )
    # Slice 0: midpoint s=150, z=75 → V=interp(75, [(0,1),(300,0)]) = 0.75
    # Slice 1: midpoint s=450, z=225 → V=interp(225, …) = 0.25
    # Ambos > 0 → ambos AHVs criados.
    assert len(ahvs) == 2
    # Mas se forçamos n_slices=1 com speed=0 em todo o domínio:
    p_zero = _uniform_profile(0.0)
    ahvs_zero = discretize_current_profile(
        p_zero, line_diameter=0.1, total_arc_length=600.0,
        water_depth=300.0, n_slices=10,
    )
    assert ahvs_zero == []  # nenhum AHV criado


def test_discretize_n_slices_1() -> None:
    p = _uniform_profile(1.0)
    ahvs = discretize_current_profile(
        p, line_diameter=0.1, total_arc_length=600.0,
        water_depth=300.0, n_slices=1,
    )
    assert len(ahvs) == 1
    assert ahvs[0].position_s_from_anchor == pytest.approx(300.0)


def test_discretize_todos_kind_ahv() -> None:
    p = _uniform_profile(1.0)
    ahvs = discretize_current_profile(
        p, line_diameter=0.1, total_arc_length=600.0,
        water_depth=300.0, n_slices=5,
    )
    assert all(a.kind == "ahv" for a in ahvs)
    assert all(a.ahv_bollard_pull is not None and a.ahv_bollard_pull > 0
               for a in ahvs)
    assert all(0.0 <= (a.ahv_heading_deg or 0.0) < 360.0 for a in ahvs)


def test_discretize_name_prefix() -> None:
    p = _uniform_profile(1.0)
    ahvs = discretize_current_profile(
        p, line_diameter=0.1, total_arc_length=600.0,
        water_depth=300.0, n_slices=3, name_prefix="cur",
    )
    assert [a.name for a in ahvs] == ["cur[0]", "cur[1]", "cur[2]"]


# ──────────────────────────────────────────────────────────────────
# Cd / ρ — defaults vs overrides vs profile-level
# ──────────────────────────────────────────────────────────────────


def test_discretize_usa_defaults_quando_profile_e_override_none() -> None:
    p = _uniform_profile(1.0)
    f = total_drag_force(
        p, line_diameter=0.1, total_arc_length=600.0,
        water_depth=300.0, n_slices=1,
    )
    expected = (0.5 * DEFAULT_WATER_DENSITY * DEFAULT_DRAG_COEFFICIENT
                * 0.1 * 600.0 * 1.0)
    assert f == pytest.approx(expected, rel=1e-12)


def test_discretize_usa_profile_drag_coefficient_quando_set() -> None:
    p = CurrentProfile(
        layers=[CurrentLayer(depth=0.0, speed=1.0)],
        drag_coefficient=2.0,  # 2× o default
    )
    f = total_drag_force(
        p, line_diameter=0.1, total_arc_length=600.0,
        water_depth=300.0, n_slices=1,
    )
    expected = (0.5 * DEFAULT_WATER_DENSITY * 2.0 * 0.1 * 600.0 * 1.0)
    assert f == pytest.approx(expected, rel=1e-12)


def test_discretize_override_tem_precedencia_sobre_profile() -> None:
    p = CurrentProfile(
        layers=[CurrentLayer(depth=0.0, speed=1.0)],
        drag_coefficient=2.0,
        water_density=2000.0,
    )
    f = total_drag_force(
        p, line_diameter=0.1, total_arc_length=600.0,
        water_depth=300.0, n_slices=1,
        cd_override=1.0, rho_override=1000.0,
    )
    expected = 0.5 * 1000.0 * 1.0 * 0.1 * 600.0 * 1.0
    assert f == pytest.approx(expected, rel=1e-12)


# ──────────────────────────────────────────────────────────────────
# Validação de args
# ──────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("kwargs", [
    {"n_slices": 0},
    {"n_slices": -1},
    {"line_diameter": 0.0},
    {"line_diameter": -0.1},
    {"total_arc_length": 0.0},
    {"total_arc_length": -100.0},
    {"water_depth": 0.0},
    {"water_depth": -10.0},
    {"cd_override": 0.0},
    {"cd_override": -1.0},
    {"rho_override": 0.0},
    {"rho_override": -1000.0},
])
def test_discretize_arg_invalido(kwargs: dict) -> None:
    base = dict(
        line_diameter=0.1, total_arc_length=600.0,
        water_depth=300.0, n_slices=10,
    )
    base.update(kwargs)
    with pytest.raises(ValueError):
        discretize_current_profile(_uniform_profile(1.0), **base)


# ──────────────────────────────────────────────────────────────────
# Invariante: chamar discretize NÃO mexe no caso original
# ──────────────────────────────────────────────────────────────────


def test_discretize_nao_modifica_profile_original() -> None:
    p = CurrentProfile(
        layers=[CurrentLayer(depth=0.0, speed=1.5),
                CurrentLayer(depth=300.0, speed=0.1)],
        drag_coefficient=1.5,
    )
    snapshot = p.model_dump()
    _ = discretize_current_profile(
        p, line_diameter=0.1, total_arc_length=600.0,
        water_depth=300.0, n_slices=5,
    )
    assert p.model_dump() == snapshot
