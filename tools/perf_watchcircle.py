"""
Profiling do watchcircle 360° (Fase 9 / Q9).

Mede wall time do `compute_watchcircle()` para sistemas mooring
representativos. Plano define dois targets:

  - **<30s** (gate AC): aceitável; passa o critério de fechamento da F9.
  - **<5s** (aspirational): performance "boa" sem necessidade de
    otimização adicional.

Estratégia:
  - 4 cenários canônicos de mooring system + flag `--include-preview-cases`
    que adiciona configurações representativas de F7 (anchor uplift) e
    F8 (AHV bollard pull). Os preview cases são SOMENTE de baseline de
    configuração — solver real desses cases ainda não existe (F7/F8
    não estão implementados); profiling deles continua sendo wall time
    da resolução das linhas individuais (`endpoint_grounded=True`),
    com flag explícita no resultado registrando "PREVIEW".

  - Cada cenário roda compute_watchcircle com magnitude_n=2_000_000
    (2 MN — carga típica de tempestade) e n_steps=36.

  - Saída: tabela markdown + JSON em docs/relatorio_F9_perf_watchcircle.md.

Uso:
    venv/bin/python tools/perf_watchcircle.py
    venv/bin/python tools/perf_watchcircle.py --include-preview-cases
    venv/bin/python tools/perf_watchcircle.py --output relatorio.md
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path
from typing import Any

# Permite executar como `python tools/perf_watchcircle.py` (script).
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.api.schemas.mooring_systems import (  # noqa: E402
    MooringSystemInput,
    SystemLineSpec,
)
from backend.solver.equilibrium import compute_watchcircle  # noqa: E402
from backend.solver.types import (  # noqa: E402
    BoundaryConditions,
    LineSegment,
    SeabedConfig,
    SolutionMode,
)


def _make_line(
    name: str,
    azimuth_deg: float,
    h: float = 300.0,
    line_length: float = 800.0,
    t_fl: float = 1_200_000.0,
    endpoint_grounded: bool = True,
) -> SystemLineSpec:
    """Compõe uma SystemLineSpec genérica de chain studded para profiling."""
    return SystemLineSpec(
        name=name,
        fairlead_azimuth_deg=azimuth_deg,
        fairlead_radius=30.0,
        segments=[
            LineSegment(
                length=line_length,
                w=1100.0,
                EA=5.83e8,
                MBL=5.57e6,
            )
        ],
        boundary=BoundaryConditions(
            h=h,
            mode=SolutionMode.TENSION,
            input_value=t_fl,
            startpoint_depth=0.0,
            endpoint_grounded=endpoint_grounded,
        ),
        seabed=SeabedConfig(mu=0.6, slope_rad=0.0),
    )


def _scenario_4_lines() -> MooringSystemInput:
    """Spread mooring 4 linhas — config canônica."""
    return MooringSystemInput(
        name="Spread 4× (perf baseline)",
        description="4 linhas chain a 90° entre si, FPSO típico.",
        platform_radius=30.0,
        lines=[
            _make_line("L1", 45.0),
            _make_line("L2", 135.0),
            _make_line("L3", 225.0),
            _make_line("L4", 315.0),
        ],
    )


def _scenario_8_lines() -> MooringSystemInput:
    """Spread mooring 8 linhas — comum em FPSOs grandes."""
    azimuths = [22.5, 67.5, 112.5, 157.5, 202.5, 247.5, 292.5, 337.5]
    return MooringSystemInput(
        name="Spread 8× (perf)",
        description="8 linhas chain — FPSO grande.",
        platform_radius=40.0,
        lines=[_make_line(f"L{i+1}", a) for i, a in enumerate(azimuths)],
    )


def _scenario_taut_deep() -> MooringSystemInput:
    """4 linhas taut-leg em águas profundas (poliéster)."""
    return MooringSystemInput(
        name="Taut deep 4× (perf)",
        description="Poliéster 2000m — taut leg.",
        platform_radius=30.0,
        lines=[
            SystemLineSpec(
                name=f"L{i+1}",
                fairlead_azimuth_deg=45.0 + i * 90.0,
                fairlead_radius=30.0,
                segments=[
                    LineSegment(length=2150.0, w=16.5, EA=4.5e7, MBL=1.2e7),
                ],
                boundary=BoundaryConditions(
                    h=2000.0,
                    mode=SolutionMode.TENSION,
                    input_value=3_500_000.0,
                    startpoint_depth=0.0,
                    endpoint_grounded=True,
                ),
                seabed=SeabedConfig(mu=0.3, slope_rad=0.0),
            )
            for i in range(4)
        ],
    )


def _scenario_shallow_chain() -> MooringSystemInput:
    """4 linhas chain em águas rasas — bastante touchdown."""
    return MooringSystemInput(
        name="Shallow chain 4× (perf)",
        description="Águas rasas, chain leve com bastante touchdown.",
        platform_radius=20.0,
        lines=[
            _make_line(
                f"L{i+1}",
                45.0 + i * 90.0,
                h=50.0,
                line_length=250.0,
                t_fl=100_000.0,
            )
            for i in range(4)
        ],
    )


# Preview cases (F9 / Q9 ajuste): preparam baseline de profiling para
# Fases 7 e 8 quando elas fecharem. Hoje rodam com endpoint_grounded=True
# (solver atual) — substituem o input por uplift/AHV quando disponíveis.
def _scenario_preview_uplift() -> MooringSystemInput:
    """PREVIEW F7: 4 linhas que serão suspended endpoint quando F7 fechar."""
    return MooringSystemInput(
        name="Preview uplift 4× (F7)",
        description="PREVIEW: 4 linhas — endpoint_grounded=True por enquanto, vira uplift quando F7 implementar.",
        platform_radius=30.0,
        lines=[
            _make_line(f"L{i+1}", 45.0 + i * 90.0, h=300.0, line_length=500.0)
            for i in range(4)
        ],
    )


def _scenario_preview_ahv() -> MooringSystemInput:
    """PREVIEW F8: 4 linhas com slot reservado para AHV bollard pull."""
    return MooringSystemInput(
        name="Preview AHV 4× (F8)",
        description="PREVIEW: 4 linhas — schema AHV pendente, vira force-on-line quando F8 implementar.",
        platform_radius=30.0,
        lines=[
            _make_line(f"L{i+1}", 45.0 + i * 90.0, h=300.0, line_length=600.0)
            for i in range(4)
        ],
    )


def time_watchcircle(
    msys: MooringSystemInput,
    *,
    magnitude_n: float = 2_000_000.0,
    n_steps: int = 36,
    repetitions: int = 3,
) -> dict[str, Any]:
    """Mede wall time de `compute_watchcircle()` em N repetições."""
    times: list[float] = []
    n_converged_total = 0
    for _ in range(repetitions):
        t0 = time.perf_counter()
        result = compute_watchcircle(msys, magnitude_n, n_steps)
        elapsed = time.perf_counter() - t0
        times.append(elapsed)
        n_converged_total = sum(
            1 for p in result.points if p.equilibrium.converged
        )
    return {
        "scenario": msys.name,
        "n_lines": len(msys.lines),
        "n_steps": n_steps,
        "magnitude_n": magnitude_n,
        "min_s": min(times),
        "median_s": statistics.median(times),
        "max_s": max(times),
        "mean_s": statistics.mean(times),
        "repetitions": repetitions,
        "n_converged_per_run": n_converged_total,
    }


def classify(median_s: float) -> str:
    """ok / warn / fail conforme targets do plano."""
    if median_s < 5.0:
        return "ok (<5s aspirational)"
    if median_s < 30.0:
        return "warn (<30s gate; >5s aspirational)"
    return "FAIL (>=30s — viola gate)"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--include-preview-cases",
        action="store_true",
        help="Inclui scenarios preview F7/F8 no profiling.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/relatorio_F9_perf_watchcircle.md"),
        help="Arquivo de saída markdown.",
    )
    parser.add_argument(
        "--repetitions",
        type=int,
        default=3,
        help="Número de execuções por cenário (médio é a métrica reportada).",
    )
    parser.add_argument(
        "--n-steps",
        type=int,
        default=36,
        help="Número de azimutes na varredura (default 36).",
    )
    args = parser.parse_args()

    scenarios = [
        ("functional", _scenario_4_lines()),
        ("functional", _scenario_8_lines()),
        ("functional", _scenario_taut_deep()),
        ("functional", _scenario_shallow_chain()),
    ]
    if args.include_preview_cases:
        scenarios.append(("preview-F7", _scenario_preview_uplift()))
        scenarios.append(("preview-F8", _scenario_preview_ahv()))

    results: list[dict[str, Any]] = []
    print(f"\nWatchcircle profiling (n_steps={args.n_steps}, "
          f"reps={args.repetitions}, magnitude=2 MN)\n")
    for kind, msys in scenarios:
        print(f"  Running '{msys.name}' ({kind})…", flush=True)
        r = time_watchcircle(
            msys,
            magnitude_n=2_000_000.0,
            n_steps=args.n_steps,
            repetitions=args.repetitions,
        )
        r["kind"] = kind
        r["classification"] = classify(r["median_s"])
        results.append(r)
        print(f"    median={r['median_s']:.3f}s  ({r['classification']})")

    write_report(results, args.output)
    print(f"\nReport written to {args.output}")

    # Exit code: 1 se qualquer functional case violar o gate <30s
    failed = [
        r for r in results if r["kind"] == "functional" and r["median_s"] >= 30.0
    ]
    if failed:
        print(f"\nFAIL: {len(failed)} functional scenario(s) violate <30s gate.")
        return 1
    return 0


def write_report(results: list[dict[str, Any]], path: Path) -> None:
    lines: list[str] = []
    lines.append("# Relatório F9 — Profiling watchcircle\n")
    lines.append(
        "Profiling do `compute_watchcircle()` em sistemas mooring "
        "representativos.\n"
    )
    lines.append("**Targets:**\n")
    lines.append("- Gate (AC): mediana <30s.")
    lines.append("- Aspiracional: mediana <5s (não-bloqueante).\n")
    lines.append("**Resultados** (mediana de N execuções):\n")
    lines.append(
        "| Cenário | Tipo | Linhas | n_steps | min (s) | mediana (s) "
        "| max (s) | classificação |"
    )
    lines.append("|---|---|---:|---:|---:|---:|---:|---|")
    for r in results:
        lines.append(
            f"| {r['scenario']} | {r['kind']} | {r['n_lines']} | "
            f"{r['n_steps']} | {r['min_s']:.3f} | {r['median_s']:.3f} "
            f"| {r['max_s']:.3f} | {r['classification']} |"
        )
    lines.append("\n## Raw JSON\n")
    lines.append("```json")
    lines.append(json.dumps(results, indent=2))
    lines.append("```\n")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
