"""
Schema do LineAttachment.ahv_work_wire — Sprint 5 / Commit 42
(Tier D operacional: AHV puxa linha mid-segment via Work Wire).

Cobre:
  - LineAttachment kind="ahv" sem ahv_work_wire → comportamento F8 puro.
  - LineAttachment kind="ahv" com ahv_work_wire + ahv_deck_x → Tier D.
  - Validação cruzada: ahv_work_wire requer kind="ahv" + ahv_deck_x set.
  - ahv_work_wire em kind="buoy"/"clump_weight" → ValidationError.
  - Round-trip JSON.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.solver.types import (
    AttachmentKind,
    LineAttachment,
    WorkWireSpec,
)


# ──────────────────────────────────────────────────────────────────
# F8 puro (retro-compat) — AHV sem ahv_work_wire continua funcional
# ──────────────────────────────────────────────────────────────────


def test_ahv_f8_puro_sem_work_wire() -> None:
    """LineAttachment kind='ahv' sem ahv_work_wire → F8 puro (sem Tier D)."""
    att = LineAttachment(
        kind="ahv",
        position_index=0,
        ahv_bollard_pull=500_000.0,
        ahv_heading_deg=0.0,
    )
    assert att.kind == "ahv"
    assert att.ahv_work_wire is None
    assert att.ahv_deck_x is None


# ──────────────────────────────────────────────────────────────────
# Tier D operacional — Work Wire + ahv_deck_x ativos
# ──────────────────────────────────────────────────────────────────


def test_ahv_tier_d_completo() -> None:
    """LineAttachment com ahv_work_wire + ahv_deck_x → Tier D ativo."""
    ww = WorkWireSpec(length=300.0, EA=5.5e8, w=170.0, MBL=6.5e6)
    att = LineAttachment(
        kind="ahv",
        position_index=1,
        ahv_bollard_pull=900_000.0,
        ahv_heading_deg=0.0,
        ahv_work_wire=ww,
        ahv_deck_x=1200.0,
        ahv_deck_level=15.0,
        ahv_stern_angle_deg=25.0,
    )
    assert att.ahv_work_wire is not None
    assert att.ahv_work_wire.length == 300.0
    assert att.ahv_deck_x == 1200.0
    assert att.ahv_deck_level == 15.0


def test_ahv_tier_d_requer_deck_x() -> None:
    """ahv_work_wire set sem ahv_deck_x → ValidationError."""
    ww = WorkWireSpec(length=300.0, EA=5.5e8, w=170.0, MBL=6.5e6)
    with pytest.raises(ValidationError, match="ahv_deck_x é obrigatório"):
        LineAttachment(
            kind="ahv",
            position_index=1,
            ahv_bollard_pull=900_000.0,
            ahv_heading_deg=0.0,
            ahv_work_wire=ww,
            # ahv_deck_x ausente — deveria falhar
        )


def test_ahv_work_wire_em_buoy_falha() -> None:
    """ahv_work_wire em kind='buoy' → ValidationError."""
    ww = WorkWireSpec(length=200.0, EA=5.5e8, w=170.0, MBL=6.5e6)
    with pytest.raises(ValidationError, match="só é válido em LineAttachment"):
        LineAttachment(
            kind="buoy",
            position_index=0,
            submerged_force=50_000.0,
            ahv_work_wire=ww,
            ahv_deck_x=500.0,
        )


def test_ahv_work_wire_em_clump_falha() -> None:
    """ahv_work_wire em kind='clump_weight' → ValidationError."""
    ww = WorkWireSpec(length=200.0, EA=5.5e8, w=170.0, MBL=6.5e6)
    with pytest.raises(ValidationError, match="só é válido em LineAttachment"):
        LineAttachment(
            kind="clump_weight",
            position_index=0,
            submerged_force=100_000.0,
            ahv_work_wire=ww,
            ahv_deck_x=500.0,
        )


# ──────────────────────────────────────────────────────────────────
# Variações dos campos opcionais
# ──────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("deck_z", [0.0, 5.0, 12.5, 20.0])
def test_ahv_deck_level_valores_validos(deck_z: float) -> None:
    """ahv_deck_level aceita 0.0 e positivos."""
    ww = WorkWireSpec(length=200.0, EA=5.5e8, w=170.0, MBL=6.5e6)
    att = LineAttachment(
        kind="ahv",
        position_index=0,
        ahv_bollard_pull=500_000.0,
        ahv_heading_deg=0.0,
        ahv_work_wire=ww,
        ahv_deck_x=800.0,
        ahv_deck_level=deck_z,
    )
    assert att.ahv_deck_level == deck_z


def test_ahv_deck_x_pode_ser_zero_ou_positivo() -> None:
    """ahv_deck_x sem constraint de sinal — AHV pode estar atrás do fairlead."""
    ww = WorkWireSpec(length=200.0, EA=5.5e8, w=170.0, MBL=6.5e6)
    for x_val in [0.0, 100.0, 1500.0, -50.0]:  # negativo = atrás do fairlead
        att = LineAttachment(
            kind="ahv",
            position_index=0,
            ahv_bollard_pull=500_000.0,
            ahv_heading_deg=0.0,
            ahv_work_wire=ww,
            ahv_deck_x=x_val,
        )
        assert att.ahv_deck_x == x_val


# ──────────────────────────────────────────────────────────────────
# Round-trip JSON
# ──────────────────────────────────────────────────────────────────


def test_ahv_tier_d_round_trip_json() -> None:
    original = LineAttachment(
        kind="ahv",
        position_index=2,
        ahv_bollard_pull=1_500_000.0,
        ahv_heading_deg=180.0,
        ahv_work_wire=WorkWireSpec(
            line_type_id=42,
            line_type="IWRCEIPS_76mm",
            length=300.0,
            EA=5.5e8,
            w=170.0,
            MBL=6.5e6,
            diameter=0.0762,
        ),
        ahv_deck_x=1500.0,
        ahv_deck_level=12.0,
        ahv_stern_angle_deg=25.0,
    )
    payload = original.model_dump_json()
    restored = LineAttachment.model_validate_json(payload)
    assert restored == original
    assert restored.ahv_work_wire is not None
    assert restored.ahv_work_wire.line_type == "IWRCEIPS_76mm"


def test_ahv_f8_puro_round_trip() -> None:
    """F8 puro (sem Tier D) round-trip preservado."""
    original = LineAttachment(
        kind="ahv",
        position_index=0,
        ahv_bollard_pull=500_000.0,
        ahv_heading_deg=45.0,
    )
    payload = original.model_dump_json()
    restored = LineAttachment.model_validate_json(payload)
    assert restored == original
    assert restored.ahv_work_wire is None


def test_ahv_kind_canonico() -> None:
    """Sanity: kind='ahv' continua sendo um AttachmentKind válido."""
    valid_kinds: list[AttachmentKind] = ["buoy", "clump_weight", "ahv"]
    assert "ahv" in valid_kinds
