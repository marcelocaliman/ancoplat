"""
Hash determinístico de CaseInput baseado em fields físicos (Fase 5 / Q3).

Decisão fechada na Fase 5:
- Algoritmo: **SHA-256** dos campos físicos (segments + boundary + seabed
  + attachments + criteria_profile + user_defined_limits).
- Excluídos: name, description, timestamps — hash não muda quando o
  caso é renomeado ou redescrito. Mesmo physical configuration sempre
  produz o mesmo hash.

Canonicalização (Ajuste 1 da Fase 5):
- Pydantic `model_dump(mode='json')` produz dict serializável.
- `json.dumps(..., sort_keys=True, separators=(',', ':'))` força ordem
  determinística de chaves + sem whitespace. Resultado bit-a-bit
  reprodutível entre runs e versões do Python (3.7+).

Determinismo testado em test_case_hash.py:
- Mesmo CaseInput → mesmo hash entre runs (estabilidade temporal).
- Renomear CaseInput → mesmo hash (independência do nome).
- Mudar field físico → hash muda (sensibilidade física).
- Reordenar dicionário → mesmo hash (canonicalização garantida).
"""
from __future__ import annotations

import hashlib
import json

from backend.api.schemas.cases import CaseInput


# Campos NÃO incluídos no hash. Mudar essa lista é breaking change —
# hashes existentes deixam de bater. Documente no relatório/changelog.
_NON_PHYSICAL_FIELDS = frozenset({"name", "description"})


def _canonicalize_case_input(case_input: CaseInput) -> str:
    """
    Serializa CaseInput em JSON canônico (ordem de chaves alfabética,
    sem whitespace, formato de números consistente via Pydantic).

    Excluí campos não-físicos (name, description). Timestamps NÃO
    fazem parte de CaseInput — não há o que excluir.
    """
    # mode='json' garante que tipos Python (Enum, etc.) sejam reduzidos
    # a primitivas JSON-serializáveis com formato estável.
    payload = case_input.model_dump(mode="json")
    physical = {k: v for k, v in payload.items() if k not in _NON_PHYSICAL_FIELDS}
    # sort_keys + separators sem whitespace = canonical JSON
    return json.dumps(physical, sort_keys=True, separators=(",", ":"))


def case_input_hash(case_input: CaseInput) -> str:
    """
    SHA-256 hexdigest (64 chars) de CaseInput canonicalizado.

    Determinístico para mesmo physical configuration. Renomear ou
    redescrever NÃO muda o hash — só mudanças em segments, boundary,
    seabed, attachments, criteria_profile ou user_defined_limits afetam.

    Use case_input_short_hash() para display em UI/PDFs (16 chars).
    """
    canonical = _canonicalize_case_input(case_input)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def case_input_short_hash(case_input: CaseInput) -> str:
    """
    Primeiros 16 chars do hash SHA-256 — suficiente para display em
    UI/PDFs (espaço de 16 hex chars = 64 bits, colisão prática
    impossível para população de cases razoável).
    """
    return case_input_hash(case_input)[:16]
