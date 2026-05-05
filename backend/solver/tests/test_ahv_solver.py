"""
Smoke test do solver com AHV (Fase 8 / Commit 3).

Cobre:
  - Solver multi-segmento converge com AHV puxando lateralmente.
  - T_fl input == T_fl output (relação fechada da catenária).
  - AHV horizontal puro (heading=0) muda H entre segmentos.
  - AHV heading=90 (perpendicular) → projeção 0 → equivalente a sem AHV
    (mas D019 deveria disparar — testado no Commit subsequente).
  - AHV + uplift → INVALID_CASE com mensagem clara (Q5 ajuste).
  - _signed_force_2d: convenção (H_jump, V_jump) por kind.

Validação numérica detalhada vs cálculo manual está em
test_ahv_moorpy.py (Commit 5 com BC-AHV-01..04).
"""
from __future__ import annotations

import math

import pytest

from backend.solver.multi_segment import (
    _signed_force_2d,
    ahv_in_plane_fraction,
)
from backend.solver.solver import solve
from backend.solver.types import (
    BoundaryConditions,
    ConvergenceStatus,
    LineAttachment,
    LineSegment,
    SolutionMode,
)


def _seg() -> LineSegment:
    return LineSegment(length=300.0, w=200.0, EA=3.4e7, MBL=3.78e6)


# ─── _signed_force_2d (Fase 8 helper) ──────────────────────────────


def test_signed_force_2d_buoy():
    att = LineAttachment(kind="buoy", submerged_force=50_000.0, position_index=0)
    assert _signed_force_2d(att) == (0.0, -50_000.0)


def test_signed_force_2d_clump():
    att = LineAttachment(kind="clump_weight", submerged_force=80_000.0, position_index=0)
    assert _signed_force_2d(att) == (0.0, 80_000.0)


def test_signed_force_2d_ahv_heading_zero_full_horizontal():
    """heading=0 → toda a força no plano da linha (caso isolado, line_az=0)."""
    att = LineAttachment(
        kind="ahv", position_index=0,
        ahv_bollard_pull=200_000.0, ahv_heading_deg=0.0,
    )
    h_jump, v_jump = _signed_force_2d(att)
    assert math.isclose(h_jump, 200_000.0, rel_tol=1e-9)
    assert v_jump == 0.0


def test_signed_force_2d_ahv_heading_60_half_horizontal():
    """heading=60° → cos(60°)=0.5 → 50% no plano."""
    att = LineAttachment(
        kind="ahv", position_index=0,
        ahv_bollard_pull=200_000.0, ahv_heading_deg=60.0,
    )
    h_jump, _ = _signed_force_2d(att)
    assert math.isclose(h_jump, 100_000.0, abs_tol=1.0)


def test_signed_force_2d_ahv_heading_90_zero_horizontal():
    """heading=90° → cos(90°)=0 → 0% no plano."""
    att = LineAttachment(
        kind="ahv", position_index=0,
        ahv_bollard_pull=200_000.0, ahv_heading_deg=90.0,
    )
    h_jump, _ = _signed_force_2d(att)
    assert abs(h_jump) < 1e-3


# ─── ahv_in_plane_fraction ─────────────────────────────────────────


def test_ahv_in_plane_fraction_zero_perpendicular():
    att = LineAttachment(
        kind="ahv", position_index=0,
        ahv_bollard_pull=200_000.0, ahv_heading_deg=90.0,
    )
    assert ahv_in_plane_fraction(att) < 1e-6


def test_ahv_in_plane_fraction_one_aligned():
    att = LineAttachment(
        kind="ahv", position_index=0,
        ahv_bollard_pull=200_000.0, ahv_heading_deg=0.0,
    )
    assert math.isclose(ahv_in_plane_fraction(att), 1.0, rel_tol=1e-9)


def test_ahv_in_plane_fraction_buoy_returns_one():
    """Não-AHV retorna 1.0 (totalmente no plano por convenção)."""
    att = LineAttachment(kind="buoy", submerged_force=1.0, position_index=0)
    assert ahv_in_plane_fraction(att) == 1.0


# ─── Solver com AHV ────────────────────────────────────────────────


def test_solver_ahv_horizontal_puro_converge():
    """AHV puxando alinhado com a linha — solver converge."""
    ahv = LineAttachment(
        kind="ahv", position_index=0,
        ahv_bollard_pull=200_000.0, ahv_heading_deg=0.0,
    )
    bc = BoundaryConditions(
        h=300.0, mode=SolutionMode.TENSION, input_value=850_000.0,
    )
    r = solve([_seg(), _seg()], bc, attachments=[ahv])
    assert r.status == ConvergenceStatus.CONVERGED


def test_solver_T_fl_input_eh_T_fl_output():
    """Relação fechada: T_fl input vira T_fl output (catenária convergiu)."""
    ahv = LineAttachment(
        kind="ahv", position_index=0,
        ahv_bollard_pull=200_000.0, ahv_heading_deg=0.0,
    )
    bc = BoundaryConditions(
        h=300.0, mode=SolutionMode.TENSION, input_value=850_000.0,
    )
    r = solve([_seg(), _seg()], bc, attachments=[ahv])
    assert math.isclose(r.fairlead_tension, 850_000.0, rel_tol=1e-3)


def test_solver_ahv_T_anchor_diferente_T_fl_com_horizontal_jump():
    """
    AHV horizontal positivo aumenta H no fairlead → T_fl > T_anchor (caso
    sem AHV, T_anchor < T_fl pelo peso da linha; aqui adiciona-se mais
    diferença pelo H_jump).
    """
    ahv = LineAttachment(
        kind="ahv", position_index=0,
        ahv_bollard_pull=200_000.0, ahv_heading_deg=0.0,
    )
    bc = BoundaryConditions(
        h=300.0, mode=SolutionMode.TENSION, input_value=850_000.0,
    )
    r_with = solve([_seg(), _seg()], bc, attachments=[ahv])
    r_without = solve([_seg(), _seg()], bc, attachments=[])
    # Ambos convergem
    assert r_with.status == ConvergenceStatus.CONVERGED
    assert r_without.status == ConvergenceStatus.CONVERGED
    # AHV deve mudar T_anchor (e geometria)
    assert abs(r_with.anchor_tension - r_without.anchor_tension) > 1000.0


def test_solver_ahv_perpendicular_zero_efeito_horizontal():
    """heading=90° → H_jump=0 → quase mesmo resultado de sem AHV."""
    ahv = LineAttachment(
        kind="ahv", position_index=0,
        ahv_bollard_pull=200_000.0, ahv_heading_deg=90.0,
    )
    bc = BoundaryConditions(
        h=300.0, mode=SolutionMode.TENSION, input_value=850_000.0,
    )
    r_perp = solve([_seg(), _seg()], bc, attachments=[ahv])
    r_no = solve([_seg(), _seg()], bc, attachments=[])
    # Geometria idêntica (rtol pequeno)
    assert math.isclose(
        r_perp.total_horz_distance, r_no.total_horz_distance, rel_tol=1e-3,
    )


# ─── AHV + uplift bloqueado (Q5) ───────────────────────────────────


def test_ahv_uplift_bloqueado_invalid_case():
    """AHV + uplift = INVALID_CASE com mensagem clara."""
    ahv = LineAttachment(
        kind="ahv", position_s_from_anchor=200.0,
        ahv_bollard_pull=200_000.0, ahv_heading_deg=0.0,
    )
    bc = BoundaryConditions(
        h=300.0, mode=SolutionMode.TENSION, input_value=850_000.0,
        endpoint_grounded=False, endpoint_depth=250.0,
    )
    r = solve([_seg()], bc, attachments=[ahv])
    assert r.status == ConvergenceStatus.INVALID_CASE
    assert "ahv" in r.message.lower() or "attachments" in r.message.lower()
    assert "uplift" in r.message.lower() or "endpoint_grounded" in r.message.lower()


# ─── AHV + boia mistos (Q5: SUPORTADO em multi-seg) ────────────────


def test_solver_ahv_mais_buoy_mistos_converge():
    """AHV em junção 0, boia em junção 1 (3 segs) → solver multi-seg
    com saltos mistos (H + V) converge."""
    seg = _seg()
    ahv = LineAttachment(
        kind="ahv", position_index=0,
        ahv_bollard_pull=100_000.0, ahv_heading_deg=0.0,
    )
    buoy = LineAttachment(
        kind="buoy", position_index=1, submerged_force=50_000.0,
    )
    bc = BoundaryConditions(
        h=300.0, mode=SolutionMode.TENSION, input_value=850_000.0,
    )
    r = solve([seg, seg, seg], bc, attachments=[ahv, buoy])
    assert r.status == ConvergenceStatus.CONVERGED


# ─── Múltiplos AHVs (Q4: suportado) ────────────────────────────────


def test_solver_multi_ahv_converge():
    """2 AHVs em junções diferentes → multi-junction com 2 jumps em H."""
    seg = _seg()
    ahv1 = LineAttachment(
        kind="ahv", position_index=0, name="AHV1",
        ahv_bollard_pull=100_000.0, ahv_heading_deg=0.0,
    )
    ahv2 = LineAttachment(
        kind="ahv", position_index=1, name="AHV2",
        ahv_bollard_pull=80_000.0, ahv_heading_deg=0.0,
    )
    bc = BoundaryConditions(
        h=300.0, mode=SolutionMode.TENSION, input_value=850_000.0,
    )
    r = solve([seg, seg, seg], bc, attachments=[ahv1, ahv2])
    assert r.status == ConvergenceStatus.CONVERGED
