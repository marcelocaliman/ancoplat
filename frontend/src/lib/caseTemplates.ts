/**
 * F5.7.6 — Templates de configurações conhecidas.
 *
 * Biblioteca de starting points testados que cobrem os principais
 * regimes de mooring estático: catenária clássica, taut leg, lazy-S,
 * etc. Cada template tem nome/descrição/ícone + valores de form
 * compatíveis com `CaseFormValues`.
 *
 * Engenheiros novatos no app começam de um preset que sabidamente
 * converge, ajustam parâmetros e veem o efeito — em vez de descobrir
 * do zero qual combinação funciona.
 */
import type { CaseFormValues } from './caseSchema'

export interface CaseTemplate {
  id: string
  name: string
  description: string
  /** Tag visual (cor + label curta). */
  tag:
    | 'classic'
    | 'lazyS'
    | 'taut'
    | 'shallow'
    | 'deep'
    | 'spread'
    | 'attachment'
    | 'slope'
    | 'preview'
  values: CaseFormValues
  /**
   * Quando definido, marca o template como **preview** de feature
   * ainda em desenvolvimento. Cards mostram banner; CaseFormPage
   * exibe alerta explicativo após carregar; teste de regressão
   * skipa preview-solve até o requirePhase fechar.
   *
   * Valores: 'F7' (Anchor uplift) | 'F8' (AHV).
   */
  requirePhase?: 'F7' | 'F8'
  /**
   * Mensagem do banner quando o sample preview é carregado no form.
   */
  previewMessage?: string
}

export const CASE_TEMPLATES: CaseTemplate[] = [
  // ───────────────────────────────────────────────────────────────────
  {
    id: 'catenary-classic',
    name: 'Catenária clássica',
    description:
      'Wire de 3" em 300m d\'água — touchdown moderado, sem attachments. Configuração de referência mais simples.',
    tag: 'classic',
    values: {
      name: 'Catenária clássica',
      description: 'Template: catenária wire 3" em 300m de lâmina d\'água.',
      segments: [
        {
          length: 450,
          w: 201.1,
          EA: 3.425e7,
          MBL: 3.78e6,
          category: 'Wire',
          line_type: null,
          diameter: 0.0762,
          dry_weight: 242.3,
          modulus: 6.76e10,
          ea_source: 'qmoor',
        },
      ],
      boundary: {
        h: 300,
        mode: 'Tension',
        input_value: 785_000,
        startpoint_depth: 0,
        endpoint_grounded: true,
        startpoint_offset_horz: 0,
        startpoint_offset_vert: 0,
        startpoint_type: 'semisub',
      },
      seabed: { mu: 0.6, slope_rad: 0 },
      criteria_profile: 'MVP_Preliminary',
      user_defined_limits: null,
      attachments: [],
    },
  },
  // ───────────────────────────────────────────────────────────────────
  {
    id: 'taut-leg',
    name: 'Taut leg (poliéster)',
    description:
      'Linha de poliéster quase taut (slack ~5%). Sem touchdown, suporta T_fl alto. Comum em águas profundas.',
    tag: 'taut',
    values: {
      name: 'Taut leg poliéster',
      description: 'Template: poliéster em águas profundas.',
      segments: [
        {
          length: 1600,
          w: 16.5,
          EA: 4.5e7,
          MBL: 8.0e6,
          category: 'Polyester',
          line_type: null,
          diameter: 0.16,
          dry_weight: 22.0,
          modulus: 2.24e9,
          ea_source: 'qmoor',
        },
      ],
      boundary: {
        h: 1500,
        mode: 'Tension',
        input_value: 2_500_000,
        startpoint_depth: 0,
        endpoint_grounded: true,
        startpoint_offset_horz: 0,
        startpoint_offset_vert: 0,
        startpoint_type: 'semisub',
      },
      seabed: { mu: 0.3, slope_rad: 0 },
      criteria_profile: 'MVP_Preliminary',
      user_defined_limits: null,
      attachments: [],
    },
  },
  // ───────────────────────────────────────────────────────────────────
  {
    id: 'lazy-s',
    name: 'Lazy-S com boia + clump',
    description:
      "Configuração 'S' clássica com boia (lift) + clump (anchor down). 1200m de cabo, T_fl moderado. Demonstra a forma S.",
    tag: 'lazyS',
    values: {
      name: 'Lazy-S boia + clump',
      description: 'Template: lazy-S com boia + clump em águas médias.',
      segments: [
        {
          length: 1200,
          w: 89.4,
          EA: 1.96e8,
          MBL: 2.197e6,
          category: 'Wire',
          line_type: null,
          diameter: 0.0508,
          dry_weight: 107.9,
          modulus: 9.65e10,
          ea_source: 'qmoor',
        },
      ],
      boundary: {
        h: 300,
        mode: 'Tension',
        input_value: 150_000,
        startpoint_depth: 0,
        endpoint_grounded: true,
        startpoint_offset_horz: 0,
        startpoint_offset_vert: 0,
        startpoint_type: 'semisub',
      },
      seabed: { mu: 0.6, slope_rad: 0 },
      criteria_profile: 'MVP_Preliminary',
      user_defined_limits: null,
      attachments: [
        {
          kind: 'buoy',
          submerged_force: 150_000,
          position_s_from_anchor: 600,
          name: 'Boia S',
          tether_length: null,
          buoy_type: 'submersible',
          buoy_end_type: 'elliptical',
          buoy_outer_diameter: null,
          buoy_length: null,
          buoy_weight_in_air: null,
          pendant_line_type: null,
          pendant_diameter: null,
        },
        {
          kind: 'clump_weight',
          submerged_force: 80_000,
          position_s_from_anchor: 900,
          name: 'Clump S',
          tether_length: null,
          buoy_type: null,
          buoy_end_type: null,
          buoy_outer_diameter: null,
          buoy_length: null,
          buoy_weight_in_air: null,
          pendant_line_type: null,
          pendant_diameter: null,
        },
      ],
    },
  },
  // ───────────────────────────────────────────────────────────────────
  {
    id: 'chain-wire-chain',
    name: 'Chain-Wire-Chain (3 segs)',
    description:
      'Pendant inferior (chain pesado) + corpo (wire) + pendant superior (chain). Configuração de referência multi-segmento.',
    tag: 'classic',
    values: {
      name: 'Chain-Wire-Chain',
      description: 'Template: configuração 3 segmentos com pendants de chain.',
      segments: [
        {
          length: 200,
          w: 1500,
          EA: 4.5e8,
          MBL: 6.0e6,
          category: 'StuddedChain',
          line_type: null,
          diameter: 0.105,
          dry_weight: 1800,
          modulus: 1.7e11,
          ea_source: 'qmoor',
        },
        {
          length: 700,
          w: 200,
          EA: 4.4e8,
          MBL: 4.8e6,
          category: 'Wire',
          line_type: null,
          diameter: 0.076,
          dry_weight: 240,
          modulus: 9.6e10,
          ea_source: 'qmoor',
        },
        {
          length: 200,
          w: 1500,
          EA: 4.5e8,
          MBL: 6.0e6,
          category: 'StuddedChain',
          line_type: null,
          diameter: 0.105,
          dry_weight: 1800,
          modulus: 1.7e11,
          ea_source: 'qmoor',
        },
      ],
      boundary: {
        h: 300,
        mode: 'Tension',
        input_value: 600_000,
        startpoint_depth: 0,
        endpoint_grounded: true,
        startpoint_offset_horz: 0,
        startpoint_offset_vert: 0,
        startpoint_type: 'semisub',
      },
      seabed: { mu: 0.6, slope_rad: 0 },
      criteria_profile: 'MVP_Preliminary',
      user_defined_limits: null,
      attachments: [],
    },
  },
  // ───────────────────────────────────────────────────────────────────
  {
    id: 'shallow-water',
    name: 'Águas rasas (h=50m)',
    description:
      'Lâmina rasa (50m) com chain leve. Razão L/h alta — bastante touchdown e baixa T_fl.',
    tag: 'shallow',
    values: {
      name: 'Águas rasas',
      description: 'Template: chain leve em águas rasas.',
      segments: [
        {
          length: 250,
          w: 800,
          EA: 2.5e8,
          MBL: 3.0e6,
          category: 'StudlessChain',
          line_type: null,
          diameter: 0.076,
          dry_weight: 950,
          modulus: 1.5e11,
          ea_source: 'qmoor',
        },
      ],
      boundary: {
        h: 50,
        mode: 'Tension',
        input_value: 100_000,
        startpoint_depth: 0,
        endpoint_grounded: true,
        startpoint_offset_horz: 0,
        startpoint_offset_vert: 0,
        startpoint_type: 'semisub',
      },
      seabed: { mu: 0.6, slope_rad: 0 },
      criteria_profile: 'MVP_Preliminary',
      user_defined_limits: null,
      attachments: [],
    },
  },
  // ───────────────────────────────────────────────────────────────────
  {
    id: 'deep-water',
    name: 'Águas profundas (h=2000m)',
    description:
      'Mooring profundo com poliéster. Linha quase taut, T_fl alto.',
    tag: 'deep',
    values: {
      name: 'Águas profundas',
      description: 'Template: poliéster em 2000m de lâmina.',
      segments: [
        {
          length: 2150,
          w: 16.5,
          EA: 4.5e7,
          MBL: 1.2e7,
          category: 'Polyester',
          line_type: null,
          diameter: 0.18,
          dry_weight: 22,
          modulus: 1.8e9,
          ea_source: 'qmoor',
        },
      ],
      boundary: {
        h: 2000,
        mode: 'Tension',
        input_value: 3_500_000,
        startpoint_depth: 0,
        endpoint_grounded: true,
        startpoint_offset_horz: 0,
        startpoint_offset_vert: 0,
        startpoint_type: 'semisub',
      },
      seabed: { mu: 0.3, slope_rad: 0 },
      criteria_profile: 'MVP_Preliminary',
      user_defined_limits: null,
      attachments: [],
    },
  },
  // ───────────────────────────────────────────────────────────────────
  // F9 — 3 samples novos cobrindo features F5.x não cobertas pelos 6
  // existentes: clump isolado, lifted-arch (F5.7.1), seabed inclinado.
  // ───────────────────────────────────────────────────────────────────
  {
    id: 'clump-weight',
    name: 'Catenária com clump',
    description:
      'Wire 3" em 300m d\'água com clump weight a meia distância da linha. Demonstra como peso pontual reduz o range a igual T_fl.',
    tag: 'attachment',
    values: {
      name: 'Catenária com clump',
      description:
        'Template: catenária wire com 1 clump pontual no meio da linha.',
      segments: [
        {
          length: 600,
          w: 201.1,
          EA: 3.425e7,
          MBL: 3.78e6,
          category: 'Wire',
          line_type: null,
          diameter: 0.0762,
          dry_weight: 242.3,
          modulus: 6.76e10,
          ea_source: 'qmoor',
        },
      ],
      boundary: {
        h: 300,
        mode: 'Tension',
        input_value: 600_000,
        startpoint_depth: 0,
        endpoint_grounded: true,
        startpoint_offset_horz: 0,
        startpoint_offset_vert: 0,
        startpoint_type: 'semisub',
      },
      seabed: { mu: 0.6, slope_rad: 0 },
      criteria_profile: 'MVP_Preliminary',
      user_defined_limits: null,
      attachments: [
        {
          kind: 'clump_weight',
          submerged_force: 100_000,
          position_s_from_anchor: 350,
          name: 'Clump central',
          tether_length: null,
          buoy_type: null,
          buoy_end_type: null,
          buoy_outer_diameter: null,
          buoy_length: null,
          buoy_weight_in_air: null,
          pendant_line_type: null,
          pendant_diameter: null,
        },
      ],
    },
  },
  // ───────────────────────────────────────────────────────────────────
  {
    id: 'lifted-arch',
    name: 'Boia em arc grounded (F5.7.1)',
    description:
      'Boia posicionada na zona apoiada em material uniforme. Solver detecta automaticamente e gera arco de levantamento (lifted arch) — porção da linha sobe acima do seabed pela ação da boia.',
    tag: 'attachment',
    values: {
      name: 'Boia em arc grounded',
      description:
        'Template F5.7.1: boia em material uniforme com posição na zona apoiada — gera lifted arch.',
      segments: [
        {
          length: 800,
          w: 1058,
          EA: 6.0e8,
          MBL: 6.0e6,
          category: 'StudlessChain',
          line_type: null,
          diameter: 0.076,
          dry_weight: 1240,
          modulus: 1.5e11,
          ea_source: 'qmoor',
        },
      ],
      boundary: {
        h: 200,
        mode: 'Tension',
        input_value: 250_000,
        startpoint_depth: 0,
        endpoint_grounded: true,
        startpoint_offset_horz: 0,
        startpoint_offset_vert: 0,
        startpoint_type: 'semisub',
      },
      seabed: { mu: 0.6, slope_rad: 0 },
      criteria_profile: 'MVP_Preliminary',
      user_defined_limits: null,
      attachments: [
        {
          kind: 'buoy',
          submerged_force: 80_000,
          position_s_from_anchor: 100, // zona apoiada
          name: 'Boia grounded',
          tether_length: null,
          buoy_type: 'submersible',
          buoy_end_type: 'elliptical',
          buoy_outer_diameter: null,
          buoy_length: null,
          buoy_weight_in_air: null,
          pendant_line_type: null,
          pendant_diameter: null,
        },
      ],
    },
  },
  // ───────────────────────────────────────────────────────────────────
  {
    id: 'sloped-seabed',
    name: 'Seabed inclinado (5°)',
    description:
      'Seabed com inclinação de ~5° (slope ≠ 0). Profundidade do seabed sob a âncora difere da profundidade sob o fairlead. Configuração via batimetria 2-pontos no painel Ambiente.',
    tag: 'slope',
    values: {
      name: 'Seabed inclinado 5°',
      description:
        'Template: seabed com slope_rad ≈ 5° demonstrando batimetria 2-pontos.',
      segments: [
        {
          length: 700,
          w: 201.1,
          EA: 3.425e7,
          MBL: 3.78e6,
          category: 'Wire',
          line_type: null,
          diameter: 0.0762,
          dry_weight: 242.3,
          modulus: 6.76e10,
          ea_source: 'qmoor',
        },
      ],
      boundary: {
        h: 350,
        mode: 'Tension',
        input_value: 500_000,
        startpoint_depth: 0,
        endpoint_grounded: true,
        startpoint_offset_horz: 0,
        startpoint_offset_vert: 0,
        startpoint_type: 'semisub',
      },
      seabed: { mu: 0.6, slope_rad: 0.0873 }, // ~5° em radianos
      criteria_profile: 'MVP_Preliminary',
      user_defined_limits: null,
      attachments: [],
    },
  },
  // ───────────────────────────────────────────────────────────────────
  // Preview samples — F7 (anchor uplift) + F8 (AHV).
  // Cards têm banner "Preview — requires Phase X". Quando F7/F8 fecharem,
  // o sample destrava: payload já está pronto, basta remover preview flag.
  // ───────────────────────────────────────────────────────────────────
  {
    id: 'anchor-uplift',
    name: 'Âncora elevada (suspended)',
    description:
      'Âncora 50m acima do seabed (h=300m, endpoint_depth=250m). Catenária livre nas duas pontas, sem touchdown. Caso BC-UP-01 do gate da Fase 7.',
    tag: 'classic',
    values: {
      name: 'Âncora elevada — BC-UP-01',
      description:
        'Anchor uplift: 50m acima do seabed em 300m d\'água. '
        + 'endpoint_grounded=false + endpoint_depth=250m. PT_1 fully suspended.',
      segments: [
        {
          length: 500,
          w: 201.1,
          EA: 3.425e7,
          MBL: 3.78e6,
          category: 'Wire',
          line_type: null,
          diameter: 0.0762,
          dry_weight: 242.3,
          modulus: 6.76e10,
          ea_source: 'qmoor',
        },
      ],
      boundary: {
        h: 300,
        mode: 'Tension',
        input_value: 850_000,
        startpoint_depth: 0,
        endpoint_grounded: false,
        endpoint_depth: 250,  // anchor 50m acima do seabed (uplift=50m)
        startpoint_offset_horz: 0,
        startpoint_offset_vert: 0,
        startpoint_type: 'semisub',
      },
      seabed: { mu: 0.6, slope_rad: 0 },
      criteria_profile: 'MVP_Preliminary',
      user_defined_limits: null,
      attachments: [],
    },
  },
  // ───────────────────────────────────────────────────────────────────
  {
    id: 'ahv-pull',
    name: 'AHV bollard pull',
    description:
      'Anchor Handler Vessel aplicando bollard pull lateral em junção entre 2 segmentos durante operação de instalação. Caso BC-AHV-01 do gate da Fase 8. Análise estática é idealização — D018 dispara automaticamente.',
    tag: 'attachment',
    values: {
      name: 'AHV bollard pull — BC-AHV-01',
      description:
        'AHV puxando lateralmente (heading=0°, alinhado com a linha) em junção 0 entre 2 segmentos wire. Bollard pull = 200 kN (aprox 20 te). Idealização estática, ver Memorial PDF seção "AHV — Domínio de aplicação".',
      segments: [
        {
          length: 300,
          w: 201.1,
          EA: 3.425e7,
          MBL: 3.78e6,
          category: 'Wire',
          line_type: null,
          diameter: 0.0762,
          dry_weight: 242.3,
          modulus: 6.76e10,
          ea_source: 'qmoor',
        },
        {
          length: 300,
          w: 201.1,
          EA: 3.425e7,
          MBL: 3.78e6,
          category: 'Wire',
          line_type: null,
          diameter: 0.0762,
          dry_weight: 242.3,
          modulus: 6.76e10,
          ea_source: 'qmoor',
        },
      ],
      boundary: {
        h: 300,
        mode: 'Tension',
        input_value: 850_000,
        startpoint_depth: 0,
        endpoint_grounded: true,
        endpoint_depth: null,
        startpoint_offset_horz: 0,
        startpoint_offset_vert: 0,
        startpoint_type: 'ahv',
      },
      seabed: { mu: 0.6, slope_rad: 0 },
      criteria_profile: 'MVP_Preliminary',
      user_defined_limits: null,
      attachments: [
        {
          kind: 'ahv',
          position_index: 0,
          name: 'AHV-1',
          submerged_force: 0,
          tether_length: null,
          buoy_type: null,
          buoy_end_type: null,
          buoy_outer_diameter: null,
          buoy_length: null,
          buoy_weight_in_air: null,
          pendant_line_type: null,
          pendant_diameter: null,
          buoy_catalog_id: null,
          ahv_bollard_pull: 200_000,
          ahv_heading_deg: 0,
          ahv_stern_angle_deg: null,
          ahv_deck_level: null,
        },
      ],
    },
  },
]

/** Encontra um template pelo id. */
export function getTemplate(id: string): CaseTemplate | undefined {
  return CASE_TEMPLATES.find((t) => t.id === id)
}

/** Filtra apenas samples preview (F7/F8 ainda não disponíveis). */
export function listPreviewTemplates(): CaseTemplate[] {
  return CASE_TEMPLATES.filter((t) => t.requirePhase != null)
}

/** Filtra apenas samples totalmente funcionais (sem preview). */
export function listFunctionalTemplates(): CaseTemplate[] {
  return CASE_TEMPLATES.filter((t) => t.requirePhase == null)
}
