"""
Lógica de negócio para mooring systems (F5.4.1 — CRUD).

Mesma estratégia adotada em `case_service`: o input completo
(`MooringSystemInput`) vai para `config_json` e os campos
desnormalizados vivem em colunas próprias para queries rápidas. A
execução do solver multi-linha + agregação de forças entra na F5.4.2.
"""
from __future__ import annotations

import logging
from typing import Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.api.db.models import MooringSystemRecord
from backend.api.schemas.mooring_systems import (
    MooringSystemInput,
    MooringSystemOutput,
    MooringSystemSummary,
)

logger = logging.getLogger("qmoor.api.mooring_systems")


# ==============================================================================
# Conversões record ↔ schemas
# ==============================================================================


def mooring_system_record_to_summary(
    rec: MooringSystemRecord,
) -> MooringSystemSummary:
    return MooringSystemSummary(
        id=rec.id,
        name=rec.name,
        description=rec.description,
        platform_radius=rec.platform_radius,
        line_count=rec.line_count,
        created_at=rec.created_at,
        updated_at=rec.updated_at,
    )


def mooring_system_record_to_output(
    rec: MooringSystemRecord,
) -> MooringSystemOutput:
    config = MooringSystemInput.model_validate_json(rec.config_json)
    return MooringSystemOutput(
        id=rec.id,
        name=rec.name,
        description=rec.description,
        input=config,
        created_at=rec.created_at,
        updated_at=rec.updated_at,
    )


# ==============================================================================
# CRUD
# ==============================================================================


def create_mooring_system(
    db: Session, msys_input: MooringSystemInput
) -> MooringSystemRecord:
    """Persiste um novo mooring system. Retorna o record criado já hidratado."""
    rec = MooringSystemRecord(
        name=msys_input.name,
        description=msys_input.description,
        platform_radius=msys_input.platform_radius,
        line_count=len(msys_input.lines),
        config_json=msys_input.model_dump_json(),
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    logger.info(
        "Mooring system criado: id=%s name=%r line_count=%d",
        rec.id, rec.name, rec.line_count,
    )
    return rec


def get_mooring_system(db: Session, msys_id: int) -> MooringSystemRecord | None:
    return db.get(MooringSystemRecord, msys_id)


def list_mooring_systems(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 50,
    search: str | None = None,
) -> tuple[Sequence[MooringSystemRecord], int]:
    """Lista paginada com filtro opcional por substring no nome."""
    stmt = select(MooringSystemRecord)
    count_stmt = select(func.count()).select_from(MooringSystemRecord)
    if search:
        like = f"%{search}%"
        stmt = stmt.where(MooringSystemRecord.name.ilike(like))
        count_stmt = count_stmt.where(MooringSystemRecord.name.ilike(like))
    stmt = stmt.order_by(MooringSystemRecord.updated_at.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size)
    items = db.scalars(stmt).all()
    total = db.scalar(count_stmt) or 0
    return items, total


def update_mooring_system(
    db: Session,
    msys_id: int,
    msys_input: MooringSystemInput,
) -> MooringSystemRecord | None:
    """Atualiza completamente. Retorna None se não existir."""
    rec = db.get(MooringSystemRecord, msys_id)
    if rec is None:
        return None
    rec.name = msys_input.name
    rec.description = msys_input.description
    rec.platform_radius = msys_input.platform_radius
    rec.line_count = len(msys_input.lines)
    rec.config_json = msys_input.model_dump_json()
    db.commit()
    db.refresh(rec)
    logger.info(
        "Mooring system atualizado: id=%s name=%r line_count=%d",
        rec.id, rec.name, rec.line_count,
    )
    return rec


def delete_mooring_system(db: Session, msys_id: int) -> bool:
    rec = db.get(MooringSystemRecord, msys_id)
    if rec is None:
        return False
    db.delete(rec)
    db.commit()
    logger.info("Mooring system deletado: id=%s", msys_id)
    return True


__all__ = [
    "create_mooring_system",
    "delete_mooring_system",
    "get_mooring_system",
    "list_mooring_systems",
    "mooring_system_record_to_output",
    "mooring_system_record_to_summary",
    "update_mooring_system",
]
