"""
Regenera o baseline numérico do MoorPy para AHV Operacional Mid-Line
(BC-AHV-OP-01..06) — Sprint 5 / Commit 43.

Modela o sistema completo:

    [PLATAFORMA fairlead]                       [AHV deck]
            |                                       |
            | upper mooring                         | Work Wire
            |                                       |
        [pega] ─── (MoorPy free point) ─────────────┘
         /
        / lower mooring (com touchdown se aplicável)
       /
      v ANCHOR

Estratégia MoorPy:
  - System com 4 pontos: anchor (fixed), pega (free), AHV deck (fixed),
    fairlead (fixed).
  - 3 Lines: lower mooring (anchor→pega), upper mooring (pega→fairlead),
    work wire (pega→AHV deck).
  - solveEquilibrium() → MoorPy resolve a posição da pega que satisfaz
    equilíbrio global de forças.

Cenários canônicos (2D plano vertical — heading limitado a 0°/180°):

  | ID  | Modo                     | h | X_AHV | L_lower | L_upper | L_ww |
  |-----|--------------------------|---|-------|---------|---------|------|
  | 01  | Favorable (AHV adiante)  | 200 | 1700 | 800 | 800 | 250  |
  | 02  | Strong-pull (alto bollard) | 200 | 1700 | 800 | 800 | 250 |
  | 03  | Pega 25% fairlead        | 300 | 2000 | 600 | 1800 | 350 |
  | 04  | Pega 75% fairlead        | 300 | 2000 | 1800 | 600 | 350 |
  | 05  | Águas profundas          | 1500 | 2500 | 2200 | 2200 | 500 |
  | 06  | Águas ultra-profundas    | 2000 | 3000 | 2700 | 2700 | 600 |

Materiais (wire 76mm IWRCEIPS para mooring + ww):
  w = 170 N/m, EA = 5.5e8 N, MBL = 6.5e6 N

NOTA xfail informativa: heading=90° (lateral fora do plano vertical 2D)
não é modelável em MoorPy 2D — fica como pendência F12 (3D).

Saída:
    docs/audit/moorpy_ahv_op_baseline_<DATE>.json — array de 6 entradas.

Uso:
    venv/bin/python tools/moorpy_env/regenerate_ahv_op_baseline.py
"""
from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
MOORPY_DIR = HERE / "MoorPy"
COMMIT_FILE = HERE / "moorpy_commit.txt"
REPO_ROOT = HERE.parent.parent

if str(MOORPY_DIR) not in sys.path:
    sys.path.insert(0, str(MOORPY_DIR))


# ─────────────────────────────────────────────────────────────────
# Materiais canônicos.
# ─────────────────────────────────────────────────────────────────
WIRE_TYPE = {
    "name": "wire_IWRCEIPS_76mm",
    "d_nom": 0.0762,
    "d_vol": 0.0762,
    "m": 22.0,
    "w": 170.0,
    "EA": 5.5e8,
    "MBL": 6.5e6,
    "material": "wire",
    "cost": 0.0,
    "input_d": 76.0,
    "input_type": "wire",
}


CASES = [
    # AHV deck SEMPRE perto da posição vertical do pega (ww quase vertical).
    # Geometria realista: ww_horizontal ≪ ww_vertical para não exigir
    # L_ww enorme.
    {
        "id": "BC-AHV-OP-01",
        "mode": "favorable-symmetric",
        "description": "Pega centralizada, AHV adiante (X_AHV = X_pega + 30).",
        "h": 200.0,
        "X_fairlead": 1700.0,
        "X_AHV": 880.0,            # ~ pega + offset 30m
        "deck_z": 10.0,
        "L_lower": 1000.0,         # > chord(anchor, pega_meio)
        "L_upper": 1000.0,
        "L_ww": 250.0,
    },
    {
        "id": "BC-AHV-OP-02",
        "mode": "ahv-strong-pull",
        "description": "AHV mais distante (offset 100m horizontal).",
        "h": 200.0,
        "X_fairlead": 1700.0,
        "X_AHV": 950.0,
        "deck_z": 10.0,
        "L_lower": 1000.0,
        "L_upper": 1000.0,
        "L_ww": 280.0,
    },
    {
        "id": "BC-AHV-OP-03",
        "mode": "pega-near-anchor",
        "description": "Pega 25% do total (próximo anchor).",
        "h": 300.0,
        "X_fairlead": 2000.0,
        "X_AHV": 580.0,            # ~ pega + 80m horizontal
        "deck_z": 15.0,
        "L_lower": 800.0,          # cobre chord anchor (0,-300) → pega (~500,-150)
        "L_upper": 1900.0,
        "L_ww": 400.0,
    },
    {
        "id": "BC-AHV-OP-04",
        "mode": "pega-near-fairlead",
        "description": "Pega 75% do total (próximo fairlead).",
        "h": 300.0,
        "X_fairlead": 2000.0,
        "X_AHV": 1580.0,           # pega (~1500) + 80m
        "deck_z": 15.0,
        "L_lower": 1900.0,
        "L_upper": 800.0,
        "L_ww": 400.0,
    },
    {
        "id": "BC-AHV-OP-05",
        "mode": "deepwater",
        "description": "Águas profundas h=1500m, geometria simétrica.",
        "h": 1500.0,
        "X_fairlead": 2500.0,
        "X_AHV": 1320.0,           # pega meio (~1250) + 70m offset
        "deck_z": 20.0,
        "L_lower": 2400.0,         # cobre chord anchor (0,-1500) → pega (1250,-750)
        "L_upper": 2400.0,
        "L_ww": 1500.0,            # AHV deck a ~1500m verticais do pega
    },
    {
        "id": "BC-AHV-OP-06",
        "mode": "ultra-deepwater",
        "description": "Águas ultra-profundas h=2000m, simétrico.",
        "h": 2000.0,
        "X_fairlead": 3000.0,
        "X_AHV": 1580.0,
        "deck_z": 25.0,
        "L_lower": 3000.0,
        "L_upper": 3000.0,
        "L_ww": 2000.0,
    },
]


def _solve_moorpy_op(case: dict) -> dict:
    """
    Resolve via MoorPy System.solveEquilibrium().

    Setup:
      4 pontos: anchor (1=fixed), pega (0=free), AHV deck (1=fixed),
                fairlead (1=fixed).
      3 lines: lower mooring, upper mooring, work wire.

    O bollard pull é INDIRETO: AHV deck está fixo em (X_AHV, deck_z).
    A tração no work wire (= bollard pull resultante) cai do
    equilíbrio. Para varrer "bollard target", iteramos position do
    AHV deck até T_ww ≈ target. Mas para o baseline, usamos o
    setup fixo e gravamos o bollard pull resultante.
    """
    import moorpy as mp  # type: ignore

    h = case["h"]
    X_fairlead = case["X_fairlead"]
    X_AHV = case["X_AHV"]
    deck_z = case["deck_z"]
    L_lower = case["L_lower"]
    L_upper = case["L_upper"]
    L_ww = case["L_ww"]

    ms = mp.System(depth=h)
    ms.setLineType(name="wire", lineType=dict(WIRE_TYPE))

    # Anchor (fixed, no fundo)
    ms.addPoint(1, np.array([0.0, 0.0, -h]))
    # Pega (free) — restrito ao plano vertical X-Z (DOFs=[0, 2]).
    # Chute inicial baseado em geometria de chord aproximada.
    pega_x_init = X_fairlead * (L_lower / (L_lower + L_upper))
    pega_z_init = -h * 0.5
    ms.addPoint(0, np.array([pega_x_init, 0.0, pega_z_init]),
                DOFs=[0, 2])
    # AHV deck (fixed, acima da água)
    ms.addPoint(1, np.array([X_AHV, 0.0, deck_z]))
    # Fairlead (fixed, na superfície da plataforma)
    ms.addPoint(1, np.array([X_fairlead, 0.0, 0.0]))

    # Lines: lower (anchor=1 → pega=2), upper (pega=2 → fairlead=4),
    #        work_wire (pega=2 → AHV=3).
    ms.addLine(L_lower, "wire", pointA=1, pointB=2)
    ms.addLine(L_upper, "wire", pointA=2, pointB=4)
    ms.addLine(L_ww, "wire", pointA=2, pointB=3)

    ms.initialize()
    ms.solveEquilibrium(tol=0.01)

    line_lower = ms.lineList[0]
    line_upper = ms.lineList[1]
    line_ww = ms.lineList[2]

    fA_lower = np.array(line_lower.fA)  # força no anchor pelo mooring
    fB_lower = np.array(line_lower.fB)  # força na pega lado lower
    fA_upper = np.array(line_upper.fA)  # força na pega lado upper
    fB_upper = np.array(line_upper.fB)  # força no fairlead pelo upper
    fA_ww = np.array(line_ww.fA)        # força na pega lado ww
    fB_ww = np.array(line_ww.fB)        # força no AHV pelo ww

    T_anchor = float(np.linalg.norm(fA_lower))
    T_pega_lower = float(np.linalg.norm(fB_lower))
    T_pega_upper = float(np.linalg.norm(fA_upper))
    T_fairlead = float(np.linalg.norm(fB_upper))
    T_pega_ww = float(np.linalg.norm(fA_ww))
    T_AHV = float(np.linalg.norm(fB_ww))

    pega_pos = ms.pointList[1].r  # (x, y, z) of free point

    # Continuidade: soma das 3 forças no pega ≈ 0
    sum_x = float(fB_lower[0] + fA_upper[0] + fA_ww[0])
    sum_z = float(fB_lower[2] + fA_upper[2] + fA_ww[2])
    sum_residual = math.hypot(sum_x, sum_z)

    return {
        "T_anchor": T_anchor,
        "T_pega_lower": T_pega_lower,
        "T_pega_upper": T_pega_upper,
        "T_fairlead": T_fairlead,
        "T_pega_ww": T_pega_ww,
        "T_AHV": T_AHV,
        "pega_x": float(pega_pos[0]),
        "pega_z": float(pega_pos[2]),
        "fA_lower": fA_lower.tolist(),
        "fB_lower": fB_lower.tolist(),
        "fA_upper": fA_upper.tolist(),
        "fB_upper": fB_upper.tolist(),
        "fA_ww": fA_ww.tolist(),
        "fB_ww": fB_ww.tolist(),
        "sum_residual_at_pega": sum_residual,
    }


def _moorpy_commit() -> str:
    if COMMIT_FILE.exists():
        return COMMIT_FILE.read_text(encoding="utf-8").strip()
    return "unknown"


def main() -> None:
    print("Regenerando baseline MoorPy AHV Op (BC-AHV-OP-01..06)…\n")
    results: list[dict] = []
    for case in CASES:
        print(f"  {case['id']} [{case['mode']}]: {case['description']}")
        try:
            moorpy = _solve_moorpy_op(case)
            print(
                f"    T_anchor={moorpy['T_anchor']/1e3:.1f} kN  "
                f"T_AHV={moorpy['T_AHV']/1e3:.1f} kN  "
                f"T_fairlead={moorpy['T_fairlead']/1e3:.1f} kN  "
                f"pega=({moorpy['pega_x']:.0f}, {moorpy['pega_z']:.0f})  "
                f"residual={moorpy['sum_residual_at_pega']:.2e} N"
            )
            results.append({
                "id": case["id"],
                "mode": case["mode"],
                "description": case["description"],
                "inputs": {
                    "h": case["h"],
                    "X_fairlead": case["X_fairlead"],
                    "X_AHV": case["X_AHV"],
                    "deck_z": case["deck_z"],
                    "L_lower": case["L_lower"],
                    "L_upper": case["L_upper"],
                    "L_ww": case["L_ww"],
                    "wire": WIRE_TYPE,
                },
                "moorpy": moorpy,
                "status": "converged",
            })
        except Exception as e:
            print(f"    ERRO: {type(e).__name__}: {e}")
            results.append({
                "id": case["id"],
                "mode": case["mode"],
                "description": case["description"],
                "inputs": {
                    "h": case["h"], "X_fairlead": case["X_fairlead"],
                    "X_AHV": case["X_AHV"], "deck_z": case["deck_z"],
                    "L_lower": case["L_lower"], "L_upper": case["L_upper"],
                    "L_ww": case["L_ww"], "wire": WIRE_TYPE,
                },
                "moorpy": None,
                "error": f"{type(e).__name__}: {e}",
                "status": "failed",
            })

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out_path = REPO_ROOT / "docs" / "audit" / f"moorpy_ahv_op_baseline_{today}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "moorpy_commit": _moorpy_commit(),
        "ancoplat_phase": "Sprint 5 / Tier D Operacional",
        "comment": (
            "Baseline MoorPy para AHV Operacional Mid-Line. 6 cenários "
            "2D plano vertical (heading 0°/180°). Wire 76mm IWRCEIPS "
            "como material único. Referência para validar solver "
            "backend/solver/ahv_operational.py com gate rtol < 1e-2."
        ),
        "cases": results,
    }
    with out_path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)

    n_ok = sum(1 for r in results if r["status"] == "converged")
    print(
        f"\nBaseline regenerado: {n_ok}/{len(CASES)} convergidos.\n"
        f"Arquivo: {out_path.relative_to(REPO_ROOT)}"
    )


if __name__ == "__main__":
    main()
