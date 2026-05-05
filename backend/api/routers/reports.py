"""Endpoint de geração de PDF (F2.7)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from backend.api.db.session import get_db
from backend.api.schemas.errors import ErrorResponse
from backend.api.services import case_service
from backend.api.services.case_service import CaseNotFound
from backend.api.schemas.cases import CaseInput
from backend.api.services.csv_export import build_geometry_csv
from backend.api.services.pdf_report import build_memorial_pdf, build_pdf
from backend.api.services.xlsx_export import build_xlsx
from backend.solver.types import SolverResult

router = APIRouter(tags=["import-export"])


@router.get(
    "/cases/{case_id}/export/pdf",
    summary="Exportar relatório técnico em PDF",
    description=(
        "Gera um relatório técnico em PDF A4 com:\n"
        "1. Header (caso, timestamp, solver version)\n"
        "2. Disclaimer técnico obrigatório (Seção 10 do Documento A v2.2)\n"
        "3. Tabela de inputs\n"
        "4. Gráfico 2D do perfil da linha (matplotlib)\n"
        "5. Tabela de resultados com alert level colorido\n"
        "6. Status e mensagem do solver\n\n"
        "Usa a **última execução** do caso. Se o caso nunca foi resolvido, "
        "gera um relatório parcial apenas com as entradas."
    ),
    response_class=Response,
    responses={
        200: {
            "content": {"application/pdf": {}},
            "description": "PDF gerado com sucesso",
        },
        404: {"model": ErrorResponse},
    },
)
def export_pdf(case_id: int, db: Session = Depends(get_db)) -> Response:
    try:
        rec = case_service.get_case(db, case_id)
    except CaseNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "case_not_found",
                "message": f"Caso id={case_id} não encontrado.",
            },
        )
    latest = rec.executions[0] if rec.executions else None
    pdf_bytes = build_pdf(rec, latest)
    filename = f"ancoplat_caso_{case_id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@router.get(
    "/cases/{case_id}/export/memorial-pdf",
    summary="Exportar memorial técnico em PDF (Fase 5)",
    description=(
        "Gera memorial técnico expandido em PDF A4 — diferente do "
        "/export/pdf resumido. Pensado para entrega ao cliente, com:\n"
        "1. Capa com hash SHA-256 do caso, solver_version, timestamp\n"
        "2. Premissas e escopo da análise\n"
        "3. Sumário executivo + ProfileType detectado (Fase 4)\n"
        "4. Identificação + boundary + segmentos detalhados (com EA "
        "source e μ_eff per segmento — Fase 1)\n"
        "5. Plot 2D + distribuição de tensão\n"
        "6. Diagnostics estruturados com severity + confidence (Fase 4)\n"
        "7. Footer com hash + solver_version + timestamp em cada página\n\n"
        "Usa a última execução do caso. Sem execução, gera memorial "
        "parcial.\n\n"
        "Reprodutibilidade científica: hash identifica unicamente esta "
        "configuração física (independente de nome/descrição)."
    ),
    response_class=Response,
    responses={
        200: {
            "content": {"application/pdf": {}},
            "description": "Memorial PDF gerado com sucesso",
        },
        404: {"model": ErrorResponse},
    },
)
def export_memorial_pdf(case_id: int, db: Session = Depends(get_db)) -> Response:
    try:
        rec = case_service.get_case(db, case_id)
    except CaseNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "case_not_found",
                "message": f"Caso id={case_id} não encontrado.",
            },
        )
    latest = rec.executions[0] if rec.executions else None
    pdf_bytes = build_memorial_pdf(rec, latest)
    filename = f"ancoplat_memorial_{case_id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@router.get(
    "/cases/{case_id}/export/csv",
    summary="Exportar geometria em CSV (international format)",
    description=(
        "CSV com a geometria do cabo em formato international (decimal "
        "ponto, separator vírgula) — para análise externa em Python/"
        "MATLAB/Octave/R.\n\n"
        "Header: `x_m,y_m,tension_x_n,tension_y_n,tension_magnitude_n`\n\n"
        "Linhas: 1 header + N pontos do solve (≥ 5000 em casos "
        "típicos). Inclui comentários iniciados com `#` para "
        "rastreabilidade (case name, timestamp, solver_version).\n\n"
        "**Para abrir no Excel BR**: use Importar Dados → Texto, não "
        "duplo-clique (Excel BR espera `;` como separator)."
    ),
    response_class=Response,
    responses={
        200: {
            "content": {"text/csv": {}},
            "description": "CSV gerado com sucesso",
        },
        404: {"model": ErrorResponse},
        409: {
            "model": ErrorResponse,
            "description": "Caso nunca foi resolvido — sem geometria",
        },
    },
)
def export_csv(case_id: int, db: Session = Depends(get_db)) -> Response:
    try:
        rec = case_service.get_case(db, case_id)
    except CaseNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "case_not_found",
                "message": f"Caso id={case_id} não encontrado.",
            },
        )
    if not rec.executions:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "no_execution",
                "message": (
                    f"Caso id={case_id} nunca foi resolvido — sem "
                    "geometria para exportar. Execute POST /cases/{id}/solve."
                ),
            },
        )
    latest = rec.executions[0]
    result = SolverResult.model_validate_json(latest.result_json)
    case_name = rec.name or f"case_{case_id}"
    csv_text = build_geometry_csv(result, case_name=case_name)
    filename = f"ancoplat_geometry_{case_id}.csv"
    return Response(
        content=csv_text,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@router.get(
    "/cases/{case_id}/export/xlsx",
    summary="Exportar caso completo em Excel (.xlsx)",
    description=(
        "Gera arquivo Excel com 3 abas + Diagnostics opcional:\n\n"
        "**Aba Caso**: metadados + inputs (segments + boundary + seabed)\n\n"
        "**Aba Resultados**: escalares (T_fl, T_anc, X, L_susp/grnd, "
        "ângulos, ProfileType detectado, utilização, alert level)\n\n"
        "**Aba Geometria**: ≥ 5000 linhas com x, y, T_x, T_y, T_mag\n\n"
        "**Aba Diagnostics** (condicional): tabela de diagnostics "
        "estruturados se houver, com severity colorida e confidence — "
        "estrutura consistente com Memorial PDF (Fase 5 / Q6 detail).\n\n"
        "Sem solve, só aba Caso é gerada."
    ),
    response_class=Response,
    responses={
        200: {
            "content": {
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {}
            },
            "description": "Excel gerado com sucesso",
        },
        404: {"model": ErrorResponse},
    },
)
def export_xlsx(case_id: int, db: Session = Depends(get_db)) -> Response:
    try:
        rec = case_service.get_case(db, case_id)
    except CaseNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "case_not_found",
                "message": f"Caso id={case_id} não encontrado.",
            },
        )
    case_input = CaseInput.model_validate_json(rec.input_json)
    result = None
    if rec.executions:
        result = SolverResult.model_validate_json(rec.executions[0].result_json)
    xlsx_bytes = build_xlsx(case_input, result)
    filename = f"ancoplat_caso_{case_id}.xlsx"
    return Response(
        content=xlsx_bytes,
        media_type=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


__all__ = ["router"]
