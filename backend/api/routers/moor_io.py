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
from backend.api.services.moor_qmoor_v0_8 import (
    QMoorV08ParseError,
    parse_qmoor_v0_8,
)
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


@router.post(
    "/import/qmoor-0_8/preview",
    summary="Preview QMoor 0.8.0 (lista profiles, não persiste nada)",
    description=(
        "Recebe JSON top-level QMoor 0.8.0. Retorna preview com lista "
        "de mooringLines × profiles disponíveis e log de parse. UI usa "
        "esse preview para mostrar selector ao usuário antes de chamar "
        "/commit. Sprint 1 / Commit 7."
    ),
    responses={
        400: {"model": ErrorResponse, "description": "Payload QMoor 0.8.0 inválido"},
    },
)
def import_qmoor_v0_8_preview(
    payload: dict[str, Any] = Body(..., description="JSON QMoor 0.8.0"),
) -> dict[str, Any]:
    try:
        cases, log = parse_qmoor_v0_8(payload)
    except QMoorV08ParseError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "qmoor_v0_8_parse_error", "message": str(exc)},
        )
    items = [
        {
            "index": i,
            "name": ci.name,
            "description": ci.description,
            "n_segments": len(ci.segments),
            "n_attachments": len(ci.attachments),
            "has_vessel": ci.vessel is not None,
            "has_current_profile": ci.current_profile is not None,
            "metadata_keys": list((ci.metadata or {}).keys()),
        }
        for i, ci in enumerate(cases)
    ]
    return {
        "items": items,
        "migration_log": log,
        "total": len(items),
    }


@router.post(
    "/import/qmoor-0_8/commit",
    status_code=status.HTTP_201_CREATED,
    summary="Importa cases QMoor 0.8.0 selecionados (cria casos no DB)",
    description=(
        "Recebe `{payload: <QMoor JSON>, selected_indices: [int, ...]}`. "
        "Re-roda o parser e persiste apenas os cases nos índices "
        "selecionados (índices baseiam-se na ordem retornada pelo "
        "/preview). Usuário sempre tem a opção de re-importar com outros "
        "índices. Sprint 1 / Commit 7."
    ),
    responses={
        400: {"model": ErrorResponse, "description": "Payload QMoor 0.8.0 inválido"},
    },
)
def import_qmoor_v0_8_commit(
    body: dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    payload = body.get("payload")
    indices = body.get("selected_indices")
    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "missing_payload", "message": "body.payload obrigatório."},
        )
    if not isinstance(indices, list) or not all(isinstance(i, int) for i in indices):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "invalid_indices",
                "message": "body.selected_indices deve ser list[int].",
            },
        )
    try:
        cases, log = parse_qmoor_v0_8(payload)
    except QMoorV08ParseError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "qmoor_v0_8_parse_error", "message": str(exc)},
        )

    created: list[dict[str, Any]] = []
    for idx in indices:
        if idx < 0 or idx >= len(cases):
            log.append({
                "field": f"selected_indices[{idx}]",
                "old": idx, "new": "skipped",
                "reason": f"índice fora do range [0, {len(cases) - 1}].",
            })
            continue
        rec = case_service.create_case(db, cases[idx])
        out = case_service.case_record_to_output(rec)
        created.append(out.model_dump(mode="json"))

    return {
        "created": created,
        "n_created": len(created),
        "migration_log": log,
    }


__all__ = ["router"]
