"""
F5.7.4 — Sistema de diagnósticos do solver.

Padroniza erros e avisos do solver em um formato estruturado que a UI
pode consumir pra mostrar mensagens claras E sugerir correções
automáticas. Cada diagnóstico tem 4 partes:

  - `code`: identificador único (E001, E002, ...) para filtros e
    documentação.
  - `severity`: 'error' | 'warning'. Erros impedem o plot; avisos
    aparecem com geometria.
  - `title` / `cause`: explicação humana.
  - `suggested_changes`: lista de mudanças propostas, cada uma com
    `field` (caminho dotado tipo 'attachments[0].submerged_force') e
    `value` (novo valor sugerido). A UI renderiza como botão "Aplicar".

Os builders neste módulo são helpers fechados (Nível 1 da auditoria
de UX): cada um recebe os parâmetros do problema e devolve um
diagnóstico com sugestão calculada por fórmula direta. Para erros que
exigem busca numérica (Nível 2 da auditoria — varredura de viabilidade),
caem no `D900_GENERIC_NONCONVERGENCE` que apenas registra a falha e
sugere ações qualitativas.
"""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


SeverityLevel = Literal["critical", "error", "warning", "info"]
"""
4-level severity hierarchy:
- critical: caso não pode ser computado (zero geometria, math impossível)
- error:    geometria existe mas viola física (boia voadora, clump enterrado)
- warning:  geometria válida mas ill-conditioned (anchor uplift alto, taut)
- info:     observação útil (margem de segurança, detalhe geométrico)

Cores e prioridade são consistentes em toda a UI: critical/error = vermelho,
warning = âmbar, info = azul/cinza.
"""


ConfidenceLevel = Literal["high", "medium", "low"]
"""
Confiança do diagnóstico (Fase 4 / Q7).

Critério de classificação (registrado no relatorio_F4_diagnostics.md):

- **high**: violação determinística de premissa física ou matemática.
  Sem ambiguidade — o diagnóstico SEMPRE é correto quando dispara.
  Exemplos: EA ≤ 0 (impossibilidade matemática), μ < 0 (Coulomb requer
  ≥ 0), startpoint_depth > h_at_fairlead (geometria inviável), boia
  acima da superfície (boia real flutua em y=0, não voa).

- **medium**: heurística calibrada com base empírica. O diagnóstico
  pode ter falso positivo em casos extremos legítimos, mas captura
  >90% dos cenários problemáticos típicos. Exemplos: P004 T_fl baixo
  (regra de thumb), D008 safety margin (limite operacional negociável),
  D013 atrito do catálogo (limiar 0.3 calibrado contra catálogo legacy).

- **low**: pattern detection sem base teórica forte. RESERVADO — ainda
  não temos diagnósticos nesta categoria. Quando aparecer, exigirá
  justificativa explícita no docstring do builder.

Default `high` mantém retro-compat: diagnósticos pré-Fase-4 não são
heurísticos. Heurísticos novos declaram `confidence="medium"` no
construtor.
"""


class SuggestedChange(BaseModel):
    """
    Uma mudança proposta para o usuário aceitar via botão "Aplicar".

    `field` segue notação dotted que a UI traduz para
    react-hook-form `setValue(field, value)`. Exemplos:
      - 'segments[0].length' (aumentar comprimento)
      - 'attachments[0].submerged_force' (reduzir empuxo)
      - 'attachments[0].position_s_from_anchor' (afastar boia)
      - 'boundary.input_value' (aumentar T_fl)
    """

    model_config = ConfigDict(frozen=True)

    field: str = Field(..., description="Caminho dotted do campo no formulário")
    value: float = Field(..., description="Novo valor sugerido (em SI)")
    label: str = Field(..., description="Rótulo curto para o botão (ex.: 'Reduzir empuxo para 7,2 te')")


class SolverDiagnostic(BaseModel):
    """
    Diagnóstico estruturado do solver — substitui mensagens de erro
    soltas por algo que a UI pode renderizar com clareza e sugerir
    correções automaticamente.

    `affected_fields` lista os caminhos dotted dos campos do form que
    causaram este diagnóstico. A UI usa essa lista pra renderizar
    indicadores visuais nos campos (dot vermelho) e no tab que contém
    eles (Boias ⚠ 2). Pode ser vazio para diagnósticos globais (e.g.,
    geometria infactível).
    """

    model_config = ConfigDict(frozen=True)

    code: str = Field(..., description="Código único (D001, D002, ...)")
    severity: SeverityLevel = Field(
        ..., description="critical, error, warning ou info"
    )
    title: str = Field(..., description="Resumo em uma linha")
    cause: str = Field(..., description="Explicação física/matemática")
    suggestion: str = Field(
        default="",
        description="Como corrigir, em prosa. Pode ser vazio se houver suggested_changes.",
    )
    suggested_changes: list[SuggestedChange] = Field(default_factory=list)
    affected_fields: list[str] = Field(
        default_factory=list,
        description=(
            "Caminhos dotted dos campos culpados (ex: 'attachments[0].submerged_force'). "
            "UI renderiza indicador visual em cada um."
        ),
    )
    confidence: ConfidenceLevel = Field(
        default="high",
        description=(
            "Fase 4 / Q7. Confiança no diagnóstico: high (determinístico), "
            "medium (heurística calibrada), low (pattern detection — reservado). "
            "Default 'high' mantém retro-compat. Critério detalhado no docstring "
            "de ConfidenceLevel."
        ),
    )


# =============================================================================
# Builders dos diagnósticos comuns
# =============================================================================


def D001_buoy_near_anchor(
    *,
    buoy_index: int,
    buoy_name: str,
    s_buoy_anchor: float,
    submerged_force_n: float,
    w_local: float,
    total_length: float,
) -> SolverDiagnostic:
    """
    Boia tão próxima da âncora que o arco de levantamento extrapolaria
    s_left < 0. Sugestões:
      - Reduzir empuxo para o máximo viável: F_max = 2·w·s_b
      - Afastar a boia para s ≥ s_arch / 2
    """
    s_arch_atual = submerged_force_n / max(w_local, 1e-9)
    F_max_n = 2.0 * w_local * s_buoy_anchor
    F_max_te = F_max_n / 9806.65
    F_atual_te = submerged_force_n / 9806.65
    s_min_anchor = s_arch_atual / 2.0
    # Posição "do fairlead" pra UI (a UI usa essa convenção)
    s_min_fairlead = total_length - s_min_anchor

    return SolverDiagnostic(
        code="D001_BUOY_NEAR_ANCHOR",
        severity="critical",
        title=f"Boia '{buoy_name}' perto demais da âncora",
        cause=(
            f"O empuxo configurado ({F_atual_te:.2f} te) exigiria um arco "
            f"de levantamento de {s_arch_atual:.0f} m. Com a boia a apenas "
            f"{s_buoy_anchor:.0f} m da âncora, o lado esquerdo do arco "
            "extrapolaria a âncora — a geometria não tem solução estática "
            "válida."
        ),
        suggestion=(
            f"Reduza o empuxo para no máximo {F_max_te:.2f} te, OU afaste "
            f"a boia para até {s_min_fairlead:.0f} m do fairlead "
            f"({s_min_anchor:.0f} m da âncora)."
        ),
        suggested_changes=[
            SuggestedChange(
                field=f"attachments[{buoy_index}].submerged_force",
                value=round(F_max_n * 0.95, 1),  # 5% de margem
                label=f"Reduzir empuxo para {F_max_te * 0.95:.2f} te",
            ),
        ],
        affected_fields=[
            f"attachments[{buoy_index}].submerged_force",
            f"attachments[{buoy_index}].position_s_from_anchor",
        ],
    )


def D002_buoy_near_fairlead(
    *,
    buoy_index: int,
    buoy_name: str,
    s_buoy_anchor: float,
    submerged_force_n: float,
    w_local: float,
    total_length: float,
) -> SolverDiagnostic:
    """
    Boia tão próxima do fairlead que o arco extrapolaria total_L.
    """
    s_arch_atual = submerged_force_n / max(w_local, 1e-9)
    s_remaining = total_length - s_buoy_anchor
    F_max_n = 2.0 * w_local * s_remaining
    F_max_te = F_max_n / 9806.65
    F_atual_te = submerged_force_n / 9806.65

    return SolverDiagnostic(
        code="D002_BUOY_NEAR_FAIRLEAD",
        severity="critical",
        title=f"Boia '{buoy_name}' perto demais do fairlead",
        cause=(
            f"O arco da boia ({s_arch_atual:.0f} m) extrapolaria o "
            f"comprimento do cabo. Restam só {s_remaining:.0f} m de cabo "
            "até o fairlead — espaço insuficiente."
        ),
        suggestion=(
            f"Reduza o empuxo para no máximo {F_max_te:.2f} te (atual: "
            f"{F_atual_te:.2f} te) OU afaste a boia da fairlead."
        ),
        suggested_changes=[
            SuggestedChange(
                field=f"attachments[{buoy_index}].submerged_force",
                value=round(F_max_n * 0.95, 1),
                label=f"Reduzir empuxo para {F_max_te * 0.95:.2f} te",
            ),
        ],
        affected_fields=[
            f"attachments[{buoy_index}].submerged_force",
            f"attachments[{buoy_index}].position_s_from_anchor",
        ],
    )


def D003_arch_does_not_fit_grounded(
    *,
    buoy_index: int,
    buoy_name: str,
    s_buoy_anchor: float,
    submerged_force_n: float,
    w_local: float,
    L_g_natural: float,
) -> SolverDiagnostic:
    """
    Caso 7→8 te do usuário: o arco da boia ultrapassa o trecho apoiado
    natural. Sugestão: encontrar F_max tal que s_buoy + s_arch/2 ≤ L_g.
    """
    s_arch_atual = submerged_force_n / max(w_local, 1e-9)
    s_right_atual = s_buoy_anchor + s_arch_atual / 2.0
    # F_max: 2·w·(L_g - s_buoy)
    s_arch_max = 2.0 * (L_g_natural - s_buoy_anchor)
    F_max_n = max(0.0, w_local * s_arch_max)
    F_max_te = F_max_n / 9806.65
    F_atual_te = submerged_force_n / 9806.65

    return SolverDiagnostic(
        code="D003_ARCH_OVERFLOWS_GROUNDED",
        severity="critical",
        title=f"Arco da boia '{buoy_name}' não cabe no trecho apoiado",
        cause=(
            f"O arco gerado pela boia ({s_arch_atual:.0f} m) extrapola o "
            f"trecho apoiado natural ({L_g_natural:.0f} m): o lado direito "
            f"chegaria em s={s_right_atual:.0f} m, invadindo a zona "
            "suspensa principal."
        ),
        suggestion=(
            f"Reduza o empuxo para no máximo {F_max_te:.2f} te (atual: "
            f"{F_atual_te:.2f} te). Alternativas: aumentar o comprimento "
            "do cabo ou T_fl pra ampliar o trecho apoiado."
        ),
        suggested_changes=[
            SuggestedChange(
                field=f"attachments[{buoy_index}].submerged_force",
                value=round(F_max_n * 0.95, 1),
                label=f"Reduzir empuxo para {F_max_te * 0.95:.2f} te",
            ),
        ],
        affected_fields=[
            f"attachments[{buoy_index}].submerged_force",
        ],
    )


def D004_buoy_above_surface(
    *,
    buoy_index: int,
    buoy_name: str,
    height_above_m: float,
    submerged_force_n: float,
) -> SolverDiagnostic:
    """
    Boia que ficaria acima da superfície (status warning, geometria
    ainda visível). Reduzir empuxo proporcionalmente.
    """
    F_atual_te = submerged_force_n / 9806.65
    # Heurística: reduzir empuxo proporcional ao "excesso vertical"
    # vs. tipico drop. Aproximação: 1m acima da superfície ≈ 5% de
    # excesso de empuxo. Conservador: corte 10% por metro até 50%.
    cut_pct = min(0.5, height_above_m * 0.05 + 0.1)
    F_max_n = submerged_force_n * (1.0 - cut_pct)
    F_max_te = F_max_n / 9806.65

    return SolverDiagnostic(
        code="D004_BUOY_ABOVE_SURFACE",
        severity="error",
        title=f"Boia '{buoy_name}' fora d'água ({height_above_m:.1f} m acima)",
        cause=(
            f"O empuxo configurado ({F_atual_te:.2f} te) é maior do que "
            "a geometria suporta — o ponto da linha onde a boia está "
            "atingiu uma altura acima da superfície da água. Boias reais "
            "não conseguem flutuar acima d'água."
        ),
        suggestion=(
            f"Reduza o empuxo (estimativa: ≤ {F_max_te:.2f} te), "
            "aumente T_fl, ou compense com clump weight."
        ),
        suggested_changes=[
            SuggestedChange(
                field=f"attachments[{buoy_index}].submerged_force",
                value=round(F_max_n, 1),
                label=f"Reduzir empuxo para {F_max_te:.2f} te",
            ),
        ],
        affected_fields=[
            f"attachments[{buoy_index}].submerged_force",
        ],
    )


def D005_buoyancy_exceeds_weight(
    *,
    buoy_index: int,
    buoy_name: str,
    submerged_force_n: float,
    cable_weight_n: float,
    clump_force_n: float = 0.0,
) -> SolverDiagnostic:
    """
    Σ F_buoy > Σ w·L + Σ F_clump → geometria invertida.
    """
    F_max_n = max(0.0, cable_weight_n + clump_force_n - 1.0)
    F_max_te = F_max_n / 9806.65
    F_atual_te = submerged_force_n / 9806.65

    return SolverDiagnostic(
        code="D005_BUOYANCY_EXCEEDS_WEIGHT",
        severity="critical",
        title=f"Empuxo da boia '{buoy_name}' excede o peso da linha",
        cause=(
            f"O empuxo total das boias ({F_atual_te:.2f} te) excede o peso "
            f"submerso da linha ({cable_weight_n / 9806.65:.2f} te) + clumps "
            f"({clump_force_n / 9806.65:.2f} te). Isso inverteria a "
            "geometria — fisicamente impossível em equilíbrio estático."
        ),
        suggestion=(
            f"Reduza o empuxo da boia para ≤ {F_max_te:.2f} te, OU adicione "
            "um clump weight maior, OU aumente o comprimento do cabo "
            "(mais peso submerso)."
        ),
        suggested_changes=[
            SuggestedChange(
                field=f"attachments[{buoy_index}].submerged_force",
                value=round(F_max_n * 0.9, 1),
                label=f"Reduzir empuxo para {F_max_te * 0.9:.2f} te",
            ),
        ],
        affected_fields=[
            f"attachments[{buoy_index}].submerged_force",
        ],
    )


def D006_cable_too_short(
    *,
    cable_length: float,
    water_depth: float,
) -> SolverDiagnostic:
    """
    Comprimento do cabo ≤ lâmina d'água: linha não atinge o fairlead.
    """
    L_min = 1.2 * water_depth

    return SolverDiagnostic(
        code="D006_CABLE_TOO_SHORT",
        severity="critical",
        title="Cabo curto demais para a lâmina d'água",
        cause=(
            f"Comprimento do cabo ({cable_length:.0f} m) é menor ou igual à "
            f"lâmina d'água ({water_depth:.0f} m). A linha não conseguiria "
            "alcançar o fairlead na geometria pedida."
        ),
        suggestion=(
            f"Aumente o comprimento do cabo para pelo menos {L_min:.0f} m "
            "(20% acima da lâmina d'água, margem mínima)."
        ),
        suggested_changes=[
            SuggestedChange(
                field="segments[0].length",
                value=round(L_min, 1),
                label=f"Aumentar comprimento para {L_min:.0f} m",
            ),
        ],
        affected_fields=["segments[0].length", "boundary.h"],
    )


def D007_tfl_below_critical_horizontal(
    *,
    tfl_atual: float,
    tfl_min_critical: float,
) -> SolverDiagnostic:
    """
    T_fl insuficiente pra sustentar coluna d'água — caso fully suspended impossível.
    """
    return SolverDiagnostic(
        code="D007_TFL_TOO_LOW",
        severity="critical",
        title="T_fl insuficiente para sustentar a coluna d'água",
        cause=(
            f"A tração no fairlead ({tfl_atual / 1000:.1f} kN) não é "
            "suficiente para sustentar o peso submerso da linha entre âncora "
            "e fairlead — a linha não consegue chegar ao fairlead."
        ),
        suggestion=(
            f"Aumente T_fl para pelo menos {tfl_min_critical / 1000:.0f} kN."
        ),
        suggested_changes=[
            SuggestedChange(
                field="boundary.input_value",
                value=round(tfl_min_critical * 1.1, 1),  # 10% margem
                label=f"Aumentar T_fl para {tfl_min_critical / 1000 * 1.1:.0f} kN",
            ),
        ],
        affected_fields=["boundary.input_value"],
    )


def D008_safety_margin(
    *,
    parameter: str,
    field_path: str,
    current: float,
    limit: float,
    margin_pct: float,
    label_unit: str = "",
) -> SolverDiagnostic:
    """
    INFO: parâmetro está perto de um limite (margem < 15%). Não é
    erro mas alerta o engenheiro pra que considere uma folga maior.
    """
    return SolverDiagnostic(
        code="D008_SAFETY_MARGIN",
        severity="info",
        title=f"{parameter} próximo do limite (margem {margin_pct:.0f}%)",
        cause=(
            f"{parameter} atual é {current:.2f}{label_unit} contra um limite "
            f"de {limit:.2f}{label_unit}. Pequenas variações de carga ambiental "
            "podem levar o sistema fora da janela de operação."
        ),
        suggestion=(
            "Considere aumentar a margem em pelo menos 25% para resiliência "
            "operacional."
        ),
        affected_fields=[field_path] if field_path else [],
    )


def D009_anchor_uplift_high(
    *,
    angle_deg: float,
    severity: SeverityLevel = "warning",
) -> SolverDiagnostic:
    """
    Anchor uplift acima do limite de drag anchors típicos (5°/15°).
    """
    return SolverDiagnostic(
        code="D009_ANCHOR_UPLIFT_HIGH",
        severity=severity,
        title=f"Anchor uplift {angle_deg:.1f}° {'crítico' if severity == 'error' else 'alto'}",
        cause=(
            f"O ângulo da linha na âncora ({angle_deg:.1f}°) está acima do "
            "tolerável para drag anchors (DA / VLA), que tipicamente "
            "operam ≤ 5°. Acima disso, a âncora pode arrastar."
        ),
        suggestion=(
            "Use um pile/suction caisson, OU aumente o comprimento do cabo "
            "para reduzir o ângulo, OU reposicione a âncora mais longe."
        ),
        affected_fields=["segments[0].length", "boundary.input_value"],
    )


def D010_high_utilization(
    *,
    utilization: float,
    threshold: float,
    severity: SeverityLevel = "warning",
) -> SolverDiagnostic:
    """
    Utilização T_fl/MBL acima do limite operacional. Não bloqueia
    o cálculo (matemática converge), mas indica que o cabo está
    trabalhando perto do MBL.
    """
    return SolverDiagnostic(
        code="D010_HIGH_UTILIZATION",
        severity=severity,
        title=f"Utilização {utilization * 100:.0f}% acima do limite operacional",
        cause=(
            f"T_fl/MBL = {utilization:.2%} acima do limite de "
            f"{threshold:.0%}. O cabo está trabalhando próximo da capacidade "
            "máxima — sensibilidade alta a aumentos de carga."
        ),
        suggestion=(
            "Use um cabo com MBL maior, OU reduza T_fl ajustando geometria, "
            "OU aceite o nível atual com revisão técnica do limite operacional."
        ),
        affected_fields=["boundary.input_value", "segments[0].MBL"],
    )


def D011_cable_below_seabed(
    *,
    depth_below_m: float,
    responsible_clump_index: int | None = None,
    responsible_clump_name: str = "",
    submerged_force_n: float = 0.0,
) -> SolverDiagnostic:
    """
    Cabo penetra o seabed em algum ponto — geometricamente possível
    pelo solver mas fisicamente inválido (seabed é sólido). Causa
    típica: clump weight com pendant longo OU força excessiva pra
    geometria, puxando o cabo abaixo da linha do fundo.

    Quando o clump responsável é identificável, a sugestão sugere
    reduzir a força. Sem identificação, sugestões qualitativas.
    """
    if responsible_clump_index is not None and submerged_force_n > 0:
        F_atual_te = submerged_force_n / 9806.65
        # Heurística: corte 10% por metro abaixo do seabed (similar ao
        # D004 mas mirror)
        cut_pct = min(0.5, depth_below_m * 0.05 + 0.1)
        F_max_n = submerged_force_n * (1.0 - cut_pct)
        F_max_te = F_max_n / 9806.65
        return SolverDiagnostic(
            code="D011_CABLE_BELOW_SEABED",
            severity="error",
            title=(
                f"Cabo abaixo do seabed ({depth_below_m:.1f} m) — clump "
                f"'{responsible_clump_name}'"
            ),
            cause=(
                f"O clump '{responsible_clump_name}' ({F_atual_te:.2f} te) "
                f"puxa o cabo abaixo do seabed em {depth_below_m:.1f} m. "
                "Seabed é sólido — não pode ser penetrado. Causa provável: "
                "força do clump alta demais para a tensão local da linha."
            ),
            suggestion=(
                f"Reduza o peso submerso do clump (estimativa: ≤ "
                f"{F_max_te:.2f} te), aumente T_fl pra erguer o cabo, ou "
                "reposicione o clump em região com mais cabo suspenso."
            ),
            suggested_changes=[
                SuggestedChange(
                    field=f"attachments[{responsible_clump_index}].submerged_force",
                    value=round(F_max_n, 1),
                    label=f"Reduzir clump para {F_max_te:.2f} te",
                ),
            ],
            affected_fields=[
                f"attachments[{responsible_clump_index}].submerged_force",
            ],
        )
    return SolverDiagnostic(
        code="D011_CABLE_BELOW_SEABED",
        severity="error",
        title=f"Cabo abaixo do seabed ({depth_below_m:.1f} m)",
        cause=(
            f"Em algum ponto a linha penetra {depth_below_m:.1f} m abaixo "
            "do seabed. Seabed é sólido — não pode ser penetrado. Causa "
            "comum: clump weight pesado demais pra tensão local da linha."
        ),
        suggestion=(
            "Reduza o peso submerso de clump weights, aumente T_fl pra "
            "erguer o cabo, ou reposicione attachments em regiões com "
            "mais cabo suspenso."
        ),
        affected_fields=[],
    )


def D900_generic_nonconvergence(
    *,
    raw_message: str = "",
) -> SolverDiagnostic:
    """
    Fallback quando o solver não converge mas nenhum diagnóstico
    específico se aplica. Sugestões qualitativas.
    """
    return SolverDiagnostic(
        code="D900_GENERIC",
        severity="critical",
        title="Solver não convergiu",
        cause=(
            "A configuração atual não tem solução numérica estável. "
            "Isso pode acontecer perto de transições críticas de geometria "
            "(linha quase taut, boia perto do touchdown principal, etc)."
            + (f"\nDetalhe técnico: {raw_message}" if raw_message else "")
        ),
        suggestion=(
            "Tente: (a) ajustar T_fl em ±20% pra encontrar uma região "
            "estável, (b) reduzir empuxo de boias se houver, (c) aumentar "
            "ou diminuir levemente o comprimento do cabo."
        ),
        affected_fields=["boundary.input_value", "segments[0].length"],
    )


# =============================================================================
# Diagnostics novos da Fase 4 — D012, D013, D014, D015
# =============================================================================


def D012_slope_high(*, slope_deg: float) -> SolverDiagnostic:
    """
    Slope alto detectado (> 30°). Solver continua válido mas o engenheiro
    deve estar ciente que rampas muito íngremes são raras no mundo real
    e podem indicar erro de input ou caso de baixa precisão numérica.

    Confidence: high — limiar 30° é determinístico (well-defined boundary).
    Severity: warning — não bloqueia, alerta.
    """
    return SolverDiagnostic(
        code="D012_SLOPE_HIGH",
        severity="warning",
        title=f"Slope do seabed alto ({slope_deg:.1f}°)",
        cause=(
            f"O slope informado ({slope_deg:.1f}°) é maior que 30°. Rampas "
            "tão íngremes são incomuns em batimetria offshore real (típicas "
            "ficam < 10°). Pode indicar inversão de sinal entre âncora e "
            "fairlead, ou caso atípico onde o solver tem precisão reduzida."
        ),
        suggestion=(
            "Verifique a batimetria nos dois pontos (profundidade do seabed "
            "sob a âncora vs sob o fairlead). Se o caso é correto, considere "
            "validar contra solução analítica simplificada."
        ),
        confidence="high",
        affected_fields=["seabed.slope_rad"],
    )


def D013_mu_zero_with_catalog_friction(
    *,
    segment_index: int,
    catalog_cf: float,
    line_type: str,
) -> SolverDiagnostic:
    """
    Atrito global zerado (`seabed.mu = 0`) mas catálogo do segmento sugere
    atrito não-trivial (`seabed_friction_cf >= 0.3`). Indica configuração
    inconsistente: o usuário pegou um line_type do catálogo mas zerou o
    atrito global sem usar o `mu_override` ou `seabed_friction_cf` por seg.

    Limiar 0.3 — justificativa empírica (Ajuste 2 do mini-plano F4):
      Catálogo do AncoPlat tem os seguintes mínimos por categoria:
        - Polyester: 1.0
        - StuddedChain: 1.0
        - StudlessChain: 0.6 (R5) ou 1.0 (R4)
        - Wire: 0.6
      Mínimo absoluto observado: 0.6. Limiar 0.3 captura todas as
      categorias com folga (50% abaixo do mínimo real). Caso o catálogo
      ganhe entradas com cf entre 0.1 e 0.3, ajustar limiar para 0.2.

    Confidence: medium — heurística calibrada empiricamente; pode ter
    falso positivo se o engenheiro intencionalmente está modelando solo
    super liso (caso raro).
    """
    return SolverDiagnostic(
        code="D013_MU_ZERO_CATALOG_HAS_FRICTION",
        severity="warning",
        title=(
            f"Atrito global = 0 mas '{line_type}' tem μ_catálogo "
            f"= {catalog_cf:.2f}"
        ),
        cause=(
            f"O segmento #{segment_index + 1} usa o tipo '{line_type}', "
            f"que segundo o catálogo tem coeficiente de atrito típico de "
            f"{catalog_cf:.2f}. O caso atual zerou o atrito global "
            "(`seabed.mu = 0`). Configuração inconsistente — o solver vai "
            "ignorar atrito completamente."
        ),
        suggestion=(
            "Se você queria usar o atrito do catálogo, deixe `seabed.mu` "
            "vazio (None) — o solver cai no `seabed_friction_cf` do "
            "catálogo. Se realmente queria μ=0 (solo perfeitamente liso), "
            "ignore este aviso."
        ),
        suggested_changes=[
            SuggestedChange(
                field="seabed.mu",
                value=catalog_cf,
                label=f"Usar μ do catálogo ({catalog_cf:.2f})",
            ),
        ],
        confidence="medium",
        affected_fields=["seabed.mu", f"segments[{segment_index}].line_type"],
    )


def D014_gmoor_without_beta(
    *,
    segment_index: int,
    line_type: str,
) -> SolverDiagnostic:
    """
    Segmento usa `ea_source="gmoor"` (EA dinâmico) mas `ea_dynamic_beta` é
    None (= 0). Modelo dinâmico completo é `EA = α + β × T_mean`; sem β,
    cai em modelo simplificado com α constante.

    Em v1.0 do AncoPlat β NÃO É implementado (decisão fechada na Fase 0,
    registrada em CLAUDE.md). Este diagnostic torna explícito que a
    aproximação está sendo aplicada — engenheiro consciente sabe que é
    OK; engenheiro distraído tem aviso.

    Confidence: high — é uma observação determinística sobre o modelo,
    não uma heurística.
    Severity: info — não bloqueia, é informativo.
    """
    return SolverDiagnostic(
        code="D014_GMOOR_WITHOUT_BETA",
        severity="info",
        title=f"Segmento '{line_type}' usa EA dinâmico simplificado (β=0)",
        cause=(
            f"O segmento #{segment_index + 1} foi configurado com "
            f"`ea_source='gmoor'` (EA dinâmico, modelo NREL/MoorPy "
            f"`α + β × T_mean`). Como `ea_dynamic_beta` não foi informado, "
            "o solver aplica modelo simplificado com α constante (β=0). "
            "Resultado é correto se T_mean estiver na faixa de operação "
            "típica do material."
        ),
        suggestion=(
            "Implementação do termo β é planejada para Fase 4+ — quando "
            "disponível, o solver iterará T_mean → EA(T_mean) → solve → "
            "atualiza T_mean. Por ora, esta aproximação é aceita como "
            "padrão NREL para análise quasi-estática."
        ),
        confidence="high",
        affected_fields=[
            f"segments[{segment_index}].ea_source",
            f"segments[{segment_index}].ea_dynamic_beta",
        ],
    )


def D015_rare_profile_type(
    *,
    profile_type: str,
) -> SolverDiagnostic:
    """
    ProfileType detectado é um dos casos raros (PT_5 U-shape slack, PT_6
    completamente vertical). PT_4 (linha boiante) está fora do escopo MVP
    v1 (w > 0 enforced) e não dispara este diagnostic.

    Confidence: high — classificação determinística do PT.
    Severity: warning — geometria válida mas atípica.
    """
    descriptions = {
        "PT_5": (
            "linha em U totalmente slack",
            "Geralmente acontece quando T_fl é muito baixo e ambos os "
            "extremos ficam acima de uma porção apoiada — caso pouco "
            "comum em mooring offshore.",
        ),
        "PT_6": (
            "linha completamente vertical",
            "X (distância horizontal âncora-fairlead) ≈ 0 — fairlead "
            "está praticamente em cima da âncora. Caso degenerado, "
            "típico de testes ou erro de input.",
        ),
        "PT_4": (
            "linha boiante com seabed",
            "Linha negativamente flutuante (w < 0) — não suportado em "
            "v1.0. Dispara pendência para Fase 12.",
        ),
    }
    pt_name, pt_explanation = descriptions.get(
        profile_type, (profile_type, "Regime catenário atípico.")
    )
    return SolverDiagnostic(
        code="D015_RARE_PROFILE_TYPE",
        severity="warning",
        title=f"Regime catenário raro: {profile_type} ({pt_name})",
        cause=(
            f"O classificador detectou {profile_type}: {pt_name}. "
            f"{pt_explanation}"
        ),
        suggestion=(
            "Verifique se a geometria do caso (T_fl, comprimento, "
            "lâmina d'água) corresponde à intenção. Resultados em "
            "regimes raros podem ter precisão numérica reduzida."
        ),
        confidence="high",
        affected_fields=[],
    )


# =============================================================================
# Diagnostics novos da Fase 7 — D016, D017 (anchor uplift)
# =============================================================================


def D016_anchor_uplift_invalid(
    *,
    endpoint_depth: float,
    h: float,
) -> SolverDiagnostic:
    """
    Anchor uplift fora do domínio válido (0 < endpoint_depth ≤ h).

    Dispara quando:
      - endpoint_depth ≤ 0 (anchor acima ou na superfície da água)
      - endpoint_depth > h + 1e-6 (anchor abaixo do seabed)

    Pré-validação Pydantic já bloqueia esse cenário, mas D016 é mantido
    como diagnostic estruturado caso o validador seja contornado (ex.:
    dados vindos de import .moor antigo com bug).

    Confidence: high — violação determinística de domínio físico.
    Severity: error — caso impossível, solver não pode prosseguir.
    """
    if endpoint_depth <= 0:
        cause = (
            f"endpoint_depth={endpoint_depth:.2f} m ≤ 0: a âncora estaria "
            f"acima ou na superfície da água. Anchor uplift requer 0 < "
            f"endpoint_depth ≤ h ({h:.2f} m)."
        )
        suggestion = (
            f"Informe endpoint_depth no intervalo (0, {h:.2f}] m. Tipicamente "
            "anchor 5-50% acima do seabed."
        )
    elif endpoint_depth > h + 1e-6:
        cause = (
            f"endpoint_depth={endpoint_depth:.2f} m > h={h:.2f} m: a "
            f"âncora estaria abaixo do seabed (geometria impossível)."
        )
        suggestion = (
            "Para anchor cravado no seabed use endpoint_grounded=True "
            f"(omita endpoint_depth). Para anchor elevado use "
            f"endpoint_depth ∈ (0, {h:.2f}] m."
        )
    else:
        # Defesa em profundidade — não deveria atingir
        cause = f"endpoint_depth={endpoint_depth:.2f} m fora do domínio."
        suggestion = "Verifique o input."

    return SolverDiagnostic(
        code="D016_ANCHOR_UPLIFT_INVALID",
        severity="error",
        title="Anchor uplift: domínio violado",
        cause=cause,
        suggestion=suggestion,
        confidence="high",
        affected_fields=["boundary.endpoint_depth"],
    )


def D017_anchor_uplift_negligible(
    *,
    endpoint_depth: float,
    h: float,
    threshold_m: float = 1.0,
) -> SolverDiagnostic:
    """
    Uplift "desprezível" — anchor a poucos metros do seabed.

    Dispara quando 0 < (h - endpoint_depth) < threshold_m (default 1m).
    Numericamente, casos quase-grounded podem ter convergência menos
    estável que o caminho dedicado de grounded (com touchdown). Sugere
    que o engenheiro reconsidere usar endpoint_grounded=True para
    obter solução mais robusta numericamente.

    Confidence: medium — heurística calibrada (1m é convencional);
    valor exato do limiar pode mudar com calibração futura.
    Severity: warning — caso solúvel, mas há alternativa mais robusta.
    """
    uplift = h - endpoint_depth
    return SolverDiagnostic(
        code="D017_ANCHOR_UPLIFT_NEGLIGIBLE",
        severity="warning",
        title=f"Anchor uplift desprezível ({uplift:.2f} m)",
        cause=(
            f"endpoint_depth={endpoint_depth:.2f} m está a apenas "
            f"{uplift:.2f} m do seabed (h={h:.2f} m). Uplift < {threshold_m:.0f} m "
            "indica anchor praticamente cravado — caso de fronteira "
            "que numericamente pode oscilar entre regimes."
        ),
        suggestion=(
            "Considere endpoint_grounded=True (anchor cravado no seabed) "
            "que usa solver dedicado com touchdown, mais robusto "
            "numericamente. Mantenha endpoint_grounded=False apenas se "
            "o anchor fica fisicamente elevado por design (ex.: pile "
            "com flutuabilidade)."
        ),
        confidence="medium",
        affected_fields=["boundary.endpoint_depth", "boundary.endpoint_grounded"],
    )


# =============================================================================
# Diagnostics novos da Fase 8 — D018, D019 (AHV)
# =============================================================================


def D018_ahv_static_idealization(
    *,
    n_ahv: int,
    tier_c_active: bool = False,
    tier_d_active: bool = False,
) -> SolverDiagnostic:
    """
    AHV (Anchor Handler Vessel) modelado como análise estática — idealização.

    **DECISÃO TÉCNICA ANTECIPADA registrada em CLAUDE.md** (seção
    "Decisão fechada — Fase 8 antecipada"):

      Análise estática de AHV é idealização — não substitui análise
      dinâmica de instalação.

    A operação real do AHV é dinâmica: rebocador se move, cabo oscila,
    hidrodinâmica entra.

    DISPARA SEMPRE quando há ≥1 AHV no caso (decisão Q6 da Fase 8). Sem
    opção de esconder.

    Sprint 4 / Commit 37: parâmetro `tier_c_active` customiza mensagem.
    Quando Tier C (Work Wire elástico) está ativo, mensagem cita
    explicitamente os limites: Work Wire é modelado como cabo estático
    elástico (não dinâmico), sem snap loads, sem hidrodinâmica do AHV.

    Confidence: medium.
    Severity: warning.
    """
    if tier_d_active:
        title = "AHV Tier D — operacional mid-line com Work Wire elástico"
        cause = (
            "Análise estática de AHV operacional (Sprint 5 / Tier D) — "
            "linha de ancoragem instalada continua íntegra entre "
            "plataforma e anchor; AHV puxa lateralmente via Work Wire "
            "conectado num ponto intermediário. Modelagem inclui: "
            "catenária elástica do mooring (split implícito no pega) + "
            "Work Wire elástico mid-line. NÃO inclui: movimento dinâmico "
            "do AHV (heave, pitch, roll), snap loads no Work Wire, "
            "hidrodinâmica do casco do AHV, fadiga por ciclos, oscilação "
            "do ângulo do ww durante operação."
        )
    elif tier_c_active:
        title = "AHV Tier C — análise estática com Work Wire elástico"
        cause = (
            "Análise estática de AHV (Sprint 4 / Tier C) — não substitui "
            "análise dinâmica de instalação. Modelagem inclui: linha de "
            "ancoragem com catenária elástica + Work Wire elástico real "
            "+ ponto de pega com continuidade horizontal. NÃO inclui: "
            "movimento dinâmico do AHV (heave, pitch, roll), snap loads "
            "no Work Wire, hidrodinâmica do casco do AHV, fadiga "
            "acumulada por ciclos."
        )
    else:
        title = (
            f"AHV — análise estática é idealização "
            f"({n_ahv} AHV{'s' if n_ahv > 1 else ''})"
        )
        cause = (
            "Análise estática de AHV é idealização — não substitui "
            "análise dinâmica de instalação. A operação real do AHV é "
            "dinâmica (rebocador se move, cabo oscila, hidrodinâmica). "
            "Esta análise modela a força aplicada pelo AHV como uma "
            "carga estática pontual aplicada à linha."
        )
    return SolverDiagnostic(
        code="D018_AHV_STATIC_IDEALIZATION",
        severity="warning",
        title=title,
        cause=cause,
        suggestion=(
            "USE para: verificação de tensão de pico em condição "
            "idealizada, dimensionamento preliminar de geometria, "
            "avaliação de equilíbrio estático.\n"
            "NÃO SUBSTITUI: análise dinâmica de instalação, avaliação "
            "de cargas de impacto (snap loads), estudo de operabilidade "
            "em condições ambientais reais. Para essas, use software "
            "dinâmico de instalação (Orcaflex, SIMA, etc.)."
        ),
        confidence="medium",
        affected_fields=[],
    )


def D019_ahv_force_mostly_out_of_plane(
    *,
    bollard_pull: float,
    in_plane_fraction: float,
    heading_deg: float,
) -> SolverDiagnostic:
    """
    Componente da força AHV no plano da linha é menor que 30% da magnitude.

    AncoPlat solver é 2D (catenária no plano vertical da linha).
    Componente "fora do plano" da força AHV não tem onde aplicar —
    solver não modela deflexão lateral da linha. Quando o heading do
    AHV resulta em força majoritariamente fora do plano, o engenheiro
    pode digitar bollard pull alto e ver resultado idêntico ao caso
    sem AHV — confusão.

    Limiar 30% (Q3 ajuste 1 do mini-plano F8): se projeção é >70% da
    magnitude, é caso típico (heading próximo do alinhamento da linha);
    abaixo disso, é avisar que a força "desaparece" matematicamente.

    Confidence: high — geometria determinística (in-plane fraction
    calculado exatamente).
    Severity: warning — análise prossegue, mas resultado pode confundir.
    """
    in_plane_pct = in_plane_fraction * 100
    out_of_plane_pct = (1 - in_plane_fraction) * 100
    return SolverDiagnostic(
        code="D019_AHV_FORCE_OUT_OF_PLANE",
        severity="warning",
        title=(
            f"AHV: componente no plano da linha pequena "
            f"({in_plane_pct:.1f}% < 30%)"
        ),
        cause=(
            f"Bollard pull = {bollard_pull/1000:.0f} kN com heading "
            f"{heading_deg:.1f}° resulta em apenas {in_plane_pct:.1f}% "
            f"da força projetada no plano vertical da linha "
            f"({out_of_plane_pct:.1f}% fica fora do plano). AncoPlat é "
            "2D — componente fora do plano NÃO é modelada. A força "
            "efetivamente aplicada pelo solver é a projeção 2D, não a "
            "magnitude total."
        ),
        suggestion=(
            "Verifique heading e geometria do caso. Se a operação real "
            "tem força majoritariamente lateral (perpendicular à linha), "
            "AncoPlat 2D não captura — considere análise 3D externa."
        ),
        confidence="high",
        affected_fields=["attachments[].ahv_heading_deg"],
    )


# =============================================================================
# Diagnostics novos da Sprint 4 — D022, D024 (AHV Tier C / Work Wire)
# =============================================================================


def D022_work_wire_near_mbl(
    *,
    bollard_pull: float,
    work_wire_mbl: float,
    threshold: float = 0.90,
) -> SolverDiagnostic:
    """
    Sprint 4 / Commit 37: Work Wire próximo da ruptura.

    Dispara quando bollard_pull >= 0.9 × MBL do Work Wire. Em operação
    real de instalação, AHV não deve operar acima de 67% do MBL como
    margem de segurança DNV-OS-E301. Atingir 90% é zona de atenção
    crítica — risco real de ruptura do cabo de trabalho.

    Confidence: high — fato determinístico (compara magnitudes).
    Severity: warning — análise prossegue mas exige revisão pelo
    engenheiro responsável.
    """
    pct = (bollard_pull / work_wire_mbl) * 100.0 if work_wire_mbl > 0 else 0.0
    return SolverDiagnostic(
        code="D022_WORK_WIRE_NEAR_MBL",
        severity="warning",
        title=(
            f"Work Wire próximo da ruptura — {pct:.0f}% do MBL "
            f"(threshold {threshold:.0%})"
        ),
        cause=(
            f"Bollard pull aplicado ({bollard_pull / 1e3:.1f} kN) "
            f"está em {pct:.0f}% do MBL do Work Wire "
            f"({work_wire_mbl / 1e3:.1f} kN). DNV-OS-E301 recomenda "
            "fator de utilização ≤ 67% para operações de instalação; "
            "valores acima de 90% indicam risco de ruptura."
        ),
        suggestion=(
            "1. Reduza o bollard_pull aplicado (use AHV de menor "
            "capacidade ou diminua a tensão do guincho).\n"
            "2. Substitua o Work Wire por cabo de maior MBL (catálogo "
            "tem opções de 89mm e 96mm).\n"
            "3. Reavalie a operação — talvez precise de 2 AHVs em "
            "tandem para distribuir carga (não modelado no Tier C)."
        ),
        confidence="high",
        affected_fields=["boundary.ahv_install.bollard_pull",
                         "boundary.ahv_install.work_wire.MBL"],
    )


def D024_tier_c_fallback_sprint2(
    *,
    fallback_reason: str,
    lay_pct: Optional[float] = None,
) -> SolverDiagnostic:
    """
    Sprint 4 / Commit 37: Tier C reduziu para Sprint 2 efetivamente.

    Dispara quando o solver Tier C detecta regime degenerado (mooring
    totalmente apoiado, ww sem suspensão viável, etc.) e cai no path
    Sprint 2 (bollard_pull aplicado direto como T_fl).

    O resultado retornado é numericamente equivalente ao Sprint 2 puro
    — Tier C não acrescenta informação no regime físico atual. Este
    diagnóstico apenas informa o engenheiro para que ele compreenda
    a equivalência (não é alarme — é transparência).

    Confidence: high — fato determinístico (solver explicitamente
    decidiu cair em fallback).
    Severity: info — apenas informativo, não ação requerida.
    """
    lay_str = f" (lay = {lay_pct:.0%} do mooring)" if lay_pct is not None else ""
    return SolverDiagnostic(
        code="D024_TIER_C_FALLBACK_SPRINT2",
        severity="info",
        title=f"Tier C reduzido a Sprint 2 (modelo equivalente){lay_str}",
        cause=(
            f"Solver Tier C detectou {fallback_reason} e usou modelo "
            "Sprint 2 efetivo (bollard pull aplicado diretamente como "
            "T_fl, Work Wire não modelado fisicamente). Resultado é "
            "matematicamente equivalente ao Sprint 2 — Tier C não "
            "acrescenta informação neste regime."
        ),
        suggestion=(
            "Para validar Tier C físico completo (Work Wire elástico "
            "com catenária real), use cenário com mooring parcialmente "
            "suspenso: águas profundas (h ≥ 1500m) + bollard pull alto "
            "(≥ 100 kN) + linha relativamente taut (folga ≤ 15%)."
        ),
        confidence="high",
        affected_fields=[],
    )


# =============================================================================
# Diagnostics novos da Sprint 5 — D025, D026 (Tier D operacional)
# =============================================================================


def D025_tier_d_fallback_f8(
    *,
    fallback_reason: str,
) -> SolverDiagnostic:
    """
    Sprint 5 / Commit 45 — Tier D reduziu para F8 puro (fallback).

    Dispara quando o solver Tier D não converge ou catenária do
    Work Wire é geometricamente inviável. Resultado equivale ao F8
    puro (carga pontual via ahv_bollard_pull/heading_deg, sem ww
    elástico modelado).

    Confidence: high — fato determinístico (solver explicitamente
    decidiu cair em fallback).
    Severity: info — apenas informativo, não-bloqueante.
    """
    return SolverDiagnostic(
        code="D025_TIER_D_FALLBACK_F8",
        severity="info",
        title="Tier D reduzido a F8 (carga pontual, sem ww modelado)",
        cause=(
            f"Solver Tier D detectou {fallback_reason} e usou modelo F8 "
            "efetivo. Resultado é matematicamente equivalente: bollard "
            "pull aplicado direto como carga pontual no ponto de pega, "
            "sem modelar a catenária elástica do Work Wire."
        ),
        suggestion=(
            "Para validar Tier D completo (ww elástico): verifique que "
            "ahv_deck_x está a uma distância horizontal ≤ ahv_work_wire."
            "length do ponto de pega, e ahv_deck_level produz chord "
            "vertical positivo (deck acima da pega)."
        ),
        confidence="high",
        affected_fields=[
            "attachments[].ahv_work_wire.length",
            "attachments[].ahv_deck_x",
            "attachments[].ahv_deck_level",
        ],
    )


def D028_snap_loads_applied(
    *,
    daf: float,
) -> SolverDiagnostic:
    """
    Sprint 7 / Commit 63 — Snap loads via DAF tabelado.

    Dispara sempre que `boundary.snap_load_daf > 1.0`. Multiplicador
    aplicado a T_fairlead/T_anchor/T_AHV no SolverResult.

    Tabela de referência DNV-RP-H103 §5.5:
      - DAF = 1.0  → análise estática pura
      - DAF = 1.5  → operação calma (mar Hs < 1m)
      - DAF = 2.0  → operação média (mar Hs 1-2m)
      - DAF = 2.5-3.0 → instalação severa (mar Hs > 2m)

    Confidence: medium — tabela aproximada, calibrada por experiência
      operacional, não derivada matematicamente.
    Severity: warning — engenheiro precisa entender que resultado é
      ENVELOPE DE PICO ESTIMADO, não dinâmica real.
    """
    if daf <= 1.5:
        regime = "operação calma (mar Hs < 1m)"
    elif daf <= 2.0:
        regime = "operação média (mar Hs 1-2m)"
    elif daf <= 3.0:
        regime = "instalação severa (mar Hs > 2m)"
    else:
        regime = "regime extremo (não-coberto pela tabela DNV)"
    return SolverDiagnostic(
        code="D028_SNAP_LOADS_APPLIED",
        severity="warning",
        title=f"Snap loads via DAF = {daf:.1f} ({regime})",
        cause=(
            f"Multiplicador dinâmico DAF = {daf:.1f} aplicado a "
            "T_fairlead, T_anchor e T_AHV no resultado. Tabela "
            "DNV-RP-H103 §5.5 recomenda este valor para o regime "
            f"'{regime}'. Resultado representa envelope de pico "
            "ESTIMADO, não simulação dinâmica real."
        ),
        suggestion=(
            "Use este valor como referência conservadora para "
            "dimensionamento preliminar. Para certificação ou "
            "operação crítica, valide com software dinâmico "
            "(Orcaflex, SIMA, RAFT) — análise estática DAF não "
            "captura: snap loads transitórios, ressonância, "
            "amortecimento hidrodinâmico, fadiga acumulada."
        ),
        confidence="medium",
        affected_fields=["boundary.snap_load_daf"],
    )


def D026_work_wire_too_horizontal(
    *,
    angle_deg: float,
    threshold_deg: float = 10.0,
) -> SolverDiagnostic:
    """
    Sprint 5 / Commit 45 — Work Wire com ângulo vertical muito raso.

    Dispara quando o ângulo do ww com a horizontal < threshold_deg.
    Indica que o AHV está muito longe do pega — geometria operacional
    incomum, possivelmente erro de parametrização.

    Confidence: medium — heurística (10° é threshold operacional).
    Severity: warning.
    """
    return SolverDiagnostic(
        code="D026_WORK_WIRE_TOO_HORIZONTAL",
        severity="warning",
        title=(
            f"Work Wire muito raso (ângulo {angle_deg:.1f}° "
            f"< threshold {threshold_deg:.0f}°)"
        ),
        cause=(
            f"O Work Wire conecta o ponto de pega ao convés do AHV "
            f"com inclinação de apenas {angle_deg:.1f}° em relação à "
            "horizontal. Em operações reais, ww quase horizontal "
            "indica que o AHV está muito distante do pega — "
            "geometria operacional incomum."
        ),
        suggestion=(
            "Reposicione o AHV (ahv_deck_x) mais perto do ponto de "
            "pega para que o ww fique predominantemente vertical "
            "(ângulo ≥ 30° tipicamente). Verifique se o caso real "
            "corresponde a esta geometria — pode indicar erro de "
            "parametrização."
        ),
        confidence="medium",
        affected_fields=[
            "attachments[].ahv_deck_x",
            "attachments[].ahv_deck_level",
        ],
    )


# =============================================================================
# Helper para classes de exceção que carregam diagnóstico
# =============================================================================


class SolverDiagnosticError(ValueError):
    """
    ValueError com diagnóstico estruturado anexado. Mantém compatibilidade
    com `pytest.raises(ValueError, match=...)` e permite que o solver
    extraia o diagnóstico no handler de exceção.
    """

    def __init__(self, diagnostic: SolverDiagnostic, message: str | None = None):
        msg = message if message is not None else f"{diagnostic.title}: {diagnostic.cause}"
        super().__init__(msg)
        self.diagnostic = diagnostic


def diagnostic_from_exception(exc: BaseException) -> SolverDiagnostic | None:
    """Extrai SolverDiagnostic de uma exceção, se disponível."""
    if isinstance(exc, SolverDiagnosticError):
        return exc.diagnostic
    return None


__all__ = [
    "D001_buoy_near_anchor",
    "D002_buoy_near_fairlead",
    "D003_arch_does_not_fit_grounded",
    "D004_buoy_above_surface",
    "D005_buoyancy_exceeds_weight",
    "D006_cable_too_short",
    "D007_tfl_below_critical_horizontal",
    "D008_safety_margin",
    "D009_anchor_uplift_high",
    "D010_high_utilization",
    "D011_cable_below_seabed",
    "D012_slope_high",
    "D013_mu_zero_with_catalog_friction",
    "D014_gmoor_without_beta",
    "D015_rare_profile_type",
    "D016_anchor_uplift_invalid",
    "D017_anchor_uplift_negligible",
    "D018_ahv_static_idealization",
    "D019_ahv_force_mostly_out_of_plane",
    "D022_work_wire_near_mbl",
    "D024_tier_c_fallback_sprint2",
    "D025_tier_d_fallback_f8",
    "D026_work_wire_too_horizontal",
    "D028_snap_loads_applied",
    "D900_generic_nonconvergence",
    "SolverDiagnostic",
    "SolverDiagnosticError",
    "SuggestedChange",
    "diagnostic_from_exception",
]
