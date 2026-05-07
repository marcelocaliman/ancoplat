"""Schemas Pydantic do catálogo de vessels (Sprint 6 / Commit 51-52)."""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

VesselType = Literal[
    "FPSO",
    "Semisubmersible",
    "FSO",
    "Spar",
    "TLP",
    "AHV",
    "Drillship",
    "MODU",
    "Barge",
]
UnitSystem = Literal["imperial", "metric"]
DataSource = Literal[
    "legacy_qmoor",
    "generic_offshore",
    "manufacturer",
    "user_input",
]


class VesselBase(BaseModel):
    """Campos comuns (create/update/output)."""

    name: str = Field(
        ..., min_length=1, max_length=120,
        description="Identificador legível (ex.: 'P-77 (FPSO)').",
    )
    vessel_type: VesselType = Field(
        ...,
        description=(
            "Classe da plataforma. Determina o ícone SVG no plot."
        ),
    )
    base_unit_system: UnitSystem = Field(
        default="metric",
        description="Sistema de origem. Valores no payload SEMPRE em SI.",
    )
    loa: float = Field(..., gt=0, description="Length Overall (m)")
    breadth: float = Field(..., gt=0, description="Boca / largura (m)")
    draft: float = Field(..., gt=0, description="Calado (m)")
    displacement: Optional[float] = Field(
        default=None, ge=0,
        description="Deslocamento em N (peso, não massa). Opcional.",
    )
    default_heading_deg: float = Field(
        default=0.0,
        description=(
            "Heading horizontal default no plano global (graus). "
            "0° = direção +X global, anti-horário positivo "
            "(mesmo referencial de F5.5 EnvironmentalLoad)."
        ),
    )
    operator: Optional[str] = Field(default=None, max_length=200)
    manufacturer: Optional[str] = Field(default=None, max_length=200)
    serial_number: Optional[str] = Field(default=None, max_length=100)
    comments: Optional[str] = Field(default=None, max_length=2000)


class VesselCreate(VesselBase):
    """Payload para POST /vessel-types (sempre user_input)."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "MyCustomFPSO",
                "vessel_type": "FPSO",
                "loa": 280.0,
                "breadth": 50.0,
                "draft": 18.0,
                "displacement": 1_800_000_000.0,
                "operator": "MyCompany",
            }
        }
    )


class VesselUpdate(VesselBase):
    """Payload para PUT /vessel-types/{id}."""


class VesselOutput(VesselBase):
    """Item retornado pelos endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    legacy_id: Optional[int]
    data_source: DataSource
    created_at: datetime
    updated_at: datetime


__all__ = [
    "DataSource",
    "UnitSystem",
    "VesselBase",
    "VesselCreate",
    "VesselOutput",
    "VesselType",
    "VesselUpdate",
]
