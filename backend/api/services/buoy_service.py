"""
Lógica do catálogo de boias (F6).

Espelha o padrão de `line_type_service`. Apenas entradas com
`data_source='user_input'` aceitam PUT/DELETE — entradas seed
(`excel_buoy_calc_v1`, `generic_offshore`, `manufacturer_*`) são
imutáveis para preservar rastreabilidade.
"""
from __future__ import annotations

from typing import Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.api.db.models import BuoyRecord
from backend.api.schemas.buoys import BuoyCreate, BuoyOutput, BuoyUpdate

# Conjunto de data_sources protegidos contra edição/remoção.
IMMUTABLE_SOURCES: frozenset[str] = frozenset(
    {"excel_buoy_calc_v1", "generic_offshore"}
)
# Prefixos de manufacturer também são imutáveis (manufacturer_*).
IMMUTABLE_PREFIXES: tuple[str, ...] = ("manufacturer",)


class BuoyNotFound(Exception):
    """id de boia inexistente."""


class BuoyImmutable(Exception):
    """Tentativa de editar entrada do seed canônico."""


def _is_immutable(rec: BuoyRecord) -> bool:
    if rec.data_source in IMMUTABLE_SOURCES:
        return True
    return any(rec.data_source.startswith(p) for p in IMMUTABLE_PREFIXES)


def to_output(rec: BuoyRecord) -> BuoyOutput:
    return BuoyOutput.model_validate(rec)


def get(db: Session, buoy_id: int) -> BuoyRecord:
    rec = db.get(BuoyRecord, buoy_id)
    if rec is None:
        raise BuoyNotFound(buoy_id)
    return rec


def list_all(
    db: Session,
    page: int = 1,
    page_size: int = 50,
    buoy_type: Optional[str] = None,
    end_type: Optional[str] = None,
    search: Optional[str] = None,
) -> tuple[Sequence[BuoyRecord], int]:
    stmt = select(BuoyRecord)
    count_stmt = select(func.count()).select_from(BuoyRecord)

    if buoy_type:
        stmt = stmt.where(BuoyRecord.buoy_type == buoy_type)
        count_stmt = count_stmt.where(BuoyRecord.buoy_type == buoy_type)
    if end_type:
        stmt = stmt.where(BuoyRecord.end_type == end_type)
        count_stmt = count_stmt.where(BuoyRecord.end_type == end_type)
    if search:
        like = f"%{search}%"
        stmt = stmt.where(BuoyRecord.name.ilike(like))
        count_stmt = count_stmt.where(BuoyRecord.name.ilike(like))

    total = db.execute(count_stmt).scalar_one()
    offset = (page - 1) * page_size
    stmt = (
        stmt.order_by(BuoyRecord.name.asc(), BuoyRecord.outer_diameter.asc())
        .offset(offset)
        .limit(page_size)
    )
    items = db.execute(stmt).scalars().all()
    return items, total


def create(db: Session, payload: BuoyCreate) -> BuoyRecord:
    rec = BuoyRecord(
        legacy_id=None,
        name=payload.name,
        buoy_type=payload.buoy_type,
        end_type=payload.end_type,
        base_unit_system=payload.base_unit_system,
        outer_diameter=payload.outer_diameter,
        length=payload.length,
        weight_in_air=payload.weight_in_air,
        submerged_force=payload.submerged_force,
        data_source="user_input",
        manufacturer=payload.manufacturer,
        serial_number=payload.serial_number,
        comments=payload.comments,
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec


def update(db: Session, buoy_id: int, payload: BuoyUpdate) -> BuoyRecord:
    rec = get(db, buoy_id)
    if _is_immutable(rec):
        raise BuoyImmutable(buoy_id)

    rec.name = payload.name
    rec.buoy_type = payload.buoy_type
    rec.end_type = payload.end_type
    rec.base_unit_system = payload.base_unit_system
    rec.outer_diameter = payload.outer_diameter
    rec.length = payload.length
    rec.weight_in_air = payload.weight_in_air
    rec.submerged_force = payload.submerged_force
    rec.manufacturer = payload.manufacturer
    rec.serial_number = payload.serial_number
    rec.comments = payload.comments
    db.commit()
    db.refresh(rec)
    return rec


def delete(db: Session, buoy_id: int) -> None:
    rec = get(db, buoy_id)
    if _is_immutable(rec):
        raise BuoyImmutable(buoy_id)
    db.delete(rec)
    db.commit()


__all__ = [
    "BuoyImmutable",
    "BuoyNotFound",
    "IMMUTABLE_PREFIXES",
    "IMMUTABLE_SOURCES",
    "create",
    "delete",
    "get",
    "list_all",
    "to_output",
    "update",
]
