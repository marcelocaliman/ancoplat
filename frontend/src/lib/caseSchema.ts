import { z } from 'zod'

/**
 * Schema Zod de validação do formulário de Caso.
 * Espelha o `CaseInput` do backend (types.ts gerado da OpenAPI) mas
 * adiciona validações e mensagens em PT-BR que a API levantaria só no submit.
 */
/**
 * Attachment pontual (boia ou clump weight). F5.2 + F5.4.6a.
 *
 * Posição pode ser informada de duas formas (exatamente uma):
 *   - `position_index` (legacy): junção entre segmentos pré-existentes.
 *   - `position_s_from_anchor`: distância em metros desde a âncora.
 *     Solver divide o segmento que contém essa posição automaticamente.
 *
 * O backend valida exclusividade. No frontend, deixamos os dois como
 * optional/nullable para permitir o toggle entre modos sem perder o
 * outro valor durante a edição.
 */
export const lineAttachmentSchema = z
  .object({
    kind: z.enum(['clump_weight', 'buoy']),
    submerged_force: z.number().positive('Força submersa deve ser > 0'),
    position_index: z.number().int().min(0).nullable().optional(),
    position_s_from_anchor: z.number().positive().nullable().optional(),
    name: z.string().trim().max(80).nullable().optional(),
    tether_length: z.number().positive().nullable().optional(),
    // Metadados detalhados (F5.7) — não afetam o cálculo. Tipos
    // soltos (string em vez de enum literal) pra evitar atrito com
    // o Select shadcn que devolve string genérica; backend Pydantic
    // já valida os valores aceitos.
    buoy_type: z.string().nullable().optional(),
    buoy_end_type: z.string().nullable().optional(),
    buoy_outer_diameter: z.number().positive().nullable().optional(),
    buoy_length: z.number().positive().nullable().optional(),
    buoy_weight_in_air: z.number().min(0).nullable().optional(),
    pendant_line_type: z.string().trim().max(80).nullable().optional(),
    pendant_diameter: z.number().positive().nullable().optional(),
  })
  .refine(
    (a) =>
      (a.position_index != null && a.position_s_from_anchor == null) ||
      (a.position_index == null && a.position_s_from_anchor != null),
    {
      message:
        'Informe exatamente um entre position_index (junção) e ' +
        'position_s_from_anchor (distância da âncora)',
    },
  )

export const lineSegmentSchema = z.object({
  length: z.number().positive('Comprimento deve ser > 0'),
  w: z.number().positive('Peso submerso deve ser > 0'),
  EA: z.number().positive('EA deve ser > 0'),
  MBL: z.number().positive('MBL deve ser > 0'),
  category: z
    .enum(['Wire', 'StuddedChain', 'StudlessChain', 'Polyester'])
    .nullable()
    .optional(),
  line_type: z.string().nullable().optional(),
  // Metadados (não entram no solver, mas documentam a linha)
  diameter: z.number().positive().nullable().optional(),
  dry_weight: z.number().positive().nullable().optional(),
  modulus: z.number().positive().nullable().optional(),
  // ─── Atrito per-segmento (Fase 1 / B3) ─────────────────────────
  mu_override: z
    .number()
    .min(0, 'Atrito não pode ser negativo')
    .nullable()
    .optional(),
  seabed_friction_cf: z
    .number()
    .min(0, 'Atrito do catálogo não pode ser negativo')
    .nullable()
    .optional(),
  // ─── EA source (Fase 1 / A1.4+B4) ──────────────────────────────
  ea_source: z.enum(['qmoor', 'gmoor']).default('qmoor'),
  ea_dynamic_beta: z.number().min(0).nullable().optional(), // reservado v1
})

export const boundarySchema = z.object({
  h: z.number().positive("Profundidade do seabed sob a âncora deve ser > 0"),
  mode: z.enum(['Tension', 'Range']),
  input_value: z.number().positive('Valor deve ser > 0'),
  startpoint_depth: z.number().min(0).default(0),
  endpoint_grounded: z.boolean().default(true),
  // Offset cosmético do startpoint (Fase 2 / A2.6) — não entra no solver.
  startpoint_offset_horz: z.number().default(0),
  startpoint_offset_vert: z.number().default(0),
  // Tipo do startpoint (Fase 3 / A2.5+D7) — só afeta o ícone do plot.
  startpoint_type: z
    .enum(['semisub', 'ahv', 'barge', 'none'])
    .default('semisub'),
})

export const seabedSchema = z.object({
  mu: z.number().min(0, 'Atrito não pode ser negativo').default(0),
  slope_rad: z
    .number()
    .min(-Math.PI / 4, 'Inclinação mín = −45°')
    .max(Math.PI / 4, 'Inclinação máx = +45°')
    .default(0),
})

export const userLimitsSchema = z.object({
  yellow_ratio: z.number().positive().max(1.0),
  red_ratio: z.number().positive().max(1.0),
  broken_ratio: z.number().positive().max(2.0),
})

export const caseInputSchema = z
  .object({
    name: z
      .string()
      .trim()
      .min(1, 'Nome obrigatório')
      .max(200, 'Máximo 200 caracteres'),
    description: z.string().trim().max(2000).optional().nullable(),
    segments: z
      .array(lineSegmentSchema)
      .min(1, 'Informe ao menos 1 segmento')
      .max(10, 'Até 10 segmentos por linha. Para mais, divida em casos.'),
    boundary: boundarySchema,
    seabed: seabedSchema,
    criteria_profile: z.enum([
      'MVP_Preliminary',
      'API_RP_2SK',
      'DNV_placeholder',
      'UserDefined',
    ]),
    user_defined_limits: userLimitsSchema.optional().nullable(),
    attachments: z
      .array(lineAttachmentSchema)
      .max(20, 'Até 20 attachments por linha.')
      .optional()
      .default([]),
  })
  .refine(
    (v) =>
      v.criteria_profile !== 'UserDefined' || v.user_defined_limits != null,
    {
      message: 'Defina limites custom para perfil UserDefined',
      path: ['user_defined_limits'],
    },
  )
  .refine(
    (v) => {
      if (v.criteria_profile !== 'UserDefined' || !v.user_defined_limits) return true
      const { yellow_ratio, red_ratio, broken_ratio } = v.user_defined_limits
      return yellow_ratio < red_ratio && red_ratio < broken_ratio
    },
    {
      message: 'yellow < red < broken',
      path: ['user_defined_limits'],
    },
  )

export type CaseFormValues = z.infer<typeof caseInputSchema>

export const EMPTY_CASE: CaseFormValues = {
  name: '',
  description: '',
  segments: [
    {
      length: 450,
      w: 201.1,
      EA: 3.425e7,
      MBL: 3.78e6,
      category: 'Wire',
      line_type: null,
      diameter: 0.0762,      // 3" ~ wire rope IWRCEIPS default
      dry_weight: 242.3,     // 16.6 lbf/ft
      modulus: 6.76e10,      // 9804 kip/in² — módulo aparente wire
      mu_override: null,
      seabed_friction_cf: null,
      ea_source: 'qmoor',
      ea_dynamic_beta: null,
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
  seabed: { mu: 0.6, slope_rad: 0 },  // default de wire em argila firme
  criteria_profile: 'MVP_Preliminary',
  user_defined_limits: null,
  attachments: [],
}
