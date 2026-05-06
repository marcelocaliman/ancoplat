"""
Diagnostics Tier C — D022 (Work Wire próximo MBL), D024 (fallback
Sprint 2), D018 update com tier_c_active.

Sprint 4 / Commit 37.
"""
from __future__ import annotations

import pytest

from backend.solver.diagnostics import (
    D018_ahv_static_idealization,
    D022_work_wire_near_mbl,
    D024_tier_c_fallback_sprint2,
)
from backend.solver.types import (
    AHVInstall,
    BoundaryConditions,
    LineSegment,
    SeabedConfig,
    SolutionMode,
    SolverConfig,
    WorkWireSpec,
)
from backend.solver.solver import solve as solver_solve


# ──────────────────────────────────────────────────────────────────
# D022 — apply tests (helper isolado)
# ──────────────────────────────────────────────────────────────────


def test_d022_dispara_quando_bollard_acima_de_90pct_mbl() -> None:
    diag = D022_work_wire_near_mbl(
        bollard_pull=5_900_000.0, work_wire_mbl=6_500_000.0,
    )
    assert diag.code == "D022_WORK_WIRE_NEAR_MBL"
    assert diag.severity == "warning"
    assert diag.confidence == "high"
    # 90.7% deve aparecer no título.
    assert "91" in diag.title or "90" in diag.title


def test_d022_threshold_default_e_90pct() -> None:
    # Em 80% não deveria ser disparado pelo solver (mas helper sempre
    # constrói; o solver decide se chamar). Esta é apenas validação
    # da estrutura do diagnóstico.
    diag = D022_work_wire_near_mbl(
        bollard_pull=5_200_000.0, work_wire_mbl=6_500_000.0,
    )
    assert "80" in diag.title


# ──────────────────────────────────────────────────────────────────
# D024 — apply tests (helper isolado)
# ──────────────────────────────────────────────────────────────────


def test_d024_dispara_com_lay_pct() -> None:
    diag = D024_tier_c_fallback_sprint2(
        fallback_reason="mooring com touchdown 92% ≥ 90%",
        lay_pct=0.92,
    )
    assert diag.code == "D024_TIER_C_FALLBACK_SPRINT2"
    assert diag.severity == "info"
    assert diag.confidence == "high"
    assert "92" in diag.title


def test_d024_dispara_sem_lay_pct() -> None:
    diag = D024_tier_c_fallback_sprint2(
        fallback_reason="fsolve não convergiu",
    )
    assert diag.severity == "info"
    # Sem lay_pct, título não deve crashar.
    assert "Sprint 2" in diag.title


# ──────────────────────────────────────────────────────────────────
# D018 update — tier_c_active customiza mensagem
# ──────────────────────────────────────────────────────────────────


def test_d018_padrao_sem_tier_c() -> None:
    diag = D018_ahv_static_idealization(n_ahv=1)
    assert diag.code == "D018_AHV_STATIC_IDEALIZATION"
    assert "idealização" in diag.title
    assert "Work Wire" not in diag.title


def test_d018_com_tier_c_active() -> None:
    diag = D018_ahv_static_idealization(n_ahv=0, tier_c_active=True)
    assert diag.code == "D018_AHV_STATIC_IDEALIZATION"
    assert "Tier C" in diag.title
    assert "Work Wire" in diag.title
    # Mensagem cita explicitamente os limites Sprint 4.
    assert "snap loads" in diag.cause
    assert "hidrodinâmica" in diag.cause


# ──────────────────────────────────────────────────────────────────
# Integração — D018 dispara via solve() quando work_wire está set
# ──────────────────────────────────────────────────────────────────


def _build_tier_c_case(
    bollard_pull: float = 50_000.0,
    work_wire_mbl: float = 6.5e6,
):
    seg = LineSegment(
        length=1500.0, w=170.0, EA=5.5e8, MBL=6.5e6,
        category="Wire",
    )
    ww = WorkWireSpec(
        length=200.0, EA=5.5e8, w=170.0, MBL=work_wire_mbl,
    )
    ahv = AHVInstall(
        bollard_pull=bollard_pull,
        deck_level_above_swl=8.0,
        target_horz_distance=1300.0,
        work_wire=ww,
    )
    bc = BoundaryConditions(
        h=200.0, mode=SolutionMode.TENSION, input_value=bollard_pull,
        startpoint_depth=0.0, endpoint_grounded=True, startpoint_type="ahv",
        ahv_install=ahv,
    )
    return [seg], bc


def test_d018_tier_c_aparece_em_solve_com_work_wire() -> None:
    """Tier C ativo → D018 com mensagem customizada."""
    segs, bc = _build_tier_c_case()
    r = solver_solve(
        line_segments=segs, boundary=bc,
        seabed=SeabedConfig(), config=SolverConfig(),
    )
    diag_codes = {d.get("code") for d in (r.diagnostics or [])}
    assert "D018_AHV_STATIC_IDEALIZATION" in diag_codes
    # Pega a entrada e verifica que o título cita Tier C.
    d018 = next(
        d for d in r.diagnostics
        if d.get("code") == "D018_AHV_STATIC_IDEALIZATION"
    )
    assert "Tier C" in d018["title"] or "Work Wire" in d018["title"]


def test_d024_aparece_quando_fallback_sprint2_ativa() -> None:
    """
    Cenário típico de instalação (mooring totalmente apoiado) ativa
    fallback automático e D024 fica visível para o engenheiro.
    """
    segs, bc = _build_tier_c_case()
    r = solver_solve(
        line_segments=segs, boundary=bc,
        seabed=SeabedConfig(), config=SolverConfig(),
    )
    diag_codes = {d.get("code") for d in (r.diagnostics or [])}
    # Cenário com bollard 50 kN e h=200m com mooring wire fica frouxo
    # → fallback ativa.
    assert "D024_TIER_C_FALLBACK_SPRINT2" in diag_codes
