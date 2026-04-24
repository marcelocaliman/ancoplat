"""
Endpoints de metadados da API (health, version, criteria-profiles).

Não dependem de nenhum outro recurso; ficam disponíveis mesmo se o
banco estiver inacessível (exceto health, que consulta o DB).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.api.db.session import get_db
from backend.solver.types import PROFILE_LIMITS, CriteriaProfile, UtilizationLimits

router = APIRouter(tags=["metadata"])

# Versões visíveis nesta release. Mudar manualmente quando apropriado.
API_VERSION = "0.1.0"
SCHEMA_VERSION = "1"       # incrementa quando migrations quebram compat
SOLVER_VERSION = "1.0.0"   # solver F1b


class HealthResponse(BaseModel):
    """Resposta do healthcheck."""

    status: str = Field(..., examples=["ok"])
    db: str = Field(..., description="Estado do banco", examples=["ok"])


class VersionResponse(BaseModel):
    """Resposta do endpoint /version."""

    api: str = Field(..., examples=["0.1.0"])
    schema_version: str = Field(..., examples=["1"])
    solver: str = Field(..., examples=["1.0.0"])


class CriteriaProfileInfo(BaseModel):
    """Descrição de um perfil de critério de utilização."""

    name: str = Field(
        ...,
        description="Identificador do perfil (usado como valor de criteria_profile).",
        examples=["MVP_Preliminary"],
    )
    yellow_ratio: float = Field(
        ..., description="Limite T_fl/MBL para alerta amarelo.", examples=[0.50]
    )
    red_ratio: float = Field(
        ..., description="Limite T_fl/MBL para alerta vermelho.", examples=[0.60]
    )
    broken_ratio: float = Field(
        ..., description="T_fl/MBL a partir do qual o caso vira INVALID_CASE.",
        examples=[1.00],
    )
    description: str = Field(
        ..., description="Explicação curta do perfil."
    )


_PROFILE_DESCRIPTIONS: dict[CriteriaProfile, str] = {
    CriteriaProfile.MVP_PRELIMINARY: (
        "Default simples: 0,50 yellow / 0,60 red / 1,00 broken. "
        "Apropriado para pré-projeto e treinamento."
    ),
    CriteriaProfile.API_RP_2SK: (
        "Conforme API RP 2SK: intacto 0,60, danificado 0,80 — "
        "após 0,80 o caso é classificado como rompido."
    ),
    CriteriaProfile.DNV_PLACEHOLDER: (
        "Reservado para DNV ULS/ALS/FLS. Até F4+ com análise dinâmica, "
        "usa os mesmos limites do MVP_Preliminary."
    ),
    CriteriaProfile.USER_DEFINED: (
        "Usuário fornece user_defined_limits (yellow/red/broken) em cada request."
    ),
}


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Healthcheck",
    description=(
        "Retorna 200 OK se a API está no ar e o banco SQLite responde a uma "
        "query trivial. Usado para smoke tests e orquestração local."
    ),
)
def health(db: Session = Depends(get_db)) -> HealthResponse:
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Banco indisponível: {exc}",
        )
    return HealthResponse(status="ok", db="ok")


@router.get(
    "/version",
    response_model=VersionResponse,
    summary="Versões dos componentes",
    description="Versão da API, do schema do banco e do solver subjacente.",
)
def version() -> VersionResponse:
    return VersionResponse(
        api=API_VERSION, schema_version=SCHEMA_VERSION, solver=SOLVER_VERSION
    )


@router.get(
    "/criteria-profiles",
    response_model=list[CriteriaProfileInfo],
    summary="Perfis de critério de utilização disponíveis",
    description=(
        "Lista os 4 perfis suportados (MVP_Preliminary, API_RP_2SK, "
        "DNV_placeholder, UserDefined) com seus limites default. "
        "Para UserDefined, os limites são fornecidos no request e este "
        "endpoint retorna placeholders."
    ),
)
def list_criteria_profiles() -> list[CriteriaProfileInfo]:
    items: list[CriteriaProfileInfo] = []
    for profile in CriteriaProfile:
        if profile == CriteriaProfile.USER_DEFINED:
            # UserDefined não tem default — placeholder com limites neutros.
            limits = UtilizationLimits()
        else:
            limits = PROFILE_LIMITS[profile]
        items.append(
            CriteriaProfileInfo(
                name=profile.value,
                yellow_ratio=limits.yellow_ratio,
                red_ratio=limits.red_ratio,
                broken_ratio=limits.broken_ratio,
                description=_PROFILE_DESCRIPTIONS[profile],
            )
        )
    return items


__all__ = ["router", "API_VERSION", "SCHEMA_VERSION", "SOLVER_VERSION"]
