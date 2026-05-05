"""
Testes de integração classify_profile_type vs MoorPy (Fase 4 / Q2 +
Commit 3 da Fase 4).

Lê os 7 BC-MOORPY ativos do baseline F0 (`docs/audit/moorpy_baseline_*.json`),
roda classify_profile_type após o solve do AncoPlat e compara com o
`info.ProfileType` reportado pelo MoorPy.

Tabela de divergências aceita (Ajuste 1 do mini-plano F4):

  Categoria 1 — bug do classifier AncoPlat (corrigir).
  Categoria 2 — diferença legítima de modelo (multi-segmento vs
                MoorPy single-segment, regime que AncoPlat trata
                diferente por razão física).
  Categoria 3 — edge case de tolerância numérica.

Divergências conhecidas (ver docs/relatorio_F4_diagnostics.md §3):

  BC-MOORPY-08 (hardest taut, L = chord exato):
    AncoPlat=PT_1, MoorPy=PT_-1 (fallback aproximação)
    Categoria 3 — MoorPy ativa modo de aproximação especial quando
    o solver normal não converge cleanly. AncoPlat resolve via
    brentq+elastic (status=ill_conditioned mas com geometria
    válida) e classifica como fully suspended. Ambas as escolhas
    são defensáveis; PT_-1 do MoorPy não tem equivalente físico
    claro no vocabulário canônico.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from backend.solver.profile_type import classify_profile_type
from backend.solver.solver import solve
from backend.solver.types import (
    BoundaryConditions,
    LineSegment,
    ProfileType,
    SeabedConfig,
    SolutionMode,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
BASELINE_PATH = REPO_ROOT / "docs/audit/moorpy_baseline_2026-05-04.json"

# Divergências aceitas (Categoria 3 — edge case de tolerância).
# Cada entrada é (case_id, motivo_curto). Se um teste de match falhar
# para um case_id NÃO listado aqui, é regressão real (Categoria 1).
ACCEPTED_DIVERGENCES = {
    "BC-MOORPY-08": (
        "Hardest taut (L = chord exato); MoorPy=PT_-1 (fallback de "
        "aproximação), AncoPlat=PT_1 (fully suspended via brentq+elastic, "
        "status=ill_conditioned). Categoria 3 — edge case numérico."
    ),
}


def _load_baseline() -> dict:
    if not BASELINE_PATH.exists():
        pytest.skip(f"Baseline MoorPy não encontrado em {BASELINE_PATH}")
    return json.loads(BASELINE_PATH.read_text(encoding="utf-8"))


def _moorpy_pt_to_ancoplat(moorpy_pt_int: int) -> ProfileType | None:
    """Converte int do MoorPy (info.ProfileType) para ProfileType do AncoPlat.

    Returns None para PT_-1 (sem equivalente — fallback do MoorPy).
    """
    mapping = {
        0: ProfileType.PT_0,
        1: ProfileType.PT_1,
        2: ProfileType.PT_2,
        3: ProfileType.PT_3,
        4: ProfileType.PT_4,
        5: ProfileType.PT_5,
        6: ProfileType.PT_6,
        7: ProfileType.PT_7,
        8: ProfileType.PT_8,
    }
    return mapping.get(moorpy_pt_int)


def _moorpy_case_indices_active() -> list[int]:
    """7 cases ativos do BC-MOORPY (sem uplift, sem buoyant)."""
    # MoorPy idx 0..9; ativos = 0,1,2,6,7,8,9 (cases 3,4,5 são uplift/buoyant)
    return [0, 1, 2, 6, 7, 8, 9]


@pytest.mark.parametrize("moorpy_idx", _moorpy_case_indices_active())
def test_classifier_BC_MOORPY_match_or_documented_divergence(moorpy_idx: int):
    """
    Para cada BC-MOORPY ativo:
      1. Roda solve do AncoPlat com mesmos inputs (modo Tension —
         mesma estratégia da F1).
      2. Classifica com classify_profile_type.
      3. Compara com MoorPy info.ProfileType.

    Match esperado, exceto divergências em ACCEPTED_DIVERGENCES.
    """
    payload = _load_baseline()
    case = payload["cases"][moorpy_idx]
    case_id = case["case_id"]
    inp = case["inputs"]
    out = case["outputs"]

    if inp["w"] <= 0 or inp["CB"] < 0:
        pytest.skip(f"{case_id} é uplift/buoyant — fora de escopo MVP v1")

    T_fl_target = math.sqrt(out["fBH"] ** 2 + out["fBV"] ** 2)
    seg = LineSegment(
        length=inp["L"], w=inp["w"], EA=inp["EA"], MBL=1e9,
    )
    bc = BoundaryConditions(
        h=inp["z"],
        mode=SolutionMode.TENSION,
        input_value=T_fl_target,
        startpoint_depth=0.0,
        endpoint_grounded=True,
    )
    sb = SeabedConfig(mu=inp["CB"], slope_rad=0.0)
    result = solve([seg], bc, sb)
    classified = classify_profile_type(result, [seg], sb)
    moorpy_pt = _moorpy_pt_to_ancoplat(out["ProfileType"])

    if classified == moorpy_pt:
        return  # match perfeito

    # Divergência — deve estar em ACCEPTED_DIVERGENCES (Categoria 3).
    if case_id in ACCEPTED_DIVERGENCES:
        # OK — divergência conhecida e justificada
        return

    # Regressão real (Categoria 1) — falha o teste com mensagem clara.
    raise AssertionError(
        f"{case_id}: AncoPlat classificou como {classified}, MoorPy reporta "
        f"PT_{out['ProfileType']} ({moorpy_pt}). Divergência NÃO documentada "
        f"em ACCEPTED_DIVERGENCES — investigar como Categoria 1 (bug) ou "
        f"Categoria 2 (diferença legítima de modelo) e atualizar a tabela."
    )


def test_accepted_divergences_documentadas():
    """Sanity: cada entrada em ACCEPTED_DIVERGENCES tem motivo não-trivial."""
    for case_id, reason in ACCEPTED_DIVERGENCES.items():
        assert len(reason) > 50, (
            f"{case_id}: motivo curto demais ({len(reason)} chars). "
            "Exigido descrição da causa-raiz e categoria (1/2/3)."
        )
        # Cada motivo deve citar a categoria
        assert (
            "Categoria 1" in reason
            or "Categoria 2" in reason
            or "Categoria 3" in reason
        ), f"{case_id}: motivo deve nomear Categoria 1/2/3"


def test_active_cases_cobre_pelo_menos_3_PTs_distintos():
    """Sanity de cobertura: BC-MOORPY 7 ativos cobrem pelo menos 3 PTs
    distintos (PT_1, PT_2, PT_3 minimal). Garante que o classifier
    é exercitado em diversidade real de regimes."""
    payload = _load_baseline()
    seen_pts: set[ProfileType] = set()
    for moorpy_idx in _moorpy_case_indices_active():
        case = payload["cases"][moorpy_idx]
        inp = case["inputs"]
        out = case["outputs"]
        if inp["w"] <= 0 or inp["CB"] < 0:
            continue
        T_fl_target = math.sqrt(out["fBH"] ** 2 + out["fBV"] ** 2)
        seg = LineSegment(
            length=inp["L"], w=inp["w"], EA=inp["EA"], MBL=1e9,
        )
        bc = BoundaryConditions(
            h=inp["z"], mode=SolutionMode.TENSION,
            input_value=T_fl_target, startpoint_depth=0.0,
            endpoint_grounded=True,
        )
        sb = SeabedConfig(mu=inp["CB"], slope_rad=0.0)
        result = solve([seg], bc, sb)
        pt = classify_profile_type(result, [seg], sb)
        if pt is not None:
            seen_pts.add(pt)
    assert len(seen_pts) >= 3, (
        f"Cobertura ProfileType insuficiente: apenas {seen_pts}. "
        "BC-MOORPY-01..10 deveria exercitar diversos regimes."
    )
