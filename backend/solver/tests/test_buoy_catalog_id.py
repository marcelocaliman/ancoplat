"""
Testes do campo `LineAttachment.buoy_catalog_id` (F6 / Q4).

AC:
  - Campo opcional, default None.
  - Aceita int >= 1.
  - **NÃO autoritativo em runtime**: solver não muda comportamento se
    presente vs ausente.
  - Round-trip via model_dump → model_validate preserva o ID.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.solver.types import LineAttachment


def _make(**kwargs) -> LineAttachment:
    base = dict(
        kind="buoy",
        submerged_force=10000.0,
        position_index=0,
        name="TestBuoy",
    )
    base.update(kwargs)
    return LineAttachment(**base)


def test_buoy_catalog_id_default_none():
    att = _make()
    assert att.buoy_catalog_id is None


def test_buoy_catalog_id_aceita_inteiro_positivo():
    att = _make(buoy_catalog_id=42)
    assert att.buoy_catalog_id == 42


def test_buoy_catalog_id_zero_rejeitado():
    with pytest.raises(ValidationError):
        _make(buoy_catalog_id=0)


def test_buoy_catalog_id_negativo_rejeitado():
    with pytest.raises(ValidationError):
        _make(buoy_catalog_id=-1)


def test_round_trip_preserva_id():
    """Serialize + deserialize preserva o ID."""
    att = _make(buoy_catalog_id=7)
    payload = att.model_dump(mode="json")
    assert payload["buoy_catalog_id"] == 7
    rebuilt = LineAttachment.model_validate(payload)
    assert rebuilt.buoy_catalog_id == 7


def test_round_trip_none_preserva_none():
    """Sem ID → JSON com None → modelo com None (não vira 0 ou string)."""
    att = _make()
    payload = att.model_dump(mode="json")
    assert payload["buoy_catalog_id"] is None
    rebuilt = LineAttachment.model_validate(payload)
    assert rebuilt.buoy_catalog_id is None


# ─── Não-autoritativo: solver não muda comportamento ────────────────


def test_solver_ignora_buoy_catalog_id():
    """
    Mesmo input físico, com vs sem `buoy_catalog_id` → mesmo solver result.
    AC: rastreabilidade não é autoritativo em runtime.
    """
    from backend.solver.solver import solve
    from backend.solver.types import (
        BoundaryConditions,
        LineSegment,
        SeabedConfig,
        SolverConfig,
        SolutionMode,
    )

    seg1 = LineSegment(length=200.0, w=1000.0, EA=4e8, MBL=5e6)
    seg2 = LineSegment(length=200.0, w=1000.0, EA=4e8, MBL=5e6)

    bc = BoundaryConditions(
        h=200.0, mode=SolutionMode.TENSION, input_value=400_000,
    )

    att_no_id = LineAttachment(
        kind="buoy", submerged_force=5000.0, position_index=0, name="X",
    )
    att_with_id = LineAttachment(
        kind="buoy", submerged_force=5000.0, position_index=0, name="X",
        buoy_catalog_id=42,
    )

    res_no = solve(
        line_segments=[seg1, seg2], boundary=bc,
        seabed=SeabedConfig(mu=0.0, slope_rad=0.0),
        config=SolverConfig(),
        attachments=[att_no_id],
    )
    res_with = solve(
        line_segments=[seg1, seg2], boundary=bc,
        seabed=SeabedConfig(mu=0.0, slope_rad=0.0),
        config=SolverConfig(),
        attachments=[att_with_id],
    )

    assert res_no.status == res_with.status
    # Confere tudo o que a runtime computa — independente de status final
    assert res_no.model_dump(exclude={"diagnostics"}) == res_with.model_dump(
        exclude={"diagnostics"}
    )
