"""Schemas Pydantic dos envelopes de erro da API (Seção 5.5 do plano F2)."""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    """Corpo interno do envelope de erro."""

    code: str = Field(
        ...,
        description="Identificador da classe de erro (ex: 'case_not_found').",
        examples=["case_not_found"],
    )
    message: str = Field(
        ..., description="Mensagem legível em português para exibir ao usuário."
    )
    detail: Optional[dict[str, Any]] = Field(
        default=None,
        description="Metadados opcionais (ex: snapshot de SolverResult).",
    )


class ErrorResponse(BaseModel):
    """Envelope padrão de erro da API."""

    error: ErrorDetail


__all__ = ["ErrorDetail", "ErrorResponse"]
