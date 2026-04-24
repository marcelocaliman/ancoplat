"""Schemas Pydantic para o catálogo de tipos de linha (F2.5)."""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


DataSource = Literal["legacy_qmoor", "manufacturer", "certificate", "user_input"]
Category = Literal["Wire", "StuddedChain", "StudlessChain", "Polyester"]
UnitSystem = Literal["imperial", "metric"]


class LineTypeBase(BaseModel):
    """Campos comuns (create/update/output)."""

    line_type: str = Field(..., min_length=1, max_length=50, examples=["IWRCEIPS"])
    category: Category
    base_unit_system: UnitSystem = Field(
        default="metric",
        description="Sistema de origem. Valores no payload estão SEMPRE em SI.",
    )
    diameter: float = Field(..., gt=0, description="Diâmetro (m)")
    dry_weight: float = Field(..., gt=0, description="Peso seco por unidade (N/m)")
    wet_weight: float = Field(..., gt=0, description="Peso submerso por unidade (N/m)")
    break_strength: float = Field(..., gt=0, description="MBL (N)")
    modulus: Optional[float] = Field(default=None, gt=0, description="Módulo (Pa)")
    qmoor_ea: Optional[float] = Field(default=None, gt=0, description="EA QMoor (N)")
    gmoor_ea: Optional[float] = Field(default=None, gt=0, description="EA GMoor (N)")
    seabed_friction_cf: float = Field(
        ..., ge=0, description="Coef. atrito seabed (adimensional)"
    )
    manufacturer: Optional[str] = Field(default=None, max_length=200)
    serial_number: Optional[str] = Field(default=None, max_length=100)
    comments: Optional[str] = Field(default=None, max_length=2000)


class LineTypeCreate(LineTypeBase):
    """Payload para POST /line-types (sempre user_input)."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "line_type": "MyCustomWire",
                "category": "Wire",
                "diameter": 0.076,
                "dry_weight": 180.0,
                "wet_weight": 150.0,
                "break_strength": 5_000_000.0,
                "modulus": 1.0e11,
                "qmoor_ea": 8.0e7,
                "seabed_friction_cf": 0.3,
                "manufacturer": "Acme",
            }
        }
    )


class LineTypeUpdate(LineTypeBase):
    """Payload para PUT /line-types/{id}."""


class LineTypeOutput(LineTypeBase):
    """Item retornado pelos endpoints de listagem e detalhe."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    legacy_id: Optional[int]
    data_source: DataSource
    created_at: datetime
    updated_at: datetime


__all__ = [
    "Category",
    "DataSource",
    "LineTypeBase",
    "LineTypeCreate",
    "LineTypeOutput",
    "LineTypeUpdate",
    "UnitSystem",
]
