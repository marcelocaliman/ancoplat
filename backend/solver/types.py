"""
Estruturas de dados base do solver AncoPlat.

Todas as grandezas físicas em SI (m, N, Pa, N/m). Conversões só nas bordas
do sistema (UI, importação/exportação).

Referências:
  - Documento A v2.2, Seções 3.2 (variáveis), 3.5 (método numérico)
  - Documentação MVP v2, Seção 6 (saídas obrigatórias) e Seção 8 (validações)
"""
from __future__ import annotations

from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class SolutionMode(str, Enum):
    """Modo de solução — qual grandeza é input, qual é output."""

    TENSION = "Tension"  # input: T_fl; output: X_total
    RANGE = "Range"  # input: X_total; output: T_fl


class ConvergenceStatus(str, Enum):
    """Estados finais do solver (Documento A v2.2, Seção 3.5.5)."""

    CONVERGED = "converged"
    MAX_ITERATIONS = "max_iterations"
    INVALID_CASE = "invalid_case"
    NUMERICAL_ERROR = "numerical_error"
    ILL_CONDITIONED = "ill_conditioned"


class AlertLevel(str, Enum):
    """
    Classificação da utilização T_fl/MBL (Seção 5 do Documento A v2.2).

    - ok:     utilização abaixo do limite amarelo (linha em regime normal)
    - yellow: atenção (padrão: T/MBL ≥ 0,50)
    - red:    limite operacional intacto atingido (padrão: T/MBL ≥ 0,60)
    - broken: linha rompida matemáticamente (T/MBL ≥ 1,00 → INVALID_CASE)
    """

    OK = "ok"
    YELLOW = "yellow"
    RED = "red"
    BROKEN = "broken"


class CriteriaProfile(str, Enum):
    """
    Perfis de critério de utilização (Seção 5 do Documento A v2.2, resposta P-04).

    - MVP_Preliminary: default simples, 0.50/0.60/1.00
    - API_RP_2SK:      intacto 0.60, danificado 0.80 (ainda 1.00 para broken)
    - DNV_placeholder: reservado para ULS/ALS/FLS; tratado como MVP até F4+
    - UserDefined:     usuário fornece yellow/red/broken ratios
    """

    MVP_PRELIMINARY = "MVP_Preliminary"
    API_RP_2SK = "API_RP_2SK"
    DNV_PLACEHOLDER = "DNV_placeholder"
    USER_DEFINED = "UserDefined"


class UtilizationLimits(BaseModel):
    """
    Limites absolutos de T_fl/MBL que disparam cada AlertLevel.

    A ordem deve ser: yellow_ratio < red_ratio < broken_ratio.
    """

    model_config = ConfigDict(frozen=True)

    yellow_ratio: float = Field(default=0.50, gt=0.0, le=1.0)
    red_ratio: float = Field(default=0.60, gt=0.0, le=1.0)
    broken_ratio: float = Field(default=1.00, gt=0.0, le=2.0)

    @model_validator(mode="after")
    def _ordered(self) -> "UtilizationLimits":
        if not (self.yellow_ratio < self.red_ratio < self.broken_ratio):
            raise ValueError(
                "limites devem satisfazer yellow < red < broken "
                f"(recebido {self.yellow_ratio}/{self.red_ratio}/{self.broken_ratio})"
            )
        return self


# Limites padrão por perfil (Seção 5 e resposta P-04 do Documento B).
PROFILE_LIMITS: dict[CriteriaProfile, UtilizationLimits] = {
    CriteriaProfile.MVP_PRELIMINARY: UtilizationLimits(
        yellow_ratio=0.50, red_ratio=0.60, broken_ratio=1.00,
    ),
    CriteriaProfile.API_RP_2SK: UtilizationLimits(
        yellow_ratio=0.50, red_ratio=0.60, broken_ratio=0.80,
    ),
    CriteriaProfile.DNV_PLACEHOLDER: UtilizationLimits(
        yellow_ratio=0.50, red_ratio=0.60, broken_ratio=1.00,
    ),
    # USER_DEFINED não tem default — o usuário obrigatoriamente passa.
}


def classify_utilization(
    utilization: float,
    profile: CriteriaProfile = CriteriaProfile.MVP_PRELIMINARY,
    user_limits: Optional[UtilizationLimits] = None,
) -> AlertLevel:
    """
    Retorna o AlertLevel dado a utilização e o perfil.

    Parâmetros
    ----------
    utilization : T_fl / MBL (adimensional, 0..∞). Valores acima de broken
                  sempre retornam BROKEN.
    profile : perfil de critério. Default MVP_PRELIMINARY.
    user_limits : obrigatório se profile == USER_DEFINED; ignorado senão.
    """
    if profile == CriteriaProfile.USER_DEFINED:
        if user_limits is None:
            raise ValueError(
                "CriteriaProfile.USER_DEFINED requer `user_limits` explicito"
            )
        limits = user_limits
    else:
        limits = PROFILE_LIMITS[profile]

    if utilization >= limits.broken_ratio:
        return AlertLevel.BROKEN
    if utilization >= limits.red_ratio:
        return AlertLevel.RED
    if utilization >= limits.yellow_ratio:
        return AlertLevel.YELLOW
    return AlertLevel.OK


LineCategory = Literal["Wire", "StuddedChain", "StudlessChain", "Polyester"]


class LineSegment(BaseModel):
    """
    Segmento homogêneo de linha de ancoragem.

    Grandezas em SI: comprimento em m, peso em N/m, EA e MBL em N.

    Campos opcionais `category` e `line_type` refletem Seção 5.1 do MVP v2
    PDF e Seção 4.2 do Documento A; servem para rastreabilidade e para
    escolher defaults de atrito na Seção 4.4 quando o solo é conhecido.

    ─── Campos físicos por segmento (Fase 1) ────────────────────────────
    Estes três campos foram adicionados na Fase 1 do plano de
    profissionalização para resolver as divergências B3 (atrito global) e
    A1.4+B4 (EA toggle):

    `mu_override`: coeficiente de atrito axial específico para este
        segmento, sobrescrevendo qualquer outra fonte. Use para casos onde
        o usuário sabe explicitamente o atrito do trecho.

    `seabed_friction_cf`: coeficiente de atrito derivado do catálogo
        (line_type → seabed_friction_cf). Populado automaticamente pelo
        API service ao traduzir do catálogo. Solver puro (sem DB) recebe
        já resolvido.

    `ea_source`: qual coluna do catálogo foi usada para popular `EA` —
        "qmoor" (default, EA estático) ou "gmoor" (EA dinâmico, modelo
        NREL/MoorPy). Documentado em CLAUDE.md seção "Modelo físico de
        QMoor vs GMoor".

    `ea_dynamic_beta`: coeficiente β do modelo dinâmico MoorPy
        (`EA = α + β × T_mean`). RESERVADO — não-implementado em v1.0.
        Quando presente e `ea_source="gmoor"`, ativaria iteração externa
        de tensão. Mantido como campo opcional para futura compatibilidade.

    ─── Precedência do atrito (resolvida pela facade `solve()`) ─────────
        segment.mu_override → segment.seabed_friction_cf → seabed.mu → 0.0
    Defaults `None` preservam o comportamento legado (cai no `seabed.mu`
    global, equivalente a antes da Fase 1). Esta é uma decisão consciente
    em substituição à feature-flag `use_per_segment_friction` originalmente
    prevista no plano (R1.1) — ver CLAUDE.md.
    """

    model_config = ConfigDict(frozen=True)

    length: float = Field(..., description="Comprimento não-esticado (m)")
    w: float = Field(..., description="Peso submerso por unidade de comprimento (N/m)")
    EA: float = Field(..., description="Rigidez axial do segmento (N)")
    MBL: float = Field(..., description="Minimum Breaking Load (N)")
    category: Optional[LineCategory] = Field(
        default=None, description="Wire, StuddedChain, StudlessChain ou Polyester"
    )
    line_type: Optional[str] = Field(
        default=None,
        description="Identificador no catálogo (ex.: 'IWRCEIPS', 'R4Studless')",
    )
    # Metadados geométricos (não entram no cálculo do solver, mas aparecem
    # em relatórios/memoriais e na UI). Opcionais para retrocompatibilidade.
    diameter: Optional[float] = Field(
        default=None, description="Diâmetro nominal (m) — metadado"
    )
    dry_weight: Optional[float] = Field(
        default=None, description="Peso seco por unidade (N/m) — metadado"
    )
    modulus: Optional[float] = Field(
        default=None, description="Módulo axial aparente (Pa) — metadado"
    )

    # ─── Atrito per-segmento (Fase 1 / B3) ────────────────────────────
    mu_override: Optional[float] = Field(
        default=None,
        ge=0.0,
        description=(
            "Coeficiente de atrito axial específico do segmento, "
            "sobrescrevendo seabed.mu global e o do catálogo. "
            "None = não sobrescreve."
        ),
    )
    seabed_friction_cf: Optional[float] = Field(
        default=None,
        ge=0.0,
        description=(
            "Coeficiente de atrito do catálogo (line_type.seabed_friction_cf). "
            "Populado pelo API service ao traduzir do catálogo. "
            "Solver consome após mu_override e antes de seabed.mu."
        ),
    )

    # ─── EA source (Fase 1 / A1.4+B4) ─────────────────────────────────
    ea_source: Literal["qmoor", "gmoor"] = Field(
        default="qmoor",
        description=(
            "Origem do EA: 'qmoor' (estático, EA_MBL × MBL) ou 'gmoor' "
            "(dinâmico, EAd × MBL — termo α do modelo NREL/MoorPy). "
            "Default 'qmoor' preserva comportamento histórico do AncoPlat."
        ),
    )
    ea_dynamic_beta: Optional[float] = Field(
        default=None,
        ge=0.0,
        description=(
            "RESERVADO — coeficiente β (EAd_Lm) do modelo dinâmico "
            "completo `EA = α + β × T_mean`. NÃO implementado em v1.0; "
            "campo existe para compatibilidade com Fase 4+. "
            "Quando None ou 0, modelo dinâmico é simplificado a α constante."
        ),
    )

    @field_validator("length", "EA", "MBL")
    @classmethod
    def _must_be_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("deve ser > 0")
        return v

    @field_validator("w")
    @classmethod
    def _weight_nonzero(cls, v: float) -> float:
        # w > 0 para linha com peso próprio (wire, chain, poliéster não-neutralizado).
        # Se um dia tivermos linha neutra (boia distribuída), relaxar esta regra.
        if v <= 0:
            raise ValueError("peso submerso w deve ser > 0 no MVP v1")
        return v


AttachmentKind = Literal["clump_weight", "buoy"]


class LineAttachment(BaseModel):
    """
    Elemento pontual ao longo da linha — boia (empuxo líquido) ou clump
    weight (peso adicional). F5.2 + F5.4.6a.

    A posição pode ser informada de duas formas (use **exatamente uma**):

    - `position_s_from_anchor` (m, recomendado) — arc length desde a
      âncora ao longo da linha **não-esticada**. O solver divide o
      segmento que contém essa posição em dois sub-segmentos idênticos
      durante o pré-processamento, transformando o attachment numa junção
      virtual (preserva a matemática original do solver de junções).

    - `position_index` (legacy, F5.2) — índice da junção pré-existente
      entre segmentos heterogêneos. 0 = entre seg 0 e seg 1.

    `submerged_force` é magnitude positiva (N). A direção física é
    determinada pelo `kind`:
      - `clump_weight`: tende a puxar a linha para BAIXO → V += force
      - `buoy`:         tende a empurrar a linha para CIMA  → V −= force
    """

    model_config = ConfigDict(frozen=True)

    kind: AttachmentKind
    submerged_force: float = Field(
        ..., gt=0,
        description="Força submersa líquida em N (sempre positiva)",
    )
    position_index: Optional[int] = Field(
        default=None,
        ge=0,
        description=(
            "(Legacy F5.2) Índice da junção pré-existente entre "
            "segmentos. 0 = entre seg 0 e seg 1; deve ser ≤ N-2."
        ),
    )
    position_s_from_anchor: Optional[float] = Field(
        default=None,
        gt=0,
        description=(
            "Arc length desde a âncora (m), ao longo da linha "
            "não-esticada. Use este modo quando a boia/clump fica no "
            "meio de um segmento — o solver divide o segmento "
            "automaticamente. Mutuamente exclusivo com `position_index`."
        ),
    )
    name: Optional[str] = Field(
        default=None, max_length=80,
        description="Identificador legível para relatórios (ex.: 'Boia A')",
    )
    tether_length: Optional[float] = Field(
        default=None,
        gt=0,
        description=(
            "Comprimento do pendant/cabo de conexão entre o corpo "
            "(boia ou clump) e a linha principal, em metros. "
            "Quando informado, indica que o corpo está a essa "
            "distância vertical do ponto de attachment na linha. "
            "Para análise estática com pendant taut, `submerged_force` "
            "deve ser informado como o EFEITO LÍQUIDO no ponto de "
            "conexão (empuxo do corpo menos peso do pendant). O "
            "solver não usa `tether_length` no cálculo — ele "
            "alimenta apenas a visualização."
        ),
    )

    # ─── Metadados detalhados da boia (espelham o que softwares
    # profissionais como AHV/AHTS expõem). Não afetam o cálculo —
    # documentam o hardware no relatório PDF e na UI. Campos
    # ignorados quando kind='clump_weight'. ─────────────────────
    buoy_type: Optional[str] = Field(
        default=None,
        description=(
            "Tipo de boia: 'surface' (boia de superfície, marca de "
            "amarração) ou 'submersible' (submergível, lazy-S/wave). "
            "Apenas metadado — não afeta o cálculo."
        ),
    )
    buoy_end_type: Optional[str] = Field(
        default=None,
        description=(
            "Formato dos terminais da boia cilíndrica: 'elliptical', "
            "'flat', 'hemispherical', 'semi_conical'. Influencia o "
            "cálculo de empuxo total quando `submerged_force` não é "
            "informado diretamente — atualmente metadado para PDF."
        ),
    )
    buoy_outer_diameter: Optional[float] = Field(
        default=None, gt=0,
        description="Diâmetro externo da boia (m). Metadado.",
    )
    buoy_length: Optional[float] = Field(
        default=None, gt=0,
        description="Comprimento da boia cilíndrica (m). Metadado.",
    )
    buoy_weight_in_air: Optional[float] = Field(
        default=None, ge=0,
        description=(
            "Peso da boia no ar (N). Metadado para auditoria; "
            "`submerged_force` deve refletir o empuxo líquido com "
            "este peso já descontado."
        ),
    )

    # ─── Pennant line (cabo de conexão) — modelo do cabo ─────
    pendant_line_type: Optional[str] = Field(
        default=None, max_length=80,
        description=(
            "Identificador do cabo do pendant no catálogo de tipos "
            "de linha (ex.: 'IWRCEIPS'). Metadado para PDF."
        ),
    )
    pendant_diameter: Optional[float] = Field(
        default=None, gt=0,
        description="Diâmetro do cabo do pendant (m). Metadado.",
    )

    @model_validator(mode="after")
    def _exactly_one_position(self) -> "LineAttachment":
        has_idx = self.position_index is not None
        has_s = self.position_s_from_anchor is not None
        if has_idx and has_s:
            raise ValueError(
                "LineAttachment: especifique exatamente um entre "
                "`position_index` e `position_s_from_anchor` (não ambos)"
            )
        if not has_idx and not has_s:
            raise ValueError(
                "LineAttachment: é obrigatório informar `position_index` "
                "(junção entre segmentos) ou `position_s_from_anchor` "
                "(distância em m da âncora)"
            )
        return self


class BoundaryConditions(BaseModel):
    """
    Condições de contorno físicas do problema.

    `h` é a **profundidade do seabed sob a âncora** medida a partir da
    superfície da água — equivalente a `water_depth_at_anchor` no
    domínio de mooring offshore. Como a âncora sempre está no seabed
    no MVP v1 (`endpoint_grounded=True`), `h` coincide com a lâmina
    d'água naquela coluna.

    O **drop vertical** efetivo usado pela catenária (distância anchor
    → fairlead) é `h - startpoint_depth`, calculado dentro do facade
    `solve()` e não exposto como input direto. Em seabed inclinado, a
    profundidade do seabed sob o FAIRLEAD difere de `h` — pelo
    `seabed.slope_rad` × distância horizontal — e é exposta no resultado
    em `SolverResult.depth_at_fairlead`.

    Decisão registrada na Fase 2 do plano de profissionalização (E4):
    a docstring antiga descrevia `h` como "distância vertical anchor →
    fairlead" — semantica errada que confundia engenheiros. Corrigida
    aqui para "profundidade do seabed sob a âncora" (water_depth_at_anchor).
    O frontend agora oferece input por batimetria nos dois pontos com
    slope derivado (`BathymetryInputGroup`).

    Campos `startpoint_depth` e `endpoint_grounded` refletem Seção 5.1 do
    MVP v2 PDF. O MVP v1 assume:
      - fairlead (startpoint) na superfície → startpoint_depth = 0
      - âncora (endpoint) no seabed         → endpoint_grounded = True
    Valores diferentes são validados pelo facade solve() e geram INVALID_CASE
    com mensagem clara. Suporte para âncora elevada fica para v2+.

    Campos `startpoint_offset_horz` e `startpoint_offset_vert` (Fase 2 /
    A2.6) são **cosméticos em v1.0** — afetam apenas a visualização
    do plot, NÃO entram no cálculo do solver. Reservados para forward-
    compat com fase futura que tornará o offset físico.
    """

    model_config = ConfigDict(frozen=True)

    h: float = Field(
        ...,
        description=(
            "Profundidade do seabed sob a âncora (water_depth_at_anchor, m). "
            "Como a âncora sempre está no seabed no MVP v1, h coincide com a "
            "lâmina d'água naquela coluna."
        ),
    )
    mode: SolutionMode
    input_value: float = Field(
        ..., description="T_fl (N) se mode=Tension; X_total (m) se mode=Range"
    )
    startpoint_depth: float = Field(
        default=0.0, ge=0.0,
        description="Profundidade do fairlead abaixo da superfície (m). MVP v1: sempre 0.",
    )
    endpoint_grounded: bool = Field(
        default=True,
        description="Se True, âncora está no seabed. MVP v1 exige True.",
    )

    # ─── Offset cosmético do startpoint (Fase 2 / A2.6) ───────────────
    # Reservado em v1.0 — afeta APENAS a posição do ícone do fairlead no
    # plot, NÃO entra no cálculo do solver. Mantido como campo opcional
    # para forward-compat com fase futura que tornará o offset físico
    # (similar ao tratamento de `ea_dynamic_beta` na Fase 1).
    startpoint_offset_horz: float = Field(
        default=0.0,
        description=(
            "Offset horizontal do startpoint a partir da âncora (m). "
            "COSMÉTICO em v1.0 — afeta apenas a visualização do plot, "
            "NÃO entra no cálculo. Reservado para fase futura."
        ),
    )
    startpoint_offset_vert: float = Field(
        default=0.0,
        description=(
            "Offset vertical do startpoint relativo à superfície (m, "
            "positivo acima). Equivalente ao 'Deck Level above SWL' do "
            "QMoor 0.8.5. COSMÉTICO em v1.0 — afeta apenas a visualização "
            "do plot. Reservado para fase futura."
        ),
    )

    # ─── Tipo do startpoint (Fase 3 / A2.5+D7) ────────────────────────
    # Cosmético: define qual ícone aparece sobre o fairlead no plot.
    # NUNCA usado pelo solver — todas as 4 opções produzem o mesmo
    # resultado físico. Default "semisub" preserva o ícone que aparecia
    # antes da Fase 3 (FPSO/semi-sub style).
    startpoint_type: Literal["semisub", "ahv", "barge", "none"] = Field(
        default="semisub",
        description=(
            "Tipo da plataforma — afeta APENAS o ícone do plot. NÃO "
            "entra no cálculo. Valores: semisub (FPSO/semi-sub, default), "
            "ahv (Anchor Handler Vessel), barge (balsa), none (sem ícone)."
        ),
    )

    @field_validator("h", "input_value")
    @classmethod
    def _must_be_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("deve ser > 0")
        return v


class SeabedConfig(BaseModel):
    """
    Configuração do seabed.

    Por padrão é horizontal (slope_rad = 0). F5.3 adiciona suporte a
    inclinação constante: o seabed é uma reta passando pelo anchor com
    inclinação `slope_rad` em relação à horizontal. Convenção:
      - slope_rad > 0: seabed sobe em direção ao fairlead (anchor mais
        profundo que o ponto sob o fairlead).
      - slope_rad < 0: seabed desce em direção ao fairlead.
    Range admitido: ±π/4 (≈ ±45°).
    """

    model_config = ConfigDict(frozen=True)

    mu: float = Field(default=0.0, ge=0.0, description="Coeficiente de atrito axial")
    slope_rad: float = Field(
        default=0.0,
        ge=-0.7854,  # -π/4
        le=0.7854,
        description=(
            "Inclinação do seabed em radianos (range ±π/4). "
            "Positivo = sobe na direção do fairlead. F5.3."
        ),
    )


class SolverConfig(BaseModel):
    """
    Tolerâncias e limites numéricos.

    Defaults conforme Seção 3.5.3 do Documento A v2.2 (validados pelo
    engenheiro revisor, resposta P-02).
    """

    model_config = ConfigDict(frozen=True)

    horz_tolerance: float = Field(default=1e-4, gt=0, description="Erro horizontal relativo")
    vert_tolerance: float = Field(default=1e-4, gt=0, description="Erro vertical relativo")
    force_tolerance: float = Field(default=1e-3, gt=0, description="Erro relativo de força")
    elastic_tolerance: float = Field(default=1e-5, gt=0, description="Tolerância loop elástico")
    max_brent_iter: int = Field(default=100, gt=0)
    max_elastic_iter: int = Field(default=30, gt=0)
    n_plot_points: int = Field(
        default=5000, ge=3,
        description=(
            "Pontos discretos da geometria (âncora → fairlead). Default 5000 "
            "entrega curva visualmente lisa em plots zoom-in; pode ser "
            "reduzido para benchmarks ou export compacto."
        ),
    )
    # Obs.: a Seção 3.5.1 do Documento A v2.2 mencionava um fallback manual
    # de bisseção (`max_bisection_iter`). Como scipy.optimize.brentq já é
    # um método híbrido Brent-Dekker com fallback de bisseção nativo e
    # nunca falhou nos 45 testes da F1b, o campo foi removido. Decisão
    # registrada em CLAUDE.md seção "Fallback de bisseção NÃO implementado".


class SolverResult(BaseModel):
    """
    Saída completa do solver.

    Campos obrigatórios conforme Seção 6 da Documentação MVP v2:
      coords.x/y, tension.x/y, fairleadTension, totalHorzDistance,
      endpointDepth, stretchedLength/unstretchedLength, elongation,
      distToFirstTD, totalGroundedLength, suspendedLength/totalSuspendedLength,
      angleWRThorz/angleWRTvert.

    Campos adicionais (H, iterations_used, …) são diagnósticos internos.
    """

    model_config = ConfigDict(frozen=True)

    # --- Status ---
    status: ConvergenceStatus
    message: str = ""

    # --- Geometria discretizada (âncora → fairlead, em SI) ---
    coords_x: list[float] = Field(default_factory=list, description="x (m)")
    coords_y: list[float] = Field(default_factory=list, description="y (m)")

    # --- Tensão ao longo da linha ---
    tension_x: list[float] = Field(default_factory=list, description="T_horizontal (N) por nó")
    tension_y: list[float] = Field(default_factory=list, description="T_vertical (N) por nó")
    tension_magnitude: list[float] = Field(default_factory=list, description="|T| (N) por nó")

    # --- Escalares ---
    fairlead_tension: float = 0.0
    anchor_tension: float = 0.0
    total_horz_distance: float = 0.0
    endpoint_depth: float = 0.0

    # --- Comprimentos ---
    unstretched_length: float = 0.0
    stretched_length: float = 0.0
    elongation: float = 0.0
    total_suspended_length: float = 0.0
    total_grounded_length: float = 0.0
    dist_to_first_td: Optional[float] = None

    # --- Ângulos (radianos) ---
    angle_wrt_horz_fairlead: float = 0.0
    angle_wrt_vert_fairlead: float = 0.0
    angle_wrt_horz_anchor: float = 0.0
    angle_wrt_vert_anchor: float = 0.0

    # --- Diagnóstico interno ---
    H: float = 0.0  # Componente horizontal da tração (constante no trecho suspenso)
    iterations_used: int = 0
    utilization: float = 0.0  # fairlead_tension / MBL (0..1)
    alert_level: AlertLevel = AlertLevel.OK  # classificação por CriteriaProfile

    # --- Anchor uplift (F5.4.6b) ---
    # `angle_wrt_horz_anchor` em radianos já está acima; aqui derivamos
    # uma severidade categórica. Drag anchors (mais comuns em mooring
    # offshore) toleram pouco uplift — convencional ≤ 5°. Pilars e
    # suction caissons toleram mais. Usamos 5°/15° como thresholds
    # default (drag-friendly); usuário pode sobrescrever em UI futura.
    anchor_uplift_severity: str = "ok"  # 'ok' | 'warning' | 'critical'

    # --- Contexto geométrico global (para plots surface-relative) ---
    # Propagados pelo facade solve() a partir de BoundaryConditions. Permitem
    # que o frontend renderize a geometria com Y=0 na superfície, fairlead
    # a y=-startpoint_depth e seabed a y=-water_depth. Opcionais para
    # compatibilidade com testes unitários que chamam diretamente o solver
    # rígido/elástico (bypassando o facade).
    water_depth: float = 0.0
    startpoint_depth: float = 0.0

    # --- Auditoria ---
    # Versão do solver que produziu este resultado. Permite identificar,
    # em uma execução antiga, qual conjunto de regras numéricas/limites foi
    # usado. Default vazio para compatibilidade com testes que constroem
    # SolverResult manualmente. O facade solve() preenche sempre.
    solver_version: str = ""

    # --- Multi-segmento (F5.1) ---
    # Índices dentro de coords_x/y onde cada segmento termina (boundary).
    # Tem N+1 entradas para N segmentos: [0, n_seg_0, n_seg_0+n_seg_1, ...].
    # Vazio para casos single-segmento (compatibilidade).
    segment_boundaries: list[int] = Field(default_factory=list)

    # --- Batimetria (F5.3.z) ---
    # Profundidade do seabed nos dois pontos críticos do problema, ambos
    # medidos da superfície da água (positivo = abaixo). Em casos sem
    # slope, ambos são iguais a `water_depth`. Com slope, eles diferem
    # exatamente por `tan(slope_rad) · total_horz_distance`.
    #
    # Convenção (slope_rad > 0 = seabed sobe ao fairlead):
    #   depth_at_anchor   ≥ depth_at_fairlead  (anchor mais fundo)
    # Convenção (slope_rad < 0 = seabed desce ao fairlead):
    #   depth_at_anchor   ≤ depth_at_fairlead  (anchor mais raso)
    depth_at_anchor: float = 0.0
    depth_at_fairlead: float = 0.0

    # --- Validação física pós-solve (F5.7.3) ---
    # Lista de boias cujo corpo (após aplicar tether/pendant) ficou ACIMA
    # da superfície da água. Fisicamente, uma boia de superfície flutua
    # em y=0 — não consegue voar acima da água. Quando isso ocorre, o
    # empuxo configurado é grande demais pra geometria do caso. O solver
    # ainda devolve a geometria (CONVERGED) pra inspeção visual, mas
    # marca aqui pra UI alertar e para o engenheiro reduzir o empuxo
    # ou aumentar T_fl/clump. Cada item é dict com keys: index (0-based),
    # name, height_above_surface_m.
    surface_violations: list[dict] = Field(default_factory=list)

    # --- Diagnósticos estruturados (F5.7.4) ---
    # Lista de avisos/erros do solver em formato estruturado, com
    # sugestões de correção que a UI pode renderizar como botões
    # "Aplicar". Formato: SolverDiagnostic em backend/solver/diagnostics.py.
    # Vazio quando o caso converge limpo. Para erros, SolverResult vem
    # com status INVALID_CASE e ESTE campo descreve o problema com
    # sugestão concreta (substitui mensagens texto soltas).
    diagnostics: list[dict] = Field(default_factory=list)


# ───────────────────────────────────────────────────────────────────────
# F5.4 — Tipos para mooring system multi-linha
# ───────────────────────────────────────────────────────────────────────


class MooringLineResult(BaseModel):
    """
    Resultado de uma linha individual dentro de um mooring system (F5.4).

    Encapsula o `SolverResult` completo da linha mais informações de
    posicionamento no plano da plataforma: posição do fairlead, posição
    da âncora e força horizontal sentida pela plataforma a partir desta
    linha. Toda geometria em metros, força em Newtons.

    Convenção: o fairlead está em
      `(R · cos(θ), R · sin(θ))`
    onde θ = azimuth em rad e R = `fairlead_radius`. A linha sai
    radialmente, então a âncora fica em
      `((R + X) · cos(θ), (R + X) · sin(θ))`
    com X = `solver_result.total_horz_distance`.

    A força horizontal sobre a plataforma vinda desta linha é a
    componente horizontal da tração no fairlead, apontando do fairlead
    em direção à âncora (ou seja, +θ — radialmente para fora):
      `horz_force_xy = H · (cos(θ), sin(θ))`
    """

    model_config = ConfigDict(frozen=True)

    line_name: str = Field(..., min_length=1, max_length=80)
    fairlead_azimuth_deg: float = Field(..., ge=0.0, lt=360.0)
    fairlead_radius: float = Field(..., gt=0.0)

    fairlead_xy: tuple[float, float] = Field(
        ..., description="Posição do fairlead no plano da plataforma (m)."
    )
    anchor_xy: tuple[float, float] = Field(
        ..., description="Posição da âncora no plano da plataforma (m)."
    )
    horz_force_xy: tuple[float, float] = Field(
        ...,
        description=(
            "Componentes Fx, Fy (N) da força horizontal exercida pela "
            "linha sobre a plataforma no plano XY do casco."
        ),
    )

    solver_result: SolverResult


class MooringSystemResult(BaseModel):
    """
    Resultado agregado de um mooring system multi-linha (F5.4).

    Cada linha é resolvida independentemente (sem equilíbrio de
    plataforma). A agregação aqui é informativa: reporta o resultante
    horizontal das forças sobre o casco e, em equilíbrio sem cargas
    externas, deve ser próximo de zero para um spread balanceado.

    `worst_alert_level` segue a hierarquia broken > red > yellow > ok;
    útil pra colorir a plan view. `n_invalid` conta linhas que não
    convergiram e portanto NÃO entram no agregado de forças.
    """

    model_config = ConfigDict(frozen=True)

    lines: list[MooringLineResult]

    aggregate_force_xy: tuple[float, float] = Field(
        ...,
        description=(
            "Soma vetorial das forças horizontais sobre a plataforma (N), "
            "ignorando linhas que não convergiram."
        ),
    )
    aggregate_force_magnitude: float = Field(..., ge=0.0)
    aggregate_force_azimuth_deg: float = Field(
        default=0.0,
        ge=0.0,
        lt=360.0,
        description=(
            "Direção do resultante. Sem significado quando "
            "`aggregate_force_magnitude` é numericamente zero."
        ),
    )

    max_utilization: float = Field(default=0.0, ge=0.0)
    worst_alert_level: AlertLevel = Field(default=AlertLevel.OK)
    n_converged: int = Field(default=0, ge=0)
    n_invalid: int = Field(default=0, ge=0)

    solver_version: str = Field(default="")


# ───────────────────────────────────────────────────────────────────────
# F5.5 — Equilíbrio de plataforma sob carga ambiental
# ───────────────────────────────────────────────────────────────────────


class EnvironmentalLoad(BaseModel):
    """
    Carga ambiental sobre a plataforma (F5.5).

    Resultante horizontal de vento + corrente + onda média (1ª ordem).
    Convenção: força ATUANDO na plataforma; o solver acha o offset
    (Δx, Δy) tal que a soma das forças das linhas restauradoras + Fenv
    seja zero.

    `Mz` (momento em torno do eixo vertical) fica reservado mas não é
    usado no MVP — para isso seria preciso modelar fairleads não-radiais
    ou tomar yaw como graus de liberdade adicional.
    """

    model_config = ConfigDict(frozen=True)

    Fx: float = Field(
        default=0.0,
        description="Componente X da carga ambiental (N) no frame da plataforma.",
    )
    Fy: float = Field(
        default=0.0,
        description="Componente Y da carga ambiental (N) no frame da plataforma.",
    )
    Mz: float = Field(
        default=0.0,
        description=(
            "Momento em torno do eixo Z (N·m). Reservado — não usado "
            "no MVP atual (mooring radial; M_z sempre 0 em equilíbrio)."
        ),
    )

    @property
    def magnitude(self) -> float:
        return (self.Fx**2 + self.Fy**2) ** 0.5


class PlatformEquilibriumResult(BaseModel):
    """
    Resultado do solver de equilíbrio de plataforma (F5.5).

    Para uma carga ambiental dada, o solver encontra o offset
    (Δx, Δy) da plataforma e resolve cada linha na geometria
    deslocada. Cada `MooringLineResult` aqui reflete a tensão e o
    perfil resultante da linha NA POSIÇÃO de equilíbrio (não no
    baseline).

    `restoring_force_xy` é a soma vetorial das forças horizontais das
    linhas no offset de equilíbrio. Em equilíbrio perfeito,
    `restoring_force_xy + (env.Fx, env.Fy) ≈ 0` (resíduo numérico).
    """

    model_config = ConfigDict(frozen=True)

    environmental_load: EnvironmentalLoad
    offset_xy: tuple[float, float] = Field(
        ...,
        description=(
            "Offset da plataforma a partir da posição neutra (m). "
            "Positivo na direção do empurrão da carga ambiental."
        ),
    )
    offset_magnitude: float = Field(..., ge=0.0)
    offset_azimuth_deg: float = Field(default=0.0, ge=0.0, lt=360.0)

    lines: list[MooringLineResult]

    restoring_force_xy: tuple[float, float] = Field(
        ...,
        description=(
            "Soma vetorial das forças das linhas no offset de equilíbrio "
            "(N). Em equilíbrio com Fenv, `restoring + env_force ≈ 0`."
        ),
    )
    residual_magnitude: float = Field(
        default=0.0, ge=0.0,
        description=(
            "‖Σ F_linhas + F_env‖ no offset final (N). Mede a qualidade "
            "da convergência; valores típicos < 10 N."
        ),
    )
    iterations: int = Field(default=0, ge=0)
    converged: bool = Field(default=False)
    message: str = Field(default="")

    max_utilization: float = Field(default=0.0, ge=0.0)
    worst_alert_level: AlertLevel = Field(default=AlertLevel.OK)
    n_converged: int = Field(default=0, ge=0)
    n_invalid: int = Field(default=0, ge=0)

    solver_version: str = Field(default="")


class WatchcirclePoint(BaseModel):
    """
    F5.6 — Um ponto da varredura watchcircle.

    Representa o estado de equilíbrio para uma carga de magnitude
    fixa aplicada num azimuth específico. A coleção de pontos forma
    o envelope (curva fechada) que o centro da plataforma traça
    quando a direção da carga varia em 360°.
    """

    model_config = ConfigDict(frozen=True)

    azimuth_deg: float = Field(..., ge=0.0, lt=360.0)
    magnitude_n: float = Field(..., ge=0.0)
    equilibrium: PlatformEquilibriumResult


class WatchcircleResult(BaseModel):
    """
    F5.6 — Resultado da varredura watchcircle.

    Engenharia offshore: o "watchcircle" é o envelope geométrico
    das posições que o centro da plataforma assume conforme a
    direção da carga ambiental varia mantida magnitude constante.
    Útil para identificar:

      - Direção em que o sistema é mais "mole" (offset máximo)
      - Direção em que linhas saturam primeiro
      - Buracos de cobertura no spread

    `points` é uma lista ordenada por `azimuth_deg`. Para fechar
    visualmente a curva, o consumidor concatena o primeiro ponto
    no fim.
    """

    model_config = ConfigDict(frozen=True)

    magnitude_n: float = Field(..., ge=0.0)
    n_steps: int = Field(..., ge=4)
    points: list[WatchcirclePoint]

    # Métricas resumidas para o card de detalhe.
    max_offset_magnitude: float = Field(default=0.0, ge=0.0)
    max_offset_load_azimuth_deg: float = Field(default=0.0, ge=0.0, lt=360.0)
    max_utilization: float = Field(default=0.0, ge=0.0)
    worst_alert_level: AlertLevel = Field(default=AlertLevel.OK)
    n_failed: int = Field(default=0, ge=0)
    solver_version: str = Field(default="")


__all__ = [
    "AlertLevel",
    "AttachmentKind",
    "BoundaryConditions",
    "ConvergenceStatus",
    "CriteriaProfile",
    "EnvironmentalLoad",
    "LineAttachment",
    "LineCategory",
    "LineSegment",
    "MooringLineResult",
    "MooringSystemResult",
    "PROFILE_LIMITS",
    "PlatformEquilibriumResult",
    "SeabedConfig",
    "SolutionMode",
    "SolverConfig",
    "SolverResult",
    "UtilizationLimits",
    "WatchcirclePoint",
    "WatchcircleResult",
    "classify_utilization",
]
