"""
Parser e exporter do formato `.moor` (F2.6, expandido na Fase 5).

Decisão Q2 da auditoria pré-F2: `.moor` é **JSON próprio do AncoPlat**
compatível com o schema da Seção 5.2 do MVP v2 PDF (o formato binário
original do QMoor 0.8.5 estava em `.pyd` e é inacessível).

Campos quantitativos do `.moor` JSON podem vir como:
  - string com unidade: "450 ft", "13.78 lbf/ft", "500 m"
  - número sem unidade: assume-se a unidade padrão do `unitSystem`

Na exportação, valores SI internos são convertidos de volta para
imperial/metric conforme o `unitSystem` declarado.

─── Versionamento (Fase 5 / Q4) ──────────────────────────────────────

`.moor` v1: schema original (Seção 5.2 MVP v2). Campo `version` ausente.
`.moor` v2: campo `version: 2` na raiz + novos campos das Fases 1-3:

  Per segmento:
    - eaSource: "qmoor" | "gmoor"
    - muOverride: float | None
    - seabedFrictionCF: float | None  (per-seg em v2; era global em v1)
    - eaDynamicBeta: float | None
  No boundary:
    - startpointOffsetHorz: float (default 0)
    - startpointOffsetVert: float (default 0)
    - startpointType: "semisub" | "ahv" | "barge" | "none"

Migrador `_migrate_v1_to_v2` popula defaults e retorna log estruturado
das transformações aplicadas (Ajuste 2 da Fase 5). Engenheiro tem
visibilidade do que foi populado por default vs. estava no arquivo
original.
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
# Versionamento e migrador (Fase 5 / Q4 + Ajuste 2)
# ==============================================================================


CURRENT_MOOR_VERSION = 2


class MigrationLogEntry(dict):
    """
    Entrada do log de migração v1→v2. Documenta cada default populado
    em campo de v1 sem o equivalente em v2. Estrutura:
      {field: dotted path, old: None ou valor original, new: valor populado,
       reason: descrição curta}.
    """


def _migrate_v1_to_v2(payload: dict[str, Any]) -> tuple[dict[str, Any], list[dict]]:
    """
    Migrador idempotente v1 → v2 (Fase 5 / Q4 + Ajuste 2).

    Detecção: ausência de `version` ou `version: 1` → v1 → migra.
    Retorna: (payload_v2, log_de_transformacoes).

    Estratégia: copia o payload inalterado e adiciona apenas os campos
    NOVOS das Fases 1-3 com defaults idempotentes. Log estruturado
    documenta cada default populado para visibilidade do usuário (UI
    pode mostrar como warnings após import).

    Campos populados (todos com defaults que preservam comportamento):
      Per segmento:
        - eaSource: "qmoor"
        - muOverride: None
        - seabedFrictionCF: copia do valor global se for o seg 0,
          None no resto
        - eaDynamicBeta: None
      Boundary:
        - startpointOffsetHorz: 0.0
        - startpointOffsetVert: 0.0
        - startpointType: "semisub"
    """
    import copy as _copy
    if payload.get("version") == 2:
        return _copy.deepcopy(payload), []  # já é v2 — passa direto

    # deepcopy evita mutar o payload original (dicts internos compartilhados
    # poderiam vazar mutações para o caller — bug capturado em testes).
    out = _copy.deepcopy(payload)
    log: list[dict] = []

    # Marcar como v2
    out["version"] = 2

    # Encontra mooringLine (formato AncoPlat) ou mooringLines[0] (QMoor 0.8.x)
    ml = out.get("mooringLine")
    if ml is None:
        lines = out.get("mooringLines") or []
        if not isinstance(lines, list) or len(lines) == 0:
            # Sem mooringLine — não há o que migrar; deixa o parser
            # downstream emitir MoorFormatError com mensagem clara.
            return out, log
        ml = lines[0]

    # Boundary: 3 fields novos da Fase 2-3
    boundary = ml.get("boundary", {})
    if "startpointOffsetHorz" not in boundary:
        boundary["startpointOffsetHorz"] = 0.0
        log.append({
            "field": "boundary.startpointOffsetHorz",
            "old": None,
            "new": 0.0,
            "reason": "default v2 (Fase 2 / A2.6 — offset cosmético)",
        })
    if "startpointOffsetVert" not in boundary:
        boundary["startpointOffsetVert"] = 0.0
        log.append({
            "field": "boundary.startpointOffsetVert",
            "old": None,
            "new": 0.0,
            "reason": "default v2 (Fase 2 / A2.6 — offset cosmético)",
        })
    if "startpointType" not in boundary:
        boundary["startpointType"] = "semisub"
        log.append({
            "field": "boundary.startpointType",
            "old": None,
            "new": "semisub",
            "reason": "default v2 (Fase 3 / A2.5+D7 — tipo de plataforma cosmético)",
        })
    ml["boundary"] = boundary

    # Segmentos: 4 fields novos da Fase 1
    segments = ml.get("segments") or []
    # Em v1, seabedFrictionCF era global no primeiro seg. Em v2, é per-seg.
    # Preserva: cf do seg 0 fica no seg 0; demais ficam None.
    for i, seg in enumerate(segments):
        line_props = seg.get("lineProps", {})
        if "eaSource" not in line_props:
            line_props["eaSource"] = "qmoor"
            log.append({
                "field": f"segments[{i}].eaSource",
                "old": None,
                "new": "qmoor",
                "reason": "default v2 (Fase 1 / A1.4+B4 — EA estático QMoor)",
            })
        if "muOverride" not in line_props:
            line_props["muOverride"] = None
            log.append({
                "field": f"segments[{i}].muOverride",
                "old": None,
                "new": None,
                "reason": "default v2 (Fase 1 / B3 — sem override)",
            })
        if "eaDynamicBeta" not in line_props:
            line_props["eaDynamicBeta"] = None
            log.append({
                "field": f"segments[{i}].eaDynamicBeta",
                "old": None,
                "new": None,
                "reason": "default v2 (Fase 1 — β reservado, não-implementado)",
            })
        seg["lineProps"] = line_props

    ml["segments"] = segments
    out["mooringLine"] = ml
    return out, log


# ==============================================================================
# Parser: .moor JSON → CaseInput
# ==============================================================================


def parse_moor_payload_with_log(
    payload: dict[str, Any],
) -> tuple[CaseInput, list[dict]]:
    """
    Versão da Fase 5 que retorna (CaseInput, migration_log).

    Ajuste 2 do mini-plano: log estruturado das transformações
    aplicadas pelo migrador v1→v2. Cada entrada do log é um dict
    {field, old, new, reason} — UI pode mostrar como warnings após
    import; servidor loga para auditoria.

    Para chamadas legadas que não querem o log, use
    `parse_moor_payload(payload)` que retorna apenas CaseInput
    (migrador é aplicado silenciosamente).
    """
    migrated, log = _migrate_v1_to_v2(payload)
    return _parse_moor_payload_internal(migrated), log


def parse_moor_payload(payload: dict[str, Any]) -> CaseInput:
    """
    Converte um payload `.moor` (v1 ou v2) em CaseInput.

    Detecta versão automaticamente e aplica migrador v1→v2
    silenciosamente. Para receber log de migração, use
    `parse_moor_payload_with_log(payload)`.
    """
    migrated, _log = _migrate_v1_to_v2(payload)
    return _parse_moor_payload_internal(migrated)


def _parse_moor_payload_internal(payload: dict[str, Any]) -> CaseInput:
    """
    Implementação interna do parser — assume payload já em schema v2
    (com fields novos populados via _migrate_v1_to_v2).

    Campos esperados:
      name, unitSystem, version (>= 2),
      mooringLine.{name, segments, boundary, solution}
      mooringLine.segments[].lineProps.{lineType, diameter, breakStrength,
          dryWeight, wetWeight, modulus, seabedFrictionCF, category?,
          eaSource (v2), muOverride (v2), eaDynamicBeta (v2)}
      boundary.{startpointDepth, endpointDepth, endpointGrounded,
          horzDistance?, startpointOffsetHorz (v2),
          startpointOffsetVert (v2), startpointType (v2)}
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
            # Fields novos da Fase 1 (v2). Defaults idempotentes preservam
            # comportamento legado quando ausente (parser legacy / migrado).
            ea_source = props.get("eaSource", "qmoor")
            if ea_source not in ("qmoor", "gmoor"):
                ea_source = "qmoor"
            mu_override = props.get("muOverride")
            ea_dynamic_beta = props.get("eaDynamicBeta")
            seabed_friction_cf_seg = props.get("seabedFrictionCF")

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
                    # Fase 1 fields (v2)
                    ea_source=ea_source,
                    mu_override=mu_override,
                    ea_dynamic_beta=ea_dynamic_beta,
                    seabed_friction_cf=seabed_friction_cf_seg,
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

        # Fields novos da Fase 2-3 (v2). Defaults idempotentes preservam
        # comportamento legado.
        startpoint_offset_horz = float(boundary_raw.get("startpointOffsetHorz", 0.0))
        startpoint_offset_vert = float(boundary_raw.get("startpointOffsetVert", 0.0))
        startpoint_type = boundary_raw.get("startpointType", "semisub")
        if startpoint_type not in ("semisub", "ahv", "barge", "none"):
            startpoint_type = "semisub"

        boundary = BoundaryConditions(
            h=h,
            mode=SolutionMode(mode),
            input_value=input_value,
            startpoint_depth=_parse_quantity(
                boundary_raw.get("startpointDepth", 0.0), "length", unit_system,
            ),
            endpoint_grounded=bool(boundary_raw.get("endpointGrounded", True)),
            # Fase 2-3 fields (v2)
            startpoint_offset_horz=startpoint_offset_horz,
            startpoint_offset_vert=startpoint_offset_vert,
            startpoint_type=startpoint_type,
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

    # F5.1 + Fase 5: serializa N segmentos com fields da Fase 1 (v2).
    # seabedFrictionCF agora é per-seg (em v1 era global no seg 0; v2
    # preserva por segmento — migrador faz a transição).
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
            # Fase 5 / v2: seabedFrictionCF per-seg (mantém compat
            # com v1 onde global = seg 0). Se segment.seabed_friction_cf
            # foi populado pelo catálogo, usa esse; senão, emite o
            # global do seabed só no seg 0.
            "seabedFrictionCF": (
                segment.seabed_friction_cf
                if segment.seabed_friction_cf is not None
                else (case_input.seabed.mu if idx == 0 else None)
            ),
            # Fields novos da Fase 1 (v2)
            "eaSource": segment.ea_source,
            "muOverride": segment.mu_override,
            "eaDynamicBeta": segment.ea_dynamic_beta,
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
        "version": CURRENT_MOOR_VERSION,  # v2 (Fase 5 / Q4)
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
                # Fields novos da Fase 2-3 (v2)
                "startpointOffsetHorz": case_input.boundary.startpoint_offset_horz,
                "startpointOffsetVert": case_input.boundary.startpoint_offset_vert,
                "startpointType": case_input.boundary.startpoint_type,
            },
            "solution": solution,
        },
    }


__all__ = [
    "CURRENT_MOOR_VERSION",
    "MoorFormatError",
    "export_case_as_moor",
    "parse_moor_payload",
    "parse_moor_payload_with_log",
]
