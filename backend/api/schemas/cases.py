"""
Schemas Pydantic da API para Casos e Execuções.

Reusa os schemas canônicos do solver (`backend.solver.types`) em vez de
duplicá-los — qualquer evolução no solver propaga automaticamente para
a API.
"""
from __future__ import annotations

from datetime import datetime
from typing import Generic, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.solver.types import (
    BoundaryConditions,
    CriteriaProfile,
    LineAttachment,
    LineSegment,
    SeabedConfig,
    SolverResult,
    UtilizationLimits,
)


T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """Envelope genérico de paginação (Seção 4.3 do plano F2)."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    items: list[T]
    total: int = Field(..., ge=0)
    page: int = Field(..., ge=1)
    page_size: int = Field(..., ge=1)


class CaseInput(BaseModel):
    """Input canônico para criar ou atualizar um caso (Seção 4.1 do plano F2)."""

    model_config = ConfigDict(
        frozen=True,
        json_schema_extra={
            "example": {
                "name": "BC-01 — catenária pura suspensa",
                "description": "Wire rope 3in, lâmina 300 m, T_fl=785 kN",
                "segments": [
                    {
                        "length": 450.0,
                        "w": 201.1,
                        "EA": 3.425e7,
                        "MBL": 3.78e6,
                        "category": "Wire",
                        "line_type": "IWRCEIPS",
                    }
                ],
                "boundary": {
                    "h": 300.0,
                    "mode": "Tension",
                    "input_value": 785000.0,
                    "startpoint_depth": 0.0,
                    "endpoint_grounded": True,
                },
                "seabed": {"mu": 0.0},
                "criteria_profile": "MVP_Preliminary",
            }
        },
    )

    name: str = Field(..., min_length=1, max_length=200, description="Nome do caso")
    description: Optional[str] = Field(
        default=None, max_length=2000, description="Descrição livre (opcional)"
    )
    segments: list[LineSegment] = Field(
        ...,
        min_length=1,
        max_length=10,
        description=(
            "Lista de segmentos (1 ou mais, F5.1). Para uma linha composta "
            "típica use 3 segmentos (chain pendant inferior + wire + chain "
            "pendant superior). Ordem do segmento 0 (mais próximo da âncora) "
            "ao último (mais próximo do fairlead)."
        ),
    )
    boundary: BoundaryConditions
    seabed: SeabedConfig = Field(default_factory=SeabedConfig)
    criteria_profile: CriteriaProfile = Field(default=CriteriaProfile.MVP_PRELIMINARY)
    user_defined_limits: Optional[UtilizationLimits] = Field(
        default=None,
        description="Obrigatório quando criteria_profile = UserDefined.",
    )
    attachments: list[LineAttachment] = Field(
        default_factory=list,
        max_length=20,
        description=(
            "Boias ou clump weights pontuais nas junções entre segmentos "
            "(F5.2). Cada attachment fica em `position_index` (0 = entre "
            "seg 0 e seg 1). Lista vazia para linha sem elementos pontuais."
        ),
    )
    metadata: Optional[dict[str, str]] = Field(
        default=None,
        description=(
            "Metadata operacional do projeto (Sprint 1 / v1.1.0). "
            "Pares chave-valor livres para preservar info de modelos "
            "importados (QMoor: rig, location, region, engineer, "
            "number, source_version). Não afeta o cálculo do solver — "
            "é exibido no Memorial PDF e na UI de detalhes do caso. "
            "Limite de 20 chaves para evitar abuso."
        ),
    )

    @field_validator("metadata")
    @classmethod
    def _validate_metadata_size(
        cls, v: Optional[dict[str, str]]
    ) -> Optional[dict[str, str]]:
        if v is None:
            return v
        if len(v) > 20:
            raise ValueError(
                f"metadata: máximo 20 chaves, recebido {len(v)}"
            )
        for key, val in v.items():
            if not isinstance(key, str) or not isinstance(val, str):
                raise ValueError(
                    "metadata: todas as chaves e valores devem ser str"
                )
            if len(key) > 80 or len(val) > 500:
                raise ValueError(
                    f"metadata['{key}']: chave > 80 chars OU valor > 500 chars"
                )
        return v


class ExecutionOutput(BaseModel):
    """Representação de uma execução persistida."""

    id: int
    case_id: int
    result: SolverResult
    executed_at: datetime


class CaseSummary(BaseModel):
    """Versão enxuta do caso para listagem (sem input completo)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: Optional[str]
    line_type: Optional[str] = Field(
        default=None, description="Primeiro segmento.line_type (se informado)"
    )
    mode: str = Field(..., examples=["Tension", "Range"])
    water_depth: float = Field(..., description="Lâmina d'água em metros")
    line_length: float = Field(..., description="Comprimento da linha em metros")
    criteria_profile: str
    created_at: datetime
    updated_at: datetime


class CaseOutput(BaseModel):
    """Representação detalhada (para GET /cases/{id})."""

    id: int
    name: str
    description: Optional[str]
    input: CaseInput
    latest_executions: list[ExecutionOutput] = Field(
        default_factory=list,
        description="Últimas 10 execuções (mais recente primeiro). Vazio se nunca foi resolvido.",
    )
    created_at: datetime
    updated_at: datetime


__all__ = [
    "CaseInput",
    "CaseOutput",
    "CaseSummary",
    "ExecutionOutput",
    "PaginatedResponse",
]
