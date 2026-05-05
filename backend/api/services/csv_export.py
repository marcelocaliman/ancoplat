"""
Exportador CSV de geometria de cabo (Fase 5 / Q5).

Formato international (decimal `.`, separator `,`) — padrão para
análise externa em Python/MATLAB/Octave/R.

Para abrir corretamente no Excel BR (que espera `;` separator),
o usuário deve usar Importar Dados → Texto, não duplo-clique
(documentado em tooltip da UI no Commit 6).
"""
from __future__ import annotations

import io
import csv
from datetime import datetime, timezone

from backend.solver.types import SolverResult


CSV_HEADER = ["x_m", "y_m", "tension_x_n", "tension_y_n", "tension_magnitude_n"]


def build_geometry_csv(result: SolverResult, case_name: str = "") -> str:
    """
    Serializa a geometria do solve em CSV.

    Header: x_m, y_m, tension_x_n, tension_y_n, tension_magnitude_n
    Encoding: UTF-8.
    Separator: , (vírgula, padrão international)
    Decimal: . (ponto)
    Linhas: ≥ 5001 (1 header + ≥ 5000 pontos) para case típico.

    Inclui prefixo de comentário com metadados (case name + timestamp +
    solver_version + hash_short) para rastreabilidade.

    AncoPlat default `n_plot_points = 5000` no SolverConfig garante
    ≥ 5000 pontos na geometria (`coords_x`/`coords_y`/etc.).
    """
    buf = io.StringIO()

    # Cabeçalho de comentários (CSV reader pode pular linhas iniciando com '#')
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    if case_name:
        buf.write(f"# AncoPlat geometry export: {case_name}\n")
    buf.write(f"# generated: {now}\n")
    buf.write(f"# solver_version: {result.solver_version}\n")
    buf.write(f"# n_points: {len(result.coords_x)}\n")
    buf.write("# unit_system: SI (m, N)\n")

    writer = csv.writer(buf, delimiter=",", lineterminator="\n")
    writer.writerow(CSV_HEADER)
    for i in range(len(result.coords_x)):
        writer.writerow([
            f"{result.coords_x[i]:.6f}",
            f"{result.coords_y[i]:.6f}",
            f"{result.tension_x[i]:.4f}",
            f"{result.tension_y[i]:.4f}",
            f"{result.tension_magnitude[i]:.4f}",
        ])
    return buf.getvalue()


__all__ = ["build_geometry_csv", "CSV_HEADER"]
