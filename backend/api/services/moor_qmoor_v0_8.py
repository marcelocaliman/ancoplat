"""
Parser do formato QMoor 0.8.0 (Sprint 1 / v1.1.0 / Commit 6).

Diferenças vs `.moor` v2 do AncoPlat (`moor_service.py`):

  • Multi-linha por arquivo: `mooringLines: [{...}, {...}]` (até 16 linhas).
  • Multi-perfil por linha: `mooringLines[i].profiles: [{...}, {...}]`
    (Operational Profile, Preset Profile, etc.).
  • Top-level metadata operacional: `rig`, `location`, `region`,
    `engineer`, `number` — vão para `CaseInput.metadata`.
  • Vessels top-level com info do hull → `CaseInput.vessel`.
  • `horzForces` por profile → `CaseInput.current_profile`.
  • Pendant multi-segmento dentro de attachments → `pendant_segments`.

Estratégia de mapping QMoor 0.8.0 → AncoPlat:

  Para cada `mooringLine` × cada `profile` selecionado, produz UM
  `CaseInput`. Nome: `f"{line.name} — {profile.name}"`. UI no Commit 7
  oferece selector que permite escolher quais profiles importar.

Modo de tolerância
─────────────────
Campos não-mapeáveis (identifiers internos do QMoor, custos, etc.)
são preservados em `CaseInput.metadata` com prefixo `qmoor_`. Isso
permite round-trip mesmo de campos que o AncoPlat não usa.

Este parser é DETERMINÍSTICO e PURO: sem I/O, sem estado global.

⚠ Parser construído sem amostra real do JSON KAR006 — testado contra
fixtures sintéticos que reproduzem a estrutura descrita. A integração
do JSON KAR006 real entra como gate em Commit 11 (E2E).
"""
from __future__ import annotations

from typing import Any, Callable, Optional

from backend.api.schemas.cases import CaseInput
from backend.solver.types import (
    BoundaryConditions,
    CriteriaProfile,
    CurrentLayer,
    CurrentProfile,
    LineAttachment,
    LineCategory,
    LineSegment,
    PendantSegment,
    SeabedConfig,
    SolutionMode,
    Vessel,
)


class QMoorV08ParseError(Exception):
    """Falha ao parsear payload QMoor 0.8.0."""


# Lista de keys top-level que vão direto para `CaseInput.metadata`.
_TOP_METADATA_KEYS = (
    "rig", "location", "region", "engineer", "number",
    "project", "client", "field",
)


def parse_qmoor_v0_8(
    payload: dict[str, Any],
    *,
    profile_filter: Optional[Callable[[dict[str, Any]], bool]] = None,
) -> tuple[list[CaseInput], list[dict[str, Any]]]:
    """
    Converte um payload QMoor 0.8.0 em lista de `CaseInput`.

    Parameters
    ----------
    payload : dict
        JSON top-level do arquivo QMoor 0.8.0.
    profile_filter : Callable[[profile_dict], bool], opcional
        Predicado para selecionar quais profiles importar. Default:
        todos. UI pode passar lambda que retorna True só para
        "operational" ou para nomes específicos.

    Returns
    -------
    (cases, log)
        cases: lista de `CaseInput` (um por mooringLine × profile).
        log: lista de entradas {field, old, new, reason} documentando
             defaults injetados, fallbacks aplicados, ou warnings.

    Raises
    ------
    QMoorV08ParseError
        Quando version não é 0.8.x ou estrutura essencial está ausente.
    """
    log: list[dict[str, Any]] = []
    _validate_version(payload)
    unit_system = _validate_unit_system(payload)

    top_metadata = _extract_top_metadata(payload, unit_system, log)
    vessel = _extract_vessel(payload, log)
    lines_raw = _extract_mooring_lines(payload)

    cases: list[CaseInput] = []
    for line_idx, line in enumerate(lines_raw):
        line_name = _get_str(line, "name") or f"Line{line_idx + 1}"
        profiles_raw = line.get("profiles") or []
        if not isinstance(profiles_raw, list) or not profiles_raw:
            log.append({
                "field": f"mooringLines[{line_idx}].profiles",
                "old": None, "new": "skipped",
                "reason": "linha sem profiles — pulada no import",
            })
            continue
        for prof_idx, profile in enumerate(profiles_raw):
            if profile_filter is not None and not profile_filter(profile):
                continue
            try:
                ci = _build_case_from_profile(
                    line_idx=line_idx,
                    line=line,
                    line_name=line_name,
                    prof_idx=prof_idx,
                    profile=profile,
                    top_metadata=top_metadata,
                    vessel=vessel,
                    log=log,
                )
                cases.append(ci)
            except (QMoorV08ParseError, ValueError, KeyError, TypeError) as e:
                log.append({
                    "field": f"mooringLines[{line_idx}].profiles[{prof_idx}]",
                    "old": _get_str(profile, "name") or "<unnamed>",
                    "new": "skipped",
                    "reason": f"erro de parse: {e}",
                })

    if not cases:
        raise QMoorV08ParseError(
            "Nenhum CaseInput produzido — verifique se o arquivo contém "
            "ao menos uma mooringLine com 1+ profiles válidos."
        )
    return cases, log


# ──────────────────────────────────────────────────────────────────
# Sub-parsers
# ──────────────────────────────────────────────────────────────────


def _validate_version(payload: dict[str, Any]) -> None:
    version = payload.get("version")
    if version is None:
        raise QMoorV08ParseError("payload sem campo 'version'.")
    v_str = str(version)
    if not v_str.startswith("0.8"):
        raise QMoorV08ParseError(
            f"versão QMoor não suportada: '{v_str}'. Este parser cobre 0.8.x."
        )


def _validate_unit_system(payload: dict[str, Any]) -> str:
    unit_system = payload.get("unitSystem", "metric")
    if unit_system not in ("metric", "imperial"):
        raise QMoorV08ParseError(
            f"unitSystem inválido: '{unit_system}' (esperado 'metric' ou 'imperial')."
        )
    return unit_system


def _extract_top_metadata(
    payload: dict[str, Any], unit_system: str, log: list[dict[str, Any]],
) -> dict[str, str]:
    md: dict[str, str] = {}
    for key in _TOP_METADATA_KEYS:
        val = payload.get(key)
        if val is None:
            continue
        md[key] = str(val)[:500]
    md["source_format"] = "qmoor_0_8"
    md["source_unit_system"] = unit_system
    if "name" in payload:
        md["source_project_name"] = str(payload["name"])[:500]
    return md


def _extract_vessel(
    payload: dict[str, Any], log: list[dict[str, Any]],
) -> Optional[Vessel]:
    vessels = payload.get("vessels")
    if not vessels or not isinstance(vessels, list):
        return None
    raw = vessels[0]
    if not isinstance(raw, dict):
        return None
    name = _get_str(raw, "name") or "Vessel"
    try:
        return Vessel(
            name=name[:120],
            vessel_type=_get_str(raw, "type"),
            displacement=_get_pos_float(raw, "displacement"),
            loa=_get_pos_float(raw, "loa") or _get_pos_float(raw, "length"),
            breadth=_get_pos_float(raw, "breadth") or _get_pos_float(raw, "beam"),
            draft=_get_pos_float(raw, "draft"),
            heading_deg=_get_heading(raw, "heading"),
            operator=_get_str(raw, "operator"),
        )
    except (ValueError, TypeError) as e:
        log.append({
            "field": "vessels[0]", "old": name, "new": None,
            "reason": f"vessel inválido — descartado: {e}",
        })
        return None


def _extract_mooring_lines(payload: dict[str, Any]) -> list[dict[str, Any]]:
    lines = payload.get("mooringLines")
    if not isinstance(lines, list) or not lines:
        raise QMoorV08ParseError(
            "payload sem 'mooringLines' não-vazio."
        )
    return [ln for ln in lines if isinstance(ln, dict)]


def _build_case_from_profile(
    *,
    line_idx: int,
    line: dict[str, Any],
    line_name: str,
    prof_idx: int,
    profile: dict[str, Any],
    top_metadata: dict[str, str],
    vessel: Optional[Vessel],
    log: list[dict[str, Any]],
) -> CaseInput:
    profile_name = _get_str(profile, "name") or f"Profile{prof_idx + 1}"
    case_name = f"{line_name} — {profile_name}"[:200]
    description = _get_str(profile, "description")

    segments = _parse_segments(profile, line_idx, prof_idx, log)
    attachments = _parse_attachments(profile, line_idx, prof_idx, log)
    boundary = _parse_boundary(profile, line, line_idx, prof_idx, log)
    seabed = _parse_seabed(profile, line)
    current_profile = _parse_current_profile(profile, line_idx, prof_idx, log)

    metadata = dict(top_metadata)
    metadata[f"line_index"] = str(line_idx)
    metadata[f"line_name"] = line_name
    metadata[f"profile_name"] = profile_name
    profile_type = _get_str(profile, "type")
    if profile_type:
        metadata["profile_type"] = profile_type

    return CaseInput(
        name=case_name,
        description=description,
        segments=segments,
        attachments=attachments,
        boundary=boundary,
        seabed=seabed,
        criteria_profile=CriteriaProfile.MVP_PRELIMINARY,
        vessel=vessel,
        current_profile=current_profile,
        metadata=metadata,
    )


def _parse_segments(
    profile: dict[str, Any],
    line_idx: int, prof_idx: int,
    log: list[dict[str, Any]],
) -> list[LineSegment]:
    raw = profile.get("segments") or []
    if not isinstance(raw, list) or not raw:
        raise QMoorV08ParseError(
            f"profile[{line_idx}.{prof_idx}] não tem segments."
        )
    if len(raw) > 10:
        log.append({
            "field": f"profiles[{line_idx}.{prof_idx}].segments",
            "old": len(raw), "new": 10,
            "reason": "QMoor permite >10 segmentos; AncoPlat trunca.",
        })
        raw = raw[:10]
    out: list[LineSegment] = []
    for i, seg in enumerate(raw):
        if not isinstance(seg, dict):
            continue
        length = _get_pos_float(seg, "length")
        if length is None:
            raise QMoorV08ParseError(
                f"segment[{i}] sem 'length' — campo obrigatório."
            )
        w = (_get_pos_float(seg, "wetWeight")
             or _get_pos_float(seg, "submergedWeight")
             or _get_pos_float(seg, "w"))
        ea = (_get_pos_float(seg, "EA")
              or _get_pos_float(seg, "ea")
              or _get_pos_float(seg, "axialStiffness"))
        mbl = (_get_pos_float(seg, "MBL")
               or _get_pos_float(seg, "breakStrength")
               or _get_pos_float(seg, "mbl"))
        if w is None or ea is None or mbl is None:
            raise QMoorV08ParseError(
                f"segment[{i}] missing required field "
                f"(w={w}, EA={ea}, MBL={mbl})."
            )
        out.append(LineSegment(
            length=length,
            w=w, EA=ea, MBL=mbl,
            category=_parse_category(_get_str(seg, "category")),
            line_type=_get_str(seg, "lineType")
                       or _get_str(seg, "line_type"),
            diameter=_get_pos_float(seg, "diameter"),
            dry_weight=_get_pos_float(seg, "dryWeight")
                       or _get_pos_float(seg, "dry_weight"),
            modulus=_get_pos_float(seg, "modulus"),
        ))
    return out


def _parse_attachments(
    profile: dict[str, Any],
    line_idx: int, prof_idx: int,
    log: list[dict[str, Any]],
) -> list[LineAttachment]:
    raw = profile.get("attachments") or []
    if not isinstance(raw, list):
        return []
    out: list[LineAttachment] = []
    for i, att in enumerate(raw):
        if not isinstance(att, dict):
            continue
        kind_raw = _get_str(att, "kind") or "buoy"
        kind = kind_raw.lower()
        if kind not in ("buoy", "clump_weight", "ahv"):
            log.append({
                "field": f"profiles[{line_idx}.{prof_idx}].attachments[{i}].kind",
                "old": kind_raw, "new": "buoy",
                "reason": "kind desconhecido — fallback para 'buoy'.",
            })
            kind = "buoy"

        position_s = _get_pos_float(att, "positionFromAnchor")
        position_idx = att.get("positionIndex")
        if position_s is None and position_idx is None:
            log.append({
                "field": f"profiles[{line_idx}.{prof_idx}].attachments[{i}]",
                "old": None, "new": "skipped",
                "reason": "attachment sem positionFromAnchor nem positionIndex.",
            })
            continue

        pendant_segments = _parse_pendant_segments(att, log,
                                                    line_idx, prof_idx, i)

        common_kwargs: dict[str, Any] = dict(
            kind=kind,
            name=_get_str(att, "name"),
            tether_length=_get_pos_float(att, "tetherLength"),
            buoy_type=_get_str(att, "buoyType"),
            buoy_end_type=_get_str(att, "buoyEndType"),
            buoy_outer_diameter=_get_pos_float(att, "buoyOuterDiameter"),
            buoy_length=_get_pos_float(att, "buoyLength"),
            buoy_weight_in_air=_get_pos_float(att, "buoyWeightInAir"),
            pendant_line_type=_get_str(att, "pendantLineType"),
            pendant_diameter=_get_pos_float(att, "pendantDiameter"),
            pendant_segments=pendant_segments or None,
        )
        if position_s is not None:
            common_kwargs["position_s_from_anchor"] = position_s
        elif isinstance(position_idx, int) and position_idx >= 0:
            common_kwargs["position_index"] = position_idx

        if kind == "ahv":
            common_kwargs["ahv_bollard_pull"] = _get_pos_float(att, "bollardPull")
            common_kwargs["ahv_heading_deg"] = _get_heading(att, "heading")
        else:
            common_kwargs["submerged_force"] = (
                _get_pos_float(att, "submergedForce") or 0.0
            )

        try:
            out.append(LineAttachment(**common_kwargs))
        except (ValueError, TypeError) as e:
            log.append({
                "field": f"profiles[{line_idx}.{prof_idx}].attachments[{i}]",
                "old": _get_str(att, "name"),
                "new": "skipped",
                "reason": f"validação falhou: {e}",
            })
    return out


def _parse_pendant_segments(
    att: dict[str, Any], log: list[dict[str, Any]],
    line_idx: int, prof_idx: int, att_idx: int,
) -> list[PendantSegment]:
    raw = att.get("pendantSegments") or att.get("pendant_segments")
    if not isinstance(raw, list) or not raw:
        return []
    out: list[PendantSegment] = []
    for j, ps in enumerate(raw):
        if not isinstance(ps, dict):
            continue
        length = _get_pos_float(ps, "length")
        if length is None:
            log.append({
                "field": (f"profiles[{line_idx}.{prof_idx}]"
                          f".attachments[{att_idx}].pendantSegments[{j}]"),
                "old": None, "new": "skipped",
                "reason": "pendant segment sem length — pulado.",
            })
            continue
        try:
            out.append(PendantSegment(
                length=length,
                line_type=_get_str(ps, "lineType")
                          or _get_str(ps, "line_type"),
                category=_parse_category(_get_str(ps, "category")),
                diameter=_get_pos_float(ps, "diameter"),
                w=_get_pos_float(ps, "wetWeight")
                  or _get_pos_float(ps, "w"),
                dry_weight=_get_pos_float(ps, "dryWeight"),
                EA=_get_pos_float(ps, "EA") or _get_pos_float(ps, "ea"),
                MBL=_get_pos_float(ps, "MBL")
                    or _get_pos_float(ps, "breakStrength"),
                material_label=_get_str(ps, "materialLabel"),
            ))
            if len(out) == 5:
                break  # respeita max_length=5 do schema
        except (ValueError, TypeError) as e:
            log.append({
                "field": (f"profiles[{line_idx}.{prof_idx}]"
                          f".attachments[{att_idx}].pendantSegments[{j}]"),
                "old": None, "new": "skipped",
                "reason": f"validação falhou: {e}",
            })
    return out


def _parse_boundary(
    profile: dict[str, Any], line: dict[str, Any],
    line_idx: int, prof_idx: int,
    log: list[dict[str, Any]],
) -> BoundaryConditions:
    bd = profile.get("boundary") or {}
    if not isinstance(bd, dict):
        bd = {}

    h = (_get_pos_float(bd, "h")
         or _get_pos_float(bd, "waterDepth")
         or _get_pos_float(bd, "depth")
         or _get_pos_float(line, "waterDepth"))
    if h is None:
        raise QMoorV08ParseError(
            f"profile[{line_idx}.{prof_idx}].boundary sem profundidade."
        )

    mode_raw = (_get_str(bd, "mode") or "Tension").lower()
    if mode_raw in ("tension", "fairlead", "fl"):
        mode = SolutionMode.TENSION
        input_value = (_get_pos_float(bd, "fairleadTension")
                       or _get_pos_float(bd, "tension")
                       or _get_pos_float(bd, "T_fl")
                       or _get_pos_float(bd, "input_value"))
    else:
        mode = SolutionMode.RANGE
        input_value = (_get_pos_float(bd, "horzDistance")
                       or _get_pos_float(bd, "range")
                       or _get_pos_float(bd, "input_value"))
    if input_value is None:
        raise QMoorV08ParseError(
            f"profile[{line_idx}.{prof_idx}].boundary sem input_value."
        )

    sd = _get_pos_float(bd, "startpointDepth")
    if sd is None:
        sd = 0.0
    return BoundaryConditions(
        h=h,
        mode=mode,
        input_value=input_value,
        startpoint_depth=sd,
        endpoint_grounded=bool(bd.get("endpointGrounded", True)),
    )


def _parse_seabed(profile: dict[str, Any], line: dict[str, Any]) -> SeabedConfig:
    sb = profile.get("seabed") or line.get("seabed") or {}
    if not isinstance(sb, dict):
        sb = {}
    mu = sb.get("mu")
    if mu is None:
        return SeabedConfig()
    try:
        return SeabedConfig(mu=float(mu))
    except (ValueError, TypeError):
        return SeabedConfig()


def _parse_current_profile(
    profile: dict[str, Any],
    line_idx: int, prof_idx: int,
    log: list[dict[str, Any]],
) -> Optional[CurrentProfile]:
    raw = profile.get("horzForces") or profile.get("currentProfile")
    if not isinstance(raw, list) or not raw:
        return None
    layers: list[CurrentLayer] = []
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            continue
        depth = item.get("depth")
        speed = (item.get("speed")
                 if "speed" in item else item.get("velocity"))
        heading = item.get("heading", 0.0)
        try:
            d = float(depth) if depth is not None else None
            s = float(speed) if speed is not None else None
            h = float(heading) if heading is not None else 0.0
        except (ValueError, TypeError):
            continue
        if d is None or s is None or d < 0 or s < 0:
            continue
        layers.append(CurrentLayer(depth=d, speed=s, heading_deg=h % 360.0))
    if not layers:
        return None
    layers.sort(key=lambda lyr: lyr.depth)
    # remove duplicate depths preservando o primeiro
    deduped: list[CurrentLayer] = []
    seen: set[float] = set()
    for lyr in layers:
        if lyr.depth in seen:
            continue
        deduped.append(lyr)
        seen.add(lyr.depth)
    if len(deduped) > 20:
        log.append({
            "field": f"profiles[{line_idx}.{prof_idx}].horzForces",
            "old": len(deduped), "new": 20,
            "reason": "QMoor permite >20 layers; AncoPlat trunca.",
        })
        deduped = deduped[:20]
    return CurrentProfile(layers=deduped)


# ──────────────────────────────────────────────────────────────────
# Helpers de parsing
# ──────────────────────────────────────────────────────────────────


def _get_str(d: dict[str, Any], key: str) -> Optional[str]:
    val = d.get(key)
    if val is None:
        return None
    s = str(val).strip()
    return s if s else None


def _get_pos_float(d: dict[str, Any], key: str) -> Optional[float]:
    val = d.get(key)
    if val is None:
        return None
    try:
        f = float(val)
    except (ValueError, TypeError):
        return None
    return f if f > 0 else None


def _get_heading(d: dict[str, Any], key: str) -> Optional[float]:
    val = d.get(key)
    if val is None:
        return None
    try:
        f = float(val)
    except (ValueError, TypeError):
        return None
    f_norm = f % 360.0
    if f_norm < 0:
        f_norm += 360.0
    return f_norm


def _parse_category(value: Optional[str]) -> Optional[LineCategory]:
    """Mapeia categoria QMoor para o Literal canônico do solver.

    `LineCategory` é `Literal[...]` (não Enum), então retornamos a
    string canônica direta — Pydantic valida no `LineSegment`/`PendantSegment`.
    """
    if not value:
        return None
    v = value.strip().lower()
    aliases: dict[str, LineCategory] = {
        "wire": "Wire", "wire_rope": "Wire",
        "studded": "StuddedChain", "studded_chain": "StuddedChain",
        "studless": "StudlessChain", "studless_chain": "StudlessChain",
        "polyester": "Polyester", "poly": "Polyester",
        "rope": "Polyester", "synthetic": "Polyester",
    }
    return aliases.get(v)


__all__ = [
    "QMoorV08ParseError",
    "parse_qmoor_v0_8",
]
