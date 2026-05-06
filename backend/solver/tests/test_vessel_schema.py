"""
Testes do schema `Vessel` e do campo `CaseInput.vessel` (Sprint 1 / v1.1.0).

Vessel é META-DADO PURO — solver não consome. Os testes garantem:

  - `name` é obrigatório; demais campos opcionais.
  - Campos numéricos (displacement, loa, breadth, draft) rejeitam ≤ 0.
  - heading_deg restrito ao range [0, 360).
  - Round-trip preserva todos os campos.
  - CaseInput aceita `vessel` opcional (default=None).
  - Solver IGNORA Vessel: caso com e sem Vessel produz resultado idêntico.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.solver.types import Vessel


def _vessel_full() -> Vessel:
    return Vessel(
        name="P-77",
        vessel_type="Semisubmersible",
        displacement=4.5e7,  # 45 000 t em kg
        loa=120.0,
        breadth=80.0,
        draft=22.0,
        heading_deg=45.0,
        operator="Petrobras",
    )


# ──────────────────────────────────────────────────────────────────
# Vessel — campos obrigatórios e validação
# ──────────────────────────────────────────────────────────────────


def test_vessel_minimo_so_nome() -> None:
    v = Vessel(name="P-77")
    assert v.name == "P-77"
    assert v.vessel_type is None
    assert v.displacement is None


def test_vessel_completo_round_trip() -> None:
    v = _vessel_full()
    payload = v.model_dump()
    v2 = Vessel.model_validate(payload)
    assert v2 == v


def test_vessel_sem_nome_invalido() -> None:
    with pytest.raises(ValidationError):
        Vessel()  # type: ignore[call-arg]


def test_vessel_nome_vazio_invalido() -> None:
    with pytest.raises(ValidationError):
        Vessel(name="")


def test_vessel_nome_muito_longo_invalido() -> None:
    with pytest.raises(ValidationError):
        Vessel(name="x" * 121)


@pytest.mark.parametrize("field", ["displacement", "loa", "breadth", "draft"])
def test_vessel_campos_numericos_rejeitam_zero(field: str) -> None:
    base = dict(name="P-77")
    base[field] = 0.0
    with pytest.raises(ValidationError):
        Vessel(**base)  # type: ignore[arg-type]


@pytest.mark.parametrize("field", ["displacement", "loa", "breadth", "draft"])
def test_vessel_campos_numericos_rejeitam_negativo(field: str) -> None:
    base = dict(name="P-77")
    base[field] = -1.0
    with pytest.raises(ValidationError):
        Vessel(**base)  # type: ignore[arg-type]


@pytest.mark.parametrize("heading", [-1.0, 360.0, 720.0])
def test_vessel_heading_fora_de_range_invalido(heading: float) -> None:
    with pytest.raises(ValidationError):
        Vessel(name="P-77", heading_deg=heading)


@pytest.mark.parametrize("heading", [0.0, 90.0, 180.0, 359.999])
def test_vessel_heading_no_range_aceito(heading: float) -> None:
    v = Vessel(name="P-77", heading_deg=heading)
    assert v.heading_deg == heading


def test_vessel_operator_max_120() -> None:
    with pytest.raises(ValidationError):
        Vessel(name="P-77", operator="x" * 121)


# ──────────────────────────────────────────────────────────────────
# CaseInput.vessel — opcional, round-trip via JSON
# ──────────────────────────────────────────────────────────────────


def test_caseinput_aceita_vessel_opcional() -> None:
    """`vessel` é Optional — caso sem ela continua válido."""
    from backend.api.schemas.cases import CaseInput
    from backend.api.tests._fixtures import BC01_LIKE_INPUT

    ci = CaseInput.model_validate(BC01_LIKE_INPUT)
    assert ci.vessel is None


def test_caseinput_round_trip_com_vessel() -> None:
    from backend.api.schemas.cases import CaseInput
    from backend.api.tests._fixtures import BC01_LIKE_INPUT

    payload = dict(BC01_LIKE_INPUT)
    payload["vessel"] = {
        "name": "P-77",
        "vessel_type": "Semisubmersible",
        "displacement": 4.5e7,
        "loa": 120.0,
        "heading_deg": 45.0,
    }
    ci = CaseInput.model_validate(payload)
    assert ci.vessel is not None
    assert ci.vessel.name == "P-77"
    assert ci.vessel.heading_deg == 45.0
    # Round-trip dump → load preserva
    ci2 = CaseInput.model_validate(ci.model_dump())
    assert ci2.vessel == ci.vessel


# ──────────────────────────────────────────────────────────────────
# Solver IGNORA Vessel — invariante crítico
# ──────────────────────────────────────────────────────────────────


def test_solver_ignora_vessel() -> None:
    """Caso com Vessel deve produzir resultado bit-idêntico ao sem Vessel.

    Esta é a garantia de que o campo é meta-dado puro — qualquer mudança
    no solver que vaze Vessel para o cálculo quebra este teste.
    """
    from copy import deepcopy

    from backend.api.schemas.cases import CaseInput
    from backend.api.tests._fixtures import BC01_LIKE_INPUT
    from backend.solver.solver import solve

    payload_sem = deepcopy(BC01_LIKE_INPUT)
    payload_com = deepcopy(BC01_LIKE_INPUT)
    payload_com["vessel"] = {
        "name": "P-77",
        "vessel_type": "Semisubmersible",
        "displacement": 4.5e7,
        "loa": 120.0,
        "draft": 22.0,
        "heading_deg": 45.0,
    }

    ci_sem = CaseInput.model_validate(payload_sem)
    ci_com = CaseInput.model_validate(payload_com)

    res_sem = solve(
        line_segments=ci_sem.segments,
        boundary=ci_sem.boundary,
        seabed=ci_sem.seabed,
        criteria_profile=ci_sem.criteria_profile,
    )
    res_com = solve(
        line_segments=ci_com.segments,
        boundary=ci_com.boundary,
        seabed=ci_com.seabed,
        criteria_profile=ci_com.criteria_profile,
    )

    assert res_sem.fairlead_tension == res_com.fairlead_tension
    assert res_sem.anchor_tension == res_com.anchor_tension
    assert res_sem.total_horz_distance == res_com.total_horz_distance
