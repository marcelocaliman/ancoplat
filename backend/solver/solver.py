"""
Camada 5/6 — Fachada pública do solver AncoPlat.

Unifica todas as camadas anteriores (catenária rígida, seabed no-friction,
atrito de Coulomb, correção elástica) em uma única função de entrada que
aceita as estruturas Pydantic de alto nível:

  solve(line_segments, boundary, seabed, config, criteria_profile, user_limits)
    -> SolverResult

Despacha para solve_elastic_iterative, que por sua vez usa o dispatch
rígido-suspenso vs touchdown em solve_rigid_suspended.

O MVP v1 suporta UMA linha homogênea (um LineSegment). Multi-segmento
fica para v2.1 conforme Seção 9 do Documento A v2.2.
"""
from __future__ import annotations

import math
from typing import Optional, Sequence

from . import SOLVER_VERSION
from .attachment_resolver import resolve_attachments
from .diagnostics import (
    D004_buoy_above_surface,
    D006_cable_too_short,
    D008_safety_margin,
    D009_anchor_uplift_high,
    D010_high_utilization,
    D011_cable_below_seabed,
    D900_generic_nonconvergence,
    SolverDiagnostic,
    diagnostic_from_exception,
)
from .elastic import solve_elastic_iterative
from .laid_line import solve_laid_line
from .multi_segment import solve_multi_segment
from .seabed_sloped import solve_sloped_seabed_single_segment
from .types import (
    PROFILE_LIMITS,
    AlertLevel,
    BoundaryConditions,
    ConvergenceStatus,
    CriteriaProfile,
    LineAttachment,
    LineSegment,
    SeabedConfig,
    SolutionMode,
    SolverConfig,
    SolverResult,
    UtilizationLimits,
    classify_utilization,
)


def _resolve_mu_per_seg(
    line_segments: Sequence[LineSegment],
    seabed: SeabedConfig,
) -> list[float]:
    """
    Resolve o coeficiente de atrito efetivo de CADA segmento aplicando a
    precedência canônica da Fase 1 do plano de profissionalização.

    Precedência (mais específico → mais geral):

        1. ``segment.mu_override``    — override explícito do usuário no segmento
        2. ``segment.seabed_friction_cf`` — valor do catálogo (line_type)
        3. ``seabed.mu``              — valor global do caso (default 0.0)
        4. ``0.0``                    — fallback final (sem atrito)

    Cada nível só é consultado se o anterior for ``None``. Defaults
    ``None`` em ambos `mu_override` e `seabed_friction_cf` preservam o
    comportamento legado (cai em ``seabed.mu`` global), garantindo
    retro-compatibilidade com cases salvos antes da Fase 1 — esta é
    decisão consciente em substituição à feature-flag
    ``use_per_segment_friction`` originalmente prevista no plano.

    Retorna lista de floats com mesma cardinalidade de ``line_segments``.

    Garantia: cada elemento é >= 0.0 (validador Pydantic do LineSegment
    e SeabedConfig já enforça isto).
    """
    out: list[float] = []
    for seg in line_segments:
        if seg.mu_override is not None:
            out.append(seg.mu_override)
        elif seg.seabed_friction_cf is not None:
            out.append(seg.seabed_friction_cf)
        else:
            out.append(seabed.mu)
    return out


def _validate_inputs(
    line_segments: Sequence[LineSegment],
    boundary: BoundaryConditions,
    seabed: SeabedConfig,
    config: SolverConfig,
) -> LineSegment:
    """Valida entradas e retorna o segmento único (MVP v1).

    Categorização dos `raise` desta função (Fase 2 / E4):
      (a) fisicamente justificada — guard físico que mantém o domínio do solver.
      (b) defensiva — duplica garantia já dada pelo Pydantic ou camada superior.
      (c) numérica — erro de convergência/bracket.
    """
    # (a) Fisicamente justificada: solver precisa de pelo menos um segmento.
    if not line_segments:
        raise ValueError(
            "segments: lista vazia recebida; esperado pelo menos 1 segmento. "
            "Verifique que segments[] no CaseInput não está vazio."
        )
    # (b) Defensiva: Pydantic LineSegment já enforça `length>0, EA>0, MBL>0, w>0`
    # via @field_validator. Mantemos como rede de segurança caso o solver seja
    # chamado fora da rota API (testes diretos, scripts).
    for i, s in enumerate(line_segments):
        if s.length <= 0 or s.EA <= 0 or s.MBL <= 0 or s.w <= 0:
            raise ValueError(
                f"segments[{i}]: grandeza não-positiva detectada "
                f"(length={s.length}, w={s.w}, EA={s.EA}, MBL={s.MBL}); "
                "esperado todas > 0. Pydantic deveria ter rejeitado antes — "
                "verifique se LineSegment foi construído via model_validate."
            )
    # Despacho single vs multi acontece em solve(): aqui retornamos o
    # primeiro segmento como conveniência para o caso single (mantém o
    # contrato anterior de _validate_inputs).
    segment = line_segments[0]
    # (a) Fisicamente justificada: h é a profundidade do seabed sob a âncora.
    # h=0 implicaria âncora na superfície — caso degenerado fora do escopo.
    if boundary.h <= 0:
        raise ValueError(
            f"boundary.h (water_depth_at_anchor): valor recebido={boundary.h:.2f} m; "
            "esperado > 0. Especifique a profundidade do seabed sob a âncora."
        )
    # (a) Fisicamente justificada: T_fl/X positivos definem boundary condition
    # válida. T_fl=0 (linha frouxa absoluta) e X=0 (fairlead sobre a âncora)
    # são casos degenerados que exigem lógica especial.
    if boundary.input_value <= 0:
        raise ValueError(
            f"boundary.input_value: valor recebido={boundary.input_value:.2f} "
            f"({'T_fl' if boundary.mode == SolutionMode.TENSION else 'X'}); "
            "esperado > 0. T_fl=0 (frouxa) ou X=0 (fairlead sobre âncora) "
            "são casos degenerados não suportados."
        )
    # (a) Fisicamente justificada: atrito de Coulomb por definição é μ ≥ 0.
    # Pydantic SeabedConfig também enforça via Field(ge=0).
    if seabed.mu < 0:
        raise ValueError(
            f"seabed.mu: valor recebido={seabed.mu}; esperado >= 0. "
            "Coeficiente de atrito de Coulomb não pode ser negativo."
        )
    # (b) Defensiva: o Pydantic SolutionMode (Enum) já garante este invariante.
    # Mantemos por simetria com tratamento textual em logs/diagnostics.
    if boundary.mode not in (SolutionMode.TENSION, SolutionMode.RANGE):
        raise ValueError(f"modo inválido: {boundary.mode}")
    # (a) Fase 7: anchor uplift é suportado para single-segment SEM
    # attachments. Multi-segmento ou attachments combinado com uplift
    # ainda não — fica para F7.x. Aqui o guard só barra essas combinações;
    # o caminho válido (single + sem-attachments + uplift) NÃO levanta —
    # o dispatcher no facade solve() chama suspended_endpoint.
    if not boundary.endpoint_grounded:
        if len(line_segments) > 1:
            raise NotImplementedError(
                "Anchor uplift (endpoint_grounded=False) com multi-segmento "
                "ainda não suportado (Fase 7 cobriu single-segment apenas; "
                "multi-segmento + uplift fica para F7.x). Use 1 segmento ou "
                "endpoint_grounded=True."
            )
    # (a) Fisicamente justificada: fairlead no ou abaixo do seabed é inviável.
    # Em seabed inclinado, a profundidade do seabed SOB O FAIRLEAD difere
    # de h (= prof. sob a âncora) — depende de slope_rad e da distância
    # horizontal. Q7 da Fase 2: validar contra `h_at_fairlead` (calculado
    # com slope), não contra `h` plano.
    h_at_fairlead = boundary.h - math.tan(seabed.slope_rad) * _x_estimate(
        line_segments, boundary,
    )
    if boundary.startpoint_depth >= h_at_fairlead + 1e-9:
        raise ValueError(
            f"startpoint_depth={boundary.startpoint_depth:.2f} m >= "
            f"h_at_fairlead={h_at_fairlead:.2f} m "
            f"(h={boundary.h:.2f} m, slope={math.degrees(seabed.slope_rad):.2f}°, "
            f"X_est={_x_estimate(line_segments, boundary):.1f} m): "
            "fairlead no ou abaixo do seabed sob ele é inviável. "
            "Verifique geometria — possível X grande demais ou inversão "
            "de sinal no slope (slope > 0 = seabed sobe ao fairlead)."
        )
    return segment


def _x_estimate(
    line_segments: Sequence[LineSegment],
    boundary: BoundaryConditions,
) -> float:
    """
    Estimativa conservadora de X (distância horizontal âncora → fairlead)
    para validar `startpoint_depth` em seabed inclinado (Q7 da Fase 2).

    Estratégia (mais específico → mais geral):
      1. Modo Range: `boundary.input_value` JÁ é o X target — usa direto.
      2. Modo Tension: upper-bound conservador é Σ L_segments (linha
         taut, X ≤ comprimento total). Garante que a validação falhe
         FECHADA — só rejeita quando geometria é impossível para
         qualquer X ≤ L_total razoável.

    A elasticidade pode esticar a linha em até ~5% (validador de strain
    no multi_segment.py); o upper-bound usa `length` (unstretched), aceitando
    pequena conservadorismo em vez de chamar o solver elástico aqui.
    """
    if boundary.mode == SolutionMode.RANGE:
        return float(boundary.input_value)
    return sum(s.length for s in line_segments)


def _broken_ratio(
    profile: CriteriaProfile, user_limits: Optional[UtilizationLimits]
) -> float:
    """Helper: broken_ratio efetivo do perfil corrente (para mensagens)."""
    if profile == CriteriaProfile.USER_DEFINED and user_limits is not None:
        return user_limits.broken_ratio
    return PROFILE_LIMITS[profile].broken_ratio


def solve(
    line_segments: Sequence[LineSegment],
    boundary: BoundaryConditions,
    seabed: SeabedConfig | None = None,
    config: SolverConfig | None = None,
    criteria_profile: CriteriaProfile = CriteriaProfile.MVP_PRELIMINARY,
    user_limits: Optional[UtilizationLimits] = None,
    attachments: Sequence[LineAttachment] = (),
) -> SolverResult:
    """
    Executa o solver completo para uma linha isolada.

    Parâmetros
    ----------
    line_segments : lista com UM LineSegment (MVP v1 é homogêneo).
    boundary : condições de contorno (h, modo, input_value).
    seabed : configuração do seabed (μ). Default μ=0.
    config : tolerâncias e max iter. Default SolverConfig().
    criteria_profile : perfil de classificação T_fl/MBL (Seção 5 Documento A).
                       Default MVP_Preliminary (0.50 yellow / 0.60 red / 1.00 broken).
    user_limits : obrigatório se criteria_profile == USER_DEFINED.

    Retorna
    -------
    SolverResult — todos os campos da Seção 6 do MVP v2, incluindo
    status de convergência, geometria, tensões, ângulos, utilization
    e `alert_level` (ok | yellow | red | broken).

    Em caso de erro de validação ou caso fisicamente impossível, captura
    a exceção e devolve um SolverResult com status=INVALID_CASE e mensagem
    descritiva (em vez de propagar).
    """
    if seabed is None:
        seabed = SeabedConfig()
    if config is None:
        config = SolverConfig()

    try:
        segment = _validate_inputs(line_segments, boundary, seabed, config)
    except (ValueError, NotImplementedError) as exc:
        return SolverResult(
            status=ConvergenceStatus.INVALID_CASE,
            message=f"Validação falhou: {exc}",
            water_depth=boundary.h,
            startpoint_depth=boundary.startpoint_depth,
            solver_version=SOLVER_VERSION,
        )

    # F5.4.6a — Resolve attachments com posição contínua.
    # Pré-processador divide o segmento que contém um
    # `position_s_from_anchor` em dois sub-segmentos idênticos, virando
    # o attachment numa "junção virtual". O solver downstream nunca sabe
    # que houve split. Attachments via `position_index` (legacy) passam
    # intactos.
    try:
        resolved_segments, resolved_attachments = resolve_attachments(
            line_segments, attachments,
        )
    except ValueError as exc:
        return SolverResult(
            status=ConvergenceStatus.INVALID_CASE,
            message=f"Attachment inválido: {exc}",
            water_depth=boundary.h,
            startpoint_depth=boundary.startpoint_depth,
            solver_version=SOLVER_VERSION,
        )

    # Drop vertical efetivo: distância entre a âncora (no seabed, y=-h)
    # e o fairlead (submerso a profundidade startpoint_depth da superfície).
    # Quando startpoint_depth = 0 (fairlead na superfície), drop = h.
    h_drop = boundary.h - boundary.startpoint_depth

    # Resolve μ por segmento (Fase 1 / B3). Helper centralizado documenta
    # a precedência: mu_override → seabed_friction_cf → seabed.mu → 0.
    # Aplicado APÓS resolve_attachments para que sub-segmentos gerados
    # pelo split de attachment herdem o μ corretamente (model_copy
    # preserva mu_override e seabed_friction_cf).
    mu_per_seg = _resolve_mu_per_seg(resolved_segments, seabed)
    # μ efetivo do primeiro segmento (segmento 0 — em contato com o
    # seabed na zona grounded). Single-segment paths usam este valor;
    # multi-segment recebe a lista completa.
    mu_seg0 = mu_per_seg[0] if mu_per_seg else seabed.mu

    try:
        n_segments = len(resolved_segments)
        slope = seabed.slope_rad
        slope_is_significant = abs(slope) > 1e-6

        # ─── Sprint 5 — Dispatcher Tier D (AHV operacional mid-line) ──
        # Quando algum attachment tem `ahv_work_wire` populado, delega
        # para `solve_with_ahv_operational` (pre-processor 2-pass com
        # refinamento iterativo). Tier D é PRIORITÁRIO sobre Tier C
        # (instalação) — ambos usam ww mas em contextos diferentes.
        from .ahv_operational import (
            has_tier_d_attachment as _has_tier_d,
            solve_with_ahv_operational as _solve_tier_d,
        )
        if _has_tier_d(resolved_attachments):
            return _solve_tier_d(
                line_segments=resolved_segments,
                boundary=boundary,
                attachments=resolved_attachments,
                seabed=seabed,
                config=config,
                criteria_profile=criteria_profile,
                user_limits=user_limits,
            )

        # ─── Sprint 4 — Dispatcher Tier C (AHV + Work Wire físico) ────
        # Quando boundary.ahv_install.work_wire está populado, delega
        # para `solve_with_work_wire` (catenárias acopladas via fsolve).
        # Comportamento Sprint 2 (sem work_wire) é preservado: cai pra
        # baixo no caminho normal (mode=Tension com bollard_pull como
        # T_fl). Validação de pré-condições acontece dentro do helper.
        ahv_install_obj = boundary.ahv_install
        if (
            ahv_install_obj is not None
            and ahv_install_obj.work_wire is not None
        ):
            from .ahv_work_wire import solve_with_work_wire
            result = solve_with_work_wire(
                line_segments=resolved_segments,
                boundary=boundary,
                seabed=seabed,
                config=config,
                criteria_profile=criteria_profile,
                user_limits=user_limits,
                attachments=resolved_attachments,
            )
        # ─── Fase 7 — Dispatcher de anchor uplift ─────────────────────
        # Single-segment SEM attachments + endpoint_grounded=False:
        # delega para suspended_endpoint.solve_suspended_endpoint().
        # Multi-seg + uplift já barrado por _validate_inputs (raise).
        # Attachments + uplift barrado aqui com mensagem clara.
        elif not boundary.endpoint_grounded:
            if resolved_attachments:
                # Fase 8: mensagem cobre AHV explicitamente (Q5: AHV +
                # uplift bloqueado em v1.0).
                # Sprint 7 / Commit 60: mensagem ATUALIZADA para citar
                # caminhos específicos. Tier D + uplift = F7.x.y (v1.5+).
                kinds_present = {att.kind for att in resolved_attachments}
                kinds_str = ", ".join(sorted(kinds_present))
                tier_d_count = sum(
                    1 for a in resolved_attachments
                    if a.kind == "ahv" and a.ahv_work_wire is not None
                )
                tier_d_note = ""
                if tier_d_count > 0:
                    tier_d_note = (
                        f" Caso inclui {tier_d_count} attachment(s) Tier D "
                        "(ahv_work_wire set) — combinação Tier D + uplift "
                        "requer F7.x.y (extensão de suspended_endpoint para "
                        "aceitar force injection mid-line). Pendência v1.5+."
                    )
                raise NotImplementedError(
                    f"Anchor uplift (endpoint_grounded=False) com "
                    f"attachments ({kinds_str}) ainda não suportado em "
                    "v1.0-1.4. Caso requer modelagem multi-segmento + uplift "
                    f"+ attachments combinados (F7.x).{tier_d_note} "
                    "Remova attachments ou use endpoint_grounded=True."
                )
            from .suspended_endpoint import solve_suspended_endpoint
            result = solve_suspended_endpoint(
                segment=resolved_segments[0],
                boundary=boundary,
                seabed=seabed,
                config=config,
            )
        # F5.3.y: attachments + slope agora suportados via integrador
        # com grounded estendido para aplicar saltos em V nas junções.
        elif n_segments > 1 or resolved_attachments:
            # Linha composta heterogênea (F5.1) ou com attachments (F5.2).
            # F5.4.6a: para ter ≥ 2 segmentos pós-resolver, ou o usuário
            # já passou multi-segmento, ou usou `position_s_from_anchor`
            # que disparou split. Attachment com `position_index` em
            # linha de 1 segmento não faz sentido (pego pelo Pydantic
            # range validator com max_position_index = N-2).
            result = solve_multi_segment(
                segments=resolved_segments,
                h=h_drop,
                mode=boundary.mode,
                input_value=boundary.input_value,
                mu=mu_seg0,  # μ no trecho grounded (sempre o segmento 0)
                config=config,
                attachments=resolved_attachments,
                slope_rad=slope,
                mu_per_seg=mu_per_seg,  # Fase 1: per-seg disponível p/ futuro
            )
        elif slope_is_significant:
            # F5.3 completa: single-segmento em rampa.
            #
            # Despacho:
            # - Fully-suspended (T_fl ≥ T_crit_horizontal): linha não toca
            #   o seabed; cálculo idêntico ao horizontal.
            # - Touchdown (T_fl < T_crit_horizontal): solver específico
            #   `solve_sloped_seabed_single_segment` com atrito modificado
            #   na rampa.
            from .seabed import (
                critical_range_for_touchdown,
                critical_tension_for_touchdown,
            )

            if boundary.mode == SolutionMode.TENSION:
                T_crit = critical_tension_for_touchdown(
                    segment.length, h_drop, segment.w,
                )
                if boundary.input_value >= T_crit:
                    # Fully suspended: usa solver horizontal (slope só visual)
                    result = solve_elastic_iterative(
                        L=segment.length, h=h_drop, w=segment.w, EA=segment.EA,
                        mode=boundary.mode, input_value=boundary.input_value,
                        config=config, mu=mu_seg0, MBL=segment.MBL,
                    )
                else:
                    # Touchdown em rampa
                    result = solve_sloped_seabed_single_segment(
                        L=segment.length, h=h_drop, w=segment.w, EA=segment.EA,
                        mode=boundary.mode, input_value=boundary.input_value,
                        mu=mu_seg0, slope_rad=slope, MBL=segment.MBL,
                        config=config,
                    )
            elif boundary.mode == SolutionMode.RANGE:
                X_crit = critical_range_for_touchdown(segment.length, h_drop)
                if boundary.input_value >= X_crit:
                    # Fully suspended em modo Range
                    result = solve_elastic_iterative(
                        L=segment.length, h=h_drop, w=segment.w, EA=segment.EA,
                        mode=boundary.mode, input_value=boundary.input_value,
                        config=config, mu=mu_seg0, MBL=segment.MBL,
                    )
                else:
                    # Touchdown em rampa, modo Range
                    result = solve_sloped_seabed_single_segment(
                        L=segment.length, h=h_drop, w=segment.w, EA=segment.EA,
                        mode=boundary.mode, input_value=boundary.input_value,
                        mu=mu_seg0, slope_rad=slope, MBL=segment.MBL,
                        config=config,
                    )
            else:
                # (b) Defensiva: este else é unreachable em prática
                # (boundary.mode é Enum SolutionMode, validado pelo
                # Pydantic). Mantemos por consistência sintática do match.
                raise ValueError(f"modo inválido: {boundary.mode}")
        elif h_drop <= 1e-6:
            # Caso degenerado: fairlead e âncora no mesmo nível (ambos no fundo).
            # Sem catenária — linha horizontal no seabed, só atrito + elasticidade.
            result = solve_laid_line(
                L=segment.length,
                w=segment.w,
                EA=segment.EA,
                mode=boundary.mode,
                input_value=boundary.input_value,
                mu=mu_seg0,
                MBL=segment.MBL,
                config=config,
            )
        else:
            result = solve_elastic_iterative(
                L=segment.length,
                h=h_drop,
                w=segment.w,
                EA=segment.EA,
                mode=boundary.mode,
                input_value=boundary.input_value,
                config=config,
                mu=mu_seg0,
                MBL=segment.MBL,
            )
    except NotImplementedError as exc:
        # Fase 7: feature não-suportada (multi-seg + uplift, attachments
        # + uplift). Retorna INVALID_CASE com mensagem clara em vez de
        # propagar — UI mostra ao engenheiro que combinação não é
        # suportada e como contornar.
        return SolverResult(
            status=ConvergenceStatus.INVALID_CASE,
            message=str(exc),
            water_depth=boundary.h,
            startpoint_depth=boundary.startpoint_depth,
            endpoint_depth=boundary.endpoint_depth or boundary.h,
            solver_version=SOLVER_VERSION,
        )
    except ValueError as exc:
        # Erros físicos previsíveis — F5.7.4 extrai diagnóstico
        # estruturado quando a exceção é SolverDiagnosticError, ou usa
        # heurística texto-base como fallback.
        diag = diagnostic_from_exception(exc)
        if diag is None:
            # Tenta inferir um diagnóstico simples a partir da mensagem
            raw = str(exc)
            if (
                "lâmina d'água" in raw.lower()
                or "linha mais curta" in raw.lower()
                or "fairlead inalcanç" in raw.lower()
            ):
                diag = D006_cable_too_short(
                    cable_length=segment.length,
                    water_depth=boundary.h,
                )
            else:
                diag = D900_generic_nonconvergence(raw_message=raw)
        friendly = _friendly_invalid_message(str(exc), segment, boundary)
        return SolverResult(
            status=ConvergenceStatus.INVALID_CASE,
            message=friendly,
            water_depth=boundary.h,
            startpoint_depth=boundary.startpoint_depth,
            solver_version=SOLVER_VERSION,
            diagnostics=[diag.model_dump()],
        )
    except Exception as exc:  # noqa: BLE001
        # Erros numéricos (overflow, div/0) caem aqui.
        return SolverResult(
            status=ConvergenceStatus.NUMERICAL_ERROR,
            message=(
                f"Erro numérico interno do solver: {exc}. "
                "Tente alterar levemente os parâmetros (ex.: ±1 % no T_fl ou L)."
            ),
            water_depth=boundary.h,
            startpoint_depth=boundary.startpoint_depth,
            solver_version=SOLVER_VERSION,
        )

    # Anexa os parâmetros geométricos globais + versão do solver para o plot
    # reconstruir o sistema de coordenadas surface-relative (superfície em
    # y=0, seabed em y=-water_depth, fairlead em y=-startpoint_depth).
    #
    # Batimetria nos dois pontos: anchor está no seabed sob a sua coluna
    # d'água (depth_at_anchor = boundary.h por convenção). Sob o fairlead,
    # a profundidade do seabed é deslocada por tan(slope)·X_total —
    # quando slope > 0 (sobe ao fairlead), depth_at_fairlead < depth_at_anchor.
    depth_at_fairlead = boundary.h - math.tan(seabed.slope_rad) * result.total_horz_distance

    # F5.4.6b — Anchor uplift severity. Drag anchors (DA / VLA) toleram
    # pouco ângulo de uplift; convencional ≤ 5° "ok", 5°–15° "warning",
    # > 15° "critical". Pilars e suction caissons toleram mais — usuário
    # pode considerar warnings como aceitáveis quando souber o tipo.
    uplift_deg = abs(math.degrees(result.angle_wrt_horz_anchor))
    if uplift_deg <= 5.0:
        uplift_severity = "ok"
    elif uplift_deg <= 15.0:
        uplift_severity = "warning"
    else:
        uplift_severity = "critical"

    # F5.7.3 — detecta boias que ficaram ACIMA da superfície da água.
    # Convenção solver: y=0 na âncora, y=h no fairlead (superfície),
    # com fairlead a startpoint_depth da superfície. Surface y_solver =
    # h - startpoint_depth. Se y_solver_da_boia + tether > surface, a
    # boia "voou" — geometria fisicamente impossível com boia real.
    surface_violations: list[dict] = []
    if (
        result.status == ConvergenceStatus.CONVERGED
        and resolved_attachments
        and result.coords_y
        and result.segment_boundaries
    ):
        surface_y_solver = boundary.h - boundary.startpoint_depth
        for idx, att in enumerate(resolved_attachments):
            if att.kind != "buoy" or att.position_index is None:
                continue
            j = att.position_index + 1  # junção = boundary[position_index + 1]
            if j >= len(result.segment_boundaries):
                continue
            coord_idx = result.segment_boundaries[j]
            if coord_idx >= len(result.coords_y):
                continue
            cable_y = result.coords_y[coord_idx]
            tether = att.tether_length or 0.0
            # Boia: corpo está ACIMA do ponto de attachment pelo
            # comprimento do pendant (convenção da UI). Se o cabo
            # já está acima da superfície, mesmo sem tether o corpo
            # estaria fora da água.
            body_y_solver = cable_y + tether
            height_above = body_y_solver - surface_y_solver
            if height_above > 0.5:  # tolerância de 0.5m pra ruído numérico
                surface_violations.append({
                    "index": idx,
                    "name": att.name or f"Boia #{idx + 1}",
                    "height_above_surface_m": round(height_above, 2),
                })

    # F5.7.4 + F5.7.6 — Popula `result.diagnostics` com:
    #   • D004 (error) para boia acima da superfície
    #   • D009 (warning/error) para anchor uplift alto
    #   • D010 (warning) para utilização > 60% (threshold operacional)
    #   • D008 (info) para margens de segurança apertadas
    #
    # Fase 7: preserva diagnostics já populados por solvers especializados
    # (ex.: D017 do suspended_endpoint). A lista pode chegar não-vazia
    # quando o caminho upstream emitiu diagnostics próprios.
    diagnostics_list: list[dict] = list(result.diagnostics or [])

    # Fase 8 — D018 (sempre que há AHV) + D019 (componente fora do plano)
    ahv_attachments = [a for a in resolved_attachments if a.kind == "ahv"]
    # Sprint 4 — D018 dispara também quando há AHVInstall com Work Wire
    # (Tier C ativo). Mensagem customizada cita Work Wire elástico.
    tier_c_active = (
        boundary.ahv_install is not None
        and boundary.ahv_install.work_wire is not None
    )
    if (ahv_attachments or tier_c_active) and result.status == ConvergenceStatus.CONVERGED:
        from .diagnostics import (
            D018_ahv_static_idealization,
            D019_ahv_force_mostly_out_of_plane,
        )
        from .multi_segment import ahv_in_plane_fraction
        # D018 — sempre dispara (decisão Q6 não-negociável)
        diagnostics_list.append(
            D018_ahv_static_idealization(
                n_ahv=len(ahv_attachments),
                tier_c_active=tier_c_active,
            ).model_dump()
        )
        # D019 — para cada AHV cuja projeção no plano da linha < 30%
        for att in ahv_attachments:
            in_plane = ahv_in_plane_fraction(att, line_azimuth_deg=0.0)
            if in_plane < 0.30:
                diagnostics_list.append(
                    D019_ahv_force_mostly_out_of_plane(
                        bollard_pull=att.ahv_bollard_pull or 0.0,
                        in_plane_fraction=in_plane,
                        heading_deg=att.ahv_heading_deg or 0.0,
                    ).model_dump()
                )

    if surface_violations:
        for v in surface_violations:
            buoy_idx = v["index"]
            if buoy_idx < len(resolved_attachments):
                att = resolved_attachments[buoy_idx]
                diag = D004_buoy_above_surface(
                    buoy_index=buoy_idx,
                    buoy_name=v["name"],
                    height_above_m=v["height_above_surface_m"],
                    submerged_force_n=att.submerged_force,
                )
                diagnostics_list.append(diag.model_dump())

    # D009 — anchor uplift alto (drag anchors toleram ≤ 5°, crítico > 15°)
    if result.status == ConvergenceStatus.CONVERGED and uplift_severity != "ok":
        diagnostics_list.append(
            D009_anchor_uplift_high(
                angle_deg=uplift_deg,
                severity="error" if uplift_severity == "critical" else "warning",
            ).model_dump()
        )

    # D010 — utilização alta (T_fl/MBL > 60% é red, > 50% é warning)
    if result.status == ConvergenceStatus.CONVERGED and result.utilization > 0:
        if result.utilization >= 0.6:
            diagnostics_list.append(
                D010_high_utilization(
                    utilization=result.utilization,
                    threshold=0.6,
                    severity="error",
                ).model_dump()
            )
        elif result.utilization >= 0.5:
            diagnostics_list.append(
                D010_high_utilization(
                    utilization=result.utilization,
                    threshold=0.5,
                    severity="warning",
                ).model_dump()
            )

    # F5.7.7 — D011: detecta cabo penetrando o seabed (caso espelho do
    # D004 boia acima d'água, mas pra clumps puxando o cabo pra baixo).
    # Convenção solver: anchor em y=0; seabed em y_solver = m·x_solver
    # (m=tan(slope)); cabo deve estar y ≥ seabed_y. Tolerância 0.5m.
    if (
        result.status == ConvergenceStatus.CONVERGED
        and result.coords_y
        and result.coords_x
    ):
        m_slope = math.tan(seabed.slope_rad)
        max_penetration = 0.0
        # Encontra a maior penetração (cabo abaixo do seabed)
        for cx, cy in zip(result.coords_x, result.coords_y):
            seabed_y = m_slope * cx
            penetration = seabed_y - cy
            if penetration > max_penetration:
                max_penetration = penetration
        if max_penetration > 0.5:  # tolerância pra ruído numérico
            # Tenta atribuir a um clump (o que estiver mais perto do
            # ponto de penetração). Pega o primeiro clump como heurística;
            # versão melhor seria localizar o clump exato pelo coord_idx.
            responsible_idx: int | None = None
            responsible_name = ""
            responsible_force = 0.0
            for idx, att in enumerate(resolved_attachments):
                if att.kind == "clump_weight":
                    responsible_idx = idx
                    responsible_name = att.name or f"Clump #{idx + 1}"
                    responsible_force = att.submerged_force
                    break
            diagnostics_list.append(
                D011_cable_below_seabed(
                    depth_below_m=max_penetration,
                    responsible_clump_index=responsible_idx,
                    responsible_clump_name=responsible_name,
                    submerged_force_n=responsible_force,
                ).model_dump()
            )

    # D008 — sensitivity de margem (info): proximidade do taut (linha quase
    # esticada). taut_margin = L_stretched / L_taut. Se < 5%, alerta.
    if (
        result.status == ConvergenceStatus.CONVERGED
        and result.stretched_length > 0
    ):
        L_taut = math.sqrt(
            result.total_horz_distance ** 2 + boundary.h ** 2
        )
        if L_taut > 0:
            taut_margin = (result.stretched_length / L_taut) - 1.0
            if 0.0 < taut_margin < 0.05:
                diagnostics_list.append(
                    D008_safety_margin(
                        parameter="Margem ao taut",
                        field_path="segments[0].length",
                        current=result.stretched_length,
                        limit=L_taut,
                        margin_pct=taut_margin * 100,
                        label_unit=" m",
                    ).model_dump()
                )

    # ─── Diagnostics novos da Fase 4 (D012, D013, D014) ──────────────
    # Esses 3 são checks "do input" (não dependem do resultado físico),
    # injetados aqui ao invés do _validate_inputs porque alguns são
    # warnings (não bloqueiam o solve) e queremos mostrá-los junto com
    # os outros diagnósticos pós-solve.

    # D012: slope > 30° (geometria atípica). Ajuste 1 / Q3 da Fase 4.
    slope_deg_abs = abs(math.degrees(seabed.slope_rad))
    if slope_deg_abs > 30.0:
        from .diagnostics import D012_slope_high
        diagnostics_list.append(
            D012_slope_high(slope_deg=math.copysign(slope_deg_abs, seabed.slope_rad)).model_dump()
        )

    # D013: μ global = 0 mas catálogo do segmento tem cf >= 0.3.
    # Limiar 0.3 é justificativa empírica — todas as categorias do
    # catálogo do AncoPlat têm cf mínimo 0.6 (ver docstring de
    # D013_mu_zero_with_catalog_friction).
    if seabed.mu == 0.0:
        from .diagnostics import D013_mu_zero_with_catalog_friction
        for i, seg in enumerate(line_segments):
            if (
                seg.line_type is not None
                and seg.seabed_friction_cf is not None
                and seg.seabed_friction_cf >= 0.3
                and seg.mu_override is None  # não tem override próprio
            ):
                diagnostics_list.append(
                    D013_mu_zero_with_catalog_friction(
                        segment_index=i,
                        catalog_cf=seg.seabed_friction_cf,
                        line_type=seg.line_type,
                    ).model_dump()
                )
                break  # 1 diagnostic por caso é suficiente — não inunda UI

    # D014: ea_source="gmoor" sem ea_dynamic_beta. Modelo β=0 implícito.
    from .diagnostics import D014_gmoor_without_beta
    for i, seg in enumerate(line_segments):
        if (
            seg.ea_source == "gmoor"
            and (seg.ea_dynamic_beta is None or seg.ea_dynamic_beta == 0.0)
        ):
            diagnostics_list.append(
                D014_gmoor_without_beta(
                    segment_index=i,
                    line_type=seg.line_type or f"segmento {i + 1}",
                ).model_dump()
            )

    result = result.model_copy(update={
        "water_depth": boundary.h,
        "startpoint_depth": boundary.startpoint_depth,
        "solver_version": SOLVER_VERSION,
        "depth_at_anchor": boundary.h,
        "depth_at_fairlead": depth_at_fairlead,
        "anchor_uplift_severity": uplift_severity,
        "surface_violations": surface_violations,
        "diagnostics": diagnostics_list,
    })

    # Se houver violations, anexa um aviso ao final da mensagem
    # (status continua CONVERGED — a geometria está matemáticamente
    # correta para os F_b configurados; só a INTERPRETAÇÃO física
    # é problemática).
    if surface_violations:
        viol_str = ", ".join(
            f"{v['name']} (+{v['height_above_surface_m']:.1f}m acima da superfície)"
            for v in surface_violations
        )
        warning_msg = (
            f" ⚠ AVISO: {len(surface_violations)} boia(s) com corpo "
            f"ACIMA da superfície da água ({viol_str}). Boias reais "
            "não conseguem flutuar acima da água — o empuxo configurado "
            "é maior do que a geometria suporta. Reduza o empuxo da boia, "
            "aumente T_fl, ou compense com clump weight."
        )
        result = result.model_copy(update={"message": result.message + warning_msg})

    # Pós-classificação (Camada 7 + alert_level da Seção 5 Documento A).
    if result.status == ConvergenceStatus.CONVERGED:
        try:
            alert = classify_utilization(
                result.utilization, criteria_profile, user_limits,
            )
        except ValueError as exc:
            # Configuração inválida do perfil (ex.: USER_DEFINED sem user_limits).
            return SolverResult(
                **{
                    **result.model_dump(),
                    "status": ConvergenceStatus.INVALID_CASE,
                    "message": f"Perfil de critério mal configurado: {exc}",
                }
            )

        # Check 1: linha rompida (utilization >= broken_ratio do perfil ativo).
        # Matemáticamente converge, mas é engenheiramente inválido.
        if alert == AlertLevel.BROKEN:
            return SolverResult(
                **{
                    **result.model_dump(),
                    "status": ConvergenceStatus.INVALID_CASE,
                    "alert_level": AlertLevel.BROKEN,
                    "message": (
                        f"Linha rompida: T_fl/MBL = {result.utilization:.2f} "
                        f"(perfil {criteria_profile.value}, broken_ratio="
                        f"{_broken_ratio(criteria_profile, user_limits):.2f}). "
                        "Caso fisicamente inviável. "
                        "Verifique comprimento, geometria ou tipo de linha."
                    ),
                }
            )

        # Check 2: ill-conditioned (linha muito taut, sensibilidade extrema).
        L_stretched = result.stretched_length
        X = result.total_horz_distance
        h = boundary.h
        L_taut = math.sqrt(X * X + h * h)
        taut_margin = L_stretched / L_taut if L_taut > 0 else float("inf")
        if 1.0 < taut_margin < 1.0001:
            return SolverResult(
                **{
                    **result.model_dump(),
                    "status": ConvergenceStatus.ILL_CONDITIONED,
                    "alert_level": alert,
                    "message": (
                        f"Convergiu mas caso mal condicionado: linha a "
                        f"{(taut_margin - 1) * 100:.3f}% do taut, alta sensibilidade. "
                        "Resultado deve ser usado com cautela. "
                        f"({result.message})"
                    ),
                }
            )

        # Caso normal convergido: injeta alert_level + profile_type.
        # Fase 4 / Q2: classify_profile_type é chamado aqui no facade,
        # após o solve completo. Função pura, não toca em DB nem
        # re-solve. None quando status != CONVERGED/ILL_CONDITIONED.
        from .profile_type import classify_profile_type as _classify_pt
        pt = _classify_pt(result, line_segments, seabed)

        # D015: ProfileType raro (PT_4, PT_5, PT_6). Append no diagnostics
        # existentes do result.
        existing_diags = list(result.diagnostics or [])
        if pt is not None and pt.value in ("PT_4", "PT_5", "PT_6"):
            from .diagnostics import D015_rare_profile_type
            existing_diags.append(
                D015_rare_profile_type(profile_type=pt.value).model_dump()
            )

        return SolverResult(
            **{
                **result.model_dump(),
                "alert_level": alert,
                "profile_type": pt,
                "diagnostics": existing_diags,
            }
        )

    return result


def _friendly_invalid_message(
    raw: str, segment: LineSegment, boundary: BoundaryConditions,
) -> str:
    """
    Converte uma mensagem técnica do solver em uma mensagem prática para o
    engenheiro, com sugestão de correção concreta sempre que possível.

    Cobre os erros mais comuns que aparecem na prática:
      - T_fl ≤ w·h  → linha não sustenta a coluna d'água
      - L ≤ √(X² + h²) (rígido)  → linha mais curta que a distância taut
      - L ≤ h (modo Tension)  → linha mais curta que a lâmina
      - Strain > 5%  → input em unidade errada
      - X < L (modo Range, laid line)  → X menor que o cabo
      - "linha rompida" (T_fl ≥ MBL)  → MBL excedido

    Para erros não reconhecidos, devolve o original prefixado com "Caso
    inviável:".
    """
    h = boundary.h
    L = segment.length
    w = segment.w
    MBL = segment.MBL
    raw_lower = raw.lower()

    # Heurística 1: T_fl insuficiente para sustentar coluna d'água
    if "insuficiente para sustentar" in raw_lower or "t_fl=" in raw_lower and "w·h" in raw:
        wh = w * h
        return (
            f"T_fl insuficiente: a tração no fairlead não sustenta o peso "
            f"da coluna d'água até o fairlead (w·h ≈ {wh / 1000:.1f} kN). "
            "Aumente T_fl, reduza a lâmina d'água, ou use um cabo mais leve."
        )

    # Heurística 2: comprimento curto para a distância pedida
    if "linha mais curta que a lâmina" in raw_lower or "fairlead inalcançável" in raw_lower:
        return (
            f"Linha curta demais: o comprimento ({L:.0f} m) é menor ou igual "
            f"à lâmina d'água ({h:.0f} m). "
            "Aumente o comprimento da linha para pelo menos h + margem."
        )

    # Heurística 3: X >= X_max (modo Range, geometria impossível sem elasticidade)
    if "x_max" in raw_lower or "linha rígida" in raw_lower or "não alcança" in raw_lower:
        return (
            "Distância horizontal X excede o máximo geométrico √(L² − h²). "
            "A linha precisaria esticar mais do que o EA permite. "
            "Reduza X (ou aumente o comprimento da linha)."
        )

    # Heurística 4: strain implausível → unidade errada
    if "strain final" in raw_lower or "implaus" in raw_lower:
        return (
            f"{raw}\n"
            f"Verificações sugeridas: w deve estar em N/m (não kgf/m), "
            f"EA em N (não te). Se você importou de um .moor antigo, "
            "use o seletor de unidades para conferir os valores."
        )

    # Heurística 5: rompimento (utilization > broken_ratio)
    if "linha rompida" in raw_lower or "broken_ratio" in raw_lower:
        return (
            f"{raw} O fairlead está sob T = {boundary.input_value / 1000:.1f} kN, "
            f"acima do MBL ({MBL / 1000:.1f} kN). "
            "Reduza T_fl, troque por um cabo de MBL maior ou alivie a geometria."
        )

    # Heurística 6: X < L em laid line
    if "x" in raw_lower and "compactar" in raw_lower:
        return (
            f"X ({boundary.input_value:.0f} m) menor que o comprimento da linha "
            f"({L:.0f} m): isso exigiria compressão axial, fisicamente impossível. "
            "Aumente X ou reduza L."
        )

    # Fallback: prepend "Caso inviável:" sem repetir se já vier
    if raw_lower.startswith("caso"):
        return raw
    return f"Caso inviável: {raw}"


__all__ = ["solve"]
