"""
Regenera o baseline numérico do MoorPy para anchor uplift (BC-UP-01..05).

Fase 7 do plano de profissionalização. Os 5 cases canônicos viram o
gate da Fase 7 (BC-UP rtol=1e-2 vs MoorPy nos componentes principais
T_fl, T_anchor, X).

Princípio (alinhado com regenerate_baseline.py da Fase 1):
  - AncoPlat resolve no modo TENSION → extrai X output.
  - MoorPy `Catenary.catenary()` recebe esse X como XF e devolve
    HF, VF, HA, VA. Comparação: T_fl_anco (input) vs T_fl_moorpy
    (sqrt(HF² + VF²)), T_anchor_anco vs T_anchor_moorpy, X.

Cases:
  | ID        | h (m) | endpoint_depth | uplift | L (m)  | T_fl (N)    | EA (N)    | w (N/m) |
  |-----------|------:|---------------:|-------:|-------:|------------:|----------:|--------:|
  | BC-UP-01  | 300   | 250            | 50     | 500    | 850_000     | 3.4e7     | 200     |
  | BC-UP-02  | 300   | 200            | 100    | 500    | 850_000     | 3.4e7     | 200     |
  | BC-UP-03  | 300   | 295            | 5      | 500    | 850_000     | 3.4e7     | 200     |
  | BC-UP-04  | 250   | 50             | 200    | 200    | 200_000     | 3.4e7     | 200     |
  | BC-UP-05  | 300   | 200            | 100    | 500    | 950_000     | 1.0e9     | 200     |

Saída:
    docs/audit/moorpy_uplift_baseline_<DATE>.json — array de 5 entradas
    com inputs (h, endpoint_depth, L, EA, w, T_fl), outputs AncoPlat,
    outputs MoorPy, erro relativo por componente.

Uso:
    venv/bin/python tools/moorpy_env/regenerate_uplift_baseline.py
"""
from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
MOORPY_DIR = HERE / "MoorPy"
COMMIT_FILE = HERE / "moorpy_commit.txt"
REPO_ROOT = HERE.parent.parent

# Adiciona MoorPy ao path
if str(MOORPY_DIR) not in sys.path:
    sys.path.insert(0, str(MOORPY_DIR))

# Adiciona repo root
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


# ─────────────────────────────────────────────────────────────────
# 5 casos canônicos BC-UP-01..05.
#
# AncoPlat usa endpoint_depth (profundidade do anchor abaixo da
# superfície). MoorPy usa CB negativo = "distance down from end A
# to seabed" = h - endpoint_depth (uplift). Mesma física.
# ─────────────────────────────────────────────────────────────────
CASES = [
    {
        "id": "BC-UP-01",
        "description": "Moderado — uplift 50m em h=300m, T_fl 850 kN.",
        "h": 300.0,
        "endpoint_depth": 250.0,
        "L": 500.0,
        "EA": 3.4e7,
        "w": 200.0,
        "T_fl": 850_000.0,
    },
    {
        "id": "BC-UP-02",
        "description": "Severo — uplift 100m, anchor longe do seabed.",
        "h": 300.0,
        "endpoint_depth": 200.0,
        "L": 500.0,
        "EA": 3.4e7,
        "w": 200.0,
        "T_fl": 850_000.0,
    },
    {
        "id": "BC-UP-03",
        "description": "Quase-grounded — uplift 5m. Continuidade vs grounded.",
        "h": 300.0,
        "endpoint_depth": 295.0,
        "L": 500.0,
        "EA": 3.4e7,
        "w": 200.0,
        "T_fl": 850_000.0,
    },
    {
        "id": "BC-UP-04",
        "description": "Próximo surface — anchor a 50m da superfície (h=250m).",
        "h": 250.0,
        "endpoint_depth": 50.0,
        "L": 200.0,
        "EA": 3.4e7,
        "w": 200.0,
        "T_fl": 200_000.0,
    },
    {
        "id": "BC-UP-05",
        "description": "Taut + uplift — EA grande, T_fl alto.",
        "h": 300.0,
        "endpoint_depth": 200.0,
        "L": 500.0,
        "EA": 1.0e9,  # 30× o EA padrão
        "w": 200.0,
        "T_fl": 950_000.0,
    },
]


def _solve_ancoplat(case: dict) -> dict:
    """AncoPlat: input T_fl, output X."""
    from backend.solver.suspended_endpoint import solve_suspended_endpoint
    from backend.solver.types import (
        BoundaryConditions, LineSegment, SolutionMode,
    )
    seg = LineSegment(
        length=case["L"], w=case["w"], EA=case["EA"], MBL=3.78e6,
    )
    bc = BoundaryConditions(
        h=case["h"],
        mode=SolutionMode.TENSION,
        input_value=case["T_fl"],
        endpoint_grounded=False,
        endpoint_depth=case["endpoint_depth"],
    )
    r = solve_suspended_endpoint(seg, bc)
    if r.status.value != "converged":
        return {"status": r.status.value, "message": r.message}
    return {
        "status": "converged",
        "T_fl": r.fairlead_tension,
        "T_anchor": r.anchor_tension,
        "X": r.total_horz_distance,
        "L_stretched": r.stretched_length,
        "elongation": r.elongation,
        "H": r.H,
        "iterations": r.iterations_used,
    }


def _solve_moorpy(case: dict, X_anchoplat: float) -> dict:
    """
    MoorPy: input XF (do AncoPlat), output via catenary().

    IMPORTANTE — convenção de retorno do MoorPy `Catenary.catenary()`:
        return (FxA, FzA, FxB, FzB, info)

    Onde end A = anchor, end B = fairlead. Isso é OPOSTO da nomenclatura
    aparente do tuple (não é H_fairlead/V_fairlead/H_anchor/V_anchor).

    T_anchor magnitude = sqrt(FxA² + FzA²)
    T_fairlead magnitude = sqrt(FxB² + FzB²)
    """
    from moorpy.Catenary import catenary  # type: ignore

    uplift = case["h"] - case["endpoint_depth"]
    # MoorPy: CB negativo = distância do anchor até o seabed (uplift).
    out = catenary(
        XF=X_anchoplat,
        ZF=case["endpoint_depth"],  # drop fairlead → anchor
        L=case["L"],
        EA=case["EA"],
        W=case["w"],
        CB=-uplift,  # negativo = anchor uplift, sem contato seabed
    )
    FxA, FzA, FxB, FzB, info = out
    T_anchor = math.sqrt(FxA * FxA + FzA * FzA)  # end A = anchor
    T_fl = math.sqrt(FxB * FxB + FzB * FzB)      # end B = fairlead
    return {
        "T_fl": float(T_fl),
        "T_anchor": float(T_anchor),
        "FxA": float(FxA),
        "FzA": float(FzA),
        "FxB": float(FxB),
        "FzB": float(FzB),
        "ProfileType": int(info["ProfileType"]),
        "LBot": float(info["LBot"]),
    }


def _rel_error(actual: float, expected: float) -> float:
    """Erro relativo |actual - expected| / |expected|. Retorna 0 se expected=0."""
    if abs(expected) < 1e-9:
        return abs(actual)
    return abs(actual - expected) / abs(expected)


def _moorpy_commit() -> str:
    if COMMIT_FILE.exists():
        return COMMIT_FILE.read_text(encoding="utf-8").strip()
    return "unknown"


def main() -> None:
    print("Regenerando baseline MoorPy uplift (BC-UP-01..05)…\n")

    results: list[dict] = []
    for case in CASES:
        print(f"  {case['id']}: {case['description']}")
        anco = _solve_ancoplat(case)
        if anco["status"] != "converged":
            print(f"    AncoPlat: {anco['status']} — {anco.get('message', '')}")
            results.append({
                "id": case["id"],
                "inputs": {k: v for k, v in case.items() if k != "id"},
                "anchoplat": anco,
                "moorpy": None,
                "relative_errors": None,
                "status": "ancoplat_failed",
            })
            continue

        moorpy = _solve_moorpy(case, anco["X"])
        # Erro relativo: T_fl input vs T_fl_moorpy (mesmo X), T_anchor.
        rel = {
            "T_fl": _rel_error(moorpy["T_fl"], anco["T_fl"]),
            "T_anchor": _rel_error(moorpy["T_anchor"], anco["T_anchor"]),
        }
        print(
            f"    AncoPlat T_fl={anco['T_fl']:.0f} N, T_anchor={anco['T_anchor']:.0f} N, "
            f"X={anco['X']:.2f} m, elong={anco['elongation']:.2f} m"
        )
        print(
            f"    MoorPy   T_fl={moorpy['T_fl']:.0f} N, T_anchor={moorpy['T_anchor']:.0f} N "
            f"(PT={moorpy['ProfileType']}, LBot={moorpy['LBot']:.0f})"
        )
        print(
            f"    rel_err  T_fl={rel['T_fl']*100:.3f}%  "
            f"T_anchor={rel['T_anchor']*100:.3f}%"
        )
        results.append({
            "id": case["id"],
            "description": case["description"],
            "inputs": {k: v for k, v in case.items() if k not in ("id", "description")},
            "anchoplat": anco,
            "moorpy": moorpy,
            "relative_errors": rel,
            "status": "ok",
        })

    output_path = (
        REPO_ROOT
        / "docs"
        / "audit"
        / f"moorpy_uplift_baseline_{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.json"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(
            {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "moorpy_commit": _moorpy_commit(),
                "phase": "F-prof.7",
                "test_id": "BC-UP-01..05",
                "tolerance_target": "rtol=1e-2 (Fase 7 / Q5)",
                "cases": results,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nBaseline salvo em: {output_path}")


if __name__ == "__main__":
    main()
