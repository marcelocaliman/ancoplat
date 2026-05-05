"""Schemas Pydantic do catálogo de boias (F6)."""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

# Mantemos o set fechado de end_types (espelha schema do `LineAttachment`
# na Fase 5.7 e fórmulas do Excel "Formula Guide" R4-R7).
EndType = Literal["flat", "hemispherical", "elliptical", "semi_conical"]
BuoyType = Literal["surface", "submersible"]
UnitSystem = Literal["imperial", "metric"]
DataSource = Literal[
    "excel_buoy_calc_v1",
    "generic_offshore",
    "manufacturer",
    "user_input",
]


class BuoyBase(BaseModel):
    """Campos comuns (create/update/output)."""

    name: str = Field(
        ..., min_length=1, max_length=120,
        description="Identificador legível (ex.: 'GEN-CYL-2.0x3.0-Hemi').",
    )
    buoy_type: BuoyType = Field(
        default="submersible",
        description=(
            "'surface' (boia de superfície / marker) ou 'submersible' "
            "(submergível, usada em lazy-S/wave). Apenas metadado."
        ),
    )
    end_type: EndType = Field(
        ...,
        description=(
            "Forma das tampas — usada na fórmula de volume "
            "(Excel Formula Guide R4-R7)."
        ),
    )
    base_unit_system: UnitSystem = Field(
        default="metric",
        description="Sistema de origem. Valores no payload SEMPRE em SI.",
    )
    outer_diameter: float = Field(..., gt=0, description="Diâmetro D (m)")
    length: float = Field(..., gt=0, description="Comprimento total L (m)")
    weight_in_air: float = Field(
        ..., ge=0, description="Peso da boia no ar (N)",
    )
    submerged_force: float = Field(
        ...,
        description=(
            "Empuxo líquido em N (V·ρ·g − weight_in_air). Pode ser "
            "negativo se o peso domina (objeto se torna clump). "
            "Pré-computado na seed via `compute_submerged_force`."
        ),
    )
    manufacturer: Optional[str] = Field(default=None, max_length=200)
    serial_number: Optional[str] = Field(default=None, max_length=100)
    comments: Optional[str] = Field(default=None, max_length=2000)


class BuoyCreate(BuoyBase):
    """Payload para POST /buoys (sempre user_input)."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "MyCustomBuoy",
                "buoy_type": "submersible",
                "end_type": "elliptical",
                "outer_diameter": 2.0,
                "length": 3.0,
                "weight_in_air": 4900.0,
                "submerged_force": 60000.0,
                "manufacturer": "Acme",
            }
        }
    )


class BuoyUpdate(BuoyBase):
    """Payload para PUT /buoys/{id}."""


class BuoyOutput(BuoyBase):
    """Item retornado pelos endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    legacy_id: Optional[int]
    data_source: DataSource
    created_at: datetime
    updated_at: datetime


__all__ = [
    "BuoyBase",
    "BuoyCreate",
    "BuoyOutput",
    "BuoyType",
    "BuoyUpdate",
    "DataSource",
    "EndType",
    "UnitSystem",
]
