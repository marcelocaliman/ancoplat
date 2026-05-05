"""
Testes de D018 + D019 (Fase 8 / Q6 + Ajuste 1).

D018 (warning, medium) — AHV é idealização:
  - Dispara SEMPRE quando há ≥1 AHV no caso. Não-negociável (decisão
    fechada Fase 8 antecipada). Engenheiro não pode esconder.

D019 (warning, high) — força AHV majoritariamente fora do plano:
  - Dispara quando projeção da força no plano vertical da linha é
    < 30% da magnitude total. Limiar Q3 ajuste 1.

NOTA: integração com solver (D018 disparar automaticamente no facade
quando há AHV no caso) vem no Commit 3 — aqui testamos apenas as
funções dos diagnostics em si.
"""
from __future__ import annotations

import pytest

from backend.solver.diagnostics import (
    D018_ahv_static_idealization,
    D019_ahv_force_mostly_out_of_plane,
)


# ─── D018: AHV idealização ──────────────────────────────────────────


def test_D018_singular_metadata():
    d = D018_ahv_static_idealization(n_ahv=1)
    assert d.code == "D018_AHV_STATIC_IDEALIZATION"
    assert d.severity == "warning"
    assert d.confidence == "medium"
    assert "1 AHV" in d.title
    assert "1 AHVs" not in d.title  # singular


def test_D018_plural_metadata():
    d = D018_ahv_static_idealization(n_ahv=3)
    assert "3 AHVs" in d.title


def test_D018_cause_contains_idealizacao_keyword():
    """Texto da causa deve incluir 'idealização' — palavra-chave do bloqueio
    técnico antecipado em CLAUDE.md."""
    d = D018_ahv_static_idealization(n_ahv=1)
    assert "idealização" in d.cause.lower()


def test_D018_suggestion_cita_dominio_uso_e_nao_substitui():
    """Sugestão precisa cobrir os 2 lados: PARA QUE USAR + PARA QUE NÃO USAR."""
    d = D018_ahv_static_idealization(n_ahv=1)
    s = d.suggestion.lower()
    assert "use para" in s or "usar" in s
    assert "não substitui" in s
    assert "dinâmic" in s  # análise dinâmica


# ─── D019: força fora do plano ──────────────────────────────────────


def test_D019_dispara_em_in_plane_baixo():
    """in_plane_fraction=0.2 (20% < 30%) → D019 dispara."""
    d = D019_ahv_force_mostly_out_of_plane(
        bollard_pull=2_000_000.0,
        in_plane_fraction=0.2,
        heading_deg=80.0,
    )
    assert d.code == "D019_AHV_FORCE_OUT_OF_PLANE"
    assert d.severity == "warning"
    assert d.confidence == "high"
    assert "20.0%" in d.cause


def test_D019_cause_explica_2D_limit():
    """Mensagem deixa claro que AncoPlat é 2D."""
    d = D019_ahv_force_mostly_out_of_plane(
        bollard_pull=1_000_000.0,
        in_plane_fraction=0.1,
        heading_deg=85.0,
    )
    assert "2D" in d.cause


def test_D019_suggestion_orienta_revisao_ou_3D_externa():
    d = D019_ahv_force_mostly_out_of_plane(
        bollard_pull=1_000_000.0,
        in_plane_fraction=0.1,
        heading_deg=85.0,
    )
    s = d.suggestion.lower()
    assert "verifique" in s or "revis" in s
    assert "3D" in d.suggestion or "perpendicular" in s


def test_D019_affected_fields_aponta_heading():
    d = D019_ahv_force_mostly_out_of_plane(
        bollard_pull=1_000_000.0,
        in_plane_fraction=0.2,
        heading_deg=85.0,
    )
    assert any("ahv_heading_deg" in f for f in d.affected_fields)


# ─── Listagem em __all__ ────────────────────────────────────────────


def test_D018_e_D019_exportados():
    """Confirma que __all__ exporta as 2 funções novas."""
    from backend.solver import diagnostics as D
    assert "D018_ahv_static_idealization" in D.__all__
    assert "D019_ahv_force_mostly_out_of_plane" in D.__all__
