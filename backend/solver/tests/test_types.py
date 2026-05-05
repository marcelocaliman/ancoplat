"""
Testes do schema Pydantic `LineSegment` — foco nos campos adicionados na
Fase 1 do plano de profissionalização (`mu_override`, `seabed_friction_cf`,
`ea_source`, `ea_dynamic_beta`).

Princípio: defaults idempotentes preservam comportamento legado. Cases
salvos antes da Fase 1 (sem esses campos no JSON) devem deserializar
limpos com os defaults aplicados, e o resultado do solve com defaults
deve ser idêntico ao comportamento anterior à Fase 1.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.solver.types import LineSegment


# ─── Defaults idempotentes ──────────────────────────────────────────


def test_segment_minimo_aplica_defaults_dos_novos_campos():
    """Um LineSegment mínimo (4 campos obrigatórios) deve receber defaults
    Fase-1 que preservam comportamento legado."""
    seg = LineSegment(length=500.0, w=200.0, EA=7.5e9, MBL=3.0e6)
    assert seg.mu_override is None
    assert seg.seabed_friction_cf is None
    assert seg.ea_source == "qmoor"
    assert seg.ea_dynamic_beta is None


def test_segment_aceita_payload_legado_sem_campos_fase1():
    """JSON legado (sem chaves Fase-1) deserializa limpo com defaults."""
    payload = {
        "length": 450.0,
        "w": 201.1,
        "EA": 3.425e7,
        "MBL": 3.78e6,
        "category": "Wire",
        "line_type": "IWRCEIPS",
    }
    seg = LineSegment.model_validate(payload)
    assert seg.mu_override is None
    assert seg.seabed_friction_cf is None
    assert seg.ea_source == "qmoor"
    assert seg.ea_dynamic_beta is None


# ─── Aceita valores válidos ────────────────────────────────────────


def test_segment_aceita_mu_override_valido():
    seg = LineSegment(length=500.0, w=200.0, EA=7.5e9, MBL=3.0e6, mu_override=0.7)
    assert seg.mu_override == 0.7


def test_segment_aceita_seabed_friction_cf_valido():
    seg = LineSegment(
        length=500.0, w=200.0, EA=7.5e9, MBL=3.0e6,
        seabed_friction_cf=1.0,
    )
    assert seg.seabed_friction_cf == 1.0


def test_segment_aceita_ea_source_gmoor():
    seg = LineSegment(
        length=500.0, w=200.0, EA=7.5e9, MBL=3.0e6, ea_source="gmoor",
    )
    assert seg.ea_source == "gmoor"


def test_segment_aceita_ea_dynamic_beta_reservado():
    """Campo reservado para Fase 4+. Aceita valor positivo, mas solver
    em v1.0 vai ignorar (modelo simplificado a α constante)."""
    seg = LineSegment(
        length=500.0, w=200.0, EA=7.5e9, MBL=3.0e6,
        ea_source="gmoor", ea_dynamic_beta=1500.0,
    )
    assert seg.ea_dynamic_beta == 1500.0


def test_segment_aceita_mu_zero():
    """μ=0 (sem atrito) é valor válido — boundary do range."""
    seg = LineSegment(
        length=500.0, w=200.0, EA=7.5e9, MBL=3.0e6, mu_override=0.0,
    )
    assert seg.mu_override == 0.0


# ─── Rejeita valores inválidos ─────────────────────────────────────


def test_segment_rejeita_mu_override_negativo():
    with pytest.raises(ValidationError):
        LineSegment(
            length=500.0, w=200.0, EA=7.5e9, MBL=3.0e6, mu_override=-0.1,
        )


def test_segment_rejeita_seabed_friction_cf_negativo():
    with pytest.raises(ValidationError):
        LineSegment(
            length=500.0, w=200.0, EA=7.5e9, MBL=3.0e6,
            seabed_friction_cf=-0.5,
        )


def test_segment_rejeita_ea_dynamic_beta_negativo():
    with pytest.raises(ValidationError):
        LineSegment(
            length=500.0, w=200.0, EA=7.5e9, MBL=3.0e6,
            ea_dynamic_beta=-100.0,
        )


def test_segment_rejeita_ea_source_invalido():
    with pytest.raises(ValidationError):
        LineSegment(
            length=500.0, w=200.0, EA=7.5e9, MBL=3.0e6, ea_source="bogus",
        )


# ─── Frozen permanece ───────────────────────────────────────────────


def test_segment_continua_frozen():
    """LineSegment é frozen (model_config). Mutação direta levanta TypeError."""
    seg = LineSegment(length=500.0, w=200.0, EA=7.5e9, MBL=3.0e6)
    with pytest.raises((ValidationError, TypeError)):
        seg.ea_source = "gmoor"  # type: ignore[misc]


# ─── BoundaryConditions — campos cosméticos da Fase 2 ───────────────


def test_boundary_minimal_aplica_defaults_offset_zero():
    """BoundaryConditions mínimo recebe defaults Fase-2 zerados."""
    from backend.solver.types import BoundaryConditions, SolutionMode
    bc = BoundaryConditions(h=300.0, mode=SolutionMode.TENSION, input_value=500_000)
    assert bc.startpoint_offset_horz == 0.0
    assert bc.startpoint_offset_vert == 0.0


def test_boundary_aceita_offset_cosmetico_positivo_e_negativo():
    """Offset é apenas visual — sem range físico restrito."""
    from backend.solver.types import BoundaryConditions, SolutionMode
    bc = BoundaryConditions(
        h=300.0, mode=SolutionMode.TENSION, input_value=500_000,
        startpoint_offset_horz=15.5,
        startpoint_offset_vert=-3.2,  # negativo aceito (deck abaixo da água?)
    )
    assert bc.startpoint_offset_horz == 15.5
    assert bc.startpoint_offset_vert == -3.2


def test_boundary_payload_legacy_sem_offset_aceito():
    """Payload pré-Fase-2 (sem startpoint_offset_*) deserializa com defaults."""
    from backend.solver.types import BoundaryConditions
    payload = {
        "h": 300.0, "mode": "Tension", "input_value": 500_000,
        "startpoint_depth": 0.0, "endpoint_grounded": True,
    }
    bc = BoundaryConditions.model_validate(payload)
    assert bc.startpoint_offset_horz == 0.0
    assert bc.startpoint_offset_vert == 0.0
