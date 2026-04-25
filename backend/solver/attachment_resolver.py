"""
F5.4.6a — Resolver de attachments com posição contínua.

Permite que boias e clump weights sejam posicionados em qualquer
distância (`position_s_from_anchor`) ao longo da linha não-esticada,
não apenas em junções pré-existentes entre segmentos.

Estratégia: pré-processamento. Antes de chamar o solver canônico,
dividimos o segmento que contém o attachment em dois sub-segmentos
**com material idêntico**; o attachment passa a ficar exatamente na
nova junção. A matemática do solver multi-segmento (saltos de V em
junções) continua valendo sem mudança — tudo o que muda é a contagem
de segmentos.

Comportamento:
  - Attachments com `position_index` ficam intactos (modo legacy).
  - Attachments com `position_s_from_anchor` são convertidos.
  - Múltiplos attachments compartilhando a mesma posição → mesma junção.
  - Edge cases (s = 0, s ≥ total_length) viram ValueError.
"""
from __future__ import annotations

import math
from typing import Sequence

from .types import LineAttachment, LineSegment


_TOL_S = 1e-6  # tolerância de "mesma posição" em metros


def _cumulative_lengths(segments: Sequence[LineSegment]) -> list[float]:
    """Retorna os arc lengths cumulativos a partir da âncora.

    `cum[0] = 0` (âncora), `cum[i+1] = cum[i] + segments[i].length`.
    `cum[-1]` = comprimento total da linha não-esticada.
    """
    cum = [0.0]
    for seg in segments:
        cum.append(cum[-1] + seg.length)
    return cum


def _canonical_position(
    att: LineAttachment, cum: list[float]
) -> float:
    """Retorna `s_from_anchor` mesmo quando o attachment foi informado
    via `position_index` (junção pré-existente)."""
    if att.position_s_from_anchor is not None:
        return att.position_s_from_anchor
    # Fallback: position_index. Junção `j` está em `cum[j+1]`.
    if att.position_index is None:
        # Pydantic validator já garante que sempre tem um dos dois.
        raise ValueError(
            "LineAttachment sem posição (validator deveria ter pego)"
        )
    j = att.position_index
    if j < 0 or j + 1 >= len(cum):
        raise ValueError(
            f"position_index={j} fora do range válido (0..{len(cum) - 2})"
        )
    return cum[j + 1]


def resolve_attachments(
    segments: Sequence[LineSegment],
    attachments: Sequence[LineAttachment],
) -> tuple[list[LineSegment], list[LineAttachment]]:
    """
    Pré-processa attachments com posição contínua.

    Retorna `(new_segments, new_attachments)` onde todos os attachments
    têm `position_index` válido e `position_s_from_anchor=None`. Quando
    nada precisa ser dividido (e.g., todos via `position_index`), retorna
    os argumentos quase intactos (mas sempre listas novas, frozen
    `LineAttachment` é mantido pela `model_copy`).
    """
    if not attachments:
        return list(segments), []

    cum = _cumulative_lengths(segments)
    total_length = cum[-1]

    # 1. Converte tudo para a forma canônica (s_from_anchor).
    canonical: list[tuple[float, LineAttachment]] = []
    for att in attachments:
        s = _canonical_position(att, cum)
        if s <= _TOL_S:
            raise ValueError(
                f"Attachment '{att.name or att.kind}' em s={s:.4f} m: "
                "posição deve ser > 0 (não pode ficar sobre a âncora)"
            )
        if s >= total_length - _TOL_S:
            raise ValueError(
                f"Attachment '{att.name or att.kind}' em "
                f"s={s:.4f} m: posição deve ser < L_total ({total_length:.4f} m); "
                "não pode ficar sobre o fairlead"
            )
        canonical.append((s, att))

    # 2. Identifica posições que NÃO coincidem com junções existentes
    #    e que precisam de split. Posições próximas (within TOL) ao
    #    de uma junção são tratadas como sendo na própria junção.
    existing_junctions = set(cum)
    split_positions: set[float] = set()
    for s, _ in canonical:
        if not any(math.isclose(s, j, abs_tol=_TOL_S) for j in existing_junctions):
            split_positions.add(s)

    # 3. Dispara split nos segmentos que contêm split_positions.
    if split_positions:
        new_segments: list[LineSegment] = []
        for i, seg in enumerate(segments):
            seg_start = cum[i]
            seg_end = cum[i + 1]
            internal = sorted(
                s for s in split_positions
                if seg_start + _TOL_S < s < seg_end - _TOL_S
            )
            if not internal:
                new_segments.append(seg)
                continue
            # Cria sub-segmentos preservando todos os atributos do segmento
            # original — mesma material, EA, MBL, etc; só `length` muda.
            boundaries = [seg_start, *internal, seg_end]
            for k in range(len(boundaries) - 1):
                sub_len = boundaries[k + 1] - boundaries[k]
                new_segments.append(seg.model_copy(update={"length": sub_len}))
    else:
        new_segments = list(segments)

    # 4. Recalcula cumulative lengths sobre a nova lista.
    new_cum = _cumulative_lengths(new_segments)

    # 5. Mapeia cada attachment para sua nova `position_index`.
    new_attachments: list[LineAttachment] = []
    for s, att in canonical:
        # Junção `j` está em new_cum[j+1]. Procura match com tolerância.
        target_idx: int | None = None
        for j in range(len(new_segments) - 1):
            if math.isclose(new_cum[j + 1], s, abs_tol=_TOL_S):
                target_idx = j
                break
        if target_idx is None:
            # Não deveria acontecer — passamos por todos os splits acima.
            raise RuntimeError(
                f"Falha interna: não encontrou junção para s={s:.6f} m "
                f"(possíveis junções: {new_cum[1:-1]})"
            )
        new_attachments.append(
            att.model_copy(
                update={
                    "position_index": target_idx,
                    "position_s_from_anchor": None,
                }
            )
        )

    return new_segments, new_attachments


__all__ = ["resolve_attachments"]
