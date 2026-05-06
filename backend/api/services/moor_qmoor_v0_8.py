"""
Parser do formato QMoor 0.8.0 (Sprint 1 / v1.1.0 / Commit 6,
fix Sprint 2 / Commit 20 para amostras reais do KAR006).

Diferenças vs `.moor` v2 do AncoPlat (`moor_service.py`):

  • Top-level: `QMoorVersion` (não `version`), `mooringLines: [...]`.
  • Cada `mooringLine` é um GRUPO de profiles (Operational/Preset);
    o `mooringLine` em si tem `segments: []` vazio — os segments reais
    estão em `mooringLines[i].profiles[j].segments[]`.
  • `mooringLines[i].profiles[j]` = uma linha individual com seus
    próprios segments + boundary + buoys + pendant.
  • Multi-perfil por grupo (4 mooring lines em "Operational Profiles"
    + 4 em "Preset Profiles" no caso KAR006).
  • Top-level metadata operacional: `rig`, `location`, `region`,
    `engineer`, `number` → `CaseInput.metadata`.
  • Vessels top-level com info do hull → `CaseInput.vessel`.
  • `horzForces` por profile → `CaseInput.current_profile`.
  • Boias em `profile.buoys[]` (não `attachments[]`) com `pennantLine.segments[]`.

Estratégia de mapping QMoor 0.8.0 → AncoPlat:

  Para cada `mooringLine` × cada `profile` selecionado, produz UM
  `CaseInput`. Nome: `f"{line.name} — {profile.name}"`. UI no Commit 7
  oferece selector que permite escolher quais profiles importar.

Quantidades como string com unidade
────────────────────────────────────
QMoor 0.8.0 emite valores como `"475.0 m"`, `"150.66 kgf / m"`,
`"81018.96 te"`, `"128001 MPa"` — strings com unidade. Reusamos
`_parse_quantity` do parser `.moor` v2 (Pint + aliases QMoor) para
normalizar tudo em SI internamente.

`lineProps` nesting
────────────────────
Os campos físicos dos segments e dos pendant_segments vêm aninhados
em `lineProps.{wetWeight, qmoorEA, breakStrength, diameter, ...}`,
não no top-level do segment. O helper `_seg_field()` busca nos dois
níveis (top primeiro, depois lineProps) para acomodar tanto fixtures
sintéticos legados quanto JSON real do QMoor.

Modo de tolerância
─────────────────
Campos não-mapeáveis (identifiers internos do QMoor, custos, etc.)
são preservados em `CaseInput.metadata` com prefixo `qmoor_`. Isso
permite round-trip mesmo de campos que o AncoPlat não usa.

Este parser é DETERMINÍSTICO e PURO: sem I/O, sem estado global.
"""
from __future__ import annotations

import math
from typing import Any, Callable, Optional

from backend.api.schemas.cases import CaseInput
from backend.api.services.moor_service import (
    MoorFormatError,
    _parse_quantity,
)
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


# Aceleração da gravidade para conversão massa→peso quando necessário.
_G = 9.80665


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
                    unit_system=unit_system,
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
    """Aceita `version` (fixtures sintéticos) e `QMoorVersion` (JSON real)."""
    version = payload.get("version") or payload.get("QMoorVersion")
    if version is None:
        raise QMoorV08ParseError(
            "payload sem campo 'version' nem 'QMoorVersion'."
        )
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
    unit_system: str = "metric",
) -> CaseInput:
    profile_name = _get_str(profile, "name") or f"Profile{prof_idx + 1}"
    case_name = f"{line_name} — {profile_name}"[:200]
    description = _get_str(profile, "description")

    segments = _parse_segments(
        profile, line_idx, prof_idx, log, unit_system,
    )
    # Attachments podem vir em 2 lugares no JSON QMoor 0.8.0:
    #   - profile.attachments[]   (formato sintético/AncoPlat)
    #   - profile.buoys[] + profile.clumps[]   (formato real QMoor)
    attachments = _parse_attachments(
        profile, line_idx, prof_idx, log, unit_system,
    )
    attachments += _parse_buoys_as_attachments(
        profile, line_idx, prof_idx, log, unit_system,
    )
    attachments += _parse_clumps_as_attachments(
        profile, line_idx, prof_idx, log, unit_system,
    )
    boundary = _parse_boundary(
        profile, line, line_idx, prof_idx, log, unit_system,
    )
    seabed = _parse_seabed(profile, line, unit_system)
    current_profile = _parse_current_profile(
        profile, line_idx, prof_idx, log,
    )

    metadata = dict(top_metadata)
    metadata["line_index"] = str(line_idx)
    metadata["line_name"] = line_name
    metadata["profile_name"] = profile_name
    profile_type = _get_str(profile, "type")
    if profile_type:
        metadata["profile_type"] = profile_type

    # Preserva fairleadOffset como metadata (cosmético v1, ver A2.6).
    bd = profile.get("boundary") or {}
    if isinstance(bd, dict):
        offset = bd.get("fairleadOffset")
        if isinstance(offset, dict):
            ox = _parse_q(offset.get("x"), "length", unit_system)
            oy = _parse_q(offset.get("y"), "length", unit_system)
            if ox is not None:
                metadata["fairlead_offset_x_m"] = f"{ox:.4f}"
            if oy is not None:
                metadata["fairlead_offset_y_m"] = f"{oy:.4f}"

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
    unit_system: str = "metric",
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
    # ⚠ ORDEM CRÍTICA — Sprint 2 / Commit 22 ⚠
    # QMoor JSON ordena segments[] na ordem `fairlead → anchor`
    # (primeiro segmento é "Rig Chain" colado no rig/fairlead, último é
    # "Anchor Chain" colado na âncora). AncoPlat espera o INVERSO:
    # `segments[0]` é o mais próximo da ÂNCORA (vide
    # `backend/api/schemas/cases.py:85-86`).
    # → Inverte a lista AQUI antes de criar `LineSegment`s, para que
    # toda a pipeline downstream (solver, plot, attachment positions
    # via position_s_from_anchor) tenha a convenção correta.
    raw = list(reversed(raw))
    out: list[LineSegment] = []
    for i, seg in enumerate(raw):
        if not isinstance(seg, dict):
            continue
        # length sempre no top-level do segment
        length = _parse_q(seg.get("length"), "length", unit_system)
        if length is None or length <= 0:
            raise QMoorV08ParseError(
                f"segment[{i}] sem 'length' válido — campo obrigatório."
            )
        # Em QMoor 0.8.0 real, dados físicos vivem em `lineProps.{...}`;
        # fixtures sintéticos antigos têm tudo no top-level. Buscar nos
        # 2 níveis (top primeiro, lineProps depois).
        w = _seg_q(seg, ["wetWeight", "submergedWeight", "w"],
                   "weight_per_length", unit_system)
        ea = _seg_q(seg, ["qmoorEA", "gmoorEA", "EA", "ea", "axialStiffness"],
                    "force", unit_system)
        mbl = _seg_q(seg, ["breakStrength", "MBL", "mbl"],
                     "force", unit_system)
        if w is None or ea is None or mbl is None:
            raise QMoorV08ParseError(
                f"segment[{i}] missing required field "
                f"(w={w}, EA={ea}, MBL={mbl})."
            )
        out.append(LineSegment(
            length=length,
            w=w, EA=ea, MBL=mbl,
            category=_parse_category(
                _seg_str(seg, ["category"])
            ),
            line_type=_seg_str(seg, ["lineType", "line_type"]),
            diameter=_seg_q(seg, ["diameter"], "diameter", unit_system),
            dry_weight=_seg_q(seg, ["dryWeight", "dry_weight"],
                              "weight_per_length", unit_system),
            modulus=_seg_q(seg, ["modulus"], "modulus", unit_system),
        ))
    return out


def _seg_q(
    seg: dict[str, Any],
    keys: list[str],
    dimension: str,
    unit_system: str,
) -> Optional[float]:
    """Busca campo numérico no top-level OU em lineProps; parseia via Pint."""
    for k in keys:
        if k in seg and seg[k] is not None:
            return _parse_q(seg[k], dimension, unit_system)
    props = seg.get("lineProps")
    if isinstance(props, dict):
        for k in keys:
            if k in props and props[k] is not None:
                return _parse_q(props[k], dimension, unit_system)
    return None


def _seg_str(seg: dict[str, Any], keys: list[str]) -> Optional[str]:
    """Busca campo string no top-level OU em lineProps."""
    for k in keys:
        if k in seg and seg[k] is not None:
            s = str(seg[k]).strip()
            if s:
                return s
    props = seg.get("lineProps")
    if isinstance(props, dict):
        for k in keys:
            if k in props and props[k] is not None:
                s = str(props[k]).strip()
                if s:
                    return s
    return None


def _parse_q(
    value: Any, dimension: str, unit_system: str,
) -> Optional[float]:
    """
    Wrapper tolerante de `_parse_quantity`. Aceita:
      - None → None
      - string com unidade ("475.0 m") → SI float
      - número puro → SI float (assume unidade default do unit_system)
      - tipo inválido → None
    Diferentemente de `_parse_quantity`, NÃO levanta exceção em caso
    de falha — devolve None para que o caller decida (warn ou raise).
    """
    if value is None:
        return None
    try:
        result = _parse_quantity(value, dimension, unit_system)
        return float(result) if math.isfinite(result) else None
    except (MoorFormatError, ValueError, TypeError):
        return None


def _parse_attachments(
    profile: dict[str, Any],
    line_idx: int, prof_idx: int,
    log: list[dict[str, Any]],
    unit_system: str = "metric",
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

        position_s = _parse_q(att.get("positionFromAnchor"), "length", unit_system)
        position_idx = att.get("positionIndex")
        if position_s is None and position_idx is None:
            log.append({
                "field": f"profiles[{line_idx}.{prof_idx}].attachments[{i}]",
                "old": None, "new": "skipped",
                "reason": "attachment sem positionFromAnchor nem positionIndex.",
            })
            continue

        pendant_segments = _parse_pendant_segments(
            att, log, line_idx, prof_idx, i, unit_system,
        )

        common_kwargs: dict[str, Any] = dict(
            kind=kind,
            name=_get_str(att, "name"),
            tether_length=_parse_q(att.get("tetherLength"), "length", unit_system),
            buoy_type=_get_str(att, "buoyType"),
            buoy_end_type=_get_str(att, "buoyEndType"),
            buoy_outer_diameter=_parse_q(att.get("buoyOuterDiameter"),
                                         "diameter", unit_system),
            buoy_length=_parse_q(att.get("buoyLength"), "length", unit_system),
            buoy_weight_in_air=_parse_q(att.get("buoyWeightInAir"),
                                        "force", unit_system),
            pendant_line_type=_get_str(att, "pendantLineType"),
            pendant_diameter=_parse_q(att.get("pendantDiameter"),
                                      "diameter", unit_system),
            pendant_segments=pendant_segments or None,
        )
        if position_s is not None:
            common_kwargs["position_s_from_anchor"] = position_s
        elif isinstance(position_idx, int) and position_idx >= 0:
            common_kwargs["position_index"] = position_idx

        if kind == "ahv":
            common_kwargs["ahv_bollard_pull"] = _parse_q(
                att.get("bollardPull"), "force", unit_system,
            )
            common_kwargs["ahv_heading_deg"] = _get_heading(att, "heading")
        else:
            common_kwargs["submerged_force"] = (
                _parse_q(att.get("submergedForce"), "force", unit_system) or 0.0
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


def _parse_buoys_as_attachments(
    profile: dict[str, Any],
    line_idx: int, prof_idx: int,
    log: list[dict[str, Any]],
    unit_system: str,
) -> list[LineAttachment]:
    """
    Converte `profile.buoys[]` (formato real QMoor 0.8.0) em
    `LineAttachment(kind="buoy")`.

    Diferenças vs `attachments[]`:
      - Posição em `distFromEnd` (m) — distância da âncora.
      - Pesos em `weightInAir` (te = tonelada-força).
      - Pendant em `buoy.pennantLine.segments[]` (não `pendant_segments`).

    submerged_force é estimado quando possível via dimensões + endType
    usando `compute_submerged_force` (Excel R4-R7, Fase 6); senão
    fallback para weightInAir como aproximação.
    """
    raw = profile.get("buoys") or []
    if not isinstance(raw, list):
        return []
    out: list[LineAttachment] = []
    for i, buoy in enumerate(raw):
        if not isinstance(buoy, dict):
            continue
        # `distFromEnd` em QMoor 0.8.0 = distância do FAIRLEAD (start)
        # de acordo com a convenção observada no KAR006 (boia em
        # 1088 m com linha total ~1883 m, o que casa com posição no
        # wire central acessada do fairlead). AncoPlat usa
        # `position_s_from_anchor` — convertemos abaixo no
        # _build_case_from_profile com base no comprimento total.
        # Por enquanto guardamos como `dist_from_fairlead` num campo
        # auxiliar; a normalização final fica para após termos os
        # segments parseados.
        dist_from_fl = _parse_q(buoy.get("distFromEnd"), "length", unit_system)
        if dist_from_fl is None:
            log.append({
                "field": f"profiles[{line_idx}.{prof_idx}].buoys[{i}]",
                "old": None, "new": "skipped",
                "reason": "boia sem distFromEnd válido.",
            })
            continue

        diameter = _parse_q(buoy.get("diameter"), "diameter", unit_system)
        length_m = _parse_q(buoy.get("length"), "length", unit_system)
        end_type_raw = (_get_str(buoy, "endType") or "").lower()
        end_type_norm = {
            "elliptical": "elliptical",
            "flat": "flat",
            "hemispherical": "hemispherical",
            "semi_conical": "semi_conical",
            "semiconical": "semi_conical",
        }.get(end_type_raw)

        weight_in_air_n = _parse_q(buoy.get("weightInAir"), "force", unit_system)

        # Tenta computar empuxo líquido (volume × ρ × g − peso_no_ar)
        # usando o helper já implementado em buoyancy.py.
        submerged_n: Optional[float] = None
        if diameter and length_m and end_type_norm and weight_in_air_n is not None:
            try:
                from backend.api.services.buoyancy import compute_submerged_force
                submerged_n = compute_submerged_force(
                    outer_diameter=diameter,
                    length=length_m,
                    end_type=end_type_norm,
                    weight_in_air=weight_in_air_n,
                    seawater_density=1025.0,
                )
            except Exception as exc:
                log.append({
                    "field": f"profiles[{line_idx}.{prof_idx}].buoys[{i}].submerged_force",
                    "old": None, "new": "fallback",
                    "reason": f"compute_submerged_force falhou: {exc}",
                })
        if submerged_n is None or submerged_n <= 0:
            # Fallback conservador: usa o peso no ar como magnitude
            # aproximada (valor positivo sentinel para passar validação).
            submerged_n = max(weight_in_air_n or 0.0, 1.0)

        pennant = buoy.get("pennantLine") or {}
        pendant_segments = _parse_pennant_line_segments(
            pennant, log, line_idx, prof_idx, i, unit_system,
        )

        # Conversão `dist_from_fairlead` → `position_s_from_anchor`:
        # precisamos do comprimento total dos segments. Buscamos aqui
        # mesmo (caller já parseou os mesmos segments antes).
        total_len = _sum_segment_lengths(profile, unit_system)
        if total_len is None or total_len <= dist_from_fl:
            # Sem total ou boia além do final da linha — log + pula
            log.append({
                "field": f"profiles[{line_idx}.{prof_idx}].buoys[{i}].distFromEnd",
                "old": dist_from_fl, "new": "skipped",
                "reason": "distFromEnd inválido vs comprimento total.",
            })
            continue
        position_s = total_len - dist_from_fl  # arc length da âncora
        if position_s <= 0 or position_s >= total_len:
            log.append({
                "field": f"profiles[{line_idx}.{prof_idx}].buoys[{i}]",
                "old": position_s, "new": "skipped",
                "reason": "posição fora de (0, L_total).",
            })
            continue

        try:
            out.append(LineAttachment(
                kind="buoy",
                submerged_force=submerged_n,
                position_s_from_anchor=position_s,
                name=_get_str(buoy, "name_id") or _get_str(buoy, "name"),
                buoy_type=(buoy.get("buoyType") or "").lower() or None,
                buoy_end_type=end_type_norm,
                buoy_outer_diameter=diameter,
                buoy_length=length_m,
                buoy_weight_in_air=weight_in_air_n,
                pendant_segments=pendant_segments or None,
            ))
        except (ValueError, TypeError) as e:
            log.append({
                "field": f"profiles[{line_idx}.{prof_idx}].buoys[{i}]",
                "old": _get_str(buoy, "name_id"),
                "new": "skipped",
                "reason": f"validação falhou: {e}",
            })
    return out


def _parse_clumps_as_attachments(
    profile: dict[str, Any],
    line_idx: int, prof_idx: int,
    log: list[dict[str, Any]],
    unit_system: str,
) -> list[LineAttachment]:
    """Espelho de _parse_buoys_as_attachments para `profile.clumps[]`.

    Estrutura QMoor é idêntica à de boias; só difere o `kind` do
    `LineAttachment` e a interpretação do peso (clump puxa a linha
    PARA BAIXO, então submerged_force ≈ weight_in_air).
    """
    raw = profile.get("clumps") or []
    if not isinstance(raw, list) or not raw:
        return []
    out: list[LineAttachment] = []
    for i, clump in enumerate(raw):
        if not isinstance(clump, dict):
            continue
        dist_from_fl = _parse_q(
            clump.get("distFromEnd"), "length", unit_system,
        )
        if dist_from_fl is None:
            continue
        weight_in_air_n = _parse_q(
            clump.get("weightInAir"), "force", unit_system,
        )
        if weight_in_air_n is None or weight_in_air_n <= 0:
            log.append({
                "field": f"profiles[{line_idx}.{prof_idx}].clumps[{i}]",
                "old": None, "new": "skipped",
                "reason": "clump sem weightInAir > 0.",
            })
            continue
        total_len = _sum_segment_lengths(profile, unit_system)
        if total_len is None or total_len <= dist_from_fl:
            continue
        position_s = total_len - dist_from_fl
        if position_s <= 0 or position_s >= total_len:
            continue
        pennant = clump.get("pennantLine") or {}
        pendant_segments = _parse_pennant_line_segments(
            pennant, log, line_idx, prof_idx, i, unit_system,
        )
        try:
            out.append(LineAttachment(
                kind="clump_weight",
                submerged_force=weight_in_air_n,
                position_s_from_anchor=position_s,
                name=_get_str(clump, "name_id") or _get_str(clump, "name"),
                pendant_segments=pendant_segments or None,
            ))
        except (ValueError, TypeError) as e:
            log.append({
                "field": f"profiles[{line_idx}.{prof_idx}].clumps[{i}]",
                "old": _get_str(clump, "name_id"),
                "new": "skipped",
                "reason": f"validação falhou: {e}",
            })
    return out


def _sum_segment_lengths(
    profile: dict[str, Any], unit_system: str,
) -> Optional[float]:
    """Soma length de todos os segments válidos do profile, em metros."""
    raw = profile.get("segments") or []
    if not isinstance(raw, list) or not raw:
        return None
    total = 0.0
    for seg in raw:
        if not isinstance(seg, dict):
            continue
        length = _parse_q(seg.get("length"), "length", unit_system)
        if length and length > 0:
            total += length
    return total if total > 0 else None


def _parse_pennant_line_segments(
    pennant: dict[str, Any],
    log: list[dict[str, Any]],
    line_idx: int, prof_idx: int, att_idx: int,
    unit_system: str,
) -> list[PendantSegment]:
    """Extrai segments do `pennantLine` (formato QMoor real)."""
    if not isinstance(pennant, dict):
        return []
    segs = pennant.get("segments") or []
    if not isinstance(segs, list) or not segs:
        return []
    out: list[PendantSegment] = []
    for j, ps in enumerate(segs):
        if not isinstance(ps, dict):
            continue
        length = _parse_q(ps.get("length"), "length", unit_system)
        if length is None or length <= 0:
            continue
        # Drill em lineProps (QMoor real) ou top-level (sintético).
        try:
            out.append(PendantSegment(
                length=length,
                line_type=_seg_str(ps, ["lineType", "line_type"]),
                category=_parse_category(_seg_str(ps, ["category"])),
                diameter=_seg_q(ps, ["diameter"], "diameter", unit_system),
                w=_seg_q(ps, ["wetWeight", "submergedWeight", "w"],
                         "weight_per_length", unit_system),
                dry_weight=_seg_q(ps, ["dryWeight"],
                                  "weight_per_length", unit_system),
                EA=_seg_q(ps, ["qmoorEA", "gmoorEA", "EA", "ea"],
                          "force", unit_system),
                MBL=_seg_q(ps, ["breakStrength", "MBL"],
                           "force", unit_system),
                material_label=_get_str(ps, "name")
                              or _get_str(ps, "materialLabel"),
            ))
            if len(out) >= 5:
                break
        except (ValueError, TypeError) as e:
            log.append({
                "field": (f"profiles[{line_idx}.{prof_idx}]"
                          f".buoys[{att_idx}].pennantLine.segments[{j}]"),
                "old": None, "new": "skipped",
                "reason": f"validação falhou: {e}",
            })
    return out


def _parse_pendant_segments(
    att: dict[str, Any], log: list[dict[str, Any]],
    line_idx: int, prof_idx: int, att_idx: int,
    unit_system: str = "metric",
) -> list[PendantSegment]:
    raw = att.get("pendantSegments") or att.get("pendant_segments")
    if not isinstance(raw, list) or not raw:
        return []
    out: list[PendantSegment] = []
    for j, ps in enumerate(raw):
        if not isinstance(ps, dict):
            continue
        length = _parse_q(ps.get("length"), "length", unit_system)
        if length is None or length <= 0:
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
                line_type=_seg_str(ps, ["lineType", "line_type"]),
                category=_parse_category(_seg_str(ps, ["category"])),
                diameter=_seg_q(ps, ["diameter"], "diameter", unit_system),
                w=_seg_q(ps, ["wetWeight", "w"],
                         "weight_per_length", unit_system),
                dry_weight=_seg_q(ps, ["dryWeight"],
                                  "weight_per_length", unit_system),
                EA=_seg_q(ps, ["qmoorEA", "gmoorEA", "EA", "ea"],
                          "force", unit_system),
                MBL=_seg_q(ps, ["breakStrength", "MBL"],
                           "force", unit_system),
                material_label=_get_str(ps, "materialLabel"),
            ))
            if len(out) == 5:
                break
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
    unit_system: str = "metric",
) -> BoundaryConditions:
    bd = profile.get("boundary") or {}
    if not isinstance(bd, dict):
        bd = {}

    # `startpointDepth` no QMoor 0.8.0 = profundidade da água sob o
    # fairlead (= profundidade total se fairlead-on-surface). O nosso `h`
    # é a profundidade do seabed sob a âncora — usamos `endpointDepth`
    # como referência primária quando disponível, com fallback para
    # `startpointDepth`/`waterDepth` quando ausente.
    h = (_parse_q(bd.get("endpointDepth"), "length", unit_system)
         or _parse_q(bd.get("startpointDepth"), "length", unit_system)
         or _parse_q(bd.get("h"), "length", unit_system)
         or _parse_q(bd.get("waterDepth"), "length", unit_system)
         or _parse_q(bd.get("depth"), "length", unit_system)
         or _parse_q(line.get("waterDepth"), "length", unit_system))
    if h is None or h <= 0:
        raise QMoorV08ParseError(
            f"profile[{line_idx}.{prof_idx}].boundary sem profundidade."
        )

    # `inputParam` é o nome canônico do QMoor; sinônimo do `mode`.
    mode_raw = (_get_str(profile.get("solution") or {}, "inputParam")
                or _get_str(bd, "mode")
                or "Tension").lower()
    sol = profile.get("solution") or {}
    if isinstance(sol, dict) and mode_raw in ("tension", "fairlead", "fl"):
        mode = SolutionMode.TENSION
        input_value = (
            _parse_q(sol.get("fairleadTension"), "force", unit_system)
            or _parse_q(bd.get("fairleadTension"), "force", unit_system)
            or _parse_q(bd.get("tension"), "force", unit_system)
            or _parse_q(bd.get("T_fl"), "force", unit_system)
            or _parse_q(bd.get("input_value"), "force", unit_system)
        )
    else:
        mode = SolutionMode.RANGE
        input_value = (
            _parse_q(bd.get("horzDistance"), "length", unit_system)
            or (_parse_q(sol.get("rangeToAnchor"), "length", unit_system)
                if isinstance(sol, dict) else None)
            or _parse_q(bd.get("range"), "length", unit_system)
            or _parse_q(bd.get("input_value"), "length", unit_system)
        )
    if input_value is None or input_value <= 0:
        raise QMoorV08ParseError(
            f"profile[{line_idx}.{prof_idx}].boundary sem input_value."
        )

    # Convenção QMoor 0.8.0:
    #   - `startpointDepth` = lâmina d'água sob o FAIRLEAD column.
    #   - `endpointDepth`   = lâmina d'água sob o ANCHOR column.
    # São BATHYMETRY readings, NÃO posição vertical do fairlead/anchor.
    # Para "Semi-Sub Fairlead" e "AHV" (os tipos que aparecem em
    # mooring estático), o fairlead está SEMPRE na superfície (y=0).
    # MVP v1 do AncoPlat trata startpoint_depth=0 nessa convenção.
    sd = 0.0

    return BoundaryConditions(
        h=h,
        mode=mode,
        input_value=input_value,
        startpoint_depth=sd,
        endpoint_grounded=bool(bd.get("endpointGrounded", True)),
    )


def _parse_seabed(
    profile: dict[str, Any], line: dict[str, Any],
    unit_system: str = "metric",
) -> SeabedConfig:
    sb = profile.get("seabed") or line.get("seabed") or {}
    if not isinstance(sb, dict):
        sb = {}
    mu = sb.get("mu")
    mu_val = 0.0
    if mu is not None:
        try:
            mu_val = float(mu)
        except (ValueError, TypeError):
            mu_val = 0.0

    # QMoor 0.8.0 não tem campo `slope_rad` explícito, mas a diferença
    # entre `boundary.startpointDepth` (lâmina sob fairlead) e
    # `boundary.endpointDepth` (lâmina sob anchor) define a inclinação
    # do seabed entre os dois pontos. tan(slope) = Δh / horzDist.
    # Convenção AncoPlat: slope_rad > 0 quando seabed sobe da âncora
    # em direção ao fairlead (anchor mais fundo que fairlead).
    slope_rad = 0.0
    bd = profile.get("boundary")
    if isinstance(bd, dict):
        sp_depth = _parse_q(bd.get("startpointDepth"), "length", unit_system)
        ep_depth = _parse_q(bd.get("endpointDepth"), "length", unit_system)
        horz = _parse_q(bd.get("horzDistance"), "length", unit_system)
        if sp_depth and ep_depth and horz and horz > 1.0:
            # delta > 0 quando anchor mais fundo que fairlead → seabed
            # sobe em direção ao fairlead → slope POSITIVO em nossa
            # convenção (radians).
            delta = ep_depth - sp_depth
            slope_rad = math.atan2(delta, horz)

    try:
        return SeabedConfig(mu=mu_val, slope_rad=slope_rad)
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

    Aceita variantes: "Wire", "wire", "wire_rope", "WireRope",
    "StuddedChain", "studded_chain", "studdedchain", "studded", etc.
    """
    if not value:
        return None
    v = value.strip().lower()
    aliases: dict[str, LineCategory] = {
        "wire": "Wire", "wire_rope": "Wire", "wirerope": "Wire",
        "studded": "StuddedChain",
        "studded_chain": "StuddedChain",
        "studdedchain": "StuddedChain",  # PascalCase lowered
        "studless": "StudlessChain",
        "studless_chain": "StudlessChain",
        "studlesschain": "StudlessChain",  # PascalCase lowered
        "polyester": "Polyester", "poly": "Polyester",
        "rope": "Polyester", "synthetic": "Polyester",
    }
    return aliases.get(v)


__all__ = [
    "QMoorV08ParseError",
    "parse_qmoor_v0_8",
]
