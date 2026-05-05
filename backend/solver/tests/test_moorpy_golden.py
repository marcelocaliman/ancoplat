"""
Gate BC-MOORPY-01..10 — V&V contra MoorPy (Fase 1 do plano de profissionalização).

Lê os 10 catenary cases capturados em
``docs/audit/moorpy_baseline_2026-05-04.json`` (gerados na Fase 0 a partir
de ``MoorPy/tests/test_catenary.py`` commit ``1fb29f8e``) e roda cada um
através do pipeline ``solve()`` do AncoPlat em modo Tension.

Razão de usar Tension (T_fl input) em vez de Range (X input):
  Modo Range converge para tensão estruturalmente errada em near-taut
  (BC-MOORPY-07..10) — diferença de ~7×. Modo Tension reproduz MoorPy
  em rtol=1e-4 para 6/7 cases ativos. Pendência da limitação do Range
  registrada na Fase 1 para investigação futura.

Ver ``backend/solver/tests/golden/moorpy/README.md`` para a tabela
completa de cobertura, mapeamento MoorPy→AncoPlat e justificativas
das tolerâncias.
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
    SeabedConfig,
    SolutionMode,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
BASELINE_PATH = REPO_ROOT / "docs/audit/moorpy_baseline_2026-05-04.json"


# Configuração por case_id: tolerância e status de skip.
# Tolerância default rtol=1e-4. Cases especiais documentados aqui.
CASE_CONFIG: dict[str, dict] = {
    "BC-MOORPY-01": {"rtol": 1e-4},
    "BC-MOORPY-02": {"rtol": 1e-4},
    "BC-MOORPY-03": {"rtol": 1e-4},
    "BC-MOORPY-04": {
        "skip": (
            "Anchor uplift (CB<0 no MoorPy = âncora elevada do seabed). "
            "Reativar em Fase 7 quando endpoint_grounded=False for "
            "implementado no solver AncoPlat."
        ),
    },
    "BC-MOORPY-05": {
        "skip": (
            "Anchor uplift (CB<0). Reativar em Fase 7 com endpoint_grounded=False."
        ),
    },
    "BC-MOORPY-06": {
        "skip": (
            "Linha boiante (w<0) + anchor uplift (CB<0). Modelo de peso "
            "distribuído negativo (riser-like) é Fase 12 futura pós-1.0; "
            "uplift é Fase 7."
        ),
    },
    "BC-MOORPY-07": {"rtol": 1e-4},
    "BC-MOORPY-08": {
        "rtol": 2e-2,
        "note": (
            "Hardest case do MoorPy: L exatamente igual à corda chord = "
            "sqrt(x²+z²). Catenária degenera para reta — ambos solvers "
            "ill-conditioned. AncoPlat retorna status=ill_conditioned com "
            "erro relativo ~1.4% no V_anchor. Tolerância relaxada conforme "
            "Ajuste 2 do mini-plano da Fase 1; pendência para Fase 4/10."
        ),
    },
    "BC-MOORPY-09": {"rtol": 1e-4},
    "BC-MOORPY-10": {"rtol": 1e-4},
}


def _load_baseline() -> dict:
    if not BASELINE_PATH.exists():
        pytest.skip(
            f"Baseline MoorPy não encontrado em {BASELINE_PATH}. "
            "Rode `bash tools/moorpy_env/regenerate_baseline.sh` para gerar."
        )
    return json.loads(BASELINE_PATH.read_text(encoding="utf-8"))


def _case_ids() -> list[str]:
    payload = _load_baseline()
    return [c["case_id"] for c in payload["cases"]]


@pytest.mark.parametrize("case_id", _case_ids())
def test_BC_MOORPY_against_baseline(case_id: str):
    """
    Para cada case do baseline MoorPy:
      - Mapeia inputs MoorPy → domínio AncoPlat (modo Tension).
      - Roda AncoPlat solve().
      - Compara componentes de força (fAH, fAV, fBH, fBV) e LBot dentro
        da tolerância configurada.

    Cases marcados com `skip` em CASE_CONFIG são pulados com motivo
    explícito (Q5 da Fase 1: cada skip cita o caso e a fase de
    reativação prevista).
    """
    payload = _load_baseline()
    case = next(c for c in payload["cases"] if c["case_id"] == case_id)
    config = CASE_CONFIG.get(case_id, {})

    if "skip" in config:
        pytest.skip(config["skip"])

    inp = case["inputs"]
    out = case["outputs"]
    rtol = config.get("rtol", 1e-4)

    # Mapping MoorPy → AncoPlat (modo Tension).
    # T_fl_target extraído da magnitude da força total no fairlead reportada
    # pelo MoorPy: sqrt(fBH² + fBV²).
    T_fl_target = math.sqrt(out["fBH"] ** 2 + out["fBV"] ** 2)

    seg = LineSegment(
        length=inp["L"],
        w=inp["w"],
        EA=inp["EA"],
        MBL=1e9,  # MBL não afeta catenária; valor alto para evitar broken
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

    # Status: aceitamos CONVERGED ou ILL_CONDITIONED. ILL_CONDITIONED
    # ocorre em near-taut onde a catenária é numericamente delicada;
    # AncoPlat ainda devolve resposta utilizável mesmo nesse caso.
    assert result.status in (
        ConvergenceStatus.CONVERGED,
        ConvergenceStatus.ILL_CONDITIONED,
    ), f"{case_id}: status={result.status.value}, msg={result.message}"

    # Comparação component-by-component. MoorPy retorna fAH/fAV positivos
    # e fBH/fBV negativos por convenção de sinal (forces ON cable AT each
    # end). AncoPlat reporta tensões em magnitude positiva. Comparação
    # absoluta resolve o atrito de convenção.
    expected = {
        "X":    inp["x"],
        "fAH":  abs(out["fAH"]),
        "fAV":  abs(out["fAV"]),
        "fBH":  abs(out["fBH"]),
        "fBV":  abs(out["fBV"]),
        "LBot": out["LBot"],
    }
    actual = {
        "X":    result.total_horz_distance,
        "fAH":  result.tension_x[0],
        "fAV":  result.tension_y[0],
        "fBH":  result.tension_x[-1],
        "fBV":  result.tension_y[-1],
        "LBot": result.total_grounded_length,
    }

    failures: list[str] = []
    for key, exp in expected.items():
        act = actual[key]
        # Para valores próximos de zero, usa tolerância absoluta de 1e-3
        # (LBot=0 e fA*=0 em casos fully-suspended caem aqui).
        if abs(exp) < 1.0:
            err = abs(act - exp)
            ok = err < 1e-3
            err_kind = "abs"
        else:
            err = abs(act - exp) / abs(exp)
            ok = err < rtol
            err_kind = "rel"
        if not ok:
            failures.append(
                f"{key}: ancoplat={act:.6g} moorpy={exp:.6g} "
                f"err({err_kind})={err:.4e} (tol={rtol if err_kind=='rel' else 1e-3:.0e})"
            )

    if failures:
        msg = (
            f"{case_id} (PT={out['ProfileType']}, status={result.status.value}) "
            f"falhou em {len(failures)} comparações:\n  "
            + "\n  ".join(failures)
        )
        if "note" in config:
            msg += f"\n  NOTA: {config['note']}"
        raise AssertionError(msg)


def test_baseline_tem_10_cases():
    """Sanidade: o JSON da Fase 0 contém exatamente 10 cases."""
    payload = _load_baseline()
    assert len(payload["cases"]) == 10
    assert payload["n_cases"] == 10


def test_3_cases_skipados_documentam_fase_de_reativacao():
    """Cada skip precisa citar a fase específica que reativará o teste
    (Q5 da Fase 1)."""
    skipped = [
        (cid, cfg["skip"])
        for cid, cfg in CASE_CONFIG.items()
        if "skip" in cfg
    ]
    assert len(skipped) == 3
    for cid, reason in skipped:
        # Cada motivo precisa nomear a fase de reativação
        assert (
            "Fase 7" in reason or "Fase 12" in reason
        ), f"{cid}: skip reason não cita fase de reativação: {reason!r}"
