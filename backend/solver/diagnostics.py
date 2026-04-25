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

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


SeverityLevel = Literal["error", "warning"]


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
    """

    model_config = ConfigDict(frozen=True)

    code: str = Field(..., description="Código único (D001, D002, ...)")
    severity: SeverityLevel = Field(..., description="error ou warning")
    title: str = Field(..., description="Resumo em uma linha")
    cause: str = Field(..., description="Explicação física/matemática")
    suggestion: str = Field(
        default="",
        description="Como corrigir, em prosa. Pode ser vazio se houver suggested_changes.",
    )
    suggested_changes: list[SuggestedChange] = Field(default_factory=list)


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
        severity="error",
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
        severity="error",
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
        severity="error",
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
        severity="warning",
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
        severity="error",
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
        severity="error",
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
        severity="error",
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
        severity="error",
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
    "D900_generic_nonconvergence",
    "SolverDiagnostic",
    "SolverDiagnosticError",
    "SuggestedChange",
    "diagnostic_from_exception",
]
