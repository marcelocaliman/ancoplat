"""
Lógica do catálogo de vessels (Sprint 6 / Commit 51).

Espelha o padrão de `buoy_service.py` (F6) e `line_type_service.py`
(F1a). Apenas entradas com `data_source='user_input'` aceitam
PUT/DELETE — entradas seed (`legacy_qmoor`, `generic_offshore`,
`manufacturer_*`) são imutáveis.
"""
from __future__ import annotations

from typing import Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.api.db.models import VesselTypeRecord
from backend.api.schemas.vessels import VesselCreate, VesselOutput, VesselUpdate

IMMUTABLE_SOURCES: frozenset[str] = frozenset(
    {"legacy_qmoor", "generic_offshore"}
)
IMMUTABLE_PREFIXES: tuple[str, ...] = ("manufacturer",)


class VesselNotFound(Exception):
    """id de vessel inexistente."""


class VesselImmutable(Exception):
    """Tentativa de editar entrada do seed canônico."""


def _is_immutable(rec: VesselTypeRecord) -> bool:
    if rec.data_source in IMMUTABLE_SOURCES:
        return True
    return any(rec.data_source.startswith(p) for p in IMMUTABLE_PREFIXES)


def to_output(rec: VesselTypeRecord) -> VesselOutput:
    return VesselOutput.model_validate(rec)


def get(db: Session, vessel_id: int) -> VesselTypeRecord:
    rec = db.get(VesselTypeRecord, vessel_id)
    if rec is None:
        raise VesselNotFound(vessel_id)
    return rec


def list_all(
    db: Session,
    page: int = 1,
    page_size: int = 50,
    vessel_type: Optional[str] = None,
    search: Optional[str] = None,
) -> tuple[Sequence[VesselTypeRecord], int]:
    stmt = select(VesselTypeRecord)
    count_stmt = select(func.count()).select_from(VesselTypeRecord)

    if vessel_type:
        stmt = stmt.where(VesselTypeRecord.vessel_type == vessel_type)
        count_stmt = count_stmt.where(VesselTypeRecord.vessel_type == vessel_type)
    if search:
        like = f"%{search}%"
        stmt = stmt.where(VesselTypeRecord.name.ilike(like))
        count_stmt = count_stmt.where(VesselTypeRecord.name.ilike(like))

    total = db.execute(count_stmt).scalar_one()
    offset = (page - 1) * page_size
    stmt = (
        stmt.order_by(VesselTypeRecord.name.asc())
        .offset(offset)
        .limit(page_size)
    )
    items = db.execute(stmt).scalars().all()
    return items, total


def create(db: Session, payload: VesselCreate) -> VesselTypeRecord:
    rec = VesselTypeRecord(
        legacy_id=None,
        name=payload.name,
        vessel_type=payload.vessel_type,
        base_unit_system=payload.base_unit_system,
        loa=payload.loa,
        breadth=payload.breadth,
        draft=payload.draft,
        displacement=payload.displacement,
        default_heading_deg=payload.default_heading_deg,
        data_source="user_input",
        operator=payload.operator,
        manufacturer=payload.manufacturer,
        serial_number=payload.serial_number,
        comments=payload.comments,
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec


def update(db: Session, vessel_id: int, payload: VesselUpdate) -> VesselTypeRecord:
    rec = get(db, vessel_id)
    if _is_immutable(rec):
        raise VesselImmutable(vessel_id)

    rec.name = payload.name
    rec.vessel_type = payload.vessel_type
    rec.base_unit_system = payload.base_unit_system
    rec.loa = payload.loa
    rec.breadth = payload.breadth
    rec.draft = payload.draft
    rec.displacement = payload.displacement
    rec.default_heading_deg = payload.default_heading_deg
    rec.operator = payload.operator
    rec.manufacturer = payload.manufacturer
    rec.serial_number = payload.serial_number
    rec.comments = payload.comments
    db.commit()
    db.refresh(rec)
    return rec


def delete(db: Session, vessel_id: int) -> None:
    rec = get(db, vessel_id)
    if _is_immutable(rec):
        raise VesselImmutable(vessel_id)
    db.delete(rec)
    db.commit()


__all__ = [
    "IMMUTABLE_PREFIXES",
    "IMMUTABLE_SOURCES",
    "VesselImmutable",
    "VesselNotFound",
    "create",
    "delete",
    "get",
    "list_all",
    "to_output",
    "update",
]
