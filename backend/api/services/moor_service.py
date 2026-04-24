"""
Parser e exporter do formato `.moor` (F2.6).

Decisão Q2 da auditoria pré-F2: `.moor` é **JSON próprio QMoor-Web**
compatível com o schema da Seção 5.2 do MVP v2 PDF (o formato binário
original do QMoor 0.8.5 estava em `.pyd` e é inacessível).

Campos quantitativos do `.moor` JSON podem vir como:
  - string com unidade: "450 ft", "13.78 lbf/ft", "500 m"
  - número sem unidade: assume-se a unidade padrão do `unitSystem`

Na exportação, valores SI internos são convertidos de volta para
imperial/metric conforme o `unitSystem` declarado.
"""
from __future__ import annotations

from typing import Any, Optional

from pint import UnitRegistry

from backend.api.db.models import CaseRecord
from backend.api.schemas.cases import CaseInput
from backend.solver.types import (
    BoundaryConditions,
    CriteriaProfile,
    LineCategory,
    LineSegment,
    SeabedConfig,
    SolutionMode,
)


_ureg = UnitRegistry()

# Unidades padrão por unit system (usadas quando o campo vem como número puro).
_DEFAULT_UNITS = {
    "imperial": {
        "length": "ft",
        "weight_per_length": "lbf/ft",
        "force": "kip",
        "modulus": "kip/inch**2",
        "diameter": "in",
    },
    "metric": {
        "length": "m",
        "weight_per_length": "N/m",
        "force": "N",
        "modulus": "Pa",
        "diameter": "m",
    },
}


class MoorFormatError(Exception):
    """Falha ao parsear ou validar um payload .moor."""


def _parse_quantity(
    value: Any, dimension: str, unit_system: str
) -> float:
    """
    Converte `value` para SI a partir de string 'X unit' ou número puro.

    `dimension` ∈ {length, weight_per_length, force, modulus, diameter}.
    Se `value` é str, usa Pint direto. Se é número, aplica a unidade
    default do unit_system.
    """
    target_si = {
        "length": "m",
        "weight_per_length": "N/m",
        "force": "N",
        "modulus": "Pa",
        "diameter": "m",
    }[dimension]

    if isinstance(value, str):
        try:
            q = _ureg(value)
        except Exception as exc:  # noqa: BLE001
            raise MoorFormatError(
                f"Valor '{value}' não é reconhecido como quantidade (dimension={dimension})"
            ) from exc
        try:
            return float(q.to(target_si).magnitude)
        except Exception as exc:  # noqa: BLE001
            raise MoorFormatError(
                f"Valor '{value}' não é compatível com dimensão {dimension}"
            ) from exc
    if isinstance(value, (int, float)):
        default_unit = _DEFAULT_UNITS[unit_system][dimension]
        q = value * _ureg(default_unit)
        return float(q.to(target_si).magnitude)
    raise MoorFormatError(
        f"Tipo inesperado para quantidade: {type(value).__name__}"
    )


def _format_quantity(
    value_si: float, dimension: str, unit_system: str
) -> str:
    """Formata valor SI como string com unidade do unit_system."""
    target = _DEFAULT_UNITS[unit_system][dimension]
    target_si = {
        "length": "m",
        "weight_per_length": "N/m",
        "force": "N",
        "modulus": "Pa",
        "diameter": "m",
    }[dimension]
    q = (value_si * _ureg(target_si)).to(target)
    # Precisão 6 casas decimais é suficiente para o MVP.
    return f"{q.magnitude:.6g} {target}"


# ==============================================================================
# Parser: .moor JSON → CaseInput
# ==============================================================================


def parse_moor_payload(payload: dict[str, Any]) -> CaseInput:
    """
    Converte um payload `.moor` (Seção 5.2 do MVP v2 PDF) em CaseInput.

    Campos esperados:
      name, unitSystem, mooringLine.{name, segments, boundary, solution}
      mooringLine.segments[].lineProps.{lineType, diameter, breakStrength,
          dryWeight, wetWeight, modulus, seabedFrictionCF, category?}
      boundary.{startpointDepth, endpointDepth, endpointGrounded, horzDistance?}
      solution.{inputParam, fairleadTension | rangeToAnchor}
    """
    try:
        unit_system = payload.get("unitSystem", "metric")
        if unit_system not in ("imperial", "metric"):
            raise MoorFormatError(f"unitSystem inválido: {unit_system}")

        name = payload.get("name") or payload.get("mooringLine", {}).get("name")
        if not name:
            raise MoorFormatError("campo 'name' obrigatório")

        ml = payload.get("mooringLine") or {}
        segments_raw = ml.get("segments") or []
        if len(segments_raw) != 1:
            raise MoorFormatError(
                f"v1 espera exatamente 1 segmento; recebidos {len(segments_raw)}"
            )
        seg_raw = segments_raw[0]
        props = seg_raw.get("lineProps") or {}

        segment = LineSegment(
            length=_parse_quantity(seg_raw["length"], "length", unit_system),
            w=_parse_quantity(props["wetWeight"], "weight_per_length", unit_system),
            EA=_parse_ea(props, unit_system),
            MBL=_parse_quantity(props["breakStrength"], "force", unit_system),
            category=_parse_category(seg_raw.get("category") or props.get("category")),
            line_type=props.get("lineType"),
        )

        boundary_raw = ml.get("boundary") or {}
        h = _parse_quantity(
            boundary_raw.get("endpointDepth") or boundary_raw.get("startpointDepth") or 0,
            "length",
            unit_system,
        )
        if h <= 0:
            raise MoorFormatError("endpointDepth (ou startpointDepth) deve ser > 0")

        solution = ml.get("solution") or {}
        mode = solution.get("inputParam") or "Tension"
        if mode == "Tension":
            input_value = _parse_quantity(solution["fairleadTension"], "force", unit_system)
        elif mode == "Range":
            input_value = _parse_quantity(
                solution.get("rangeToAnchor") or boundary_raw.get("horzDistance"),
                "length",
                unit_system,
            )
        else:
            raise MoorFormatError(f"inputParam inválido: {mode}")

        boundary = BoundaryConditions(
            h=h,
            mode=SolutionMode(mode),
            input_value=input_value,
            startpoint_depth=_parse_quantity(
                boundary_raw.get("startpointDepth", 0.0), "length", unit_system,
            ),
            endpoint_grounded=bool(boundary_raw.get("endpointGrounded", True)),
        )

        seabed = SeabedConfig(
            mu=float(props.get("seabedFrictionCF", 0.0)),
        )

        return CaseInput(
            name=name,
            description=payload.get("description"),
            segments=[segment],
            boundary=boundary,
            seabed=seabed,
            criteria_profile=CriteriaProfile(
                payload.get("criteriaProfile") or "MVP_Preliminary"
            ),
        )
    except MoorFormatError:
        raise
    except KeyError as exc:
        raise MoorFormatError(f"campo obrigatório ausente: {exc}") from exc
    except Exception as exc:  # noqa: BLE001
        raise MoorFormatError(f"falha ao parsear .moor: {exc}") from exc


def _parse_ea(props: dict[str, Any], unit_system: str) -> float:
    """`modulus` OU `qmoorEA` — converge para EA em N."""
    if "qmoorEA" in props:
        return _parse_quantity(props["qmoorEA"], "force", unit_system)
    if "modulus" in props and "diameter" in props:
        # EA = modulus × área; mas na prática o catálogo guarda qmoor_ea diretamente.
        # Para .moor sem qmoorEA, devemos ter modulus e diameter e calcular:
        modulus_pa = _parse_quantity(props["modulus"], "modulus", unit_system)
        diameter_m = _parse_quantity(props["diameter"], "diameter", unit_system)
        area_m2 = 3.14159265358979 * (diameter_m / 2.0) ** 2
        return modulus_pa * area_m2
    raise MoorFormatError(
        "lineProps deve conter 'qmoorEA' ou ('modulus' e 'diameter')"
    )


def _parse_category(value: Optional[str]) -> Optional[LineCategory]:
    if value is None:
        return None
    valid = ("Wire", "StuddedChain", "StudlessChain", "Polyester")
    if value not in valid:
        raise MoorFormatError(
            f"category '{value}' inválida; esperado um de {valid}"
        )
    return value  # type: ignore[return-value]


# ==============================================================================
# Exporter: CaseRecord → .moor JSON
# ==============================================================================


def export_case_as_moor(
    record: CaseRecord, unit_system: str = "metric"
) -> dict[str, Any]:
    """
    Serializa um caso no formato .moor (Seção 5.2 do MVP v2 PDF),
    convertendo valores SI para o unit_system solicitado.
    """
    if unit_system not in ("imperial", "metric"):
        raise MoorFormatError(f"unitSystem inválido: {unit_system}")

    case_input = CaseInput.model_validate_json(record.input_json)
    segment = case_input.segments[0]

    solution: dict[str, Any] = {"inputParam": case_input.boundary.mode.value}
    if case_input.boundary.mode == SolutionMode.TENSION:
        solution["fairleadTension"] = _format_quantity(
            case_input.boundary.input_value, "force", unit_system
        )
    else:
        solution["rangeToAnchor"] = _format_quantity(
            case_input.boundary.input_value, "length", unit_system
        )

    return {
        "name": case_input.name,
        "description": case_input.description,
        "unitSystem": unit_system,
        "criteriaProfile": case_input.criteria_profile.value,
        "mooringLine": {
            "name": case_input.name,
            "rigidityType": "qmoor",
            "segments": [
                {
                    "category": segment.category,
                    "length": _format_quantity(segment.length, "length", unit_system),
                    "lineProps": {
                        "lineType": segment.line_type,
                        "wetWeight": _format_quantity(
                            segment.w, "weight_per_length", unit_system
                        ),
                        "breakStrength": _format_quantity(
                            segment.MBL, "force", unit_system
                        ),
                        "qmoorEA": _format_quantity(segment.EA, "force", unit_system),
                        "seabedFrictionCF": case_input.seabed.mu,
                    },
                }
            ],
            "boundary": {
                "startpointDepth": _format_quantity(
                    case_input.boundary.startpoint_depth, "length", unit_system
                ),
                "endpointDepth": _format_quantity(
                    case_input.boundary.h, "length", unit_system
                ),
                "endpointGrounded": case_input.boundary.endpoint_grounded,
            },
            "solution": solution,
        },
    }


__all__ = [
    "MoorFormatError",
    "export_case_as_moor",
    "parse_moor_payload",
]
