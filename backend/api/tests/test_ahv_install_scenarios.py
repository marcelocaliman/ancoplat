"""
BC-AHV-INSTALL-01..05 — Regressão para cenários AHV de instalação
(Sprint 2 / Commit 25). Reproduz os 5 casos do KAR006 que motivaram
o fix Sprint 2 / Commit 24+24.1: parser detecta cenário AHV e força
mode=Tension automaticamente.

Cobre 3 caminhos de detecção:
  • startpointType="AHV" no JSON QMoor (BC-AHV-INSTALL-01).
  • Nome do mooringLine contendo "Hookup" (BC-AHV-INSTALL-02).
  • Nome do mooringLine contendo "Load Transfer" (BC-AHV-INSTALL-03..04).
  • Nome do mooringLine contendo "Backing Down" (BC-AHV-INSTALL-05).

Verifica para cada:
  1. Parser converte mode Range → Tension.
  2. boundary.ahv_install populado com bollard_pull + target_horz_distance.
  3. startpoint_type mapeado corretamente (ahv/semisub).
  4. Diagnostic D021 emitido no migration log.
  5. Solver converge com status=converged.
"""
from __future__ import annotations

import pytest

from backend.api.services.moor_qmoor_v0_8 import parse_qmoor_v0_8
from backend.solver.solver import solve


# ──────────────────────────────────────────────────────────────────
# Helpers — constrói payloads minimais espelhando KAR006
# ──────────────────────────────────────────────────────────────────


def _segs_5() -> list[dict]:
    """5 segments KAR006 ML3: chain + wire + chain + wire + chain."""
    return [
        {"category": "StuddedChain", "length": "475.0 m",
         "lineProps": {"wetWeight": "150.66 kgf / m", "qmoorEA": "81018.96 te",
                       "category": "StuddedChain", "breakStrength": "815.16 te",
                       "lineType": "R4Chain", "diameter": "88.9 mm"}},
        {"category": "Wire", "length": "609.0 m",
         "lineProps": {"wetWeight": "33.97 kgf / m", "qmoorEA": "51992.85 te",
                       "category": "Wire", "breakStrength": "732.58 te",
                       "lineType": "EIPS20", "diameter": "98 mm"}},
        {"category": "StuddedChain", "length": "6.0 m",
         "lineProps": {"wetWeight": "134.51 kgf / m", "qmoorEA": "72333.87 te",
                       "category": "StuddedChain", "breakStrength": "735.56 te",
                       "lineType": "R4Chain", "diameter": "84 mm"}},
        {"category": "Wire", "length": "305.0 m",
         "lineProps": {"wetWeight": "28.04 kgf / m", "qmoorEA": "42785.34 te",
                       "category": "Wire", "breakStrength": "660 te",
                       "lineType": "EIPS20", "diameter": "88.9 mm"}},
        {"category": "StuddedChain", "length": "488.0 m",
         "lineProps": {"wetWeight": "134.51 kgf / m", "qmoorEA": "72333.87 te",
                       "category": "StuddedChain", "breakStrength": "735.56 te",
                       "lineType": "R4Chain", "diameter": "84 mm"}},
    ]


def _payload(line_name: str, profile_name: str, *,
             startpoint_type: str = "Semi-Sub Fairlead",
             input_param: str = "Range",
             horz_distance: str = "1828.8 m",
             fairlead_tension: str | None = None) -> dict:
    sol = {"inputParam": input_param}
    if fairlead_tension:
        sol["fairleadTension"] = fairlead_tension
    return {
        "QMoorVersion": "0.8.0", "unitSystem": "metric", "name": "test",
        "mooringLines": [{
            "name": line_name, "segments": [],
            "profiles": [{
                "name": profile_name,
                "segments": _segs_5(),
                "boundary": {
                    "startpointDepth": "284.0 m", "horzDistance": horz_distance,
                    "endpointGrounded": True, "endpointDepth": "311.0 m",
                    "startpointType": startpoint_type,
                },
                "solution": sol, "buoys": [], "clumps": [],
            }],
        }],
    }


# ──────────────────────────────────────────────────────────────────
# BC-AHV-INSTALL — gate canônico
# ──────────────────────────────────────────────────────────────────


def test_BC_AHV_INSTALL_01_explicit_startpointType_AHV() -> None:
    """startpointType='AHV' explícito → ahv_install populado, mode Tension."""
    payload = _payload("Preset Profiles", "ML3/4",
                       startpoint_type="AHV",
                       fairlead_tension="173.0 te")
    cases, log = parse_qmoor_v0_8(payload)
    case = cases[0]
    assert case.boundary.mode == "Tension"
    assert case.boundary.ahv_install is not None
    assert case.boundary.ahv_install.bollard_pull == pytest.approx(
        173.0 * 9806.65, rel=1e-3,
    )
    assert case.boundary.ahv_install.target_horz_distance == pytest.approx(
        1828.8, rel=1e-9,
    )
    assert case.boundary.startpoint_type == "ahv"
    assert any("D021" in e.get("reason", "") for e in log)
    res = solve(line_segments=case.segments, boundary=case.boundary,
                seabed=case.seabed, criteria_profile=case.criteria_profile)
    assert res.status.value == "converged"


def test_BC_AHV_INSTALL_02_inferred_by_name_hookup() -> None:
    """Nome 'Hookup Profiles' infere AHV mesmo com startpointType='Semi-Sub'."""
    payload = _payload("Hookup Profiles", "ML3",
                       startpoint_type="Semi-Sub Fairlead",
                       input_param="Range")  # sem fairleadTension → heurística
    cases, log = parse_qmoor_v0_8(payload)
    case = cases[0]
    assert case.boundary.mode == "Tension"
    assert case.boundary.ahv_install is not None
    # Heurística: max(50 te, 1.5·w_max·h). w_max = 1477 N/m (Rig Chain), h=311m
    # → 1.5·1477·311 ≈ 689 kN ≈ 70 te
    assert case.boundary.ahv_install.bollard_pull > 50 * 9806.65
    res = solve(line_segments=case.segments, boundary=case.boundary,
                seabed=case.seabed, criteria_profile=case.criteria_profile)
    assert res.status.value == "converged"


def test_BC_AHV_INSTALL_03_inferred_by_name_load_transfer() -> None:
    """Nome 'Load Transfer Profiles' → AHV inferido."""
    payload = _payload("Load Transfer Profiles", "ML3",
                       startpoint_type="Semi-Sub Fairlead",
                       input_param="Range")
    cases, log = parse_qmoor_v0_8(payload)
    case = cases[0]
    assert case.boundary.mode == "Tension"
    assert case.boundary.ahv_install is not None
    res = solve(line_segments=case.segments, boundary=case.boundary,
                seabed=case.seabed, criteria_profile=case.criteria_profile)
    assert res.status.value == "converged"


def test_BC_AHV_INSTALL_04_load_transfer_with_ml4_variant() -> None:
    """Variante ML4 do Load Transfer com horzDistance diferente."""
    payload = _payload("Load Transfer Profiles", "ML4",
                       startpoint_type="Semi-Sub Fairlead",
                       horz_distance="1372.0 m",
                       input_param="Range")
    cases, _ = parse_qmoor_v0_8(payload)
    case = cases[0]
    assert case.boundary.ahv_install is not None
    assert case.boundary.ahv_install.target_horz_distance == pytest.approx(
        1372.0, rel=1e-9,
    )
    res = solve(line_segments=case.segments, boundary=case.boundary,
                seabed=case.seabed, criteria_profile=case.criteria_profile)
    assert res.status.value == "converged"


def test_BC_AHV_INSTALL_05_inferred_by_name_backing_down() -> None:
    """Nome 'Backing Down Profiles' → AHV inferido."""
    payload = _payload("Backing Down Profiles", "ML1/2/5/6/7/8",
                       startpoint_type="Semi-Sub Fairlead",
                       horz_distance="1372.0 m",
                       input_param="Range")
    cases, _ = parse_qmoor_v0_8(payload)
    case = cases[0]
    assert case.boundary.mode == "Tension"
    assert case.boundary.ahv_install is not None
    res = solve(line_segments=case.segments, boundary=case.boundary,
                seabed=case.seabed, criteria_profile=case.criteria_profile)
    assert res.status.value == "converged"


# ──────────────────────────────────────────────────────────────────
# Negativo: cases NÃO-AHV não devem ser convertidos
# ──────────────────────────────────────────────────────────────────


def test_operational_profiles_NAO_e_convertido_AHV() -> None:
    """Operational Profiles é cenário rotineiro — não AHV install."""
    payload = _payload("Operational Profiles", "ML3",
                       startpoint_type="Semi-Sub Fairlead",
                       input_param="Tension",
                       fairlead_tension="150.0 te")
    cases, _ = parse_qmoor_v0_8(payload)
    case = cases[0]
    # Mode Tension preservado por inputParam, mas SEM ahv_install.
    assert case.boundary.mode == "Tension"
    assert case.boundary.ahv_install is None
    assert case.boundary.startpoint_type == "semisub"


def test_operational_em_range_preserva_range() -> None:
    """Operational + Range + L > L_min: NÃO é AHV install."""
    payload = _payload("Operational Profiles", "ML4",
                       startpoint_type="Semi-Sub Fairlead",
                       horz_distance="1500.0 m",  # < L_total=1883m
                       input_param="Range")
    cases, _ = parse_qmoor_v0_8(payload)
    case = cases[0]
    assert case.boundary.mode == "Range"
    assert case.boundary.ahv_install is None


# ──────────────────────────────────────────────────────────────────
# Heurística adaptativa de bollard_pull
# ──────────────────────────────────────────────────────────────────


def test_heuristica_bollard_pull_quando_fairleadTension_ausente() -> None:
    """Sem fairleadTension: heurística max(50 te, 1.5·w_max·h)."""
    payload = _payload("Hookup Profiles", "ML3",
                       startpoint_type="AHV",
                       horz_distance="1828.8 m",
                       input_param="Range")  # sem fairleadTension
    cases, log = parse_qmoor_v0_8(payload)
    case = cases[0]
    # w_max = 1477 N/m (Rig Chain), h = 311 m
    expected_min = 1.5 * 1477 * 311  # ~689 kN
    assert case.boundary.ahv_install.bollard_pull >= expected_min * 0.95
    # Log explícito sobre heurística aplicada
    heur_logs = [e for e in log if "heurística" in e.get("reason", "").lower()]
    assert len(heur_logs) >= 1


def test_fairleadTension_explicito_tem_precedencia() -> None:
    """Quando fairleadTension presente, usa-o (não heurística)."""
    payload = _payload("Hookup Profiles", "ML3",
                       startpoint_type="AHV",
                       fairlead_tension="100.0 te",
                       input_param="Tension")
    cases, _ = parse_qmoor_v0_8(payload)
    case = cases[0]
    assert case.boundary.ahv_install.bollard_pull == pytest.approx(
        100.0 * 9806.65, rel=1e-3,
    )


# ──────────────────────────────────────────────────────────────────
# Sprint 4 / Commit 38 — parser detecta Work Wire (Tier C)
# ──────────────────────────────────────────────────────────────────


def _payload_with_work_wire(
    *,
    ww_length: str | None = "200.0 m",
    ww_ea: str | None = "55000.0 te",
    ww_w: str | None = "17.34 kgf / m",
    ww_mbl: str | None = "660 te",
    horz_distance: str | None = "1828.8 m",
) -> dict:
    """Constrói payload AHV com work_wire opcional no boundary."""
    payload = _payload(
        "Hookup Profiles", "ML3", startpoint_type="AHV",
        fairlead_tension="100.0 te",
        horz_distance=horz_distance or "1828.8 m",
        input_param="Tension",
    )
    if any([ww_length, ww_ea, ww_w, ww_mbl]):
        ww = {}
        if ww_length:
            ww["length"] = ww_length
        if ww_ea:
            ww["EA"] = ww_ea
        if ww_w:
            ww["wetWeight"] = ww_w
        if ww_mbl:
            ww["MBL"] = ww_mbl
        ww["lineType"] = "IWRCEIPS_76mm"
        ww["diameter"] = "76 mm"
        payload["mooringLines"][0]["profiles"][0]["boundary"]["workWire"] = ww
    return payload


def test_parser_popula_work_wire_quando_json_traz_workWire() -> None:
    """JSON QMoor 0.8.0 com `boundary.workWire` → WorkWireSpec popula AHVInstall.work_wire."""
    payload = _payload_with_work_wire()
    cases, log = parse_qmoor_v0_8(payload)
    case = cases[0]
    assert case.boundary.ahv_install is not None
    ww = case.boundary.ahv_install.work_wire
    assert ww is not None, "WorkWireSpec não foi populado"
    assert ww.length == pytest.approx(200.0, rel=1e-9)
    # 55000 te × 9806.65 = 5.39e8 N (próximo de 5.5e8)
    assert ww.EA > 5.0e8
    assert ww.MBL > 6.0e6
    assert ww.line_type == "IWRCEIPS_76mm"
    assert ww.diameter == pytest.approx(0.076, rel=1e-3)
    # D023 emitido
    assert any("D023" in e.get("reason", "") for e in log)


def test_parser_ignora_work_wire_invalido() -> None:
    """workWire incompleto (length ausente) → ignorado, sem D023."""
    payload = _payload_with_work_wire(ww_length=None)  # length ausente
    cases, log = parse_qmoor_v0_8(payload)
    case = cases[0]
    assert case.boundary.ahv_install is not None
    assert case.boundary.ahv_install.work_wire is None
    assert not any("D023:" in e.get("reason", "") for e in log)


def test_parser_sem_workWire_preserva_sprint2() -> None:
    """Retro-compat: sem `workWire` no JSON, ahv_install.work_wire é None."""
    payload = _payload(
        "Hookup Profiles", "ML3", startpoint_type="AHV",
        fairlead_tension="100.0 te", input_param="Tension",
    )
    cases, log = parse_qmoor_v0_8(payload)
    case = cases[0]
    assert case.boundary.ahv_install is not None
    assert case.boundary.ahv_install.work_wire is None
    # Sem D023 emitido (não há work_wire para detectar).
    assert not any("D023" in e.get("reason", "") for e in log)


def test_parser_work_wire_sem_target_horz_distance_e_ignorado() -> None:
    """work_wire requer target_horz_distance — sem horz_distance, ignora."""
    # Constrói payload sem horz_distance (forçando target_horz_distance=None).
    payload = _payload(
        "Hookup Profiles", "ML3", startpoint_type="AHV",
        fairlead_tension="100.0 te", input_param="Tension",
    )
    # Remove horzDistance e adiciona workWire
    bd = payload["mooringLines"][0]["profiles"][0]["boundary"]
    bd.pop("horzDistance", None)
    bd["workWire"] = {
        "length": "200.0 m", "EA": "55000.0 te",
        "wetWeight": "17.34 kgf / m", "MBL": "660 te",
        "lineType": "IWRCEIPS_76mm",
    }
    cases, _ = parse_qmoor_v0_8(payload)
    case = cases[0]
    assert case.boundary.ahv_install is not None
    # work_wire ignorado porque target_horz_distance é None
    assert case.boundary.ahv_install.work_wire is None
