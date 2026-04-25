"""Testes do resolver de attachments com posição contínua (F5.4.6a)."""
from __future__ import annotations

import math
import pytest
from pydantic import ValidationError

from backend.solver.attachment_resolver import resolve_attachments
from backend.solver.types import LineAttachment, LineSegment


def _seg(length: float, category: str = "Wire", line_type: str = "TEST") -> LineSegment:
    return LineSegment(
        length=length, w=200.0, EA=3e7, MBL=4e6,
        category=category, line_type=line_type,
    )


# ──────────────────────────────────────────────────────────────────────
# Pydantic validator
# ──────────────────────────────────────────────────────────────────────


def test_pydantic_exige_posicao_alguma() -> None:
    """LineAttachment sem nenhuma posição → ValidationError."""
    with pytest.raises(ValidationError, match="obrigatório"):
        LineAttachment(kind="buoy", submerged_force=50_000)


def test_pydantic_rejeita_dupla_posicao() -> None:
    """Não pode informar position_index E position_s_from_anchor."""
    with pytest.raises(ValidationError, match="exatamente um"):
        LineAttachment(
            kind="buoy", submerged_force=50_000,
            position_index=0, position_s_from_anchor=100.0,
        )


def test_pydantic_aceita_apenas_position_index() -> None:
    a = LineAttachment(kind="buoy", submerged_force=50_000, position_index=1)
    assert a.position_index == 1
    assert a.position_s_from_anchor is None


def test_pydantic_aceita_apenas_position_s() -> None:
    a = LineAttachment(
        kind="buoy", submerged_force=50_000, position_s_from_anchor=250.0,
    )
    assert a.position_s_from_anchor == 250.0
    assert a.position_index is None


# ──────────────────────────────────────────────────────────────────────
# Resolver — modo legacy (position_index)
# ──────────────────────────────────────────────────────────────────────


def test_resolver_legacy_position_index_passa_intacto() -> None:
    """Quando todos os attachments usam position_index, segments não
    devem mudar."""
    segs = [_seg(100), _seg(200), _seg(150)]
    atts = [LineAttachment(kind="buoy", submerged_force=10_000, position_index=0)]
    new_segs, new_atts = resolve_attachments(segs, atts)
    assert len(new_segs) == 3
    assert [s.length for s in new_segs] == [100, 200, 150]
    assert new_atts[0].position_index == 0
    assert new_atts[0].position_s_from_anchor is None


def test_resolver_lista_vazia_retorna_lista_vazia() -> None:
    segs = [_seg(100)]
    new_segs, new_atts = resolve_attachments(segs, [])
    assert new_segs == segs
    assert new_atts == []


# ──────────────────────────────────────────────────────────────────────
# Resolver — modo contínuo (position_s_from_anchor)
# ──────────────────────────────────────────────────────────────────────


def test_resolver_position_s_em_meio_de_segmento_divide() -> None:
    """s=150 em linha homogênea de 400m vira 2 sub-segmentos (150/250)."""
    segs = [_seg(400)]
    atts = [
        LineAttachment(
            kind="buoy", submerged_force=20_000, position_s_from_anchor=150.0,
        )
    ]
    new_segs, new_atts = resolve_attachments(segs, atts)
    assert len(new_segs) == 2
    assert math.isclose(new_segs[0].length, 150.0)
    assert math.isclose(new_segs[1].length, 250.0)
    # Attachment vira junção 0 (entre os dois sub-segmentos)
    assert new_atts[0].position_index == 0
    assert new_atts[0].position_s_from_anchor is None
    # Material preservado em ambos os sub-segmentos
    assert new_segs[0].line_type == new_segs[1].line_type == "TEST"
    assert new_segs[0].EA == new_segs[1].EA


def test_resolver_position_s_coincidindo_com_juncao_existente_nao_divide() -> None:
    """s=300 em linha [200, 200, 200] cai exatamente na junção 0→1
    (cum=300). Não deve dividir nada."""
    segs = [_seg(200), _seg(200), _seg(200)]
    atts = [
        LineAttachment(
            kind="clump_weight", submerged_force=30_000,
            position_s_from_anchor=200.0,
        )
    ]
    new_segs, new_atts = resolve_attachments(segs, atts)
    assert len(new_segs) == 3
    assert new_atts[0].position_index == 0  # junção entre seg 0 e seg 1


def test_resolver_multiplos_attachments_no_mesmo_s() -> None:
    """2 attachments na mesma posição → mesma junção, 1 split só."""
    segs = [_seg(500)]
    atts = [
        LineAttachment(
            kind="buoy", submerged_force=10_000, position_s_from_anchor=200.0,
            name="Boia A",
        ),
        LineAttachment(
            kind="clump_weight", submerged_force=20_000,
            position_s_from_anchor=200.0, name="Clump B",
        ),
    ]
    new_segs, new_atts = resolve_attachments(segs, atts)
    assert len(new_segs) == 2
    assert math.isclose(new_segs[0].length, 200)
    assert math.isclose(new_segs[1].length, 300)
    # Ambos compartilham junção 0
    assert all(a.position_index == 0 for a in new_atts)


def test_resolver_dois_attachments_em_pontos_distintos() -> None:
    """Boia em 100 e clump em 300 numa linha de 500 → 3 sub-segmentos."""
    segs = [_seg(500)]
    atts = [
        LineAttachment(
            kind="buoy", submerged_force=10_000, position_s_from_anchor=100.0,
        ),
        LineAttachment(
            kind="clump_weight", submerged_force=20_000,
            position_s_from_anchor=300.0,
        ),
    ]
    new_segs, new_atts = resolve_attachments(segs, atts)
    assert len(new_segs) == 3
    assert math.isclose(new_segs[0].length, 100)
    assert math.isclose(new_segs[1].length, 200)
    assert math.isclose(new_segs[2].length, 200)
    # Boia na junção 0, clump na junção 1
    boia = next(a for a in new_atts if a.kind == "buoy")
    clump = next(a for a in new_atts if a.kind == "clump_weight")
    assert boia.position_index == 0
    assert clump.position_index == 1


def test_resolver_split_em_segmento_intermediario_preserva_outros() -> None:
    """Linha [200(Wire), 300(Chain), 200(Wire)]; boia em s=300 (meio do
    segmento Chain). Resultado: [Wire 200, Chain 100, Chain 200, Wire 200]."""
    segs = [
        _seg(200, "Wire", "W"),
        _seg(300, "StuddedChain", "C"),
        _seg(200, "Wire", "W"),
    ]
    atts = [
        LineAttachment(
            kind="buoy", submerged_force=15_000, position_s_from_anchor=300.0,
        )
    ]
    new_segs, new_atts = resolve_attachments(segs, atts)
    assert len(new_segs) == 4
    assert [s.length for s in new_segs] == [200, 100, 200, 200]
    assert [s.line_type for s in new_segs] == ["W", "C", "C", "W"]
    # Boia na junção 1 (entre Chain-100 e Chain-200)
    assert new_atts[0].position_index == 1


# ──────────────────────────────────────────────────────────────────────
# Casos de erro
# ──────────────────────────────────────────────────────────────────────


def test_resolver_rejeita_position_s_na_ancora() -> None:
    """s=0 não é permitido — colocaria sobre a âncora."""
    # s=0 é rejeitado pelo Pydantic (gt=0). Testa com s muito pequeno
    # que passa o Pydantic mas é rejeitado pelo resolver.
    segs = [_seg(100)]
    atts = [
        LineAttachment(
            kind="buoy", submerged_force=10_000,
            position_s_from_anchor=1e-9,
        )
    ]
    with pytest.raises(ValueError, match="sobre a âncora"):
        resolve_attachments(segs, atts)


def test_resolver_rejeita_position_s_no_fairlead() -> None:
    """s = total_length não é permitido — sobre o fairlead."""
    segs = [_seg(100), _seg(200)]
    atts = [
        LineAttachment(
            kind="clump_weight", submerged_force=10_000,
            position_s_from_anchor=300.0,
        )
    ]
    with pytest.raises(ValueError, match="sobre o fairlead"):
        resolve_attachments(segs, atts)


def test_resolver_rejeita_position_s_alem_da_linha() -> None:
    segs = [_seg(100)]
    atts = [
        LineAttachment(
            kind="buoy", submerged_force=10_000,
            position_s_from_anchor=500.0,
        )
    ]
    with pytest.raises(ValueError, match="sobre o fairlead"):
        resolve_attachments(segs, atts)


def test_resolver_rejeita_position_index_invalido() -> None:
    """position_index aceita pelo Pydantic mas fora do range pós-segmentos."""
    segs = [_seg(100)]  # 1 segmento, sem junções
    atts = [
        LineAttachment(
            kind="buoy", submerged_force=10_000, position_index=0,
        )
    ]
    # position_index=0 numa linha de 1 segmento aponta pra cum[1]=100 (fairlead)
    with pytest.raises(ValueError, match="sobre o fairlead"):
        resolve_attachments(segs, atts)
