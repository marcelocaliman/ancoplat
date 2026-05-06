"""
Testes do schema `CurrentLayer` / `CurrentProfile` e do campo
`CaseInput.current_profile` (Sprint 1 / v1.1.0 / Commit 4).

CurrentProfile é METADADO em v1.0 — solver não consome. Os testes
garantem:

  - CurrentLayer aceita depth ≥ 0 e speed ≥ 0; heading no range [0, 360).
  - CurrentProfile exige ≥ 1 layer e aceita ≤ 20 layers.
  - Layers fora de ordem por depth → ValidationError.
  - Layers com depths duplicados → ValidationError.
  - drag_coefficient e water_density rejeitam ≤ 0.
  - Round-trip preserva todos os campos.
  - CaseInput.current_profile opcional (default None).
  - Solver IGNORA: caso com/sem CurrentProfile produz resultado idêntico.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.solver.types import CurrentLayer, CurrentProfile


# ──────────────────────────────────────────────────────────────────
# CurrentLayer
# ──────────────────────────────────────────────────────────────────


def test_current_layer_minimo() -> None:
    lyr = CurrentLayer(depth=0.0, speed=0.5)
    assert lyr.depth == 0.0
    assert lyr.speed == 0.5
    assert lyr.heading_deg == 0.0  # default


def test_current_layer_round_trip() -> None:
    lyr = CurrentLayer(depth=100.0, speed=1.2, heading_deg=45.0)
    assert CurrentLayer.model_validate(lyr.model_dump()) == lyr


def test_current_layer_depth_negativo_invalido() -> None:
    with pytest.raises(ValidationError):
        CurrentLayer(depth=-1.0, speed=0.5)


def test_current_layer_speed_negativo_invalido() -> None:
    with pytest.raises(ValidationError):
        CurrentLayer(depth=0.0, speed=-0.1)


@pytest.mark.parametrize("heading", [-1.0, 360.0, 720.0])
def test_current_layer_heading_fora_de_range_invalido(heading: float) -> None:
    with pytest.raises(ValidationError):
        CurrentLayer(depth=0.0, speed=1.0, heading_deg=heading)


# ──────────────────────────────────────────────────────────────────
# CurrentProfile
# ──────────────────────────────────────────────────────────────────


def test_current_profile_uniforme_1_layer() -> None:
    p = CurrentProfile(layers=[CurrentLayer(depth=0.0, speed=1.0)])
    assert len(p.layers) == 1


def test_current_profile_linear_2_layers() -> None:
    p = CurrentProfile(
        layers=[
            CurrentLayer(depth=0.0, speed=1.5),
            CurrentLayer(depth=300.0, speed=0.2),
        ],
    )
    assert p.layers[0].depth < p.layers[1].depth


def test_current_profile_lista_vazia_invalida() -> None:
    with pytest.raises(ValidationError):
        CurrentProfile(layers=[])


def test_current_profile_layers_excede_20() -> None:
    layers = [CurrentLayer(depth=float(i), speed=1.0) for i in range(21)]
    with pytest.raises(ValidationError):
        CurrentProfile(layers=layers)


def test_current_profile_layers_fora_de_ordem_invalido() -> None:
    with pytest.raises(ValidationError, match="ordenado"):
        CurrentProfile(
            layers=[
                CurrentLayer(depth=300.0, speed=0.5),
                CurrentLayer(depth=0.0, speed=1.5),  # superfície depois do fundo
            ],
        )


def test_current_profile_layers_duplicados_invalido() -> None:
    with pytest.raises(ValidationError, match="duplicad"):
        CurrentProfile(
            layers=[
                CurrentLayer(depth=100.0, speed=0.5),
                CurrentLayer(depth=100.0, speed=0.8),
            ],
        )


def test_current_profile_drag_coefficient_zero_invalido() -> None:
    with pytest.raises(ValidationError):
        CurrentProfile(
            layers=[CurrentLayer(depth=0.0, speed=1.0)],
            drag_coefficient=0.0,
        )


def test_current_profile_water_density_negativo_invalido() -> None:
    with pytest.raises(ValidationError):
        CurrentProfile(
            layers=[CurrentLayer(depth=0.0, speed=1.0)],
            water_density=-1.0,
        )


def test_current_profile_completo_round_trip() -> None:
    p = CurrentProfile(
        layers=[
            CurrentLayer(depth=0.0, speed=1.5, heading_deg=45.0),
            CurrentLayer(depth=100.0, speed=0.8, heading_deg=45.0),
            CurrentLayer(depth=300.0, speed=0.1, heading_deg=45.0),
        ],
        drag_coefficient=1.2,
        water_density=1025.0,
    )
    p2 = CurrentProfile.model_validate(p.model_dump())
    assert p2 == p


# ──────────────────────────────────────────────────────────────────
# CaseInput.current_profile — opcional + invariante "solver ignora"
# ──────────────────────────────────────────────────────────────────


def test_caseinput_aceita_current_profile_opcional() -> None:
    from backend.api.schemas.cases import CaseInput
    from backend.api.tests._fixtures import BC01_LIKE_INPUT

    ci = CaseInput.model_validate(BC01_LIKE_INPUT)
    assert ci.current_profile is None


def test_caseinput_round_trip_com_current_profile() -> None:
    from backend.api.schemas.cases import CaseInput
    from backend.api.tests._fixtures import BC01_LIKE_INPUT

    payload = dict(BC01_LIKE_INPUT)
    payload["current_profile"] = {
        "layers": [
            {"depth": 0.0, "speed": 1.5, "heading_deg": 45.0},
            {"depth": 300.0, "speed": 0.1, "heading_deg": 45.0},
        ],
        "drag_coefficient": 1.2,
        "water_density": 1025.0,
    }
    ci = CaseInput.model_validate(payload)
    assert ci.current_profile is not None
    assert len(ci.current_profile.layers) == 2
    ci2 = CaseInput.model_validate(ci.model_dump())
    assert ci2.current_profile == ci.current_profile


def test_solver_ignora_current_profile() -> None:
    """Caso com CurrentProfile vs sem deve produzir resultado idêntico
    em v1.0 — solver é blind ao perfil de corrente até Commit 5."""
    from copy import deepcopy

    from backend.api.schemas.cases import CaseInput
    from backend.api.tests._fixtures import BC01_LIKE_INPUT
    from backend.solver.solver import solve

    payload_sem = deepcopy(BC01_LIKE_INPUT)
    payload_com = deepcopy(BC01_LIKE_INPUT)
    payload_com["current_profile"] = {
        "layers": [
            {"depth": 0.0, "speed": 1.5},
            {"depth": 300.0, "speed": 0.1},
        ],
        "drag_coefficient": 1.2,
    }

    ci_sem = CaseInput.model_validate(payload_sem)
    ci_com = CaseInput.model_validate(payload_com)

    res_sem = solve(
        line_segments=ci_sem.segments,
        boundary=ci_sem.boundary,
        seabed=ci_sem.seabed,
        criteria_profile=ci_sem.criteria_profile,
    )
    res_com = solve(
        line_segments=ci_com.segments,
        boundary=ci_com.boundary,
        seabed=ci_com.seabed,
        criteria_profile=ci_com.criteria_profile,
    )

    assert res_sem.fairlead_tension == res_com.fairlead_tension
    assert res_sem.anchor_tension == res_com.anchor_tension
    assert res_sem.total_horz_distance == res_com.total_horz_distance
