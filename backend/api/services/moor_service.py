"""
Parser e exporter do formato `.moor` (F2.6).

Decisão Q2 da auditoria pré-F2: `.moor` é **JSON próprio do AncoPlat**
compatível com o schema da Seção 5.2 do MVP v2 PDF (o formato binário
original do QMoor 0.8.5 estava em `.pyd` e é inacessível).

Campos quantitativos do `.moor` JSON podem vir como:
  - string com unidade: "450 ft", "13.78 lbf/ft", "500 m"
  - número sem unidade: assume-se a unidade padrão do `unitSystem`

Na exportação, valores SI internos são convertidos de volta para
imperial/metric conforme o `unitSystem` declarado.
"""
from __future__ import annotations

import re
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


# Aliases comuns em arquivos .moor que o Pint default não reconhece.
# Ordem importa: aliases mais específicos primeiro.
_UNIT_ALIASES: list[tuple[re.Pattern[str], str]] = [
    # `te` = tonelada-força métrica (convenção QMoor/offshore BR), diferente
    # de `t` ou `tonne` (que são MASSA no Pint). Substituímos antes do
    # parsing para que a dimensão saia como [força].
    (re.compile(r"\bte\b"), "metric_ton_force"),
    (re.compile(r"\btonnef\b"), "metric_ton_force"),
    # `tf` às vezes aparece como tonne-force; protegemos a substituição
    # contra conflito com `T_fl`/`Tf` minúsculo tratando-o só quando isolado.
    (re.compile(r"(?<![A-Za-z_])tf(?![A-Za-z_])"), "metric_ton_force"),
]


def _normalize_unit_string(s: str) -> str:
    """Substitui aliases QMoor-specific por unidades reconhecidas pelo Pint."""
    out = s
    for pattern, replacement in _UNIT_ALIASES:
        out = pattern.sub(replacement, out)
    return out


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
        normalized = _normalize_unit_string(value)
        try:
            q = _ureg(normalized)
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

        # O QMoor 0.8.x emite `mooringLines` (plural, array). Nosso schema
        # interno antigo era `mooringLine` (singular). Aceitamos ambos.
        ml: dict[str, Any] | None = payload.get("mooringLine")
        if ml is None:
            lines = payload.get("mooringLines") or []
            if not isinstance(lines, list) or len(lines) == 0:
                raise MoorFormatError(
                    "Arquivo .moor não contém 'mooringLine' nem 'mooringLines'."
                )
            if len(lines) > 1:
                raise MoorFormatError(
                    f"v1 aceita 1 mooring line por arquivo; recebeu {len(lines)}. "
                    "Importe cada linha separadamente ou aguarde multi-linha em v2."
                )
            ml = lines[0]
        if not isinstance(ml, dict):
            raise MoorFormatError("mooringLine deve ser um objeto.")

        name = payload.get("name") or ml.get("name")
        if not name:
            raise MoorFormatError("campo 'name' obrigatório")

        segments_raw = ml.get("segments") or []
        if not segments_raw:
            raise MoorFormatError("mooringLine.segments está vazio")
        if len(segments_raw) > 10:
            raise MoorFormatError(
                f"Suporte atual é até 10 segmentos por linha; recebidos {len(segments_raw)}."
            )

        # F5.1: parse de cada segmento da lista. Convenção do .moor é a mesma
        # do nosso schema interno — primeiro segmento é o mais próximo da
        # âncora.
        segments: list[LineSegment] = []
        for seg_raw in segments_raw:
            props = seg_raw.get("lineProps") or {}
            diameter_m: Optional[float] = None
            if "diameter" in props and props["diameter"] is not None:
                diameter_m = _parse_quantity(
                    props["diameter"], "diameter", unit_system,
                )
            dry_weight_si: Optional[float] = None
            if "dryWeight" in props and props["dryWeight"] is not None:
                dry_weight_si = _parse_quantity(
                    props["dryWeight"], "weight_per_length", unit_system,
                )
            modulus_pa: Optional[float] = None
            if "modulus" in props and props["modulus"] is not None:
                modulus_pa = _parse_quantity(
                    props["modulus"], "modulus", unit_system,
                )
            segments.append(
                LineSegment(
                    length=_parse_quantity(seg_raw["length"], "length", unit_system),
                    w=_parse_quantity(
                        props["wetWeight"], "weight_per_length", unit_system,
                    ),
                    EA=_parse_ea(props, unit_system),
                    MBL=_parse_quantity(
                        props["breakStrength"], "force", unit_system,
                    ),
                    category=_parse_category(
                        seg_raw.get("category") or props.get("category"),
                    ),
                    line_type=props.get("lineType"),
                    diameter=diameter_m,
                    dry_weight=dry_weight_si,
                    modulus=modulus_pa,
                )
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
        # QMoor 0.8.x grava `inputParam` em minúsculas ("tension"); normalizamos.
        mode_raw = (solution.get("inputParam") or "Tension").strip()
        mode = mode_raw.capitalize()
        if mode == "Tension":
            input_value = _parse_quantity(solution["fairleadTension"], "force", unit_system)
        elif mode == "Range":
            input_value = _parse_quantity(
                solution.get("rangeToAnchor") or boundary_raw.get("horzDistance"),
                "length",
                unit_system,
            )
        else:
            raise MoorFormatError(f"inputParam inválido: {mode_raw}")

        boundary = BoundaryConditions(
            h=h,
            mode=SolutionMode(mode),
            input_value=input_value,
            startpoint_depth=_parse_quantity(
                boundary_raw.get("startpointDepth", 0.0), "length", unit_system,
            ),
            endpoint_grounded=bool(boundary_raw.get("endpointGrounded", True)),
        )

        # μ do seabed: usa o do PRIMEIRO segmento (mais próximo da âncora) —
        # convenção offshore, é ele que toca o fundo. Se ausente em todos,
        # cai para 0.
        first_props = (segments_raw[0].get("lineProps") or {})
        seabed = SeabedConfig(
            mu=float(first_props.get("seabedFrictionCF", 0.0)),
        )

        return CaseInput(
            name=name,
            description=payload.get("description"),
            segments=segments,
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

    solution: dict[str, Any] = {"inputParam": case_input.boundary.mode.value}
    if case_input.boundary.mode == SolutionMode.TENSION:
        solution["fairleadTension"] = _format_quantity(
            case_input.boundary.input_value, "force", unit_system
        )
    else:
        solution["rangeToAnchor"] = _format_quantity(
            case_input.boundary.input_value, "length", unit_system
        )

    # F5.1: serializa N segmentos. seabedFrictionCF aparece no primeiro
    # segmento (que toca o fundo), demais ficam null.
    seg_dicts: list[dict[str, Any]] = []
    for idx, segment in enumerate(case_input.segments):
        line_props: dict[str, Any] = {
            "lineType": segment.line_type,
            "wetWeight": _format_quantity(
                segment.w, "weight_per_length", unit_system
            ),
            "breakStrength": _format_quantity(
                segment.MBL, "force", unit_system
            ),
            "qmoorEA": _format_quantity(segment.EA, "force", unit_system),
            "seabedFrictionCF": case_input.seabed.mu if idx == 0 else None,
        }
        if segment.diameter:
            line_props["diameter"] = _format_quantity(
                segment.diameter, "diameter", unit_system,
            )
        if segment.dry_weight:
            line_props["dryWeight"] = _format_quantity(
                segment.dry_weight, "weight_per_length", unit_system,
            )
        if segment.modulus:
            line_props["modulus"] = _format_quantity(
                segment.modulus, "modulus", unit_system,
            )
        seg_dicts.append(
            {
                "category": segment.category,
                "length": _format_quantity(segment.length, "length", unit_system),
                "lineProps": line_props,
            }
        )

    return {
        "name": case_input.name,
        "description": case_input.description,
        "unitSystem": unit_system,
        "criteriaProfile": case_input.criteria_profile.value,
        "mooringLine": {
            "name": case_input.name,
            "rigidityType": "qmoor",
            "segments": seg_dicts,
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
