"""
Diagnostics Tier D — D025 (fallback F8), D026 (ww raso), D018 update.

Sprint 5 / Commit 45.
"""
from __future__ import annotations

import pytest

from backend.solver.diagnostics import (
    D018_ahv_static_idealization,
    D025_tier_d_fallback_f8,
    D026_work_wire_too_horizontal,
)


# ──────────────────────────────────────────────────────────────────
# D025 — apply tests (helper isolado)
# ──────────────────────────────────────────────────────────────────


def test_d025_dispara_com_reason() -> None:
    diag = D025_tier_d_fallback_f8(
        fallback_reason="catenária do Work Wire não converge",
    )
    assert diag.code == "D025_TIER_D_FALLBACK_F8"
    assert diag.severity == "info"
    assert diag.confidence == "high"
    assert "F8" in diag.title
    assert "catenária" in diag.cause


# ──────────────────────────────────────────────────────────────────
# D026 — apply tests
# ──────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("angle", [1.0, 5.0, 9.0])
def test_d026_dispara_para_angulo_raso(angle: float) -> None:
    diag = D026_work_wire_too_horizontal(angle_deg=angle)
    assert diag.code == "D026_WORK_WIRE_TOO_HORIZONTAL"
    assert diag.severity == "warning"
    assert diag.confidence == "medium"
    assert f"{angle:.1f}" in diag.title


def test_d026_threshold_default_10() -> None:
    """Threshold default é 10°. Mensagem cita o valor."""
    diag = D026_work_wire_too_horizontal(angle_deg=5.0)
    assert "10" in diag.title


# ──────────────────────────────────────────────────────────────────
# D018 update — tier_d_active customiza mensagem
# ──────────────────────────────────────────────────────────────────


def test_d018_com_tier_d_active() -> None:
    diag = D018_ahv_static_idealization(n_ahv=1, tier_d_active=True)
    assert diag.code == "D018_AHV_STATIC_IDEALIZATION"
    assert "Tier D" in diag.title
    assert "operacional" in diag.title.lower()
    assert "snap loads" in diag.cause
    assert "Work Wire" in diag.cause


def test_d018_tier_d_prioridade_sobre_tier_c() -> None:
    """Quando ambos active, Tier D ganha (operacional é mais específico)."""
    diag = D018_ahv_static_idealization(
        n_ahv=1, tier_c_active=True, tier_d_active=True,
    )
    # Tier D message dominante.
    assert "Tier D" in diag.title


def test_d018_padrao_sem_tier_c_ou_d() -> None:
    diag = D018_ahv_static_idealization(n_ahv=2)
    assert "Tier" not in diag.title
    assert "idealização" in diag.title
