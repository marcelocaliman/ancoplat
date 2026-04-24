"""Endpoints do catálogo de tipos de linha (Seção 3.2 do plano F2)."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.api.db.session import get_db
from backend.api.schemas.cases import PaginatedResponse
from backend.api.schemas.errors import ErrorResponse
from backend.api.schemas.line_types import (
    Category,
    LineTypeCreate,
    LineTypeOutput,
    LineTypeUpdate,
)
from backend.api.services import line_type_service

router = APIRouter(prefix="/line-types", tags=["catalog"])


def _not_found(line_type_id: int) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={
            "code": "line_type_not_found",
            "message": f"Tipo de linha id={line_type_id} não encontrado.",
        },
    )


def _immutable(line_type_id: int) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "code": "line_type_immutable",
            "message": (
                f"Tipo de linha id={line_type_id} é do catálogo legado "
                "(data_source='legacy_qmoor') e não pode ser modificado ou "
                "removido. Crie uma nova entrada user_input se precisar."
            ),
        },
    )


@router.get(
    "",
    response_model=PaginatedResponse[LineTypeOutput],
    summary="Listar tipos de linha",
    description=(
        "Lista paginada do catálogo. Filtros: `category`, `search` (ILIKE em "
        "line_type), `diameter_min`, `diameter_max`."
    ),
)
def list_line_types(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    category: Optional[Category] = Query(default=None),
    search: Optional[str] = Query(default=None),
    diameter_min: Optional[float] = Query(default=None, ge=0),
    diameter_max: Optional[float] = Query(default=None, ge=0),
    db: Session = Depends(get_db),
) -> PaginatedResponse[LineTypeOutput]:
    items, total = line_type_service.list_all(
        db,
        page=page,
        page_size=page_size,
        category=category,
        search=search,
        diameter_min=diameter_min,
        diameter_max=diameter_max,
    )
    return PaginatedResponse[LineTypeOutput](
        items=[line_type_service.to_output(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/lookup",
    response_model=LineTypeOutput,
    summary="Buscar por (line_type, diameter)",
    description=(
        "Retorna a entrada que combina exatamente `line_type` (nome) e "
        "`diameter` (em metros). Útil para resolver um segmento do solver "
        "via identificador + dimensão."
    ),
    responses={404: {"model": ErrorResponse}},
)
def lookup_line_type(
    line_type: str = Query(..., description="Nome do tipo (ex: 'IWRCEIPS')"),
    diameter: float = Query(..., gt=0, description="Diâmetro em metros"),
    db: Session = Depends(get_db),
) -> LineTypeOutput:
    rec = line_type_service.lookup(db, line_type, diameter)
    if rec is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "line_type_not_found",
                "message": (
                    f"Nenhuma entrada com line_type='{line_type}' e diameter="
                    f"{diameter:.6f} m. Verifique se o diâmetro está em SI (m)."
                ),
            },
        )
    return line_type_service.to_output(rec)


@router.get(
    "/{line_type_id}",
    response_model=LineTypeOutput,
    summary="Detalhar tipo de linha por id",
    responses={404: {"model": ErrorResponse}},
)
def get_line_type(
    line_type_id: int, db: Session = Depends(get_db)
) -> LineTypeOutput:
    try:
        rec = line_type_service.get(db, line_type_id)
    except line_type_service.LineTypeNotFound:
        raise _not_found(line_type_id)
    return line_type_service.to_output(rec)


@router.post(
    "",
    response_model=LineTypeOutput,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastrar tipo user_input",
    description=(
        "Cria uma nova entrada com `data_source='user_input'`. As 522 "
        "entradas legacy_qmoor não podem ser modificadas; use este endpoint "
        "para adicionar tipos próprios."
    ),
    responses={422: {"model": ErrorResponse}},
)
def create_line_type(
    payload: LineTypeCreate, db: Session = Depends(get_db)
) -> LineTypeOutput:
    rec = line_type_service.create(db, payload)
    return line_type_service.to_output(rec)


@router.put(
    "/{line_type_id}",
    response_model=LineTypeOutput,
    summary="Editar tipo user_input",
    description=(
        "Só permite edição de entradas com `data_source='user_input'`. "
        "Entradas `legacy_qmoor` são imutáveis (retorna 403)."
    ),
    responses={
        403: {"model": ErrorResponse, "description": "Entrada legacy_qmoor"},
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
def update_line_type(
    line_type_id: int, payload: LineTypeUpdate, db: Session = Depends(get_db)
) -> LineTypeOutput:
    try:
        rec = line_type_service.update(db, line_type_id, payload)
    except line_type_service.LineTypeNotFound:
        raise _not_found(line_type_id)
    except line_type_service.LineTypeImmutable:
        raise _immutable(line_type_id)
    return line_type_service.to_output(rec)


@router.delete(
    "/{line_type_id}",
    status_code=status.HTTP_200_OK,
    summary="Remover tipo user_input",
    description="Apenas entradas `user_input` podem ser removidas.",
    responses={
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
def delete_line_type(
    line_type_id: int, db: Session = Depends(get_db)
) -> dict[str, str]:
    try:
        line_type_service.delete(db, line_type_id)
    except line_type_service.LineTypeNotFound:
        raise _not_found(line_type_id)
    except line_type_service.LineTypeImmutable:
        raise _immutable(line_type_id)
    return {"status": "deleted", "message": f"Tipo id={line_type_id} removido."}


__all__ = ["router"]
