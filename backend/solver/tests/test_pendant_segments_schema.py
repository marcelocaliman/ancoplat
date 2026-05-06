"""
Testes do schema `PendantSegment` e do campo `LineAttachment.pendant_segments`
(Sprint 1 / v1.1.0).

Pendant multi-segmento é META-DADO PURO: solver não lê esse campo. Os
testes garantem:

  - PendantSegment exige `length > 0`; demais campos opcionais.
  - Campos numéricos rejeitam ≤ 0.
  - LineAttachment aceita `pendant_segments` opcional (default=None).
  - Limite máximo de 5 trechos.
  - Round-trip preserva ordem e todos os campos.
  - Coexistência com `pendant_line_type`/`pendant_diameter` legados é
    permitida (sem conflito enforced em runtime — UI decide qual mostrar).
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.solver.types import LineAttachment, PendantSegment


# ──────────────────────────────────────────────────────────────────
# PendantSegment — campos obrigatórios e validação
# ──────────────────────────────────────────────────────────────────


def test_pendant_segment_minimo_so_length() -> None:
    seg = PendantSegment(length=12.0)
    assert seg.length == 12.0
    assert seg.line_type is None
    assert seg.diameter is None


def test_pendant_segment_completo_round_trip() -> None:
    seg = PendantSegment(
        length=15.0,
        line_type="R4Studless",
        category="StudlessChain",
        diameter=0.076,
        w=1500.0,
        dry_weight=1700.0,
        EA=5.0e8,
        MBL=6.0e6,
        material_label="R4 Studless 76 mm",
    )
    payload = seg.model_dump()
    seg2 = PendantSegment.model_validate(payload)
    assert seg2 == seg


def test_pendant_segment_sem_length_invalido() -> None:
    with pytest.raises(ValidationError):
        PendantSegment()  # type: ignore[call-arg]


@pytest.mark.parametrize("field", ["length", "diameter", "w", "dry_weight", "EA", "MBL"])
def test_pendant_segment_campos_numericos_rejeitam_zero(field: str) -> None:
    base = dict(length=10.0)
    if field != "length":
        base[field] = 0.0
    else:
        base["length"] = 0.0
    with pytest.raises(ValidationError):
        PendantSegment(**base)  # type: ignore[arg-type]


def test_pendant_segment_material_label_max_120() -> None:
    with pytest.raises(ValidationError):
        PendantSegment(length=1.0, material_label="x" * 121)


# ──────────────────────────────────────────────────────────────────
# LineAttachment.pendant_segments — coexistência com legacy
# ──────────────────────────────────────────────────────────────────


def _buoy_base(**kwargs) -> LineAttachment:
    base = dict(
        kind="buoy",
        submerged_force=50_000.0,
        position_s_from_anchor=200.0,
    )
    base.update(kwargs)
    return LineAttachment(**base)


def test_attachment_sem_pendant_segments_default_none() -> None:
    att = _buoy_base()
    assert att.pendant_segments is None


def test_attachment_com_pendant_segments_aceito() -> None:
    att = _buoy_base(
        pendant_segments=[
            PendantSegment(length=10.0, line_type="R4Studless", diameter=0.076),
            PendantSegment(length=5.0, line_type="IWRCEIPS", diameter=0.080),
        ],
    )
    assert att.pendant_segments is not None
    assert len(att.pendant_segments) == 2
    assert att.pendant_segments[0].line_type == "R4Studless"


def test_attachment_pendant_segments_limit_5() -> None:
    with pytest.raises(ValidationError):
        _buoy_base(
            pendant_segments=[PendantSegment(length=1.0) for _ in range(6)],
        )


def test_attachment_pendant_segments_round_trip() -> None:
    att = _buoy_base(
        pendant_segments=[
            PendantSegment(
                length=12.0,
                line_type="R4Studless",
                diameter=0.076,
                w=1500.0,
                MBL=6.0e6,
            ),
        ],
    )
    payload = att.model_dump()
    att2 = LineAttachment.model_validate(payload)
    assert att2 == att


def test_attachment_pendant_segments_ordem_preservada() -> None:
    """Pendant ordenado: linha principal → boia/clump."""
    s1 = PendantSegment(length=10.0, material_label="primeiro")
    s2 = PendantSegment(length=5.0, material_label="segundo")
    s3 = PendantSegment(length=3.0, material_label="terceiro")
    att = _buoy_base(pendant_segments=[s1, s2, s3])
    assert [s.material_label for s in att.pendant_segments or []] == [
        "primeiro", "segundo", "terceiro"
    ]


def test_attachment_pendant_segments_coexiste_com_legado() -> None:
    """`pendant_line_type`+`pendant_diameter` legados continuam aceitos
    junto com `pendant_segments` — UI/PDF resolvem precedência."""
    att = _buoy_base(
        pendant_line_type="IWRCEIPS",
        pendant_diameter=0.076,
        pendant_segments=[
            PendantSegment(length=10.0, line_type="R4Studless", diameter=0.076),
        ],
    )
    assert att.pendant_line_type == "IWRCEIPS"
    assert att.pendant_segments is not None
    assert att.pendant_segments[0].line_type == "R4Studless"


def test_attachment_pendant_segments_lista_vazia_aceita() -> None:
    """Lista vazia equivale a None semanticamente — não rejeita."""
    att = _buoy_base(pendant_segments=[])
    assert att.pendant_segments == []
