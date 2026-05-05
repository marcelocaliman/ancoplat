"""
Testes do helper centralizado `_resolve_mu_per_seg` (Fase 1 / B3).

Conforme Ajuste 1 do mini-plano da Fase 1: o helper é OBRIGATÓRIO
(não opcional) e precisa ter teste unitário próprio com matriz de
combinações dos 4 níveis de precedência.

Precedência (mais específico → mais geral):

    1. segment.mu_override        — override explícito do usuário
    2. segment.seabed_friction_cf — valor do catálogo (line_type)
    3. seabed.mu                  — valor global do caso
    4. 0.0                        — fallback final

Cada nível só é consultado se o anterior for None.
"""
from __future__ import annotations

import pytest

from backend.solver.solver import _resolve_mu_per_seg
from backend.solver.types import LineSegment, SeabedConfig


def _seg(**kw) -> LineSegment:
    """Factory de segmento mínimo + overrides nos campos μ-relevantes."""
    base = dict(length=500.0, w=200.0, EA=7.5e9, MBL=3.0e6)
    base.update(kw)
    return LineSegment(**base)


# ─── Matriz de precedência: cada nível ativo isoladamente ───────────


def test_nivel_1_mu_override_vence_tudo():
    seg = _seg(mu_override=0.7, seabed_friction_cf=0.3)
    seabed = SeabedConfig(mu=0.5)
    out = _resolve_mu_per_seg([seg], seabed)
    assert out == [0.7]


def test_nivel_2_seabed_friction_cf_quando_sem_override():
    seg = _seg(mu_override=None, seabed_friction_cf=0.6)
    seabed = SeabedConfig(mu=0.3)
    out = _resolve_mu_per_seg([seg], seabed)
    assert out == [0.6]


def test_nivel_3_seabed_mu_quando_sem_override_nem_catalogo():
    seg = _seg(mu_override=None, seabed_friction_cf=None)
    seabed = SeabedConfig(mu=0.4)
    out = _resolve_mu_per_seg([seg], seabed)
    assert out == [0.4]


def test_nivel_4_zero_quando_tudo_None_e_seabed_default():
    """seabed.mu default é 0.0 — então o resultado também é 0.0."""
    seg = _seg(mu_override=None, seabed_friction_cf=None)
    seabed = SeabedConfig()  # default mu=0.0
    out = _resolve_mu_per_seg([seg], seabed)
    assert out == [0.0]


# ─── Matriz com múltiplos segmentos ─────────────────────────────────


def test_per_segmento_resolve_independente():
    """Cada segmento resolve sua precedência separadamente — chain mu=1.0,
    wire mu=0.3 (catálogo), conector sem catálogo cai no global mu=0.5."""
    chain = _seg(mu_override=None, seabed_friction_cf=1.0, line_type="R4Studless")
    wire = _seg(mu_override=None, seabed_friction_cf=0.3, line_type="IWRCEIPS")
    custom = _seg(mu_override=None, seabed_friction_cf=None)
    seabed = SeabedConfig(mu=0.5)
    out = _resolve_mu_per_seg([chain, wire, custom], seabed)
    assert out == [1.0, 0.3, 0.5]


def test_override_em_um_segmento_nao_afeta_outros():
    """Se usuário fizer override só no chain, wire mantém o catálogo."""
    chain = _seg(mu_override=0.9, seabed_friction_cf=1.0)
    wire = _seg(mu_override=None, seabed_friction_cf=0.3)
    seabed = SeabedConfig(mu=0.5)
    out = _resolve_mu_per_seg([chain, wire], seabed)
    assert out == [0.9, 0.3]


# ─── Combinações onde mu_override=0.0 é DIFERENTE de None ───────────


def test_mu_override_zero_vence_catalogo():
    """μ=0.0 é override válido (sem atrito explícito) e não cai pra fallback."""
    seg = _seg(mu_override=0.0, seabed_friction_cf=1.0)
    seabed = SeabedConfig(mu=0.5)
    out = _resolve_mu_per_seg([seg], seabed)
    assert out == [0.0]


def test_seabed_friction_cf_zero_vence_seabed_global():
    """cf=0.0 do catálogo (caso especial) também vence o global."""
    seg = _seg(mu_override=None, seabed_friction_cf=0.0)
    seabed = SeabedConfig(mu=0.5)
    out = _resolve_mu_per_seg([seg], seabed)
    assert out == [0.0]


# ─── Sanidade: cardinalidade e não-negatividade ─────────────────────


def test_cardinalidade_bate_com_segmentos():
    segs = [_seg() for _ in range(5)]
    seabed = SeabedConfig(mu=0.5)
    out = _resolve_mu_per_seg(segs, seabed)
    assert len(out) == 5


def test_lista_vazia_retorna_vazio():
    out = _resolve_mu_per_seg([], SeabedConfig(mu=0.5))
    assert out == []


def test_todos_valores_nao_negativos():
    """Validador Pydantic já enforça ge=0; helper não modifica os valores."""
    seg = _seg(mu_override=2.5)  # μ alto mas válido
    out = _resolve_mu_per_seg([seg], SeabedConfig(mu=0.0))
    assert all(v >= 0.0 for v in out)


# ─── Documentação executável: cenário do BC-FR-01 ───────────────────


def test_BC_FR_01_cenario_linha_mista():
    """
    Cenário do gate BC-FR-01: linha mista chain (catálogo R5Studless μ=0.6)
    + wire (catálogo IWRCEIPS μ=0.3) + chain (override do usuário μ=1.0).
    seabed.mu=0.0 não deveria interferir já que catálogo cobre.
    """
    chain_studless = _seg(seabed_friction_cf=0.6, line_type="R5Studless")
    wire_eips = _seg(seabed_friction_cf=0.3, line_type="IWRCEIPS")
    chain_overridden = _seg(
        mu_override=1.0, seabed_friction_cf=0.6, line_type="R5Studless",
    )
    seabed = SeabedConfig(mu=0.0)
    out = _resolve_mu_per_seg(
        [chain_studless, wire_eips, chain_overridden], seabed,
    )
    assert out == [0.6, 0.3, 1.0]
