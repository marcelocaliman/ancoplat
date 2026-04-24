"""
Camada 4 — Correção elástica da catenária.

Modelo: cada elemento estica segundo
  dL_stretched = dL_unstretched · (1 + T_média / EA)

conforme Seção 3.3.2 do Documento A v2.2 (decisão fechada: "tração axial
média do elemento, não tração local, por estabilidade numérica em malha
grosseira").

Como temos UMA linha (um segmento homogêneo) no MVP v1, aplica-se uma
T_média global:
  L_stretched = L_unstretched · (1 + T_média_global / EA)

Algoritmo (loop externo)
------------------------
1. Inicializa L_eff := L (linha não-esticada).
2. Resolve rígido usando L_eff como comprimento de linha para a geometria.
3. Mede T_mean a partir da tensão ao longo da linha.
4. Atualiza L_eff := L · (1 + T_mean / EA).
5. Repete até |ΔL_eff / L_eff| < elastic_tolerance (default 1e-5).
6. Retorna resultado com stretched_length e elongation preenchidos.

Referências:
  - Documento A v2.2, Seções 3.3.2, 3.5.3
  - Documentação MVP v2, Seção 7.3
"""
from __future__ import annotations

import numpy as np

from .catenary import solve_rigid_suspended
from .types import (
    ConvergenceStatus,
    SolutionMode,
    SolverConfig,
    SolverResult,
)


def _mean_tension(result: SolverResult) -> float:
    """Tração média ao longo da linha, estimada pela média aritmética da
    magnitude da tração na discretização (uniforme em arc-length)."""
    return float(np.mean(result.tension_magnitude))


def apply_elastic_correction(
    unstretched_length: float, EA: float, T_mean: float
) -> float:
    """
    Retorna o comprimento esticado de acordo com a Seção 3.3.2:
      L_stretched = L · (1 + T_mean / EA).
    """
    if EA <= 0:
        raise ValueError("EA deve ser > 0 no modo elástico")
    return unstretched_length * (1.0 + T_mean / EA)


def solve_elastic_iterative(
    L: float,
    h: float,
    w: float,
    EA: float,
    mode: SolutionMode,
    input_value: float,
    config: SolverConfig | None = None,
    mu: float = 0.0,
    MBL: float = 0.0,
) -> SolverResult:
    """
    Solver completo com correção elástica.

    Loop externo: resolve rígido com L_eff, atualiza L_eff usando T_mean
    até convergir. Se EA é "infinito" (muito grande), converge em 1-2
    iterações para o resultado rígido.
    """
    if config is None:
        config = SolverConfig()
    if EA <= 0:
        raise ValueError("EA deve ser > 0 no modo elástico")

    L_eff = L
    T_mean = 0.0
    iters = 0
    rigid_result: SolverResult | None = None
    for iters in range(1, config.max_elastic_iter + 1):
        # Resolve rígido com comprimento corrente (L_eff)
        rigid_result = solve_rigid_suspended(
            L=L_eff, h=h, w=w, mode=mode, input_value=input_value,
            config=config, mu=mu, MBL=MBL,
        )
        # Reporta tração média ao longo da linha
        T_mean = _mean_tension(rigid_result)
        L_new = apply_elastic_correction(L, EA, T_mean)
        # Teste de convergência: mudança relativa em L_eff
        rel_change = abs(L_new - L_eff) / max(L_eff, 1e-12)
        L_eff = L_new
        if rel_change < config.elastic_tolerance:
            break
    else:
        # não quebrou por break → atingiu max_elastic_iter sem convergir
        assert rigid_result is not None
        return SolverResult(
            **{
                **rigid_result.model_dump(),
                "status": ConvergenceStatus.MAX_ITERATIONS,
                "message": (
                    f"Loop elástico atingiu {config.max_elastic_iter} iterações "
                    f"sem convergir (última variação relativa: {rel_change:.2e})."
                ),
                "unstretched_length": L,
                "stretched_length": L_eff,
                "elongation": L_eff - L,
                "iterations_used": iters,
            }
        )

    assert rigid_result is not None

    # Ajusta campos relacionados a alongamento.
    # Obs.: os campos de geometria já refletem L_eff, pois foi isso que
    # passamos ao solver rígido. total_suspended/grounded continuam consistentes.
    final = SolverResult(
        **{
            **rigid_result.model_dump(),
            "unstretched_length": L,
            "stretched_length": L_eff,
            "elongation": L_eff - L,
            "iterations_used": iters,
            "message": (
                "Catenária elástica convergida "
                f"em {iters} iterações (ΔL_rel={rel_change:.2e})."
            ),
        }
    )
    return final


__all__ = [
    "apply_elastic_correction",
    "solve_elastic_iterative",
]
