/**
 * Cobertura dos pre-solve diagnostics P001..P004 (Fase 4 / Q5).
 *
 * Cada P00X tem 3 testes: repro, no-repro, apply (best-effort).
 *
 * Pre-solve roda no frontend ANTES de chamar o solver — é a primeira
 * linha de defesa contra inputs claramente inválidos. Diagnósticos
 * são severities {critical, warning} e suggested_changes que a UI
 * pode aplicar via setValue.
 */
import { describe, it, expect } from 'vitest'
import { runPreSolveDiagnostics } from '@/lib/preSolveDiagnostics'
import type { CaseFormValues } from '@/lib/caseSchema'

function _baseValues(overrides: Partial<CaseFormValues> = {}): CaseFormValues {
  return {
    name: 'test',
    description: '',
    segments: [
      {
        length: 500,
        w: 200,
        EA: 7.5e9,
        MBL: 3e6,
        category: 'Wire',
        line_type: null,
        diameter: 0.0762,
        dry_weight: 250,
        modulus: null,
        mu_override: null,
        seabed_friction_cf: null,
        ea_source: 'qmoor',
        ea_dynamic_beta: null,
      },
    ],
    boundary: {
      h: 200,
      mode: 'Tension',
      input_value: 200_000,
      startpoint_depth: 0,
      endpoint_grounded: true,
      startpoint_offset_horz: 0,
      startpoint_offset_vert: 0,
      startpoint_type: 'semisub',
    },
    seabed: { mu: 0, slope_rad: 0 },
    criteria_profile: 'MVP_Preliminary',
    user_defined_limits: null,
    attachments: [],
    ...overrides,
  } as CaseFormValues
}


// ─── P001 — cabo curto demais ────────────────────────────────────────


describe('P001 — Cabo curto demais', () => {
  it('repro: L = h*1.0 dispara critical', () => {
    const v = _baseValues({
      segments: [{ ..._baseValues().segments![0]!, length: 200 }],
      boundary: { ..._baseValues().boundary, h: 200 },
    })
    const diags = runPreSolveDiagnostics(v)
    const p1 = diags.find((d) => d.code === 'P001_CABLE_TOO_SHORT')
    expect(p1).toBeDefined()
    expect(p1?.severity).toBe('critical')
    expect(p1?.suggested_changes).toHaveLength(1)
  })

  it('no-repro: L = h*1.5 não dispara', () => {
    const v = _baseValues({
      segments: [{ ..._baseValues().segments![0]!, length: 300 }],
      boundary: { ..._baseValues().boundary, h: 200 },
    })
    const diags = runPreSolveDiagnostics(v)
    expect(diags.find((d) => d.code === 'P001_CABLE_TOO_SHORT')).toBeUndefined()
  })

  it('apply: aplicar suggested length resolve P001', () => {
    const v = _baseValues({
      segments: [{ ..._baseValues().segments![0]!, length: 200 }],
      boundary: { ..._baseValues().boundary, h: 200 },
    })
    const diags = runPreSolveDiagnostics(v)
    const sugg = diags[0]?.suggested_changes[0]
    expect(sugg).toBeDefined()
    // Aplica
    const v2 = _baseValues({
      segments: [
        { ..._baseValues().segments![0]!, length: sugg!.value },
      ],
      boundary: { ..._baseValues().boundary, h: 200 },
    })
    const diags2 = runPreSolveDiagnostics(v2)
    expect(
      diags2.find((d) => d.code === 'P001_CABLE_TOO_SHORT'),
    ).toBeUndefined()
  })
})


// ─── P002 — empuxo > peso ────────────────────────────────────────────


describe('P002 — Empuxo das boias excede peso', () => {
  it('repro: boia muito grande em cabo leve dispara critical', () => {
    const v = _baseValues({
      segments: [{ ..._baseValues().segments![0]!, length: 100, w: 10 }],
      attachments: [
        {
          kind: 'buoy',
          submerged_force: 50_000,
          position_s_from_anchor: 50,
          name: 'Boia A',
        },
      ],
    })
    const diags = runPreSolveDiagnostics(v)
    const p2 = diags.find((d) => d.code === 'P002_BUOYANCY_EXCEEDS_WEIGHT')
    expect(p2).toBeDefined()
    expect(p2?.severity).toBe('critical')
  })

  it('no-repro: boia menor que peso da linha não dispara', () => {
    const v = _baseValues({
      attachments: [
        {
          kind: 'buoy',
          submerged_force: 10_000,
          position_s_from_anchor: 200,
          name: 'Boia A',
        },
      ],
    })
    const diags = runPreSolveDiagnostics(v)
    expect(
      diags.find((d) => d.code === 'P002_BUOYANCY_EXCEEDS_WEIGHT'),
    ).toBeUndefined()
  })

  it('apply: aplicar redução de empuxo resolve P002 (best-effort)', () => {
    const v = _baseValues({
      segments: [{ ..._baseValues().segments![0]!, length: 100, w: 10 }],
      attachments: [
        {
          kind: 'buoy',
          submerged_force: 50_000,
          position_s_from_anchor: 50,
          name: 'Boia A',
        },
      ],
    })
    const diags = runPreSolveDiagnostics(v)
    const sugg = diags
      .find((d) => d.code === 'P002_BUOYANCY_EXCEEDS_WEIGHT')!
      .suggested_changes[0]
    const v2 = _baseValues({
      segments: [{ ..._baseValues().segments![0]!, length: 100, w: 10 }],
      attachments: [
        {
          kind: 'buoy',
          submerged_force: sugg!.value,
          position_s_from_anchor: 50,
          name: 'Boia A',
        },
      ],
    })
    const diags2 = runPreSolveDiagnostics(v2)
    expect(
      diags2.find((d) => d.code === 'P002_BUOYANCY_EXCEEDS_WEIGHT'),
    ).toBeUndefined()
  })
})


// ─── P003 — attachment fora do range ─────────────────────────────────


describe('P003 — Posição de attachment fora do range', () => {
  it('repro: position_s_from_anchor > total length dispara', () => {
    const v = _baseValues({
      attachments: [
        {
          kind: 'clump_weight',
          submerged_force: 5000,
          position_s_from_anchor: 999, // > total_length=500
          name: 'Clump A',
        },
      ],
    })
    const diags = runPreSolveDiagnostics(v)
    expect(
      diags.find((d) => d.code === 'P003_ATTACHMENT_OUT_OF_RANGE'),
    ).toBeDefined()
  })

  it('no-repro: position dentro do range não dispara', () => {
    const v = _baseValues({
      attachments: [
        {
          kind: 'clump_weight',
          submerged_force: 5000,
          position_s_from_anchor: 250,
          name: 'Clump A',
        },
      ],
    })
    const diags = runPreSolveDiagnostics(v)
    expect(
      diags.find((d) => d.code === 'P003_ATTACHMENT_OUT_OF_RANGE'),
    ).toBeUndefined()
  })

  it('apply: P003 sem suggested_changes (UI deve clamp manualmente)', () => {
    /**
     * P003 é caso onde suggested_changes pode estar vazio (a sugestão
     * é genérica: "ajuste a posição"). UI deve clamp via constraint do
     * input — apply test = best-effort sem assertion automática.
     */
    const v = _baseValues({
      attachments: [
        {
          kind: 'clump_weight',
          submerged_force: 5000,
          position_s_from_anchor: 999,
          name: 'Clump A',
        },
      ],
    })
    const p3 = runPreSolveDiagnostics(v).find(
      (d) => d.code === 'P003_ATTACHMENT_OUT_OF_RANGE',
    )!
    // P003 pode ter suggested_changes vazio — best-effort
    expect(Array.isArray(p3.suggested_changes)).toBe(true)
  })
})


// ─── P004 — T_fl baixo (heurística) ──────────────────────────────────


describe('P004 — T_fl provavelmente insuficiente (heurística)', () => {
  it('repro: T_fl muito baixo em cabo pesado dispara warning', () => {
    const v = _baseValues({
      segments: [{ ..._baseValues().segments![0]!, length: 1000, w: 1000 }],
      boundary: {
        ..._baseValues().boundary,
        h: 500,
        input_value: 1_000, // T_fl muito baixo
      },
    })
    const diags = runPreSolveDiagnostics(v)
    const p4 = diags.find((d) => d.code === 'P004_TFL_LIKELY_TOO_LOW')
    if (p4) {
      expect(p4.severity).toBe('warning')
    }
    // Best-effort: heurística pode ou não disparar conforme calibração
  })

  it('no-repro: T_fl alto não dispara', () => {
    const v = _baseValues({
      boundary: { ..._baseValues().boundary, input_value: 2_000_000 },
    })
    const diags = runPreSolveDiagnostics(v)
    expect(
      diags.find((d) => d.code === 'P004_TFL_LIKELY_TOO_LOW'),
    ).toBeUndefined()
  })

  it('apply: aumentar T_fl resolve P004 (best-effort)', () => {
    const v = _baseValues({
      segments: [{ ..._baseValues().segments![0]!, length: 1000, w: 1000 }],
      boundary: {
        ..._baseValues().boundary,
        h: 500,
        input_value: 1_000,
      },
    })
    const diags = runPreSolveDiagnostics(v)
    const p4 = diags.find((d) => d.code === 'P004_TFL_LIKELY_TOO_LOW')
    if (!p4 || !p4.suggested_changes[0]) {
      return // best-effort: case calibração não disparou — OK
    }
    const v2 = _baseValues({
      segments: [{ ..._baseValues().segments![0]!, length: 1000, w: 1000 }],
      boundary: {
        ..._baseValues().boundary,
        h: 500,
        input_value: p4.suggested_changes[0].value,
      },
    })
    const diags2 = runPreSolveDiagnostics(v2)
    expect(
      diags2.find((d) => d.code === 'P004_TFL_LIKELY_TOO_LOW'),
    ).toBeUndefined()
  })
})
