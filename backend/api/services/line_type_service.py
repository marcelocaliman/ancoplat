"""
Lógica do catálogo de tipos de linha (F2.5).

Protege entradas legacy_qmoor contra edição/remoção. Apenas user_input
pode ser modificado.
"""
from __future__ import annotations

from typing import Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.api.db.models import LineTypeRecord
from backend.api.schemas.line_types import (
    LineTypeCreate,
    LineTypeOutput,
    LineTypeUpdate,
)


LEGACY_SOURCE = "legacy_qmoor"


class LineTypeNotFound(Exception):
    """id de line_type inexistente."""


class LineTypeImmutable(Exception):
    """Tentativa de editar ou remover entrada legacy_qmoor."""


def to_output(rec: LineTypeRecord) -> LineTypeOutput:
    return LineTypeOutput.model_validate(rec)


def get(db: Session, line_type_id: int) -> LineTypeRecord:
    rec = db.get(LineTypeRecord, line_type_id)
    if rec is None:
        raise LineTypeNotFound(line_type_id)
    return rec


def lookup(
    db: Session, line_type_name: str, diameter: float, tol: float = 1e-6
) -> Optional[LineTypeRecord]:
    """
    Busca por (line_type, diameter) com tolerância numérica (útil para
    diâmetros em SI com muitas casas decimais).
    """
    stmt = (
        select(LineTypeRecord)
        .where(LineTypeRecord.line_type == line_type_name)
        .where(LineTypeRecord.diameter.between(diameter - tol, diameter + tol))
        .order_by(LineTypeRecord.id.asc())
        .limit(1)
    )
    return db.execute(stmt).scalar_one_or_none()


def list_all(
    db: Session,
    page: int = 1,
    page_size: int = 50,
    category: Optional[str] = None,
    search: Optional[str] = None,
    diameter_min: Optional[float] = None,
    diameter_max: Optional[float] = None,
) -> tuple[Sequence[LineTypeRecord], int]:
    """Listagem com filtros."""
    stmt = select(LineTypeRecord)
    count_stmt = select(func.count()).select_from(LineTypeRecord)

    if category:
        stmt = stmt.where(LineTypeRecord.category == category)
        count_stmt = count_stmt.where(LineTypeRecord.category == category)
    if search:
        like = f"%{search}%"
        stmt = stmt.where(LineTypeRecord.line_type.ilike(like))
        count_stmt = count_stmt.where(LineTypeRecord.line_type.ilike(like))
    if diameter_min is not None:
        stmt = stmt.where(LineTypeRecord.diameter >= diameter_min)
        count_stmt = count_stmt.where(LineTypeRecord.diameter >= diameter_min)
    if diameter_max is not None:
        stmt = stmt.where(LineTypeRecord.diameter <= diameter_max)
        count_stmt = count_stmt.where(LineTypeRecord.diameter <= diameter_max)

    total = db.execute(count_stmt).scalar_one()
    offset = (page - 1) * page_size
    stmt = (
        stmt.order_by(LineTypeRecord.line_type.asc(), LineTypeRecord.diameter.asc())
        .offset(offset)
        .limit(page_size)
    )
    items = db.execute(stmt).scalars().all()
    return items, total


def create(db: Session, payload: LineTypeCreate) -> LineTypeRecord:
    """Cria entrada no catálogo com data_source='user_input'."""
    rec = LineTypeRecord(
        legacy_id=None,
        line_type=payload.line_type,
        category=payload.category,
        base_unit_system=payload.base_unit_system,
        diameter=payload.diameter,
        dry_weight=payload.dry_weight,
        wet_weight=payload.wet_weight,
        break_strength=payload.break_strength,
        modulus=payload.modulus,
        qmoor_ea=payload.qmoor_ea,
        gmoor_ea=payload.gmoor_ea,
        seabed_friction_cf=payload.seabed_friction_cf,
        data_source="user_input",
        manufacturer=payload.manufacturer,
        serial_number=payload.serial_number,
        comments=payload.comments,
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec


def update(
    db: Session, line_type_id: int, payload: LineTypeUpdate
) -> LineTypeRecord:
    """Atualiza entrada. Bloqueia entradas legacy_qmoor."""
    rec = get(db, line_type_id)
    if rec.data_source == LEGACY_SOURCE:
        raise LineTypeImmutable(line_type_id)

    rec.line_type = payload.line_type
    rec.category = payload.category
    rec.base_unit_system = payload.base_unit_system
    rec.diameter = payload.diameter
    rec.dry_weight = payload.dry_weight
    rec.wet_weight = payload.wet_weight
    rec.break_strength = payload.break_strength
    rec.modulus = payload.modulus
    rec.qmoor_ea = payload.qmoor_ea
    rec.gmoor_ea = payload.gmoor_ea
    rec.seabed_friction_cf = payload.seabed_friction_cf
    rec.manufacturer = payload.manufacturer
    rec.serial_number = payload.serial_number
    rec.comments = payload.comments
    db.commit()
    db.refresh(rec)
    return rec


def delete(db: Session, line_type_id: int) -> None:
    """Remove entrada user_input. Bloqueia legacy_qmoor."""
    rec = get(db, line_type_id)
    if rec.data_source == LEGACY_SOURCE:
        raise LineTypeImmutable(line_type_id)
    db.delete(rec)
    db.commit()


__all__ = [
    "LEGACY_SOURCE",
    "LineTypeImmutable",
    "LineTypeNotFound",
    "create",
    "delete",
    "get",
    "list_all",
    "lookup",
    "to_output",
    "update",
]
