"""Endpoints do catálogo de boias (F6 / Q1+Q3)."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.api.db.session import get_db
from backend.api.schemas.buoys import (
    BuoyCreate,
    BuoyOutput,
    BuoyType,
    BuoyUpdate,
    EndType,
)
from backend.api.schemas.cases import PaginatedResponse
from backend.api.schemas.errors import ErrorResponse
from backend.api.services import buoy_service

router = APIRouter(prefix="/buoys", tags=["catalog"])


def _not_found(buoy_id: int) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={
            "code": "buoy_not_found",
            "message": f"Boia id={buoy_id} não encontrada.",
        },
    )


def _immutable(buoy_id: int) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "code": "buoy_immutable",
            "message": (
                f"Boia id={buoy_id} é do seed canônico (data_source"
                " excel_buoy_calc_v1, generic_offshore ou manufacturer_*)"
                " e não pode ser modificada ou removida. Crie uma nova"
                " entrada user_input se precisar."
            ),
        },
    )


@router.get(
    "",
    response_model=PaginatedResponse[BuoyOutput],
    summary="Listar boias",
    description=(
        "Lista paginada do catálogo de boias. Filtros: `buoy_type`, "
        "`end_type`, `search` (ILIKE em name)."
    ),
)
def list_buoys(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    buoy_type: Optional[BuoyType] = Query(default=None),
    end_type: Optional[EndType] = Query(default=None),
    search: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
) -> PaginatedResponse[BuoyOutput]:
    items, total = buoy_service.list_all(
        db,
        page=page,
        page_size=page_size,
        buoy_type=buoy_type,
        end_type=end_type,
        search=search,
    )
    return PaginatedResponse[BuoyOutput](
        items=[buoy_service.to_output(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{buoy_id}",
    response_model=BuoyOutput,
    summary="Detalhar boia por id",
    responses={404: {"model": ErrorResponse}},
)
def get_buoy(buoy_id: int, db: Session = Depends(get_db)) -> BuoyOutput:
    try:
        rec = buoy_service.get(db, buoy_id)
    except buoy_service.BuoyNotFound:
        raise _not_found(buoy_id)
    return buoy_service.to_output(rec)


@router.post(
    "",
    response_model=BuoyOutput,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastrar boia user_input",
    description=(
        "Cria uma nova entrada com `data_source='user_input'`. As "
        "entradas seed (`excel_buoy_calc_v1`, `generic_offshore`, "
        "`manufacturer_*`) não podem ser modificadas; use este "
        "endpoint para adicionar boias próprias."
    ),
    responses={422: {"model": ErrorResponse}},
)
def create_buoy(
    payload: BuoyCreate, db: Session = Depends(get_db)
) -> BuoyOutput:
    rec = buoy_service.create(db, payload)
    return buoy_service.to_output(rec)


@router.put(
    "/{buoy_id}",
    response_model=BuoyOutput,
    summary="Editar boia user_input",
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
def update_buoy(
    buoy_id: int, payload: BuoyUpdate, db: Session = Depends(get_db)
) -> BuoyOutput:
    try:
        rec = buoy_service.update(db, buoy_id, payload)
    except buoy_service.BuoyNotFound:
        raise _not_found(buoy_id)
    except buoy_service.BuoyImmutable:
        raise _immutable(buoy_id)
    return buoy_service.to_output(rec)


@router.delete(
    "/{buoy_id}",
    status_code=status.HTTP_200_OK,
    summary="Remover boia user_input",
    description="Apenas entradas `user_input` podem ser removidas.",
    responses={
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
def delete_buoy(buoy_id: int, db: Session = Depends(get_db)) -> dict[str, str]:
    try:
        buoy_service.delete(db, buoy_id)
    except buoy_service.BuoyNotFound:
        raise _not_found(buoy_id)
    except buoy_service.BuoyImmutable:
        raise _immutable(buoy_id)
    return {"status": "deleted", "message": f"Boia id={buoy_id} removida."}


__all__ = ["router"]
