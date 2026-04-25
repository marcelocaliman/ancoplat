"""
Schemas Pydantic da API para Mooring Systems (F5.4).

Um *mooring system* é um conjunto de N linhas de ancoragem ligadas a
uma mesma plataforma. Cada linha tem geometria própria (segmentos,
boundary, seabed, etc.) e uma posição local no fairlead, descrita por
azimuth e raio (coordenadas polares no plano da plataforma).

MVP F5.4 não faz equilíbrio de plataforma: cada linha é resolvida de
forma independente com `boundary.input_value` fixo (`Tension` ou
`Range`). O agregado de forças é calculado em F5.4.2 a partir das
soluções individuais.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.solver.types import (
    BoundaryConditions,
    CriteriaProfile,
    LineAttachment,
    LineSegment,
    MooringSystemResult,
    SeabedConfig,
    UtilizationLimits,
)


class SystemLineSpec(BaseModel):
    """
    Definição de uma linha dentro de um mooring system.

    Equivale a um `CaseInput` (sem o nome do caso e sem a descrição),
    acrescido das coordenadas polares do fairlead no frame da plataforma.

    Convenção do plano horizontal:
      - Origem no centro da plataforma.
      - +X aponta para a proa (azimuth = 0°).
      - Sentido anti-horário (ângulo cresce de proa → bombordo → popa).
      - `fairlead_radius` em metros, distância radial do centro até o ponto
        de fixação da linha no casco.
      - Linha sai radialmente (azimuth + 180°) — a âncora fica no
        prolongamento radial, a uma distância `total_horz_distance` da
        plataforma (resolvida pelo solver).
    """

    model_config = ConfigDict(frozen=True)

    name: str = Field(
        ...,
        min_length=1,
        max_length=80,
        description="Identificador da linha (ex.: 'L1', 'proa BB').",
    )
    fairlead_azimuth_deg: float = Field(
        ...,
        ge=0.0,
        lt=360.0,
        description="Azimuth do fairlead no plano da plataforma, em graus.",
    )
    fairlead_radius: float = Field(
        ...,
        gt=0.0,
        description="Raio do fairlead a partir do centro da plataforma (m).",
    )

    # Definição da linha em si — mesma estrutura usada em CaseInput.
    segments: list[LineSegment] = Field(..., min_length=1, max_length=10)
    boundary: BoundaryConditions
    seabed: SeabedConfig = Field(default_factory=SeabedConfig)
    criteria_profile: CriteriaProfile = Field(default=CriteriaProfile.MVP_PRELIMINARY)
    user_defined_limits: Optional[UtilizationLimits] = Field(default=None)
    attachments: list[LineAttachment] = Field(default_factory=list, max_length=20)


class MooringSystemInput(BaseModel):
    """
    Configuração completa de um mooring system multi-linha.

    Persistida como `config_json` em `mooring_systems`. Não inclui
    resultados — a execução é responsabilidade da F5.4.2.
    """

    model_config = ConfigDict(
        frozen=True,
        json_schema_extra={
            "example": {
                "name": "Spread 4x — turret bow",
                "description": "Configuração simétrica 4 linhas, FPSO 60 m raio",
                "platform_radius": 30.0,
                "lines": [
                    {
                        "name": "L1",
                        "fairlead_azimuth_deg": 45.0,
                        "fairlead_radius": 30.0,
                        "segments": [
                            {
                                "length": 800.0,
                                "w": 1100.0,
                                "EA": 5.83e8,
                                "MBL": 5.57e6,
                                "category": "StuddedChain",
                                "line_type": "ORQ20",
                            }
                        ],
                        "boundary": {
                            "h": 300.0,
                            "mode": "Tension",
                            "input_value": 1_200_000.0,
                            "startpoint_depth": 0.0,
                            "endpoint_grounded": True,
                        },
                    }
                ],
            }
        },
    )

    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=2000)

    platform_radius: float = Field(
        ...,
        gt=0.0,
        description=(
            "Raio nominal da plataforma (m), usado para visualização "
            "(plan view) e não afeta o cálculo das linhas."
        ),
    )
    lines: list[SystemLineSpec] = Field(
        ...,
        min_length=1,
        max_length=16,
        description="Lista de linhas que compõem o sistema.",
    )

    @field_validator("lines")
    @classmethod
    def _unique_line_names(cls, lines: list[SystemLineSpec]) -> list[SystemLineSpec]:
        seen: set[str] = set()
        for line in lines:
            key = line.name.strip().lower()
            if key in seen:
                raise ValueError(f"Nome de linha duplicado: '{line.name}'")
            seen.add(key)
        return lines

    @model_validator(mode="after")
    def _user_limits_when_user_defined(self) -> "MooringSystemInput":
        for i, line in enumerate(self.lines):
            if (
                line.criteria_profile == CriteriaProfile.USER_DEFINED
                and line.user_defined_limits is None
            ):
                raise ValueError(
                    f"lines[{i}] usa criteria_profile=UserDefined mas não "
                    "tem user_defined_limits — campo é obrigatório."
                )
        return self


class MooringSystemSummary(BaseModel):
    """Versão enxuta para listagem (sem `config_json` completo)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: Optional[str]
    platform_radius: float
    line_count: int = Field(..., ge=1)
    created_at: datetime
    updated_at: datetime


class MooringSystemExecutionOutput(BaseModel):
    """Representação de uma execução persistida do mooring system."""

    id: int
    mooring_system_id: int
    result: MooringSystemResult
    executed_at: datetime


class MooringSystemOutput(BaseModel):
    """Representação detalhada (para GET /mooring-systems/{id})."""

    id: int
    name: str
    description: Optional[str]
    input: MooringSystemInput
    latest_executions: list[MooringSystemExecutionOutput] = Field(
        default_factory=list,
        description=(
            "Últimas 10 execuções (mais recente primeiro). Vazio se "
            "nunca foi resolvido."
        ),
    )
    created_at: datetime
    updated_at: datetime


__all__ = [
    "MooringSystemExecutionOutput",
    "MooringSystemInput",
    "MooringSystemOutput",
    "MooringSystemSummary",
    "SystemLineSpec",
]
