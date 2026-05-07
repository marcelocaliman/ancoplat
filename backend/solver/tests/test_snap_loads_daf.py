"""
Snap loads via DAF tabelado — Sprint 7 / Commits 61-63.

Cobre:
  - Schema BoundaryConditions.snap_load_daf opt-in (None default).
  - Validador Pydantic: range [1.0, 5.0].
  - Solver multiplica T_fairlead/T_anchor por DAF antes de retornar.
  - D028 dispara sempre que DAF > 1.0.
  - DAF None ou 1.0 → comportamento legado (sem multiplicação, sem D028).
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.solver.diagnostics import D028_snap_loads_applied
from backend.solver.solver import solve as facade_solve
from backend.solver.types import (
    BoundaryConditions,
    LineSegment,
    SeabedConfig,
    SolutionMode,
    SolverConfig,
)


# ──────────────────────────────────────────────────────────────────
# Schema validators
# ──────────────────────────────────────────────────────────────────


def test_boundary_snap_load_daf_default_none() -> None:
    bc = BoundaryConditions(
        h=200.0, mode=SolutionMode.TENSION, input_value=500_000.0,
        startpoint_depth=0.0, endpoint_grounded=True,
    )
    assert bc.snap_load_daf is None


def test_boundary_snap_load_daf_aceita_valores_validos() -> None:
    for daf in [1.0, 1.5, 2.0, 2.5, 3.0, 5.0]:
        bc = BoundaryConditions(
            h=200.0, mode=SolutionMode.TENSION, input_value=500_000.0,
            startpoint_depth=0.0, endpoint_grounded=True,
            snap_load_daf=daf,
        )
        assert bc.snap_load_daf == daf


@pytest.mark.parametrize("daf", [0.5, 0.99, -1.0])
def test_boundary_snap_load_daf_rejeita_menor_que_1(daf: float) -> None:
    with pytest.raises(ValidationError, match="greater than or equal to 1"):
        BoundaryConditions(
            h=200.0, mode=SolutionMode.TENSION, input_value=500_000.0,
            startpoint_depth=0.0, endpoint_grounded=True,
            snap_load_daf=daf,
        )


@pytest.mark.parametrize("daf", [5.1, 10.0, 100.0])
def test_boundary_snap_load_daf_rejeita_maior_que_5(daf: float) -> None:
    with pytest.raises(ValidationError, match="less than or equal to 5"):
        BoundaryConditions(
            h=200.0, mode=SolutionMode.TENSION, input_value=500_000.0,
            startpoint_depth=0.0, endpoint_grounded=True,
            snap_load_daf=daf,
        )


# ──────────────────────────────────────────────────────────────────
# D028 helper
# ──────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("daf,expected_regime", [
    (1.5, "calma"),
    (2.0, "média"),
    (2.5, "severa"),
    (3.0, "severa"),
])
def test_d028_titulos_por_regime(daf: float, expected_regime: str) -> None:
    diag = D028_snap_loads_applied(daf=daf)
    assert diag.code == "D028_SNAP_LOADS_APPLIED"
    assert diag.severity == "warning"
    assert expected_regime in diag.title.lower()


def test_d028_extreme_regime() -> None:
    diag = D028_snap_loads_applied(daf=4.5)
    assert "extremo" in diag.cause.lower() or "extremo" in diag.title.lower()


# ──────────────────────────────────────────────────────────────────
# Integração — solver multiplica e dispara D028
# ──────────────────────────────────────────────────────────────────


def _solve_basic(daf: float | None) -> "object":
    seg = LineSegment(
        length=1000.0, w=170.0, EA=5.5e8, MBL=6.5e6, category="Wire",
    )
    bc = BoundaryConditions(
        h=200.0, mode=SolutionMode.TENSION, input_value=500_000.0,
        startpoint_depth=0.0, endpoint_grounded=True,
        snap_load_daf=daf,
    )
    return facade_solve(
        line_segments=[seg], boundary=bc,
        seabed=SeabedConfig(), config=SolverConfig(),
    )


def test_solver_daf_none_nao_multiplica() -> None:
    """Default (DAF None): comportamento legado preservado."""
    result = _solve_basic(daf=None)
    assert result.fairlead_tension == pytest.approx(500_000.0, rel=1e-6)
    diag_codes = {d.get("code") for d in (result.diagnostics or [])}
    assert "D028_SNAP_LOADS_APPLIED" not in diag_codes


def test_solver_daf_1_nao_multiplica() -> None:
    """DAF = 1.0: equivale a estático puro, sem D028."""
    result = _solve_basic(daf=1.0)
    assert result.fairlead_tension == pytest.approx(500_000.0, rel=1e-6)
    diag_codes = {d.get("code") for d in (result.diagnostics or [])}
    assert "D028_SNAP_LOADS_APPLIED" not in diag_codes


def test_solver_daf_2_multiplica_e_dispara_d028() -> None:
    """DAF = 2.0: T_fairlead dobra, D028 disparado."""
    result_estatico = _solve_basic(daf=None)
    result_daf2 = _solve_basic(daf=2.0)
    assert result_daf2.fairlead_tension == pytest.approx(
        result_estatico.fairlead_tension * 2.0, rel=1e-3
    )
    assert result_daf2.anchor_tension == pytest.approx(
        result_estatico.anchor_tension * 2.0, rel=1e-3
    )
    diag_codes = {d.get("code") for d in (result_daf2.diagnostics or [])}
    assert "D028_SNAP_LOADS_APPLIED" in diag_codes


def test_solver_daf_recalcula_utilization() -> None:
    """Utilization recalculada com tensão escalada por DAF."""
    result_estatico = _solve_basic(daf=None)
    result_daf2 = _solve_basic(daf=2.5)
    # utilization = T_fl / MBL → escala linearmente com DAF.
    assert result_daf2.utilization == pytest.approx(
        result_estatico.utilization * 2.5, rel=1e-3
    )
