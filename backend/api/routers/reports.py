"""Endpoint de geração de PDF (F2.7)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from backend.api.db.session import get_db
from backend.api.schemas.errors import ErrorResponse
from backend.api.services import case_service
from backend.api.services.case_service import CaseNotFound
from backend.api.services.pdf_report import build_memorial_pdf, build_pdf

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


__all__ = ["router"]
