"""
Endpoint POST /api/v1/cases/{case_id}/solve (Seção 3.1 do plano F2).

Resolve o caso, persiste a execução, retorna SolverResult. Mapeamento
de status → HTTP conforme Seção 5.3 do plano:
  - converged / ill_conditioned → 200
  - max_iterations              → 200 (com aviso no body)
  - invalid_case / numerical    → 422
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from backend.api.db.session import get_db
from backend.api.schemas.cases import ExecutionOutput
from backend.api.schemas.errors import ErrorResponse
from backend.api.services.case_service import CaseNotFound
from backend.api.services.execution_service import (
    http_status_for_solver_status,
    run_solve_and_persist,
)

router = APIRouter(tags=["solve"])


@router.post(
    "/cases/{case_id}/solve",
    response_model=ExecutionOutput,
    summary="Executar solver no caso",
    description=(
        "Invoca o solver de catenária estática no caso salvo. Persiste a "
        "execução no histórico (mantém últimas 10 por caso) e retorna o "
        "resultado completo.\n\n"
        "HTTP response codes:\n"
        "- **200** se o solver convergiu ou detectou caso mal-condicionado\n"
        "- **200** (com `status=max_iterations`) se atingiu limite sem convergir\n"
        "- **422** se o caso é fisicamente inviável (`invalid_case` ou "
        "`numerical_error`); o body ainda inclui o SolverResult"
    ),
    responses={
        404: {"model": ErrorResponse, "description": "Caso não encontrado"},
        422: {
            "model": ErrorResponse,
            "description": (
                "Caso inviável fisicamente (T_fl ≤ w·h, linha rompida, "
                "âncora elevada, etc.)."
            ),
        },
    },
)
def solve_case(
    case_id: int, response: Response, db: Session = Depends(get_db),
) -> ExecutionOutput:
    try:
        exec_rec, result = run_solve_and_persist(db, case_id)
    except CaseNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "case_not_found",
                "message": f"Caso id={case_id} não encontrado.",
            },
        )

    http_status = http_status_for_solver_status(result.status)
    if http_status != 200:
        # Caso inviável: sinaliza 422 mas devolve o SolverResult no body
        # (através do ExecutionOutput). O envelope ErrorResponse é usado
        # apenas para erros não-do-solver (404, 400, etc.).
        raise HTTPException(
            status_code=http_status,
            detail={
                "code": f"solver_{result.status.value}",
                "message": result.message,
                "detail": {
                    "execution_id": exec_rec.id,
                    "case_id": exec_rec.case_id,
                    "status": result.status.value,
                    "alert_level": result.alert_level.value,
                    "message": result.message,
                },
            },
        )

    response.status_code = http_status
    return ExecutionOutput(
        id=exec_rec.id,
        case_id=exec_rec.case_id,
        result=result,
        executed_at=exec_rec.executed_at,
    )


__all__ = ["router"]
