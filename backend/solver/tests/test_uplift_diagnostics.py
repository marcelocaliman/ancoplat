"""
Testes de D016 + D017 (Fase 7 / Q8).

D016 (high, error) — anchor uplift fora de domínio:
  - endpoint_depth ≤ 0 (acima da superfície)
  - endpoint_depth > h + ε (abaixo do seabed)
  Pré-validação Pydantic já bloqueia; D016 é defesa em profundidade
  para inputs vindos de fora (import .moor antigo, scripts diretos).

D017 (medium, warning) — uplift desprezível:
  - 0 < (h - endpoint_depth) < 1m
  Caso de fronteira numericamente delicado; sugere endpoint_grounded=True.
"""
from __future__ import annotations

import pytest

from backend.solver.diagnostics import (
    D016_anchor_uplift_invalid,
    D017_anchor_uplift_negligible,
)
from backend.solver.solver import solve
from backend.solver.types import (
    BoundaryConditions,
    ConvergenceStatus,
    LineSegment,
    SolutionMode,
)


def _seg() -> LineSegment:
    return LineSegment(length=500.0, w=200.0, EA=3.4e7, MBL=3.78e6)


# ─── D016: domínio violado ──────────────────────────────────────────


def test_D016_endpoint_depth_zero_message():
    """endpoint_depth ≤ 0 → mensagem clara."""
    d = D016_anchor_uplift_invalid(endpoint_depth=0.0, h=300.0)
    assert d.code == "D016_ANCHOR_UPLIFT_INVALID"
    assert d.severity == "error"
    assert d.confidence == "high"
    assert "≤ 0" in d.cause or "acima ou na superfície" in d.cause
    assert "boundary.endpoint_depth" in d.affected_fields


def test_D016_endpoint_depth_above_h_message():
    """endpoint_depth > h → mensagem distinta orientando para grounded."""
    d = D016_anchor_uplift_invalid(endpoint_depth=350.0, h=300.0)
    assert d.severity == "error"
    assert "abaixo do seabed" in d.cause
    assert "endpoint_grounded=True" in d.suggestion


# ─── D017: uplift desprezível ───────────────────────────────────────


def test_D017_dispara_em_uplift_pequeno():
    """uplift = 0.5m < 1m → D017 dispara."""
    d = D017_anchor_uplift_negligible(endpoint_depth=299.5, h=300.0)
    assert d.code == "D017_ANCHOR_UPLIFT_NEGLIGIBLE"
    assert d.severity == "warning"
    assert d.confidence == "medium"
    assert "0.50 m" in d.cause or "0.5 m" in d.cause
    assert "endpoint_grounded=True" in d.suggestion


def test_D017_solver_inclui_no_result_quando_uplift_small():
    """
    Solver real popula D017 em result.diagnostics quando uplift < 1m.
    Caso de teste: h=300, endpoint_depth=299.5 → uplift=0.5m.
    """
    bc = BoundaryConditions(
        h=300.0, mode=SolutionMode.TENSION, input_value=850_000.0,
        endpoint_grounded=False, endpoint_depth=299.5,
    )
    r = solve([_seg()], bc)
    assert r.status == ConvergenceStatus.CONVERGED
    codes = [d["code"] for d in r.diagnostics]
    assert "D017_ANCHOR_UPLIFT_NEGLIGIBLE" in codes


def test_D017_NAO_dispara_em_uplift_normal():
    """
    Uplift ≥ 1m não dispara D017. Caso BC-UP-01 (uplift=50m) limpo.
    """
    bc = BoundaryConditions(
        h=300.0, mode=SolutionMode.TENSION, input_value=850_000.0,
        endpoint_grounded=False, endpoint_depth=250.0,  # uplift=50m
    )
    r = solve([_seg()], bc)
    assert r.status == ConvergenceStatus.CONVERGED
    codes = [d["code"] for d in r.diagnostics]
    assert "D017_ANCHOR_UPLIFT_NEGLIGIBLE" not in codes


def test_D017_NAO_dispara_em_grounded():
    """endpoint_grounded=True não dispara D017 (caso normal)."""
    bc = BoundaryConditions(
        h=300.0, mode=SolutionMode.TENSION, input_value=785_000.0,
    )  # grounded default
    r = solve([_seg()], bc)
    codes = [d["code"] for d in r.diagnostics]
    assert "D017_ANCHOR_UPLIFT_NEGLIGIBLE" not in codes


# ─── D017 fronteiras ────────────────────────────────────────────────


def test_D017_threshold_boundary_uplift_1m_exato_nao_dispara():
    """uplift=1m exato → D017 NÃO dispara (limiar < 1m)."""
    bc = BoundaryConditions(
        h=300.0, mode=SolutionMode.TENSION, input_value=850_000.0,
        endpoint_grounded=False, endpoint_depth=299.0,  # uplift=1m
    )
    r = solve([_seg()], bc)
    if r.status == ConvergenceStatus.CONVERGED:
        codes = [d["code"] for d in r.diagnostics]
        assert "D017_ANCHOR_UPLIFT_NEGLIGIBLE" not in codes


def test_D017_threshold_uplift_0_99m_dispara():
    """uplift=0.99m → D017 dispara."""
    bc = BoundaryConditions(
        h=300.0, mode=SolutionMode.TENSION, input_value=850_000.0,
        endpoint_grounded=False, endpoint_depth=299.01,  # uplift=0.99m
    )
    r = solve([_seg()], bc)
    if r.status == ConvergenceStatus.CONVERGED:
        codes = [d["code"] for d in r.diagnostics]
        assert "D017_ANCHOR_UPLIFT_NEGLIGIBLE" in codes
