"""
Lógica de negócio para casos (CRUD).

Centraliza serialização CaseInput ↔ CaseRecord.input_json e as queries
comuns. Router fica fino.
"""
from __future__ import annotations

import logging
from typing import Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.api.db.models import CaseRecord, ExecutionRecord, LineTypeRecord

logger = logging.getLogger("ancoplat.api.cases")
from backend.api.schemas.cases import (
    CaseInput,
    CaseOutput,
    CaseSummary,
    ExecutionOutput,
)
from backend.solver.types import SolverResult


# ==============================================================================
# Validações específicas (Fase 1)
# ==============================================================================


class GmoorNotAvailableInCatalog(Exception):
    """
    Disparada quando um segmento pede `ea_source="gmoor"` mas o
    `line_type` referenciado tem `gmoor_ea = NULL` no catálogo.

    Esta validação é defesa em profundidade no backend (Q4 da Fase 1):
    a UI já desabilita a opção GMoor visualmente quando catálogo não tem
    o coeficiente, mas chamadas via API direta (sem frontend) precisam
    rejeitar com mensagem orientadora citando o tipo específico.
    """

    def __init__(self, segment_index: int, line_type: str) -> None:
        self.segment_index = segment_index
        self.line_type = line_type
        super().__init__(
            f"Linha '{line_type}' (segmento #{segment_index + 1}) não tem "
            f"coeficiente GMoor no catálogo. Use ea_source='qmoor' ou "
            f"escolha outro tipo."
        )


def _validate_ea_source_against_catalog(
    db: Session, case_input: CaseInput
) -> None:
    """
    Para cada segmento com `line_type` definido E `ea_source="gmoor"`,
    confirma que o catálogo tem `gmoor_ea` populado.

    Comportamento:
      - segmento sem `line_type` (custom do usuário): não valida — confia
        no EA fornecido pelo usuário.
      - `line_type` no payload mas não no catálogo: passa silenciosamente
        (custom line_type, não está no catálogo legado).
      - `line_type` existe no catálogo, `ea_source="gmoor"`, gmoor_ea NULL:
        levanta `GmoorNotAvailableInCatalog`.
      - `ea_source="qmoor"` (default): nunca valida.
    """
    for i, seg in enumerate(case_input.segments):
        if seg.line_type is None or seg.ea_source != "gmoor":
            continue
        # `line_type` é uma família (ex.: "IWRCEIPS", "R4Studless"), pode
        # haver múltiplas entradas no catálogo (uma por diâmetro). A
        # existência de `gmoor_ea` é uniforme dentro da família — basta
        # checar qualquer registro com esse `line_type`.
        rec = db.execute(
            select(LineTypeRecord)
            .where(LineTypeRecord.line_type == seg.line_type)
            .limit(1)
        ).scalar_one_or_none()
        if rec is None:
            # line_type custom (não está no catálogo) — confia no EA fornecido
            continue
        if rec.gmoor_ea is None:
            raise GmoorNotAvailableInCatalog(i, seg.line_type)


# ==============================================================================
# Serialização CaseInput ↔ CaseRecord
# ==============================================================================


def _line_type_of(case_input: CaseInput) -> str | None:
    """Primeiro segmento.line_type (desnormalizado para filtros)."""
    if case_input.segments:
        return case_input.segments[0].line_type
    return None


def case_record_to_summary(rec: CaseRecord) -> CaseSummary:
    return CaseSummary(
        id=rec.id,
        name=rec.name,
        description=rec.description,
        line_type=rec.line_type,
        mode=rec.mode,
        water_depth=rec.water_depth,
        line_length=rec.line_length,
        criteria_profile=rec.criteria_profile,
        created_at=rec.created_at,
        updated_at=rec.updated_at,
    )


def case_record_to_output(rec: CaseRecord) -> CaseOutput:
    """
    Hidrata CaseRecord em CaseOutput incluindo execuções.

    Se uma execução individual tem `result_json` corrompido (campo
    legacy ou edição manual no banco), pulamos só essa entrada com
    aviso no log — sem derrubar a resposta inteira.
    """
    case_input = CaseInput.model_validate_json(rec.input_json)
    executions: list[ExecutionOutput] = []
    for e in rec.executions:
        try:
            executions.append(
                ExecutionOutput(
                    id=e.id,
                    case_id=e.case_id,
                    result=SolverResult.model_validate_json(e.result_json),
                    executed_at=e.executed_at,
                )
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "execução id=%s do caso id=%s ignorada (result_json corrompido): %s",
                e.id, rec.id, exc,
            )
    return CaseOutput(
        id=rec.id,
        name=rec.name,
        description=rec.description,
        input=case_input,
        latest_executions=executions,
        created_at=rec.created_at,
        updated_at=rec.updated_at,
    )


# ==============================================================================
# CRUD
# ==============================================================================


class CaseNotFound(Exception):
    """Disparado quando um case_id inexistente é consultado."""


def create_case(db: Session, case_input: CaseInput) -> CaseRecord:
    """Persiste um novo caso e retorna o registro com id/timestamps.

    F5.1: linha pode ter múltiplos segmentos. As colunas denormalizadas
    `line_type` e `line_length` da tabela `cases` (usadas em listagens
    e busca) ganham:
      - line_type = primeiro line_type não-nulo (ou junção 'A+B+C' para
        listagens) — adotamos o primeiro pra manter compatibilidade.
      - line_length = soma dos comprimentos.

    Fase 1: valida `ea_source="gmoor"` contra o catálogo (defesa em
    profundidade — UI também valida).
    """
    _validate_ea_source_against_catalog(db, case_input)
    first = case_input.segments[0]
    rec = CaseRecord(
        name=case_input.name,
        description=case_input.description,
        input_json=case_input.model_dump_json(),
        line_type=first.line_type,
        mode=case_input.boundary.mode.value,
        water_depth=case_input.boundary.h,
        line_length=sum(s.length for s in case_input.segments),
        criteria_profile=case_input.criteria_profile.value,
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec


def get_case(db: Session, case_id: int) -> CaseRecord:
    """Carrega caso com execuções ou levanta CaseNotFound."""
    rec = db.get(CaseRecord, case_id)
    if rec is None:
        raise CaseNotFound(case_id)
    return rec


def update_case(
    db: Session, case_id: int, case_input: CaseInput
) -> CaseRecord:
    """Atualiza campos do caso (substitui input_json integralmente).

    Fase 1: valida `ea_source="gmoor"` contra o catálogo antes de
    persistir.
    """
    _validate_ea_source_against_catalog(db, case_input)
    rec = get_case(db, case_id)
    first = case_input.segments[0]
    rec.name = case_input.name
    rec.description = case_input.description
    rec.input_json = case_input.model_dump_json()
    rec.line_type = first.line_type
    rec.mode = case_input.boundary.mode.value
    rec.water_depth = case_input.boundary.h
    rec.line_length = sum(s.length for s in case_input.segments)
    rec.criteria_profile = case_input.criteria_profile.value
    # updated_at é atualizado automaticamente pelo SQLAlchemy via `onupdate`
    db.commit()
    db.refresh(rec)
    return rec


def delete_case(db: Session, case_id: int) -> None:
    """Remove caso (cascade deleta execuções via FK ON DELETE CASCADE)."""
    rec = get_case(db, case_id)
    db.delete(rec)
    db.commit()


def list_cases(
    db: Session,
    page: int = 1,
    page_size: int = 20,
    search: str | None = None,
) -> tuple[Sequence[CaseRecord], int]:
    """
    Lista casos paginados. `search` filtra por `name ILIKE %search%`.
    Retorna (itens_da_pagina, total_total).
    """
    stmt = select(CaseRecord)
    count_stmt = select(func.count()).select_from(CaseRecord)
    if search:
        like = f"%{search}%"
        stmt = stmt.where(CaseRecord.name.ilike(like))
        count_stmt = count_stmt.where(CaseRecord.name.ilike(like))
    total = db.execute(count_stmt).scalar_one()
    offset = (page - 1) * page_size
    stmt = stmt.order_by(CaseRecord.updated_at.desc()).offset(offset).limit(page_size)
    items = db.execute(stmt).scalars().all()
    return items, total


__all__ = [
    "CaseNotFound",
    "GmoorNotAvailableInCatalog",
    "case_record_to_output",
    "case_record_to_summary",
    "create_case",
    "delete_case",
    "get_case",
    "list_cases",
    "update_case",
]
