"""
Testes de schema do `BoundaryConditions.endpoint_depth` (Fase 7 / Q2).

AC:
  - endpoint_grounded=True (default): endpoint_depth=None aceito; equiv. a omitir.
  - endpoint_grounded=False sem endpoint_depth → ValidationError claro.
  - endpoint_grounded=False com endpoint_depth válido (0 < depth ≤ h) → OK.
  - endpoint_depth ≤ 0 → ValidationError ("anchor não pode estar acima ou na superfície").
  - endpoint_depth > h → ValidationError ("anchor estaria abaixo do seabed").
  - Round-trip Pydantic preserva endpoint_depth.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.solver.types import BoundaryConditions, SolutionMode


def _bc(**kwargs) -> BoundaryConditions:
    base = dict(
        h=300.0,
        mode=SolutionMode.TENSION,
        input_value=500_000.0,
    )
    base.update(kwargs)
    return BoundaryConditions(**base)


# ─── grounded (default) ───────────────────────────────────────────


def test_grounded_default_accepts_no_endpoint_depth():
    bc = _bc()  # endpoint_grounded=True default
    assert bc.endpoint_grounded is True
    assert bc.endpoint_depth is None


def test_grounded_explicit_no_endpoint_depth():
    bc = _bc(endpoint_grounded=True)
    assert bc.endpoint_depth is None


# ─── suspended (uplift) — Q2 ─────────────────────────────────────


def test_suspended_without_endpoint_depth_rejected():
    """endpoint_grounded=False sem endpoint_depth → erro claro."""
    with pytest.raises(ValidationError, match="endpoint_depth é obrigatório"):
        _bc(endpoint_grounded=False)  # endpoint_depth=None implícito


def test_suspended_with_valid_endpoint_depth():
    """endpoint_grounded=False + endpoint_depth=250 em h=300 → 50m uplift."""
    bc = _bc(endpoint_grounded=False, endpoint_depth=250.0)
    assert bc.endpoint_grounded is False
    assert bc.endpoint_depth == 250.0


def test_suspended_endpoint_depth_zero_rejected():
    """endpoint_depth=0 (anchor na superfície) → erro de domínio."""
    with pytest.raises(ValidationError, match="deve ser > 0"):
        _bc(endpoint_grounded=False, endpoint_depth=0.0)


def test_suspended_endpoint_depth_negative_rejected():
    """endpoint_depth=-50 (anchor acima da superfície) → erro de domínio."""
    with pytest.raises(ValidationError, match="deve ser > 0"):
        _bc(endpoint_grounded=False, endpoint_depth=-50.0)


def test_suspended_endpoint_depth_above_h_rejected():
    """endpoint_depth > h → anchor abaixo do seabed → erro."""
    with pytest.raises(ValidationError, match="não pode exceder h"):
        _bc(endpoint_grounded=False, endpoint_depth=350.0)  # h=300


def test_suspended_endpoint_depth_equal_h_accepted():
    """endpoint_depth = h é aceito (anchor exatamente no seabed; quase-grounded)."""
    bc = _bc(endpoint_grounded=False, endpoint_depth=300.0)  # h=300
    assert bc.endpoint_depth == 300.0


def test_suspended_endpoint_depth_just_above_h_within_tolerance():
    """endpoint_depth = h + 1e-7 (dentro da tolerância) é aceito."""
    bc = _bc(endpoint_grounded=False, endpoint_depth=300.0 + 1e-7)
    assert bc.endpoint_depth > 300.0  # tolerância 1e-6 absorve


# ─── round-trip ──────────────────────────────────────────────────


def test_round_trip_preserves_endpoint_depth():
    """Serialize + deserialize preserva endpoint_depth."""
    bc = _bc(endpoint_grounded=False, endpoint_depth=200.0)
    payload = bc.model_dump(mode="json")
    assert payload["endpoint_depth"] == 200.0
    rebuilt = BoundaryConditions.model_validate(payload)
    assert rebuilt.endpoint_depth == 200.0
    assert rebuilt.endpoint_grounded is False


def test_round_trip_grounded_endpoint_depth_none():
    """Grounded preserva None — não vira 0."""
    bc = _bc()
    payload = bc.model_dump(mode="json")
    assert payload["endpoint_depth"] is None
    rebuilt = BoundaryConditions.model_validate(payload)
    assert rebuilt.endpoint_depth is None


# ─── BC-UP-01..05 payload smoke ───────────────────────────────────


@pytest.mark.parametrize(
    "case_id,h,endpoint_depth,uplift",
    [
        ("BC-UP-01", 300.0, 250.0, 50.0),    # moderado
        ("BC-UP-02", 300.0, 200.0, 100.0),   # severo
        ("BC-UP-03", 300.0, 295.0, 5.0),     # quase-grounded
        ("BC-UP-04", 250.0, 50.0, 200.0),    # próximo surface
        ("BC-UP-05", 300.0, 200.0, 100.0),   # taut + uplift (mesmas dims, EA grande)
    ],
)
def test_bc_up_payloads_validam(case_id, h, endpoint_depth, uplift):
    """Os 5 BCs canônicos passam pelo schema."""
    del case_id  # presente para auditoria
    bc = _bc(h=h, endpoint_grounded=False, endpoint_depth=endpoint_depth)
    actual_uplift = bc.h - bc.endpoint_depth
    assert abs(actual_uplift - uplift) < 1e-6
