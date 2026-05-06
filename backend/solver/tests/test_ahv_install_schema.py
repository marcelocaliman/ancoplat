"""
Schema do AHVInstall e BoundaryConditions.ahv_install — Sprint 2/Commit 23.

Cobre:
  • AHVInstall: bollard_pull obrigatório > 0; demais campos opcionais.
  • Defaults: deck_level=0, stern_angle=0, target_horz_distance=None.
  • BoundaryConditions.ahv_install opcional (default=None).
  • Round-trip JSON preserva todos os campos.
  • Forward-ref resolvido via model_rebuild — BoundaryConditions
    referencia AHVInstall mesmo definida abaixo dela no arquivo.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.solver.types import (
    AHVInstall,
    BoundaryConditions,
    SolutionMode,
)


# ──────────────────────────────────────────────────────────────────
# AHVInstall — campos
# ──────────────────────────────────────────────────────────────────


def test_ahv_install_minimo_so_bollard_pull() -> None:
    ahv = AHVInstall(bollard_pull=294_000.0)
    assert ahv.bollard_pull == 294_000.0
    assert ahv.deck_level_above_swl == 0.0
    assert ahv.stern_angle_deg == 0.0
    assert ahv.target_horz_distance is None


def test_ahv_install_completo() -> None:
    ahv = AHVInstall(
        bollard_pull=1_960_000.0,  # 200 te
        deck_level_above_swl=5.0,
        stern_angle_deg=15.0,
        target_horz_distance=1828.8,
    )
    assert ahv.bollard_pull == 1_960_000.0
    assert ahv.deck_level_above_swl == 5.0
    assert ahv.stern_angle_deg == 15.0
    assert ahv.target_horz_distance == 1828.8


def test_ahv_install_round_trip_json() -> None:
    ahv = AHVInstall(
        bollard_pull=294_000.0, deck_level_above_swl=3.5,
        stern_angle_deg=-10.0, target_horz_distance=1500.0,
    )
    payload = ahv.model_dump()
    ahv2 = AHVInstall.model_validate(payload)
    assert ahv2 == ahv


def test_ahv_install_bollard_pull_obrigatorio() -> None:
    with pytest.raises(ValidationError):
        AHVInstall()  # type: ignore[call-arg]


def test_ahv_install_bollard_pull_zero_invalido() -> None:
    with pytest.raises(ValidationError):
        AHVInstall(bollard_pull=0)


def test_ahv_install_bollard_pull_negativo_invalido() -> None:
    with pytest.raises(ValidationError):
        AHVInstall(bollard_pull=-1000)


def test_ahv_install_deck_level_negativo_invalido() -> None:
    with pytest.raises(ValidationError):
        AHVInstall(bollard_pull=294_000, deck_level_above_swl=-1.0)


def test_ahv_install_target_horz_distance_zero_invalido() -> None:
    with pytest.raises(ValidationError):
        AHVInstall(bollard_pull=294_000, target_horz_distance=0)


# ──────────────────────────────────────────────────────────────────
# BoundaryConditions.ahv_install
# ──────────────────────────────────────────────────────────────────


def test_boundary_sem_ahv_install_default_none() -> None:
    bc = BoundaryConditions(h=300, mode=SolutionMode.TENSION, input_value=785_000)
    assert bc.ahv_install is None


def test_boundary_com_ahv_install() -> None:
    ahv = AHVInstall(bollard_pull=294_000, target_horz_distance=1828.8)
    bc = BoundaryConditions(
        h=311, mode=SolutionMode.TENSION, input_value=294_000,
        startpoint_type="ahv", ahv_install=ahv,
    )
    assert bc.ahv_install is not None
    assert bc.ahv_install.bollard_pull == 294_000
    assert bc.startpoint_type == "ahv"


def test_boundary_round_trip_com_ahv_install() -> None:
    ahv = AHVInstall(
        bollard_pull=1_470_000.0, deck_level_above_swl=4.5,
        stern_angle_deg=12.0, target_horz_distance=1796.88,
    )
    bc = BoundaryConditions(
        h=311, mode=SolutionMode.TENSION, input_value=1_470_000.0,
        startpoint_type="ahv", ahv_install=ahv,
    )
    payload = bc.model_dump()
    bc2 = BoundaryConditions.model_validate(payload)
    assert bc2 == bc
    assert bc2.ahv_install == ahv


def test_boundary_ahv_install_forward_ref_resolvida() -> None:
    """Garantia de que `model_rebuild()` foi chamado — sem isso,
    a forward reference `Optional["AHVInstall"]` não resolveria
    e qualquer model_validate com ahv_install daria erro."""
    payload = {
        "h": 311.0, "mode": "Tension", "input_value": 1_470_000.0,
        "startpoint_type": "ahv",
        "ahv_install": {"bollard_pull": 1_470_000.0,
                        "target_horz_distance": 1796.88},
    }
    bc = BoundaryConditions.model_validate(payload)
    assert isinstance(bc.ahv_install, AHVInstall)
    assert bc.ahv_install.bollard_pull == 1_470_000.0


# ──────────────────────────────────────────────────────────────────
# Solver IGNORA campos cosméticos (deck_level, stern_angle)
# ──────────────────────────────────────────────────────────────────


def test_solver_ignora_deck_level_e_stern_angle() -> None:
    """deck_level_above_swl e stern_angle_deg são METADADOS — solver
    nunca consome em v1.1.0. Caso com e sem esses campos produz
    resultado idêntico."""
    from backend.solver.solver import solve
    from backend.solver.types import LineSegment, SeabedConfig, CriteriaProfile

    seg = LineSegment(
        length=450, w=201.1, EA=3.425e7, MBL=3.78e6,
        category="Wire", line_type="IWRCEIPS",
    )
    bc_minimal = BoundaryConditions(
        h=300, mode=SolutionMode.TENSION, input_value=785_000,
        ahv_install=AHVInstall(bollard_pull=785_000),
    )
    bc_rich = BoundaryConditions(
        h=300, mode=SolutionMode.TENSION, input_value=785_000,
        ahv_install=AHVInstall(
            bollard_pull=785_000, deck_level_above_swl=5.0,
            stern_angle_deg=20.0, target_horz_distance=350.0,
        ),
    )
    seabed = SeabedConfig(mu=0.0, slope_rad=0.0)
    r1 = solve([seg], bc_minimal, seabed=seabed,
               criteria_profile=CriteriaProfile.MVP_PRELIMINARY)
    r2 = solve([seg], bc_rich, seabed=seabed,
               criteria_profile=CriteriaProfile.MVP_PRELIMINARY)
    assert r1.fairlead_tension == r2.fairlead_tension
    assert r1.anchor_tension == r2.anchor_tension
    assert r1.total_horz_distance == r2.total_horz_distance
