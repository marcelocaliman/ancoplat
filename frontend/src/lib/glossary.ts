/**
 * Glossário canônico do AncoPlat (Fase 9 / Q5+Q6).
 *
 * Vocabulário técnico exposto ao engenheiro pela UI. Cada termo:
 *  - `term`: nome canônico (PT-BR, exceto siglas técnicas como MBL/EA/AHV).
 *  - `category`: agrupamento para navegação (geometria/físico/componentes/
 *                operacional/boia).
 *  - `definition`: 1-2 frases. Não enciclopédico.
 *  - `seeAlso`: lista de outros term ids relacionados (forward-compat).
 *  - `requirePhase`: marca verbete de feature ainda em desenvolvimento
 *                   (F7 anchor uplift, F8 AHV) — UI mostra badge.
 *
 * Verbetes adicionados na F9 cobrem features de F7/F8 que entram em
 * v1.0 (paridade total com QMoor).
 */

export type GlossaryCategory =
  | 'geometria'
  | 'fisico'
  | 'componentes'
  | 'operacional'
  | 'boia'

export interface GlossaryEntry {
  id: string
  term: string
  category: GlossaryCategory
  definition: string
  seeAlso?: string[]
  requirePhase?: 'F7' | 'F8'
}

export const CATEGORY_LABELS: Record<GlossaryCategory, string> = {
  geometria: 'Geometria',
  fisico: 'Físico',
  componentes: 'Componentes',
  operacional: 'Operacional',
  boia: 'Boia (catálogo)',
}

export const GLOSSARY: GlossaryEntry[] = [
  // ─── Geometria (8 + 1 F7) ──────────────────────────────────────────
  {
    id: 'catenaria',
    term: 'Catenária',
    category: 'geometria',
    definition:
      'Curva natural assumida por uma linha flexível pesada suspensa entre dois pontos sob ação da gravidade. AncoPlat resolve a forma elástica (com alongamento) com seabed e atrito.',
    seeAlso: ['touchdown', 'arc-length', 'profile-type'],
  },
  {
    id: 'anchor',
    term: 'Anchor (âncora)',
    category: 'geometria',
    definition:
      'Ponto de fixação inferior da linha. No MVP v1 sempre no seabed (`endpoint_grounded=true`); a partir da Fase 7, anchor pode ser elevado (suspended endpoint).',
    seeAlso: ['fairlead', 'anchor-uplift'],
  },
  {
    id: 'fairlead',
    term: 'Fairlead',
    category: 'geometria',
    definition:
      'Ponto de fixação superior da linha na plataforma (semisub, FPSO, etc.). Localização do "startpoint" no schema; tipicamente na superfície (`startpoint_depth=0`).',
    seeAlso: ['anchor', 'startpoint-type'],
  },
  {
    id: 'touchdown',
    term: 'Touchdown / TDP',
    category: 'geometria',
    definition:
      'Ponto onde a linha encontra o seabed. À direita do TDP (em direção ao fairlead) a linha está suspensa; à esquerda, apoiada (grounded). Aparece no plot como transição entre traço sólido e pontilhado vermelho.',
    seeAlso: ['catenaria', 'profile-type'],
  },
  {
    id: 'range',
    term: 'Range / X_total',
    category: 'geometria',
    definition:
      'Distância horizontal anchor → fairlead (m). Em modo Tension é output; em modo Range é input.',
    seeAlso: ['mode-tension', 'fairlead', 'anchor'],
  },
  {
    id: 'arc-length',
    term: 'Arc length',
    category: 'geometria',
    definition:
      'Comprimento ao longo da linha não-esticada (m), medido desde a âncora. Atributos como posição de attachment (`position_s_from_anchor`) usam arc length.',
    seeAlso: ['catenaria', 'attachment'],
  },
  {
    id: 'slope',
    term: 'Slope (inclinação do seabed)',
    category: 'geometria',
    definition:
      'Inclinação do seabed em radianos (`slope_rad`). Frontend permite informar via batimetria 2-pontos (lâmina sob anchor + lâmina sob fairlead) com slope derivado read-only.',
    seeAlso: ['water-depth', 'bathymetry'],
  },
  {
    id: 'water-depth',
    term: 'Lâmina d\'água sob anchor (h)',
    category: 'geometria',
    definition:
      'Profundidade do seabed sob a âncora (m). Em seabed inclinado, difere da profundidade sob o fairlead (`depth_at_fairlead` no resultado).',
    seeAlso: ['slope', 'bathymetry'],
  },
  {
    id: 'anchor-uplift',
    term: 'Anchor uplift / suspended endpoint',
    category: 'geometria',
    definition:
      'Configuração em que a âncora está elevada do seabed (não cravada). Sem touchdown na âncora — catenária livre nas duas pontas (PT_1 fully suspended). Profundidade do anchor é `endpoint_depth` (m); uplift = `h − endpoint_depth`. Implementado na Fase 7 do plano de profissionalização para single-segmento sem attachments (multi-seg + uplift fica para F7.x).',
    seeAlso: ['anchor', 'profile-type'],
  },
  {
    id: 'bathymetry',
    term: 'Batimetria 2-pontos',
    category: 'geometria',
    definition:
      'Modo de entrada do seabed inclinado: usuário informa lâmina d\'água sob anchor + sob fairlead, e o slope é derivado. Mais ergonômico que digitar slope_rad direto.',
    seeAlso: ['slope', 'water-depth'],
  },

  // ─── Físico (9 + 1 F8) ────────────────────────────────────────────
  {
    id: 'mbl',
    term: 'MBL (Minimum Breaking Load)',
    category: 'fisico',
    definition:
      'Carga mínima de ruptura da linha (N). Define o limite operacional via critério de utilização (T_fl/MBL).',
    seeAlso: ['utilization', 'criteria-profile'],
  },
  {
    id: 'ea',
    term: 'EA (rigidez axial)',
    category: 'fisico',
    definition:
      'Rigidez axial da linha (N). AncoPlat suporta EA estático (`qmoor_ea`, default) e EA dinâmico (`gmoor_ea`, opcional). Modelo NREL/MoorPy: `EA_dynamic = α + β·T_mean`.',
    seeAlso: ['ea-source', 'mbl'],
  },
  {
    id: 'ea-source',
    term: 'EA source (qmoor / gmoor)',
    category: 'fisico',
    definition:
      'Toggle per-segmento que escolhe a coluna do catálogo: `qmoor` (estático, default — preserva QMoor 0.8.5) ou `gmoor` (dinâmico, curto prazo). Ver `LineSegment.ea_source`.',
    seeAlso: ['ea'],
  },
  {
    id: 't-fl',
    term: 'T_fl (tensão no fairlead)',
    category: 'fisico',
    definition:
      'Magnitude da força que a linha aplica no fairlead (N). Em modo Tension é input; em modo Range é output.',
    seeAlso: ['range', 'utilization', 'mode-tension'],
  },
  {
    id: 't-anchor',
    term: 'T_anchor (tensão na âncora)',
    category: 'fisico',
    definition:
      'Magnitude da força horizontal na âncora (N). Diferente de T_fl pelo efeito do peso submerso da linha + atrito do seabed.',
    seeAlso: ['t-fl', 'mu-seabed'],
  },
  {
    id: 'wet-weight',
    term: 'Peso submerso (w)',
    category: 'fisico',
    definition:
      'Peso linear submerso da linha (N/m). É o peso seco menos o empuxo da água. Catálogo armazena ambos.',
    seeAlso: ['dry-weight'],
  },
  {
    id: 'dry-weight',
    term: 'Peso seco',
    category: 'fisico',
    definition:
      'Peso linear da linha no ar (N/m). Catálogo armazena para auditoria; solver usa `wet_weight` (peso submerso) para a catenária.',
    seeAlso: ['wet-weight'],
  },
  {
    id: 'mu-seabed',
    term: 'Atrito do seabed (μ)',
    category: 'fisico',
    definition:
      'Coeficiente de atrito de Coulomb axial entre linha e seabed (adimensional). Precedência per-segmento: `mu_override` → `seabed_friction_cf` (catálogo) → `seabed.mu` global → 0.',
    seeAlso: ['t-anchor'],
  },
  {
    id: 'pendant',
    term: 'Pendant',
    category: 'fisico',
    definition:
      'Cabo de conexão entre uma boia/clump e a linha principal. Comprimento (`tether_length`) afeta visualização; força submersa entra como efeito líquido no ponto de conexão.',
    seeAlso: ['attachment', 'lifted-arch'],
  },
  {
    id: 'lifted-arch',
    term: 'Lifted arch (arco de levantamento)',
    category: 'fisico',
    definition:
      'Boia posicionada na zona apoiada em material uniforme — gera arco simétrico. Solver F5.7.1 detecta automaticamente (`s_arch = F_b / w_local`) e integra catenárias com vértice em cada touchdown e kink na boia.',
    seeAlso: ['attachment', 'pendant'],
  },
  {
    id: 'bollard-pull',
    term: 'Bollard pull',
    category: 'fisico',
    definition:
      'Força de tração disponibilizada por um rebocador (AHV). Spec do rebocador medido em toneladas-força (te) — ex.: 200 te = 1.96e6 N. Em AncoPlat (Fase 8) é o input `ahv_bollard_pull` da magnitude, complementado pelo heading horizontal. Idealização estática — D018 sempre dispara avisando que NÃO substitui análise dinâmica de instalação.',
    seeAlso: ['ahv'],
  },

  // ─── Componentes (5 + 1 F8) ────────────────────────────────────────
  {
    id: 'mooring-system',
    term: 'Mooring system',
    category: 'componentes',
    definition:
      'Conjunto de várias linhas (legs) ancorando a mesma plataforma. Cada line tem fairlead próprio em ângulo e raio configuráveis. Support para análise multi-line + equilíbrio + watchcircle.',
    seeAlso: ['line', 'equilibrium', 'watchcircle'],
  },
  {
    id: 'line',
    term: 'Line (leg)',
    category: 'componentes',
    definition:
      'Linha de ancoragem completa. Pode ser um caso isolado ou uma das legs de um mooring system.',
    seeAlso: ['segment', 'mooring-system'],
  },
  {
    id: 'segment',
    term: 'Segment',
    category: 'componentes',
    definition:
      'Trecho de linha com material homogêneo (e.g., chain, wire, polyester). Multi-segmento permite combinar materiais (chain-wire-chain). Cada segmento tem L, w, EA, MBL próprios.',
    seeAlso: ['line', 'ea-source'],
  },
  {
    id: 'attachment',
    term: 'Attachment (boia / clump weight)',
    category: 'componentes',
    definition:
      'Elemento pontual ao longo da linha. `kind=buoy` adiciona empuxo (puxa para cima); `kind=clump_weight` adiciona peso (puxa para baixo). Posição via arc length ou índice de junção.',
    seeAlso: ['lifted-arch', 'pendant', 'submerged-force'],
  },
  {
    id: 'watchcircle',
    term: 'Watchcircle',
    category: 'componentes',
    definition:
      'Envelope de offset da plataforma sob carga ambiental rotacionada 360°. Cada azimuth produz um ponto de equilíbrio; o conjunto desenha o "círculo" de excursão da plataforma. Default 36 steps.',
    seeAlso: ['equilibrium', 'mooring-system'],
  },
  {
    id: 'ahv',
    term: 'AHV (Anchor Handler Vessel)',
    category: 'componentes',
    definition:
      'Embarcação de manuseio de âncoras durante operação de instalação. Implementado na Fase 8 (paridade total com QMoor) como `LineAttachment.kind="ahv"` aplicando carga estática pontual. **Idealização explícita** — operação real é dinâmica (rebocador se move, cabo oscila, hidrodinâmica). Mitigação obrigatória: D018 dispara automaticamente; Memorial PDF inclui seção "AHV — Domínio de aplicação"; manual de usuário (Fase 11) cobrirá detalhes. NÃO substitui análise dinâmica de instalação.',
    seeAlso: ['bollard-pull'],
  },

  // ─── Operacional (8) ───────────────────────────────────────────────
  {
    id: 'mode-tension',
    term: 'Modo Tension vs Range',
    category: 'operacional',
    definition:
      'Tension: input T_fl, output X_total. Range: input X_total, output T_fl. AncoPlat usa Tension como default — alinha com QMoor 0.8.5.',
    seeAlso: ['t-fl', 'range'],
  },
  {
    id: 'profile-type',
    term: 'ProfileType (PT_0..PT_8)',
    category: 'operacional',
    definition:
      'Taxonomia de regimes catenários espelhando MoorPy/NREL. PT_0 (laid line), PT_1 (fully suspended), PT_2 (com touchdown e atrito), PT_3 (touchdown sem atrito), PT_7 (seabed inclinado), etc. Forward-compat com Fase 7+.',
    seeAlso: ['catenaria', 'touchdown'],
  },
  {
    id: 'criteria-profile',
    term: 'Criteria profile',
    category: 'operacional',
    definition:
      'Perfil de classificação T_fl/MBL: MVP_Preliminary (default 0.50/0.60/1.0), API_RP_2SK (0.60 intacto / 0.80 danificado), DNV (placeholder), UserDefined (custom).',
    seeAlso: ['utilization', 'alert-level'],
  },
  {
    id: 'alert-level',
    term: 'Alert level (ok/yellow/red/broken)',
    category: 'operacional',
    definition:
      'Classificação do solver. ok: utilização abaixo do limite amarelo. yellow: atenção. red: limite operacional atingido. broken: T_fl/MBL ≥ 1 → INVALID_CASE.',
    seeAlso: ['criteria-profile', 'utilization'],
  },
  {
    id: 'utilization',
    term: 'Utilização (T_fl/MBL)',
    category: 'operacional',
    definition:
      'Razão tensão de fairlead vs MBL. Critério principal de safety. Alert level e profile crítico determinam thresholds.',
    seeAlso: ['mbl', 't-fl', 'criteria-profile'],
  },
  {
    id: 'diagnostic',
    term: 'Diagnostic (D001..D015)',
    category: 'operacional',
    definition:
      'Mensagens estruturadas do solver. Cada uma tem `code`, `severity` (info/warning/error), `confidence` (high/medium/low) e `message`. Cobertura total de `diagnostics.py` em 100%.',
    seeAlso: ['confidence'],
  },
  {
    id: 'confidence',
    term: 'Confidence (high/medium/low)',
    category: 'operacional',
    definition:
      'Nível de confiança no diagnostic. high: violação determinística (sempre correto). medium: heurística calibrada (pode ter falso positivo). low: pattern detection sem base teórica forte (reservado).',
    seeAlso: ['diagnostic'],
  },
  {
    id: 'case-hash',
    term: 'Hash do caso',
    category: 'operacional',
    definition:
      'SHA-256 canonicalizado dos campos físicos do CaseInput (exclui name/description). 16 chars no display, 64 chars completo. Aparece em footer de cada página do Memorial PDF para rastreabilidade.',
    seeAlso: ['memorial-pdf'],
  },
  {
    id: 'memorial-pdf',
    term: 'Memorial PDF',
    category: 'operacional',
    definition:
      'Relatório técnico gerado pelo endpoint `/cases/{id}/export/memorial-pdf`. Cobre premissas, sumário, geometria, tensões, diagnostics estruturados, convergência. Footer com hash + solver_version + timestamp em cada página.',
    seeAlso: ['case-hash', 'diagnostic'],
  },

  // ─── Boia (catálogo) (4) ───────────────────────────────────────────
  {
    id: 'submerged-force',
    term: 'Submerged force (F_b)',
    category: 'boia',
    definition:
      'Empuxo líquido da boia em N: `V·ρ_seawater·g − weight_in_air`. Pode ser negativo se peso domina (objeto vira clump_weight). Pré-computado na seed via fórmula do Excel "Formula Guide".',
    seeAlso: ['attachment', 'end-type'],
  },
  {
    id: 'end-type',
    term: 'End type (4 valores)',
    category: 'boia',
    definition:
      'Forma das tampas da boia cilíndrica: flat, hemispherical, elliptical, semi_conical. Cada uma tem fórmula geométrica de volume distinta (Excel Formula Guide R4-R7).',
    seeAlso: ['submerged-force'],
  },
  {
    id: 'buoy-type',
    term: 'Buoy type (surface vs submersible)',
    category: 'boia',
    definition:
      'surface: boia de superfície / marker buoy. submersible: submergível, usada em lazy-S/wave attenuator. Apenas metadado — não afeta o cálculo.',
    seeAlso: ['submerged-force'],
  },
  {
    id: 'weight-in-air',
    term: 'Weight in air',
    category: 'boia',
    definition:
      'Peso da boia no ar (N). Auditoria — `submerged_force` já é a força líquida (empuxo descontando este peso).',
    seeAlso: ['submerged-force'],
  },
]

export function getGlossaryEntry(id: string): GlossaryEntry | undefined {
  return GLOSSARY.find((g) => g.id === id)
}

/** Filtra por busca textual + categoria. Case-insensitive. */
export function searchGlossary(
  search: string,
  category?: GlossaryCategory,
): GlossaryEntry[] {
  const needle = search.trim().toLowerCase()
  return GLOSSARY.filter((g) => {
    if (category && g.category !== category) return false
    if (!needle) return true
    return (
      g.term.toLowerCase().includes(needle) ||
      g.definition.toLowerCase().includes(needle) ||
      g.id.toLowerCase().includes(needle)
    )
  })
}
