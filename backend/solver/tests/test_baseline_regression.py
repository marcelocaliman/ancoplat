"""
Regressão sobre cases_baseline_2026-05-04.json (Fase 1).

Cada case salvo em produção (snapshotado durante a Fase 0) deve, quando
re-resolvido com o solver atual, produzir SolverResult equivalente ao
gravado naquele momento — dentro de tolerância de ponto flutuante.

Esta é a rede de segurança que substitui a feature-flag
``use_per_segment_friction`` originalmente prevista no plano (R1.1).
Defaults idempotentes (`mu_override=None`, `seabed_friction_cf=None`,
`ea_source="qmoor"`, `ea_dynamic_beta=None`) preservam comportamento
legado naturalmente — confirmamos isso aqui.

Toda PR que toca ``backend/solver/`` precisa passar este gate.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from backend.api.schemas.cases import CaseInput
from backend.solver.solver import solve
from backend.solver.types import (
    PROFILE_LIMITS,
    CriteriaProfile,
    SolverResult,
    UtilizationLimits,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
BASELINE_PATH = REPO_ROOT / "docs/audit/cases_baseline_2026-05-04.json"


def _load_baseline() -> dict:
    if not BASELINE_PATH.exists():
        pytest.skip(f"Baseline não encontrado em {BASELINE_PATH}")
    return json.loads(BASELINE_PATH.read_text(encoding="utf-8"))


def _case_ids() -> list[int]:
    payload = _load_baseline()
    return [c["id"] for c in payload["cases"]]


@pytest.mark.parametrize("case_id", _case_ids())
def test_caso_baseline_reroda_com_resultado_equivalente(case_id: int):
    """
    Para cada case salvo em produção (Fase 0 snapshot):
      - Lê input_json e resolve com defaults Fase 1.
      - Compara SolverResult reproduzido com o salvo.
      - Tolerância: rtol=1e-9 em escalares, rtol=1e-7 em arrays grandes
        (geometria discretizada — pequenas diferenças de ponto flutuante
        em iterações elásticas são esperadas).
    """
    payload = _load_baseline()
    case = next(c for c in payload["cases"] if c["id"] == case_id)

    if case["latest_execution"] is None:
        pytest.skip(f"case {case_id} sem execução salva — sem baseline")

    input_data = case["input_json"]
    saved_result = case["latest_execution"]["result_json"]

    # Deserializa com defaults Fase 1 aplicados (campos None dos novos
    # adicionados em LineSegment garantem retro-compat).
    case_input = CaseInput.model_validate(input_data)

    # Resolve user_limits para criteria_profile.USER_DEFINED conforme
    # padrão do projeto.
    profile = case_input.criteria_profile
    user_limits = case_input.user_defined_limits

    result = solve(
        case_input.segments,
        case_input.boundary,
        case_input.seabed,
        criteria_profile=profile,
        user_limits=user_limits,
        attachments=case_input.attachments,
    )

    # Compara escalares principais
    failures: list[str] = []
    scalar_keys = [
        "fairlead_tension",
        "anchor_tension",
        "total_horz_distance",
        "endpoint_depth",
        "unstretched_length",
        "stretched_length",
        "elongation",
        "total_suspended_length",
        "total_grounded_length",
        "H",
        "utilization",
    ]
    for k in scalar_keys:
        actual = getattr(result, k)
        expected = saved_result.get(k)
        if expected is None:
            continue
        if math.isfinite(actual) and math.isfinite(expected):
            if abs(expected) < 1e-9:
                err = abs(actual - expected)
                ok = err < 1e-6
            else:
                err = abs(actual - expected) / abs(expected)
                ok = err < 1e-9
            if not ok:
                failures.append(
                    f"{k}: actual={actual:.6g}, saved={expected:.6g}, err={err:.4e}"
                )

    # Status não pode regredir (se era CONVERGED, continua sendo)
    if saved_result.get("status") == "converged":
        assert result.status.value == "converged", (
            f"case {case_id}: status saved=converged, atual={result.status.value} "
            f"({result.message})"
        )

    if failures:
        raise AssertionError(
            f"case {case_id} ({case['name']!r}) divergiu da baseline:\n  "
            + "\n  ".join(failures)
            + "\n\nSe a divergência for INTENCIONAL (mudança de modelo físico), "
              "regenere o baseline via `python tools/dump_cases_baseline.py` e "
              "documente em docs/relatorio_F1_correcoes_fisicas.md."
        )


def test_baseline_tem_pelo_menos_um_case_com_execucao():
    """Sanidade: o baseline precisa ter ≥ 1 case com execução salva
    para o teste de regressão fazer sentido."""
    payload = _load_baseline()
    n_with_exec = sum(
        1 for c in payload["cases"] if c["latest_execution"] is not None
    )
    assert n_with_exec >= 1, (
        "baseline sem nenhum case com execução salva — gate de "
        "regressão não pode validar nada"
    )
