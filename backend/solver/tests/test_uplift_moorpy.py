"""
Gate BC-UP-01..05 — V&V de anchor uplift contra MoorPy (Fase 7 / Q5).

Lê os 5 cases capturados em
``docs/audit/moorpy_uplift_baseline_2026-05-05.json`` (gerados por
``tools/moorpy_env/regenerate_uplift_baseline.py``) e roda cada um
através do dispatcher ``solve()`` do AncoPlat.

Para cada caso:
  1. AncoPlat (modo TENSION): input T_fl → output X.
  2. MoorPy (Catenary.catenary): input XF=X_anchoplat, ZF=endpoint_depth,
     CB=-uplift → output T_fl_moorpy, T_anchor_moorpy.
  3. Compara magnitudes T_fl e T_anchor entre os dois solvers.

Tolerância: rtol=1e-2 (Q5 do mini-plano F7). Em prática os 5 BCs
medidos ficam ≤ 0.25% (bem abaixo do gate). Tabela de erro relativo
por componente registrada no relatório F7 (Q9 reforço).

Nota: o módulo `regenerate_uplift_baseline.py` já roda AncoPlat e
MoorPy em conjunto e calcula os erros relativos. Este teste é uma
sanidade ADICIONAL que confirma:
  (a) o solver AncoPlat reproduz o output que estava em moorpy_uplift_
      baseline.json (regression contra mudanças no solver).
  (b) o erro relativo armazenado no baseline está dentro do gate.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from backend.solver.solver import solve
from backend.solver.types import (
    BoundaryConditions,
    ConvergenceStatus,
    LineSegment,
    SolutionMode,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
BASELINE_PATH = REPO_ROOT / "docs/audit/moorpy_uplift_baseline_2026-05-05.json"


# Tolerância padrão Fase 7 / Q5.
DEFAULT_RTOL = 1e-2

# Configuração por caso. Override em casos específicos se necessário.
CASE_CONFIG: dict[str, dict] = {
    "BC-UP-01": {"rtol": DEFAULT_RTOL},
    "BC-UP-02": {"rtol": DEFAULT_RTOL},
    "BC-UP-03": {"rtol": DEFAULT_RTOL},
    "BC-UP-04": {"rtol": DEFAULT_RTOL},
    "BC-UP-05": {"rtol": DEFAULT_RTOL},
}


def _load_baseline() -> dict:
    if not BASELINE_PATH.exists():
        pytest.skip(
            f"Baseline uplift não encontrado em {BASELINE_PATH}. "
            "Rode `python tools/moorpy_env/regenerate_uplift_baseline.py`."
        )
    return json.loads(BASELINE_PATH.read_text(encoding="utf-8"))


def _case_ids() -> list[str]:
    payload = _load_baseline()
    return [c["id"] for c in payload["cases"]]


@pytest.mark.parametrize("case_id", _case_ids())
def test_BC_UP_against_baseline(case_id: str) -> None:
    """
    Cada BC-UP-NN: AncoPlat reproduz outputs registrados no baseline
    + erro relativo vs MoorPy <= rtol.
    """
    payload = _load_baseline()
    case = next(c for c in payload["cases"] if c["id"] == case_id)
    config = CASE_CONFIG.get(case_id, {})
    rtol = config.get("rtol", DEFAULT_RTOL)

    inp = case["inputs"]
    expected_anco = case["anchoplat"]
    expected_moorpy = case["moorpy"]
    expected_rel = case["relative_errors"]

    # ─── Roda AncoPlat (regression vs registro do baseline) ──────────
    seg = LineSegment(
        length=inp["L"], w=inp["w"], EA=inp["EA"], MBL=3.78e6,
    )
    bc = BoundaryConditions(
        h=inp["h"],
        mode=SolutionMode.TENSION,
        input_value=inp["T_fl"],
        endpoint_grounded=False,
        endpoint_depth=inp["endpoint_depth"],
    )
    r = solve([seg], bc)
    assert r.status == ConvergenceStatus.CONVERGED, (
        f"{case_id}: AncoPlat não convergiu — {r.message}"
    )

    # Regression vs baseline (rtol bem apertado: o solver não pode mudar
    # silenciosamente). Pequena tolerância numérica para float roundtrip.
    assert math.isclose(
        r.fairlead_tension, expected_anco["T_fl"], rel_tol=1e-9
    ), (
        f"{case_id}: AncoPlat T_fl mudou — atual {r.fairlead_tension}, "
        f"baseline {expected_anco['T_fl']}"
    )
    assert math.isclose(
        r.anchor_tension, expected_anco["T_anchor"], rel_tol=1e-9
    )
    assert math.isclose(
        r.total_horz_distance, expected_anco["X"], rel_tol=1e-9
    )

    # ─── Erro relativo vs MoorPy <= gate (Q5: rtol=1e-2) ─────────────
    actual_rel_T_fl = abs(
        r.fairlead_tension - expected_moorpy["T_fl"]
    ) / abs(expected_moorpy["T_fl"])
    actual_rel_T_anchor = abs(
        r.anchor_tension - expected_moorpy["T_anchor"]
    ) / abs(expected_moorpy["T_anchor"])

    assert actual_rel_T_fl <= rtol, (
        f"{case_id}: T_fl rel_err {actual_rel_T_fl*100:.4f}% > {rtol*100}%. "
        f"AncoPlat T_fl={r.fairlead_tension:.0f}, MoorPy T_fl={expected_moorpy['T_fl']:.0f}"
    )
    assert actual_rel_T_anchor <= rtol, (
        f"{case_id}: T_anchor rel_err {actual_rel_T_anchor*100:.4f}% > {rtol*100}%. "
        f"AncoPlat T_anchor={r.anchor_tension:.0f}, MoorPy T_anchor={expected_moorpy['T_anchor']:.0f}"
    )

    # Confirma que ambos AncoPlat e MoorPy classificam como PT_1
    # (fully suspended) — sanidade do regime físico.
    assert expected_moorpy["ProfileType"] == 1, (
        f"{case_id}: MoorPy ProfileType={expected_moorpy['ProfileType']} != 1 (PT_1)"
    )
    assert expected_moorpy["LBot"] == 0, (
        f"{case_id}: MoorPy LBot={expected_moorpy['LBot']} — uplift não pode "
        "ter linha no seabed"
    )

    # Sanidade do erro registrado no baseline (segue mesma metodologia
    # do test mas usando o MoorPy direto durante regenerate)
    assert expected_rel["T_fl"] <= rtol, (
        f"{case_id}: erro T_fl registrado no baseline ({expected_rel['T_fl']*100:.3f}%) "
        f"> rtol ({rtol*100}%)"
    )
    assert expected_rel["T_anchor"] <= rtol


def test_baseline_inclui_5_BC_UP():
    """Baseline tem exatamente os 5 BCs canônicos do mini-plano F7."""
    payload = _load_baseline()
    ids = sorted(c["id"] for c in payload["cases"])
    assert ids == ["BC-UP-01", "BC-UP-02", "BC-UP-03", "BC-UP-04", "BC-UP-05"]


def test_baseline_metadata_phase_F_prof_7():
    """Baseline citado como Fase 7 + tolerância Q5."""
    payload = _load_baseline()
    assert payload["phase"] == "F-prof.7"
    assert "1e-2" in payload["tolerance_target"]


def test_todos_5_BC_UP_passam_rtol_1e_2():
    """
    Sumário: 5/5 BCs com erro rel ≤ 1e-2 (Q5 critério de fechamento da
    Fase 7). Reforço Q9 do usuário: "Não basta dizer '5/5 passa rtol=1e-2';
    mostrar o erro real para cada um." Tabela imprimida abaixo.
    """
    payload = _load_baseline()
    rows = []
    for c in payload["cases"]:
        rel = c["relative_errors"]
        rows.append({
            "id": c["id"],
            "T_fl_rel_pct": rel["T_fl"] * 100,
            "T_anchor_rel_pct": rel["T_anchor"] * 100,
            "passes_rtol_1e_2": rel["T_fl"] <= 1e-2 and rel["T_anchor"] <= 1e-2,
        })
    # Print tabular (vai aparecer no -v output do pytest)
    print("\nBC-UP erro relativo vs MoorPy (Fase 7 / Q9):")
    print(
        f"{'ID':<10}  {'T_fl (%)':>10}  {'T_anchor (%)':>12}  {'gate 1e-2':>10}"
    )
    for r in rows:
        gate = "✓" if r["passes_rtol_1e_2"] else "✗"
        print(
            f"{r['id']:<10}  {r['T_fl_rel_pct']:>10.4f}  "
            f"{r['T_anchor_rel_pct']:>12.4f}  {gate:>10}"
        )
    failures = [r for r in rows if not r["passes_rtol_1e_2"]]
    assert not failures, f"{len(failures)} BCs violam rtol=1e-2"
