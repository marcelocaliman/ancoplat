"""
Endpoints de import/export .moor (Seção 3.3 do plano F2).

Rotas implementadas:
  POST /api/v1/import/moor           — body JSON no formato Seção 5.2 MVP v2
  GET  /api/v1/cases/{id}/export/moor?unit_system=imperial|metric
  GET  /api/v1/cases/{id}/export/json — input + última execução

Upload multipart de arquivo `.moor` binário não é suportado neste MVP
(Q2 da auditoria: formato original era .pyd inacessível). Para importar,
cole o JSON diretamente.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.api.db.session import get_db
from backend.api.schemas.cases import CaseOutput
from backend.api.schemas.errors import ErrorResponse
from backend.api.services import case_service, moor_service
from backend.api.services.case_service import CaseNotFound
from backend.api.services.moor_service import MoorFormatError

router = APIRouter(tags=["import-export"])


@router.post(
    "/import/moor",
    status_code=status.HTTP_201_CREATED,
    summary="Importar caso no formato .moor",
    description=(
        "Aceita JSON body no schema da Seção 5.2 do MVP v2 PDF. Campos "
        "quantitativos podem vir como strings com unidade (\"450 ft\", "
        "\"13.78 lbf/ft\") ou números puros (usa unidade padrão do "
        "`unitSystem`).\n\n"
        "Exemplo minimal (imperial):\n"
        "```json\n"
        "{\"name\": \"Import test\", \"unitSystem\": \"imperial\",\n"
        " \"mooringLine\": {\"name\": \"ML1\",\n"
        "  \"segments\": [{\"category\": \"Wire\",\n"
        "    \"length\": \"1476.4 ft\",\n"
        "    \"lineProps\": {\"lineType\": \"IWRCEIPS\",\n"
        "      \"diameter\": \"3 in\", \"breakStrength\": \"850 kip\",\n"
        "      \"wetWeight\": \"13.78 lbf/ft\", \"dryWeight\": \"16.6 lbf/ft\",\n"
        "      \"modulus\": \"9804 kip/in^2\", \"seabedFrictionCF\": 0.6}}],\n"
        "  \"boundary\": {\"startpointDepth\": \"0 ft\",\n"
        "    \"endpointDepth\": \"984 ft\", \"endpointGrounded\": true},\n"
        "  \"solution\": {\"inputParam\": \"Tension\",\n"
        "    \"fairleadTension\": \"150 kip\"}}}\n"
        "```"
    ),
    responses={
        400: {"model": ErrorResponse, "description": "Schema .moor inválido"},
        422: {"model": ErrorResponse, "description": "Conversão para SI falhou"},
    },
)
def import_moor(
    payload: dict[str, Any] = Body(..., description="JSON no formato .moor"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Importa `.moor` v1 ou v2. Retorna `{case: CaseOutput, migration_log:
    list[dict]}`. `migration_log` é não-vazio quando o payload era v1 e
    o migrador populou defaults — UI deve renderizar como warnings
    estruturados (Fase 5 / Ajuste 2).
    """
    try:
        case_input, migration_log = moor_service.parse_moor_payload_with_log(payload)
    except MoorFormatError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "moor_format_error", "message": str(exc)},
        )
    rec = case_service.create_case(db, case_input)
    case_output = case_service.case_record_to_output(rec)
    return {
        "case": case_output.model_dump(mode="json"),
        "migration_log": migration_log,
    }


@router.get(
    "/cases/{case_id}/export/moor",
    summary="Exportar caso como .moor",
    description=(
        "Serializa o caso no schema .moor (Seção 5.2 MVP v2). Escolha o "
        "`unit_system` — `imperial` ou `metric`. Valores SI internos são "
        "convertidos para a unidade de saída."
    ),
    responses={404: {"model": ErrorResponse}},
)
def export_moor(
    case_id: int,
    unit_system: str = Query(
        default="metric",
        pattern="^(imperial|metric)$",
        description="Sistema de unidades da saída",
    ),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        rec = case_service.get_case(db, case_id)
    except CaseNotFound:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "case_not_found",
                "message": f"Caso id={case_id} não encontrado.",
            },
        )
    return moor_service.export_case_as_moor(rec, unit_system=unit_system)


@router.get(
    "/cases/{case_id}/export/json",
    summary="Exportar caso como JSON normalizado",
    description=(
        "Retorna o `CaseOutput` completo (input em SI + últimas execuções). "
        "Equivalente a GET /cases/{id}, mas tem rota explícita de export."
    ),
    response_model=CaseOutput,
    responses={404: {"model": ErrorResponse}},
)
def export_json(
    case_id: int, db: Session = Depends(get_db)
) -> CaseOutput:
    try:
        rec = case_service.get_case(db, case_id)
    except CaseNotFound:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "case_not_found",
                "message": f"Caso id={case_id} não encontrado.",
            },
        )
    return case_service.case_record_to_output(rec)


__all__ = ["router"]
