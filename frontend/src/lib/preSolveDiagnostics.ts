/**
 * F5.7.6 — Pre-solve diagnostics: validações rápidas no frontend antes
 * de chamar o solver. Pegam erros óbvios em ms, dando feedback
 * instantâneo ao engenheiro sem esperar pelo backend.
 *
 * Cada checagem que retornar um diagnóstico segue o mesmo formato do
 * `SolverDiagnostic` do backend (severidade + affected_fields +
 * suggested_changes), assim o `SolverDiagnosticsCard` renderiza
 * pre-solve e post-solve com a mesma UX.
 */
import type { CaseFormValues } from './caseSchema'

export type DiagnosticSeverity = 'critical' | 'error' | 'warning' | 'info'

export interface SuggestedChange {
  field: string
  value: number
  label: string
}

export interface PreSolveDiagnostic {
  code: string
  severity: DiagnosticSeverity
  title: string
  cause: string
  suggestion: string
  suggested_changes: SuggestedChange[]
  affected_fields: string[]
}

/**
 * Roda checagens rápidas em <1ms. Pega erros óbvios:
 *  - L ≤ h (cabo curto)
 *  - L < √(X²+h²) em modo Range (cabo mais curto que o taut)
 *  - sum_F_buoy > sum_w·L (empuxo excede peso)
 *  - posição fora do range [0, L_total]
 *
 * Retorna lista (vazia se tudo OK).
 */
export function runPreSolveDiagnostics(
  values: CaseFormValues,
): PreSolveDiagnostic[] {
  const diagnostics: PreSolveDiagnostic[] = []
  if (!values.segments?.length) return diagnostics

  const totalLength = values.segments.reduce(
    (sum, s) => sum + (s.length ?? 0),
    0,
  )
  const totalWeight = values.segments.reduce(
    (sum, s) => sum + (s.w ?? 0) * (s.length ?? 0),
    0,
  )
  const h = values.boundary?.h ?? 0
  const startpointDepth = values.boundary?.startpoint_depth ?? 0
  const hDrop = h - startpointDepth

  // ── Pre-solve 1: cabo curto demais ──
  if (hDrop > 0 && totalLength > 0 && totalLength <= hDrop * 1.05) {
    diagnostics.push({
      code: 'P001_CABLE_TOO_SHORT',
      severity: 'critical',
      title: "Cabo curto demais para a lâmina d'água",
      cause: `Comprimento total (${totalLength.toFixed(0)} m) é menor ou próximo da lâmina d'água (${hDrop.toFixed(0)} m). A linha não conseguiria alcançar o fairlead.`,
      suggestion: `Aumente o comprimento total para pelo menos ${(hDrop * 1.2).toFixed(0)} m (20% acima da lâmina).`,
      suggested_changes: [
        {
          field: 'segments[0].length',
          value: Math.round(hDrop * 1.2),
          label: `Aumentar para ${(hDrop * 1.2).toFixed(0)} m`,
        },
      ],
      affected_fields: ['segments[0].length', 'boundary.h'],
    })
  }

  // ── Pre-solve 2: empuxo total das boias > peso total da linha ──
  const buoyTotalForce = (values.attachments ?? [])
    .filter((a) => a.kind === 'buoy')
    .reduce((sum, a) => sum + (a.submerged_force ?? 0), 0)
  const clumpTotalForce = (values.attachments ?? [])
    .filter((a) => a.kind === 'clump_weight')
    .reduce((sum, a) => sum + (a.submerged_force ?? 0), 0)
  const sumTotal = totalWeight - buoyTotalForce + clumpTotalForce
  if (totalWeight > 0 && sumTotal <= 0) {
    const firstBuoyIdx = (values.attachments ?? []).findIndex(
      (a) => a.kind === 'buoy',
    )
    if (firstBuoyIdx >= 0) {
      const buoy = values.attachments![firstBuoyIdx]!
      const F_max = totalWeight + clumpTotalForce - 1
      const F_max_te = F_max / 9806.65
      diagnostics.push({
        code: 'P002_BUOYANCY_EXCEEDS_WEIGHT',
        severity: 'critical',
        title: 'Empuxo das boias excede o peso da linha',
        cause: `Σ F_buoy (${(buoyTotalForce / 9806.65).toFixed(2)} te) − Σ F_clump (${(clumpTotalForce / 9806.65).toFixed(2)} te) > Σ w·L (${(totalWeight / 9806.65).toFixed(2)} te). Geometria seria invertida.`,
        suggestion: `Reduza o empuxo da boia '${buoy.name ?? `#${firstBuoyIdx + 1}`}' para ≤ ${F_max_te.toFixed(2)} te, OU adicione clump weight maior, OU aumente o cabo.`,
        suggested_changes: [
          {
            field: `attachments[${firstBuoyIdx}].submerged_force`,
            value: Math.round(F_max * 0.9),
            label: `Reduzir empuxo para ${(F_max_te * 0.9).toFixed(2)} te`,
          },
        ],
        affected_fields: [
          `attachments[${firstBuoyIdx}].submerged_force`,
        ],
      })
    }
  }

  // ── Pre-solve 3: posição de attachment fora do range [0.01, L_total) ──
  ;(values.attachments ?? []).forEach((att, idx) => {
    if (att.position_s_from_anchor != null && totalLength > 0) {
      if (
        att.position_s_from_anchor <= 0.0 ||
        att.position_s_from_anchor >= totalLength
      ) {
        diagnostics.push({
          code: 'P003_ATTACHMENT_OUT_OF_RANGE',
          severity: 'critical',
          title: `Posição inválida do ${att.kind === 'buoy' ? 'boia' : 'clump'} '${att.name ?? `#${idx + 1}`}'`,
          cause: `Posição da âncora ${att.position_s_from_anchor.toFixed(1)} m está fora do range válido (0, ${totalLength.toFixed(0)} m). UI clampa internamente, mas a configuração pode ficar imprevisível.`,
          suggestion: `Ajuste a "Distância do fairlead" para um valor entre 0 e ${totalLength.toFixed(0)} m.`,
          suggested_changes: [],
          affected_fields: [`attachments[${idx}].position_s_from_anchor`],
        })
      }
    }
  })

  // ── Pre-solve 4: T_fl muito baixo no modo Tension ──
  if (
    values.boundary?.mode === 'Tension' &&
    values.boundary.input_value > 0 &&
    totalWeight > 0 &&
    hDrop > 0
  ) {
    // T_fl_crit_min ~ w·h (linha quase vertical, sem catenária)
    // Aproximação grosseira pra alertar antes de chamar o solver
    const Tfl_min_approx = totalWeight * (hDrop / totalLength) * 0.8
    if (values.boundary.input_value < Tfl_min_approx) {
      diagnostics.push({
        code: 'P004_TFL_LIKELY_TOO_LOW',
        severity: 'warning',
        title: 'T_fl provavelmente insuficiente',
        cause: `Estimativa rápida indica T_fl ≥ ${(Tfl_min_approx / 1000).toFixed(0)} kN para sustentar a coluna d'água. T_fl atual é ${(values.boundary.input_value / 1000).toFixed(0)} kN.`,
        suggestion: `Considere aumentar T_fl para pelo menos ${(Tfl_min_approx * 1.3 / 1000).toFixed(0)} kN.`,
        suggested_changes: [
          {
            field: 'boundary.input_value',
            value: Math.round(Tfl_min_approx * 1.3),
            label: `T_fl = ${(Tfl_min_approx * 1.3 / 1000).toFixed(0)} kN`,
          },
        ],
        affected_fields: ['boundary.input_value'],
      })
    }
  }

  return diagnostics
}

/**
 * Computa a severidade pior (worst-case) de uma lista de diagnósticos.
 * Ordem: critical > error > warning > info > null.
 * Usada pra colorir o plot border, badges, etc.
 */
export function worstSeverity(
  diagnostics: { severity: DiagnosticSeverity }[] | null | undefined,
): DiagnosticSeverity | null {
  if (!diagnostics || diagnostics.length === 0) return null
  const order: Record<DiagnosticSeverity, number> = {
    critical: 4,
    error: 3,
    warning: 2,
    info: 1,
  }
  let worst: DiagnosticSeverity = 'info'
  let worstScore = 0
  for (const d of diagnostics) {
    const score = order[d.severity] ?? 0
    if (score > worstScore) {
      worstScore = score
      worst = d.severity
    }
  }
  return worst
}

/**
 * Retorna mapeamento `affectedFieldsSet` para query rápida no UI.
 * Cada path do form (e.g., "attachments[0].submerged_force") aparece
 * no Set se algum diagnostic o tiver listado em affected_fields.
 */
export function buildAffectedFieldsSet(
  diagnostics: { affected_fields: string[]; severity: DiagnosticSeverity }[]
    | null
    | undefined,
): {
  /** Set de paths afetados por algum diagnostic. */
  fields: Set<string>
  /** Map de path → pior severity afetando esse path. */
  fieldSeverity: Map<string, DiagnosticSeverity>
} {
  const fields = new Set<string>()
  const fieldSeverity = new Map<string, DiagnosticSeverity>()
  if (!diagnostics) return { fields, fieldSeverity }

  const order: Record<DiagnosticSeverity, number> = {
    critical: 4,
    error: 3,
    warning: 2,
    info: 1,
  }

  for (const diag of diagnostics) {
    for (const f of diag.affected_fields ?? []) {
      fields.add(f)
      const cur = fieldSeverity.get(f)
      if (!cur || order[diag.severity] > order[cur]) {
        fieldSeverity.set(f, diag.severity)
      }
    }
  }
  return { fields, fieldSeverity }
}
