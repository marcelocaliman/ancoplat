"""
Parser QMoor 0.8.0 — AHV Operacional Mid-Line (Tier D).

Sprint 5 / Commit 46. Testa que `boundary.anchorHandlerVessels[]`
do JSON QMoor 0.8.0 é convertido em LineAttachment kind='ahv' com
ahv_work_wire populado.
"""
from __future__ import annotations

import pytest

from backend.api.services.moor_qmoor_v0_8 import parse_qmoor_v0_8


def _segs_2() -> list[dict]:
    """2 segments simples para somar L_total = 1500m."""
    return [
        {"category": "Wire", "length": "750.0 m",
         "lineProps": {"wetWeight": "17.34 kgf / m", "qmoorEA": "55000 te",
                       "category": "Wire", "breakStrength": "660 te",
                       "lineType": "wire76"}},
        {"category": "Wire", "length": "750.0 m",
         "lineProps": {"wetWeight": "17.34 kgf / m", "qmoorEA": "55000 te",
                       "category": "Wire", "breakStrength": "660 te",
                       "lineType": "wire76"}},
    ]


def _payload_with_ahv_op(
    *,
    line_dist_from_fl: str = "750.0 m",
    bollard: str = "90 te",
    heading: str = "Away from Fairlead",
    ww_length: str = "300.0 m",
    ww_ea: str = "55000 te",
    ww_w: str = "17.34 kgf / m",
    ww_mbl: str = "660 te",
) -> dict:
    """Constrói payload com 1 AHV operacional em boundary."""
    bd = {
        "startpointDepth": "0.0 m",
        "horzDistance": "1300.0 m",
        "endpointGrounded": True,
        "endpointDepth": "200.0 m",
        "anchorHandlerVessels": [
            {
                "name": "AHV-1",
                "heading": heading,
                "sternAngle": 25.0,
                "deckLevelAboveSWL": "10.0 m",
                "bollardPull": {"force": bollard, "direction": heading},
                "connectionPosition": {
                    "lineDistanceFromFairlead": line_dist_from_fl,
                },
                "workLine": {
                    "lineType": "IWRCEIPS",
                    "diameter": "76.2 mm",
                    "length": ww_length,
                    "EA": ww_ea,
                    "wetWeight": ww_w,
                    "MBL": ww_mbl,
                },
            },
        ],
    }
    return {
        "QMoorVersion": "0.8.0",
        "unitSystem": "metric",
        "name": "test-ahv-op",
        "mooringLines": [{
            "name": "ML1",
            "segments": [],
            "profiles": [{
                "name": "Operational Profiles",
                "segments": _segs_2(),
                "boundary": bd,
                "solution": {"inputParam": "Range"},
                "buoys": [],
                "clumps": [],
            }],
        }],
    }


def test_parser_detecta_ahv_operational() -> None:
    """JSON com `anchorHandlerVessels[]` → LineAttachment Tier D."""
    payload = _payload_with_ahv_op()
    cases, log = parse_qmoor_v0_8(payload)
    case = cases[0]
    ahv_atts = [
        a for a in case.attachments
        if a.kind == "ahv" and a.ahv_work_wire is not None
    ]
    assert len(ahv_atts) == 1, "Deveria ter 1 AHV operacional"
    att = ahv_atts[0]
    assert att.name == "AHV-1"
    assert att.ahv_bollard_pull == pytest.approx(90.0 * 9806.65, rel=1e-3)
    assert att.position_s_from_anchor is not None
    # 1500m total - 750m from_fl = 750m from anchor
    assert att.position_s_from_anchor == pytest.approx(750.0, rel=1e-9)
    assert att.ahv_work_wire is not None
    assert att.ahv_work_wire.length == pytest.approx(300.0, rel=1e-9)
    # D026 emitido
    assert any("D026" in e.get("reason", "") for e in log)


def test_parser_heading_away_from_fairlead() -> None:
    """`Away from Fairlead` → heading=0°."""
    payload = _payload_with_ahv_op(heading="Away from Fairlead")
    cases, _ = parse_qmoor_v0_8(payload)
    att = next(
        a for a in cases[0].attachments
        if a.kind == "ahv" and a.ahv_work_wire is not None
    )
    assert att.ahv_heading_deg == 0.0


def test_parser_heading_toward_fairlead() -> None:
    """`Toward Fairlead` → heading=180°."""
    payload = _payload_with_ahv_op(heading="Toward Fairlead")
    cases, _ = parse_qmoor_v0_8(payload)
    att = next(
        a for a in cases[0].attachments
        if a.kind == "ahv" and a.ahv_work_wire is not None
    )
    assert att.ahv_heading_deg == 180.0


def test_parser_workline_incompleto_pula() -> None:
    """Work line sem MBL → AHV pulado, log estruturado."""
    payload = _payload_with_ahv_op(ww_mbl="")
    cases, log = parse_qmoor_v0_8(payload)
    ahv_atts = [
        a for a in cases[0].attachments
        if a.kind == "ahv" and a.ahv_work_wire is not None
    ]
    assert len(ahv_atts) == 0
    assert any("D026b" in e.get("reason", "") for e in log)


def test_parser_sem_anchorHandlerVessels_nao_quebra() -> None:
    """JSON sem `anchorHandlerVessels` → comportamento legacy preservado."""
    payload = _payload_with_ahv_op()
    bd = payload["mooringLines"][0]["profiles"][0]["boundary"]
    bd.pop("anchorHandlerVessels")
    cases, log = parse_qmoor_v0_8(payload)
    case = cases[0]
    ahv_atts = [
        a for a in case.attachments
        if a.kind == "ahv" and a.ahv_work_wire is not None
    ]
    assert len(ahv_atts) == 0
    # Sem D026 emitido
    assert not any("D026:" in e.get("reason", "") for e in log)
