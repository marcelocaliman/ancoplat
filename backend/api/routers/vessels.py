"""Endpoints do catálogo de vessels (Sprint 6 / Commit 51)."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.api.db.session import get_db
from backend.api.schemas.cases import PaginatedResponse
from backend.api.schemas.errors import ErrorResponse
from backend.api.schemas.vessels import (
    VesselCreate,
    VesselOutput,
    VesselType,
    VesselUpdate,
)
from backend.api.services import vessel_service

router = APIRouter(prefix="/vessel-types", tags=["catalog"])


def _not_found(vessel_id: int) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={
            "code": "vessel_not_found",
            "message": f"Vessel id={vessel_id} não encontrado.",
        },
    )


def _immutable(vessel_id: int) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "code": "vessel_immutable",
            "message": (
                f"Vessel id={vessel_id} é do seed canônico (data_source"
                " legacy_qmoor, generic_offshore ou manufacturer_*)"
                " e não pode ser modificado ou removido. Crie uma nova"
                " entrada user_input se precisar."
            ),
        },
    )


@router.get(
    "",
    response_model=PaginatedResponse[VesselOutput],
    summary="Listar vessels",
    description=(
        "Lista paginada do catálogo de vessels. Filtros: `vessel_type`, "
        "`search` (ILIKE em name)."
    ),
)
def list_vessels(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    vessel_type: Optional[VesselType] = Query(default=None),
    search: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
) -> PaginatedResponse[VesselOutput]:
    items, total = vessel_service.list_all(
        db,
        page=page,
        page_size=page_size,
        vessel_type=vessel_type,
        search=search,
    )
    return PaginatedResponse[VesselOutput](
        items=[vessel_service.to_output(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{vessel_id}",
    response_model=VesselOutput,
    summary="Detalhar vessel por id",
    responses={404: {"model": ErrorResponse}},
)
def get_vessel(vessel_id: int, db: Session = Depends(get_db)) -> VesselOutput:
    try:
        rec = vessel_service.get(db, vessel_id)
    except vessel_service.VesselNotFound:
        raise _not_found(vessel_id)
    return vessel_service.to_output(rec)


@router.post(
    "",
    response_model=VesselOutput,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastrar vessel user_input",
    description=(
        "Cria uma nova entrada com `data_source='user_input'`. As "
        "entradas seed (`legacy_qmoor`, `generic_offshore`, "
        "`manufacturer_*`) não podem ser modificadas; use este "
        "endpoint para adicionar vessels próprios."
    ),
    responses={422: {"model": ErrorResponse}},
)
def create_vessel(
    payload: VesselCreate, db: Session = Depends(get_db)
) -> VesselOutput:
    rec = vessel_service.create(db, payload)
    return vessel_service.to_output(rec)


@router.put(
    "/{vessel_id}",
    response_model=VesselOutput,
    summary="Editar vessel user_input",
    description=(
        "Só permite edição de entradas com `data_source='user_input'`. "
        "Entradas seed são imutáveis (retorna 403)."
    ),
    responses={
        403: {"model": ErrorResponse, "description": "Entrada seed protegida"},
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
def update_vessel(
    vessel_id: int, payload: VesselUpdate, db: Session = Depends(get_db)
) -> VesselOutput:
    try:
        rec = vessel_service.update(db, vessel_id, payload)
    except vessel_service.VesselNotFound:
        raise _not_found(vessel_id)
    except vessel_service.VesselImmutable:
        raise _immutable(vessel_id)
    return vessel_service.to_output(rec)


@router.delete(
    "/{vessel_id}",
    status_code=status.HTTP_200_OK,
    summary="Remover vessel user_input",
    description="Apenas entradas `user_input` podem ser removidas.",
    responses={
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
def delete_vessel(vessel_id: int, db: Session = Depends(get_db)) -> dict[str, str]:
    try:
        vessel_service.delete(db, vessel_id)
    except vessel_service.VesselNotFound:
        raise _not_found(vessel_id)
    except vessel_service.VesselImmutable:
        raise _immutable(vessel_id)
    return {"status": "deleted", "message": f"Vessel id={vessel_id} removido."}


__all__ = ["router"]
