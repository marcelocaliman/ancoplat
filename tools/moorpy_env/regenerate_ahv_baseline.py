"""
Regenera o baseline numérico do MoorPy Subsystem para AHV Tier C
(BC-AHV-MOORPY-01..08) — Sprint 4 / Commit 34.

Modela o sistema completo:

    [AHV deck]  (X = X_AHV, Z = deck_z)        ← endpoint B (AHV virtual)
        |
        |  Work Wire (cabo de trabalho — wire elástico, peso submerso)
        |
    [pega]  (X intermediário, Z negativo)      ← junção interna
         \\
          \\  Mooring line (chain/wire — pode ter trecho grounded)
           \\
            v Anchor                            ← endpoint A
            (X = 0, Z = -h se grounded; -endpoint_depth se uplift)

Padrão alinhado com `regenerate_baseline.py` (Fase 1) e
`regenerate_uplift_baseline.py` (Fase 7):
  - Inputs FIXOS: h, X_AHV, deck_z, L_moor, mooring props, L_ww, ww props.
  - MoorPy `Subsystem.makeGeneric([L_moor, L_ww], [mooring_type, ww_type])`
    + `staticSolve()` resolve o equilíbrio.
  - Output salvo: T_fl (no AHV), T_anchor (no fundo), T_pega (junção
    interna), L_lay (grounded), perfis x/z para sanity.
  - Comparação com AncoPlat virá no Commit 35 (test_vs_moorpy.py).

Cenários BC-AHV-MOORPY (8 = 6 grounded + 2 uplift):
  | ID  | Modo         | h(m) | X_AHV(m) | deck(m) | L_moor(m) | L_ww(m) | uplift |
  |-----|--------------|-----:|---------:|--------:|----------:|--------:|-------:|
  | 01  | Backing-1    |  100 |      800 |       5 |      1000 |     100 |     no |
  | 02  | Backing-2    |  200 |     1500 |       8 |      1800 |     150 |     no |
  | 03  | Hookup-1     |  100 |      600 |       5 |      1000 |      80 |     no |
  | 04  | Hookup-2     |  150 |      900 |       6 |      1500 |     120 |     no |
  | 05  | LoadXfer-1   |  200 |     1300 |       8 |      1700 |     200 |     no |
  | 06  | LoadXfer-2   |  300 |     2000 |      10 |      2400 |     300 |     no |
  | 07  | Backing+UP   |  100 |      800 |       5 |       800 |     100 |    yes |
  | 08  | LoadXfer+UP  |  200 |     1500 |       8 |      1500 |     150 |    yes |

Materiais canônicos (constantes em todos os cenários):
  - mooring: chain R4 76mm — w=1241 N/m, EA=6.0e8, MBL=7.5e6
  - work_wire: IWRCEIPS 76mm — w=170 N/m, EA=5.5e8, MBL=6.5e6

Saída:
    docs/audit/moorpy_ahv_baseline_<DATE>.json — array de 8 entradas.

Uso:
    venv/bin/python tools/moorpy_env/regenerate_ahv_baseline.py
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
# Materiais canônicos (constantes — fixados para reprodutibilidade).
# Espelham R4 chain 76mm + IWRCEIPS wire 76mm típicos de instalação.
# ─────────────────────────────────────────────────────────────────
MOORING_TYPE = {
    # Wire 76mm IWRCEIPS (mais leve que chain — suspensão parcial em
    # cenários típicos de instalação AHV com bollard moderado).
    "name": "mooring_wire_IWRCEIPS_76mm",
    "d_nom": 0.076,
    "d_vol": 0.076,
    "m": 22.0,         # kg/m (massa no ar)
    "w": 170.0,        # N/m (peso submerso)
    "EA": 5.5e8,       # N
    "MBL": 6.5e6,      # N
    "material": "wire",
    "cost": 0.0,
    "input_d": 76.0,
    "input_type": "wire",
}
WW_TYPE = {
    "name": "work_wire_IWRCEIPS_76mm",
    "d_nom": 0.076,
    "d_vol": 0.076,
    "m": 22.0,         # kg/m
    "w": 170.0,        # N/m peso submerso
    "EA": 5.5e8,       # N
    "MBL": 6.5e6,      # N
    "material": "wire",
    "cost": 0.0,
    "input_d": 76.0,
    "input_type": "wire",
}


# ─────────────────────────────────────────────────────────────────
# 8 casos canônicos BC-AHV-MOORPY-01..08.
#
# `endpoint_depth` = profundidade do anchor abaixo da superfície.
# Em casos sem uplift, endpoint_depth == h (anchor no fundo).
# Em casos com uplift, endpoint_depth < h (anchor suspenso).
# ─────────────────────────────────────────────────────────────────
CASES = [
    {
        "id": "BC-AHV-MOORPY-01",
        "mode": "backing-down",
        "description": "Backing Down taut elástico — L≈chord, T_anchor>0.",
        "h": 100.0,
        "endpoint_depth": 100.0,
        "X_AHV": 800.0,
        "deck_z": 5.0,
        "L_moor": 802.0,    # chord≈806, déficit 4m → estira elasticamente
        "L_ww": 100.0,
    },
    {
        "id": "BC-AHV-MOORPY-02",
        "mode": "backing-down",
        "description": "Backing Down águas profundas taut elástico.",
        "h": 200.0,
        "endpoint_depth": 200.0,
        "X_AHV": 1500.0,
        "deck_z": 8.0,
        "L_moor": 1520.0,   # chord≈1513, folga 0.5%
        "L_ww": 150.0,
    },
    {
        "id": "BC-AHV-MOORPY-03",
        "mode": "hookup",
        "description": "Hookup conexão inicial — linha frouxa, bollard baixo.",
        "h": 100.0,
        "endpoint_depth": 100.0,
        "X_AHV": 600.0,
        "deck_z": 5.0,
        "L_moor": 800.0,    # chord≈608, folga 32%
        "L_ww": 80.0,
    },
    {
        "id": "BC-AHV-MOORPY-04",
        "mode": "hookup",
        "description": "Hookup intermediário — folga 20%.",
        "h": 150.0,
        "endpoint_depth": 150.0,
        "X_AHV": 900.0,
        "deck_z": 6.0,
        "L_moor": 1100.0,   # chord≈912, folga 21%
        "L_ww": 120.0,
    },
    {
        "id": "BC-AHV-MOORPY-05",
        "mode": "load-transfer",
        "description": "Load Transfer transição — folga 12%.",
        "h": 200.0,
        "endpoint_depth": 200.0,
        "X_AHV": 1300.0,
        "deck_z": 8.0,
        "L_moor": 1480.0,   # chord≈1315, folga 12%
        "L_ww": 200.0,
    },
    {
        "id": "BC-AHV-MOORPY-06",
        "mode": "load-transfer",
        "description": "Load Transfer águas ultra-profundas — folga 12%.",
        "h": 300.0,
        "endpoint_depth": 300.0,
        "X_AHV": 2000.0,
        "deck_z": 10.0,
        "L_moor": 2280.0,   # chord≈2022, folga 13%
        "L_ww": 300.0,
    },
    {
        "id": "BC-AHV-MOORPY-07",
        "mode": "backing-down + uplift",
        "description": "Backing Down com anchor suspenso — uplift 20m, folga moderada.",
        "h": 200.0,
        "endpoint_depth": 180.0,  # uplift 20m
        "X_AHV": 1300.0,
        "deck_z": 8.0,
        "L_moor": 1500.0,
        "L_ww": 150.0,
    },
    {
        "id": "BC-AHV-MOORPY-08",
        "mode": "load-transfer + uplift",
        "description": "Load Transfer com anchor suspenso — uplift 30m águas profundas.",
        "h": 300.0,
        "endpoint_depth": 270.0,  # uplift 30m
        "X_AHV": 1700.0,
        "deck_z": 10.0,
        "L_moor": 2000.0,
        "L_ww": 200.0,
    },
    {
        "id": "BC-AHV-MOORPY-09",
        "mode": "deepwater taut",
        "description": (
            "Águas profundas com mooring suspenso real — gate Tier C matemático."
        ),
        "h": 1500.0,
        "endpoint_depth": 1500.0,
        "X_AHV": 2000.0,
        "deck_z": 15.0,
        "L_moor": 2700.0,   # chord ≈ 2502, folga 8%
        "L_ww": 300.0,
    },
    {
        "id": "BC-AHV-MOORPY-10",
        "mode": "deepwater taut",
        "description": (
            "Águas ultra-profundas — Tier C matemático com suspensão completa."
        ),
        "h": 2000.0,
        "endpoint_depth": 2000.0,
        "X_AHV": 2500.0,
        "deck_z": 20.0,
        "L_moor": 3500.0,   # chord ≈ 3208, folga 9%
        "L_ww": 350.0,
    },
]


def _solve_moorpy_subsystem(case: dict) -> dict:
    """
    Resolve via MoorPy Subsystem.makeGeneric() + staticSolve().

    Configuração:
      - depth = h (água do caso)
      - 2 segmentos: [mooring (anchor → pega), work_wire (pega → AHV)]
      - rA = (0, 0, -endpoint_depth)  → anchor (no fundo ou suspenso)
      - rB = (X_AHV, 0, deck_z)        → AHV deck na superfície

    Outputs lidos do estado pós-solve:
      - T no anchor (end A do segmento mooring)
      - T no AHV (end B do segmento work wire) — equivale ao bollard pull
      - T na pega (junção entre os 2 segmentos)
      - lay length (grounded portion)
    """
    from moorpy.subsystem import Subsystem  # type: ignore

    h = case["h"]
    endpoint_depth = case["endpoint_depth"]
    X_AHV = case["X_AHV"]
    deck_z = case["deck_z"]
    L_moor = case["L_moor"]
    L_ww = case["L_ww"]

    # Subsystem com depth=h. rad_fair=0 e rBfair=[0,0,deck_z] coloca
    # o "fairlead virtual" (AHV) na coordenada relativa do deck.
    ss = Subsystem(depth=h, spacing=X_AHV, rBfair=[0.0, 0.0, deck_z])

    # Adiciona lineTypes via dict direto (mais controle do que MoorProps).
    ss.setLineType(name="mooring", lineType=dict(MOORING_TYPE))
    ss.setLineType(name="work_wire", lineType=dict(WW_TYPE))

    # makeGeneric: ordem é [anchor → fairlead]. Primeiro a mooring
    # (lado do anchor), depois o Work Wire (lado do AHV).
    ss.makeGeneric(
        lengths=[L_moor, L_ww],
        types=["mooring", "work_wire"],
        suspended=0,  # end A (anchor) no fundo
        nSegs=20,
    )

    # Posiciona endpoints em coordenadas globais (override do default).
    # End A = anchor: (0, 0, -endpoint_depth) — uplift se < h.
    # End B = AHV deck: (X_AHV, 0, deck_z).
    ss.setEndPosition(np.array([0.0, 0.0, -endpoint_depth]), endB=0)
    ss.setEndPosition(np.array([X_AHV, 0.0, deck_z]), endB=1)

    # Resolver equilíbrio estático.
    ss.staticSolve(tol=1e-6, maxIter=500)

    # Tensões nos endpoints — Line.fA e Line.fB são forças no end A/B
    # em coords globais (Fx, Fy, Fz). Magnitude = sqrt(Fx²+Fy²+Fz²).
    line_moor = ss.lineList[0]   # mooring line
    line_ww = ss.lineList[1]     # work wire

    fA_moor = np.array(line_moor.fA)  # força no anchor
    fB_moor = np.array(line_moor.fB)  # força na pega (lado mooring)
    fA_ww = np.array(line_ww.fA)      # força na pega (lado work wire)
    fB_ww = np.array(line_ww.fB)      # força no AHV

    T_anchor = float(np.linalg.norm(fA_moor))
    T_pega_moor = float(np.linalg.norm(fB_moor))
    T_pega_ww = float(np.linalg.norm(fA_ww))
    T_AHV = float(np.linalg.norm(fB_ww))

    # Lay length: getLayLength(iLine=0) retorna comprimento grounded
    # do segmento iLine. Pega só do mooring (work wire é sempre suspenso).
    try:
        lay_moor = float(ss.getLayLength(iLine=0))
    except Exception:
        lay_moor = 0.0

    # Sanity: H deve ser contínuo entre os 2 segmentos na pega.
    H_pega_moor = float(fB_moor[0])  # Fx no end B do mooring
    H_pega_ww = float(fA_ww[0])      # Fx no end A do ww (com sinal)
    # Convenção MoorPy: fA é força APLICADA no end A da linha pelo
    # ponto. Logo no ponto de pega, fB_moor + fA_ww deve ≈ 0 (ponto sem massa).
    H_continuity_residual = H_pega_moor + H_pega_ww

    return {
        "T_anchor": T_anchor,
        "T_pega_moor": T_pega_moor,
        "T_pega_ww": T_pega_ww,
        "T_AHV": T_AHV,
        "lay_length_moor": lay_moor,
        "fA_moor": fA_moor.tolist(),
        "fB_moor": fB_moor.tolist(),
        "fA_ww": fA_ww.tolist(),
        "fB_ww": fB_ww.tolist(),
        "H_continuity_residual": H_continuity_residual,
    }


def _moorpy_commit() -> str:
    if COMMIT_FILE.exists():
        return COMMIT_FILE.read_text(encoding="utf-8").strip()
    return "unknown"


def main() -> None:
    print("Regenerando baseline MoorPy AHV Tier C (BC-AHV-MOORPY-01..08)…\n")

    results: list[dict] = []
    for case in CASES:
        print(f"  {case['id']} [{case['mode']}]: {case['description']}")
        try:
            moorpy = _solve_moorpy_subsystem(case)
            print(
                f"    T_anchor = {moorpy['T_anchor']/1e3:.1f} kN  |  "
                f"T_AHV = {moorpy['T_AHV']/1e3:.1f} kN  |  "
                f"lay = {moorpy['lay_length_moor']:.1f} m  |  "
                f"H_residual = {moorpy['H_continuity_residual']:.2e} N"
            )
            results.append({
                "id": case["id"],
                "mode": case["mode"],
                "description": case["description"],
                "inputs": {
                    "h": case["h"],
                    "endpoint_depth": case["endpoint_depth"],
                    "X_AHV": case["X_AHV"],
                    "deck_z": case["deck_z"],
                    "L_moor": case["L_moor"],
                    "L_ww": case["L_ww"],
                    "mooring": MOORING_TYPE,
                    "work_wire": WW_TYPE,
                },
                "moorpy": moorpy,
                "status": "converged",
            })
        except Exception as e:  # noqa: BLE001
            print(f"    ERRO: {type(e).__name__}: {e}")
            results.append({
                "id": case["id"],
                "mode": case["mode"],
                "description": case["description"],
                "inputs": {
                    "h": case["h"],
                    "endpoint_depth": case["endpoint_depth"],
                    "X_AHV": case["X_AHV"],
                    "deck_z": case["deck_z"],
                    "L_moor": case["L_moor"],
                    "L_ww": case["L_ww"],
                    "mooring": MOORING_TYPE,
                    "work_wire": WW_TYPE,
                },
                "moorpy": None,
                "error": f"{type(e).__name__}: {e}",
                "status": "failed",
            })

    # Salva JSON.
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out_path = REPO_ROOT / "docs" / "audit" / f"moorpy_ahv_baseline_{today}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "moorpy_commit": _moorpy_commit(),
        "ancoplat_phase": "Sprint 4 / Tier C",
        "comment": (
            "Baseline MoorPy Subsystem para AHV Tier C. 8 cenários "
            "(6 grounded + 2 uplift). Materiais canônicos R4 chain "
            "76mm + IWRCEIPS wire 76mm. Output usado pelo "
            "test_ahv_tier_c_vs_moorpy.py com gate rtol < 1e-2."
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
