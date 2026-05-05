/**
 * Testes do schema Zod (caseSchema.ts) — foco nos campos
 * adicionados na Fase 1 do plano de profissionalização:
 *   - mu_override
 *   - seabed_friction_cf
 *   - ea_source (com default 'qmoor')
 *   - ea_dynamic_beta (reservado v1)
 *
 * Espelha o teste backend test_types.py para garantir que frontend
 * e backend deserializam consistentemente.
 */
import { describe, it, expect } from 'vitest'
import { lineSegmentSchema } from '@/lib/caseSchema'

const minimalSegment = {
  length: 500,
  w: 200,
  EA: 7.5e9,
  MBL: 3e6,
}

describe('lineSegmentSchema — campos da Fase 1', () => {
  it('aceita segmento mínimo aplicando default ea_source=qmoor', () => {
    const parsed = lineSegmentSchema.parse(minimalSegment)
    expect(parsed.ea_source).toBe('qmoor')
    expect(parsed.mu_override ?? null).toBeNull()
    expect(parsed.seabed_friction_cf ?? null).toBeNull()
    expect(parsed.ea_dynamic_beta ?? null).toBeNull()
  })

  it('aceita ea_source=gmoor explícito', () => {
    const parsed = lineSegmentSchema.parse({
      ...minimalSegment,
      ea_source: 'gmoor',
    })
    expect(parsed.ea_source).toBe('gmoor')
  })

  it('rejeita ea_source inválido', () => {
    expect(() =>
      lineSegmentSchema.parse({ ...minimalSegment, ea_source: 'bogus' }),
    ).toThrow()
  })

  it('aceita mu_override válido (zero ou positivo)', () => {
    expect(
      lineSegmentSchema.parse({ ...minimalSegment, mu_override: 0 }).mu_override,
    ).toBe(0)
    expect(
      lineSegmentSchema.parse({ ...minimalSegment, mu_override: 0.7 }).mu_override,
    ).toBe(0.7)
  })

  it('rejeita mu_override negativo', () => {
    expect(() =>
      lineSegmentSchema.parse({ ...minimalSegment, mu_override: -0.1 }),
    ).toThrow()
  })

  it('aceita seabed_friction_cf do catálogo', () => {
    const parsed = lineSegmentSchema.parse({
      ...minimalSegment,
      seabed_friction_cf: 1.0,
    })
    expect(parsed.seabed_friction_cf).toBe(1.0)
  })

  it('rejeita seabed_friction_cf negativo', () => {
    expect(() =>
      lineSegmentSchema.parse({
        ...minimalSegment,
        seabed_friction_cf: -0.5,
      }),
    ).toThrow()
  })

  it('aceita ea_dynamic_beta reservado (não usado em v1)', () => {
    const parsed = lineSegmentSchema.parse({
      ...minimalSegment,
      ea_source: 'gmoor',
      ea_dynamic_beta: 1500,
    })
    expect(parsed.ea_dynamic_beta).toBe(1500)
  })

  it('aceita payload legado sem campos Fase 1 (retro-compat)', () => {
    // Simula JSON salvo antes da Fase 1
    const legacy = {
      length: 450,
      w: 201.1,
      EA: 3.425e7,
      MBL: 3.78e6,
      category: 'Wire',
      line_type: 'IWRCEIPS',
    }
    const parsed = lineSegmentSchema.parse(legacy)
    expect(parsed.ea_source).toBe('qmoor') // default aplicado
    expect(parsed.mu_override ?? null).toBeNull()
    expect(parsed.seabed_friction_cf ?? null).toBeNull()
  })
})
