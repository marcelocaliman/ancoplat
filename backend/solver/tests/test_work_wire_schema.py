"""
Schema do WorkWireSpec e AHVInstall.work_wire — Sprint 4 / Commit 33
(Tier C físico AHV, validado vs MoorPy Subsystem).

Cobre:
  • WorkWireSpec: 4 campos físicos obrigatórios (length, EA, w, MBL).
  • Defaults: category='Wire', n_segs=1, line_type_id=None, demais None.
  • Validação Pydantic: length>0, EA>0, w>=0, MBL>0, n_segs∈[1,20].
  • AHVInstall.work_wire: opcional (default=None preserva Sprint 2).
  • Cross-validator: work_wire requer target_horz_distance set.
  • Round-trip JSON preserva todos os campos.
  • Frozen — model_config impede mutação acidental.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.solver.types import (
    AHVInstall,
    BoundaryConditions,
    SolutionMode,
    WorkWireSpec,
)


# ──────────────────────────────────────────────────────────────────
# WorkWireSpec — construção válida
# ──────────────────────────────────────────────────────────────────


def test_work_wire_minimo() -> None:
    """Apenas os 4 físicos obrigatórios — defaults preenchem o resto."""
    ww = WorkWireSpec(
        length=200.0,
        EA=5.0e8,
        w=190.0,
        MBL=6.0e6,
    )
    assert ww.length == 200.0
    assert ww.EA == 5.0e8
    assert ww.w == 190.0
    assert ww.MBL == 6.0e6
    assert ww.category == "Wire"
    assert ww.n_segs == 1
    assert ww.line_type_id is None
    assert ww.line_type is None
    assert ww.diameter is None
    assert ww.dry_weight is None


def test_work_wire_completo() -> None:
    """Todos os campos populados — espelha entrada via LineTypePicker."""
    ww = WorkWireSpec(
        line_type_id=42,
        line_type="IWRCEIPS 76mm",
        length=250.0,
        EA=5.5e8,
        w=195.0,
        MBL=6.5e6,
        category="Wire",
        n_segs=4,
        diameter=0.076,
        dry_weight=210.0,
    )
    assert ww.line_type_id == 42
    assert ww.line_type == "IWRCEIPS 76mm"
    assert ww.n_segs == 4
    assert ww.diameter == 0.076


# ──────────────────────────────────────────────────────────────────
# WorkWireSpec — validação Pydantic
# ──────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("length", [0.0, -1.0, -100.0])
def test_work_wire_length_must_be_positive(length: float) -> None:
    with pytest.raises(ValidationError, match="greater than 0"):
        WorkWireSpec(length=length, EA=5e8, w=190.0, MBL=6e6)


@pytest.mark.parametrize("ea", [0.0, -1.0, -1e6])
def test_work_wire_ea_must_be_positive(ea: float) -> None:
    with pytest.raises(ValidationError, match="greater than 0"):
        WorkWireSpec(length=200.0, EA=ea, w=190.0, MBL=6e6)


@pytest.mark.parametrize("w", [-0.001, -1.0, -100.0])
def test_work_wire_w_must_be_nonneg(w: float) -> None:
    with pytest.raises(ValidationError, match="greater than or equal to 0"):
        WorkWireSpec(length=200.0, EA=5e8, w=w, MBL=6e6)


def test_work_wire_w_zero_allowed() -> None:
    """w=0 é fisicamente válido — wire neutralmente flutuante (raro mas OK)."""
    ww = WorkWireSpec(length=200.0, EA=5e8, w=0.0, MBL=6e6)
    assert ww.w == 0.0


@pytest.mark.parametrize("mbl", [0.0, -1.0])
def test_work_wire_mbl_must_be_positive(mbl: float) -> None:
    with pytest.raises(ValidationError, match="greater than 0"):
        WorkWireSpec(length=200.0, EA=5e8, w=190.0, MBL=mbl)


@pytest.mark.parametrize("n_segs", [0, -1, 21, 100])
def test_work_wire_nsegs_range(n_segs: int) -> None:
    with pytest.raises(ValidationError):
        WorkWireSpec(length=200.0, EA=5e8, w=190.0, MBL=6e6, n_segs=n_segs)


def test_work_wire_category_only_wire() -> None:
    """Sprint 4: category fixa em 'Wire' — Polyester/Chain reservados."""
    with pytest.raises(ValidationError):
        WorkWireSpec(
            length=200.0, EA=5e8, w=190.0, MBL=6e6,
            category="Polyester",  # type: ignore[arg-type]
        )


def test_work_wire_frozen() -> None:
    """model_config frozen=True — mutação direta deve falhar."""
    ww = WorkWireSpec(length=200.0, EA=5e8, w=190.0, MBL=6e6)
    with pytest.raises(ValidationError):
        ww.length = 300.0  # type: ignore[misc]


# ──────────────────────────────────────────────────────────────────
# AHVInstall.work_wire — integração + cross-validator
# ──────────────────────────────────────────────────────────────────


def test_ahv_install_sem_work_wire_continua_funcional() -> None:
    """Retro-compat Sprint 2: AHVInstall sem work_wire é válido."""
    ahv = AHVInstall(bollard_pull=294_000.0)
    assert ahv.work_wire is None


def test_ahv_install_com_work_wire_e_target() -> None:
    """Tier C: work_wire requer target_horz_distance para posicionar pega."""
    ahv = AHVInstall(
        bollard_pull=1_500_000.0,
        target_horz_distance=1500.0,
        work_wire=WorkWireSpec(length=200.0, EA=5e8, w=190.0, MBL=6e6),
    )
    assert ahv.work_wire is not None
    assert ahv.work_wire.length == 200.0
    assert ahv.target_horz_distance == 1500.0


def test_ahv_install_work_wire_sem_target_falha() -> None:
    """Cross-validator: work_wire sem target_horz_distance levanta."""
    with pytest.raises(ValidationError, match="target_horz_distance"):
        AHVInstall(
            bollard_pull=1_500_000.0,
            work_wire=WorkWireSpec(length=200.0, EA=5e8, w=190.0, MBL=6e6),
        )


# ──────────────────────────────────────────────────────────────────
# Round-trip JSON
# ──────────────────────────────────────────────────────────────────


def test_work_wire_round_trip_json() -> None:
    original = WorkWireSpec(
        line_type_id=42,
        line_type="IWRCEIPS 76mm",
        length=250.0,
        EA=5.5e8,
        w=195.0,
        MBL=6.5e6,
        n_segs=4,
        diameter=0.076,
        dry_weight=210.0,
    )
    payload = original.model_dump_json()
    restored = WorkWireSpec.model_validate_json(payload)
    assert restored == original


def test_ahv_install_with_work_wire_round_trip_json() -> None:
    original = AHVInstall(
        bollard_pull=1_960_000.0,
        deck_level_above_swl=5.0,
        stern_angle_deg=15.0,
        target_horz_distance=1828.8,
        work_wire=WorkWireSpec(
            line_type="IWRCEIPS 76mm",
            length=250.0,
            EA=5.5e8,
            w=195.0,
            MBL=6.5e6,
            diameter=0.076,
        ),
    )
    payload = original.model_dump_json()
    restored = AHVInstall.model_validate_json(payload)
    assert restored == original
    assert restored.work_wire is not None
    assert restored.work_wire.line_type == "IWRCEIPS 76mm"


# ──────────────────────────────────────────────────────────────────
# BoundaryConditions integration
# ──────────────────────────────────────────────────────────────────


def test_boundary_conditions_with_ahv_install_work_wire() -> None:
    """BoundaryConditions.ahv_install referencia AHVInstall com forward
    ref via model_rebuild — Tier C via composição completa."""
    bc = BoundaryConditions(
        h=300.0,
        mode=SolutionMode.TENSION,
        input_value=1_500_000.0,
        startpoint_depth=0.0,
        endpoint_grounded=True,
        startpoint_type="ahv",
        ahv_install=AHVInstall(
            bollard_pull=1_500_000.0,
            target_horz_distance=1500.0,
            work_wire=WorkWireSpec(length=200.0, EA=5e8, w=190.0, MBL=6e6),
        ),
    )
    assert bc.ahv_install is not None
    assert bc.ahv_install.work_wire is not None
    assert bc.ahv_install.work_wire.MBL == 6e6
