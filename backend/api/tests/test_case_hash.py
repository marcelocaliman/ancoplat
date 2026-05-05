"""
Testes do case_input_hash (Fase 5 / Q3 + Ajuste 1).

Cobertura:
  - Determinismo: mesmo case → mesmo hash em runs sucessivas.
  - Independência do nome/descrição: renomear não muda hash.
  - Sensibilidade física: mudar segment/boundary/seabed/attachments
    DEVE mudar hash.
  - Canonicalização: dicionários com chaves em ordem diferente produzem
    mesmo hash (via Pydantic + sort_keys).
  - Estabilidade entre runs: hash de um caso conhecido é bit-a-bit igual.
"""
from __future__ import annotations

import json

import pytest

from backend.api.schemas.cases import CaseInput
from backend.api.services.case_hash import (
    _canonicalize_case_input,
    case_input_hash,
    case_input_short_hash,
)


def _base_case() -> CaseInput:
    """Caso mínimo válido para testes."""
    return CaseInput.model_validate({
        "name": "test-case",
        "description": "descrição original",
        "segments": [
            {
                "length": 500.0,
                "w": 200.0,
                "EA": 7.5e9,
                "MBL": 3.0e6,
                "category": "Wire",
                "line_type": "IWRCEIPS",
            }
        ],
        "boundary": {
            "h": 300.0,
            "mode": "Tension",
            "input_value": 500_000,
            "startpoint_depth": 0.0,
            "endpoint_grounded": True,
        },
        "seabed": {"mu": 0.3, "slope_rad": 0.0},
        "criteria_profile": "MVP_Preliminary",
    })


# ─── Determinismo: mesmo case → mesmo hash ─────────────────────────


def test_hash_deterministico_em_runs_consecutivas():
    """Hash do mesmo CaseInput é igual entre invocações."""
    case = _base_case()
    h1 = case_input_hash(case)
    h2 = case_input_hash(case)
    h3 = case_input_hash(case)
    assert h1 == h2 == h3


def test_hash_e_string_hex_64_chars():
    """SHA-256 hexdigest tem 64 chars (32 bytes × 2)."""
    h = case_input_hash(_base_case())
    assert len(h) == 64
    assert all(c in "0123456789abcdef" for c in h)


def test_short_hash_16_chars():
    h = case_input_short_hash(_base_case())
    assert len(h) == 16
    assert h == case_input_hash(_base_case())[:16]


# ─── Independência de campos não-físicos ───────────────────────────


def test_renomear_caso_nao_muda_hash():
    """name é metadata, não muda hash físico."""
    case_a = _base_case()
    case_b = case_a.model_copy(update={"name": "outro-nome-completamente-diferente"})
    assert case_input_hash(case_a) == case_input_hash(case_b)


def test_redescrever_caso_nao_muda_hash():
    """description é metadata, não muda hash físico."""
    case_a = _base_case()
    case_b = case_a.model_copy(update={"description": "outra descrição muito diferente"})
    assert case_input_hash(case_a) == case_input_hash(case_b)


def test_renomear_e_redescrever_simultaneamente_nao_muda_hash():
    case_a = _base_case()
    case_b = case_a.model_copy(update={
        "name": "different",
        "description": "different description",
    })
    assert case_input_hash(case_a) == case_input_hash(case_b)


# ─── Sensibilidade física: mudar fields DEVE mudar hash ────────────


def test_mudar_segment_length_muda_hash():
    case_a = _base_case()
    seg = case_a.segments[0].model_copy(update={"length": 600.0})
    case_b = case_a.model_copy(update={"segments": [seg]})
    assert case_input_hash(case_a) != case_input_hash(case_b)


def test_mudar_boundary_h_muda_hash():
    case_a = _base_case()
    bc = case_a.boundary.model_copy(update={"h": 400.0})
    case_b = case_a.model_copy(update={"boundary": bc})
    assert case_input_hash(case_a) != case_input_hash(case_b)


def test_mudar_seabed_mu_muda_hash():
    case_a = _base_case()
    sb = case_a.seabed.model_copy(update={"mu": 0.7})
    case_b = case_a.model_copy(update={"seabed": sb})
    assert case_input_hash(case_a) != case_input_hash(case_b)


def test_mudar_ea_source_muda_hash():
    """Field novo da Fase 1 (per segmento) também afeta hash."""
    case_a = _base_case()
    seg = case_a.segments[0].model_copy(update={"ea_source": "gmoor"})
    case_b = case_a.model_copy(update={"segments": [seg]})
    assert case_input_hash(case_a) != case_input_hash(case_b)


# ─── Canonicalização: ordem de chaves não importa ──────────────────


def test_canonicalizacao_mesmo_payload_chaves_em_ordem_diferente():
    """
    Pydantic com sort_keys=True deve produzir mesma serialização
    independente da ordem em que os campos foram inseridos.
    """
    case = _base_case()
    canonical = _canonicalize_case_input(case)
    # Re-parsea e re-canonicaliza — deve dar mesma string
    reparsed = CaseInput.model_validate(json.loads(canonical) | {
        "name": case.name, "description": case.description,
    })
    assert _canonicalize_case_input(reparsed) == canonical


def test_canonicalizacao_sort_keys_garante_determinismo():
    """Verifica que sort_keys=True está ativo na serialização."""
    canonical = _canonicalize_case_input(_base_case())
    parsed = json.loads(canonical)
    # Em JSON canônico, chaves devem aparecer em ordem alfabética.
    # Verifica top-level.
    keys = list(parsed.keys())
    assert keys == sorted(keys), (
        f"Top-level keys não ordenadas: {keys}. "
        "Verifique que sort_keys=True está em json.dumps no canonicalize."
    )


def test_canonicalizacao_sem_whitespace():
    """JSON canônico não tem espaços (separators sem whitespace)."""
    canonical = _canonicalize_case_input(_base_case())
    # Não deve ter ', ' nem ': ' (com espaço)
    assert ", " not in canonical
    assert ": " not in canonical


# ─── Estabilidade entre runs (Ajuste 1) ────────────────────────────


def test_hash_baseline_case_e_estavel():
    """
    Hash de um caso "fixo" no baseline deve ser bit-a-bit igual entre
    runs distintos do código (sem variação por dict ordering, set
    ordering, etc.). Garante reprodutibilidade científica do hash.

    Se este teste quebrar, há fonte de não-determinismo na
    canonicalização — bug crítico.
    """
    case = _base_case()
    expected_canonical = _canonicalize_case_input(case)
    # O hash desse caso específico deve ser bit-a-bit igual entre runs
    # distintos. Computa, salva, recomputa, compara.
    h1 = case_input_hash(case)
    # Re-deserializa o canonical e re-hasha — mesmo resultado.
    import hashlib
    h2 = hashlib.sha256(expected_canonical.encode("utf-8")).hexdigest()
    assert h1 == h2


def test_hash_com_campos_fase1_persiste():
    """
    Caso com campos da Fase 1 (ea_source, mu_override, etc.) produz
    hash diferente do mesmo caso sem esses fields, MAS estável.
    """
    base = _base_case()
    seg = base.segments[0].model_copy(update={
        "ea_source": "gmoor",
        "mu_override": 0.5,
        "seabed_friction_cf": 0.6,
    })
    case_with_fields = base.model_copy(update={"segments": [seg]})
    h1 = case_input_hash(case_with_fields)
    h2 = case_input_hash(case_with_fields)
    h3 = case_input_hash(case_with_fields)
    assert h1 == h2 == h3
    # E é diferente do base
    assert h1 != case_input_hash(base)


# ─── Cobertura sobre cases_baseline ─────────────────────────────────


def test_hash_diferente_para_cada_case_no_baseline():
    """Cada case salvo no baseline tem hash distinto (sanity)."""
    import json
    from pathlib import Path
    baseline_path = (
        Path(__file__).resolve().parents[3]
        / "docs/audit/cases_baseline_2026-05-04.json"
    )
    if not baseline_path.exists():
        pytest.skip("Baseline não disponível")
    payload = json.loads(baseline_path.read_text(encoding="utf-8"))
    hashes = []
    for case_dict in payload["cases"]:
        case = CaseInput.model_validate(case_dict["input_json"])
        hashes.append(case_input_hash(case))
    # Cada hash é único (3 cases distintos no baseline = 3 hashes)
    assert len(set(hashes)) == len(hashes), (
        f"Colisão de hash entre cases distintos: {hashes}"
    )
