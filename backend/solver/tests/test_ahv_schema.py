"""
Testes de schema do `LineAttachment.kind="ahv"` e campos AHV (Fase 8 / Q1+Q2).

AC:
  - kind="ahv" aceita ahv_bollard_pull, ahv_heading_deg, ahv_stern_angle_deg
    (opcional), ahv_deck_level (opcional).
  - kind="ahv" sem ahv_bollard_pull → ValidationError claro.
  - kind="ahv" sem ahv_heading_deg → ValidationError claro.
  - kind="buoy" mantém validação submerged_force > 0.
  - kind="clump_weight" mantém validação submerged_force > 0.
  - Round-trip preserva todos os campos.
  - Heading_deg fora de [0, 360) → ValidationError.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.solver.types import LineAttachment


def _ahv(**kwargs) -> LineAttachment:
    base = dict(
        kind="ahv",
        position_s_from_anchor=200.0,
        ahv_bollard_pull=1_960_000.0,  # 200 te
        ahv_heading_deg=0.0,
    )
    base.update(kwargs)
    return LineAttachment(**base)


def _buoy(**kwargs) -> LineAttachment:
    base = dict(
        kind="buoy",
        submerged_force=50_000.0,
        position_s_from_anchor=200.0,
    )
    base.update(kwargs)
    return LineAttachment(**base)


# ─── kind="ahv" — happy path ────────────────────────────────────────


def test_ahv_minimal_aceito():
    """kind=ahv com bollard_pull + heading + position é o mínimo necessário."""
    att = _ahv()
    assert att.kind == "ahv"
    assert att.ahv_bollard_pull == 1_960_000.0
    assert att.ahv_heading_deg == 0.0
    assert att.ahv_stern_angle_deg is None
    assert att.ahv_deck_level is None


def test_ahv_com_metadados_opcionais():
    att = _ahv(ahv_stern_angle_deg=45.0, ahv_deck_level=8.5)
    assert att.ahv_stern_angle_deg == 45.0
    assert att.ahv_deck_level == 8.5


def test_ahv_submerged_force_default_zero_aceito():
    """submerged_force não é required em AHV — solver usa bollard_pull."""
    att = _ahv()  # default submerged_force=0
    assert att.submerged_force == 0.0


# ─── kind="ahv" — campos required ──────────────────────────────────


def test_ahv_sem_bollard_pull_rejeitado():
    with pytest.raises(ValidationError, match="ahv_bollard_pull"):
        _ahv(ahv_bollard_pull=None)


def test_ahv_bollard_pull_zero_rejeitado():
    with pytest.raises(ValidationError):
        _ahv(ahv_bollard_pull=0.0)


def test_ahv_bollard_pull_negativo_rejeitado():
    with pytest.raises(ValidationError):
        _ahv(ahv_bollard_pull=-100.0)


def test_ahv_sem_heading_rejeitado():
    with pytest.raises(ValidationError, match="ahv_heading_deg"):
        _ahv(ahv_heading_deg=None)


def test_ahv_heading_negativo_rejeitado():
    with pytest.raises(ValidationError):
        _ahv(ahv_heading_deg=-1.0)


def test_ahv_heading_360_rejeitado():
    """Range [0, 360) — 360 não é incluído."""
    with pytest.raises(ValidationError):
        _ahv(ahv_heading_deg=360.0)


def test_ahv_heading_359_99_aceito():
    att = _ahv(ahv_heading_deg=359.99)
    assert att.ahv_heading_deg == 359.99


# ─── kind="buoy" / "clump_weight" preservados ──────────────────────


def test_buoy_preserva_submerged_force_required():
    """kind=buoy ainda exige submerged_force > 0."""
    with pytest.raises(ValidationError, match="submerged_force"):
        _buoy(submerged_force=0.0)


def test_clump_weight_preserva_submerged_force_required():
    """kind=clump_weight ainda exige submerged_force > 0."""
    with pytest.raises(ValidationError, match="submerged_force"):
        LineAttachment(
            kind="clump_weight",
            submerged_force=0.0,
            position_s_from_anchor=200.0,
        )


def test_buoy_funciona_normalmente():
    att = _buoy()
    assert att.kind == "buoy"
    assert att.submerged_force == 50_000.0


# ─── Round-trip ──────────────────────────────────────────────────


def test_ahv_round_trip_preserva_todos_campos():
    """Serialize + deserialize preserva todos os campos AHV."""
    att = _ahv(
        ahv_bollard_pull=2_500_000.0,
        ahv_heading_deg=45.0,
        ahv_stern_angle_deg=30.0,
        ahv_deck_level=10.0,
    )
    payload = att.model_dump(mode="json")
    assert payload["kind"] == "ahv"
    assert payload["ahv_bollard_pull"] == 2_500_000.0
    assert payload["ahv_heading_deg"] == 45.0
    assert payload["ahv_stern_angle_deg"] == 30.0
    assert payload["ahv_deck_level"] == 10.0
    rebuilt = LineAttachment.model_validate(payload)
    assert rebuilt == att


def test_buoy_round_trip_ahv_fields_default_none():
    """Buoy continua funcionando; campos AHV ficam None no JSON."""
    att = _buoy()
    payload = att.model_dump(mode="json")
    assert payload["ahv_bollard_pull"] is None
    assert payload["ahv_heading_deg"] is None
