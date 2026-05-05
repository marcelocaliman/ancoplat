/**
 * Round-trip de unidades: SI ↔ unidade ↔ SI deve ser numericamente
 * exato dentro de rtol=1e-10 (Fase 10 / Commit 7).
 *
 * Garante que uma conversão de ida e volta entre Newton (SI) e
 * tonelada-força (te), kN, kgf/m etc. NÃO acumule erro além da
 * precisão de double-precision IEEE 754 (~1.1e-16 epsilon).
 *
 * Tolerância 1e-10: 4 ordens de magnitude acima do epsilon, capta
 * qualquer erro real na conversão sem ser pego por ruído numérico.
 */
import { describe, it, expect } from 'vitest'
import { siToUnit, unitToSi, type Unit } from '@/lib/units'

const ROUND_TRIP_TOL = 1e-10

const FORCE_UNITS: Unit[] = ['N', 'kN', 'te']
const FORCE_PER_M_UNITS: Unit[] = ['N/m', 'kgf/m']

const SAMPLE_SI_VALUES_FORCE = [
  0,
  1,
  10,
  1_000,
  9_806.65,    // 1 te exato
  100_000,
  1_000_000,
  1_500_000,   // típico T_fl
  5_000_000,
  9.8e6,
  1e9,
  1e-3,
  1e-6,
]

const SAMPLE_SI_VALUES_W = [
  0,
  1,
  9.80665,    // 1 kgf/m exato
  100,
  200,        // chain leve
  1_100,      // chain pesado
  10_000,
]

describe('Round-trip SI ↔ unidade força (rtol < 1e-10)', () => {
  for (const unit of FORCE_UNITS) {
    for (const si of SAMPLE_SI_VALUES_FORCE) {
      it(`${si} N → ${unit} → N`, () => {
        const inUnit = siToUnit(si, unit)
        const back = unitToSi(inUnit, unit)
        if (si === 0) {
          expect(Math.abs(back - si)).toBeLessThan(ROUND_TRIP_TOL)
        } else {
          const relErr = Math.abs(back - si) / Math.abs(si)
          expect(relErr).toBeLessThan(ROUND_TRIP_TOL)
        }
      })
    }
  }
})

describe('Round-trip SI ↔ unidade peso/m (rtol < 1e-10)', () => {
  for (const unit of FORCE_PER_M_UNITS) {
    for (const si of SAMPLE_SI_VALUES_W) {
      it(`${si} N/m → ${unit} → N/m`, () => {
        const inUnit = siToUnit(si, unit)
        const back = unitToSi(inUnit, unit)
        if (si === 0) {
          expect(Math.abs(back - si)).toBeLessThan(ROUND_TRIP_TOL)
        } else {
          const relErr = Math.abs(back - si) / Math.abs(si)
          expect(relErr).toBeLessThan(ROUND_TRIP_TOL)
        }
      })
    }
  }
})

describe('Round-trip ida-e-volta (unidade → SI → unidade)', () => {
  it('te → N → te preserva 1 te exato', () => {
    const back = siToUnit(unitToSi(1, 'te'), 'te')
    expect(Math.abs(back - 1)).toBeLessThan(ROUND_TRIP_TOL)
  })

  it('kN → N → kN preserva 1500 kN', () => {
    const back = siToUnit(unitToSi(1500, 'kN'), 'kN')
    expect(Math.abs(back - 1500) / 1500).toBeLessThan(ROUND_TRIP_TOL)
  })

  it('kgf/m → N/m → kgf/m preserva 100 kgf/m', () => {
    const back = siToUnit(unitToSi(100, 'kgf/m'), 'kgf/m')
    expect(Math.abs(back - 100) / 100).toBeLessThan(ROUND_TRIP_TOL)
  })
})

describe('Identidades específicas (G, ρ_seawater)', () => {
  it('1 te = 9806.65 N (exato pelo SI)', () => {
    const inSI = unitToSi(1, 'te')
    expect(inSI).toBeCloseTo(9806.65, 10)
  })

  it('1 kgf/m = 9.80665 N/m (exato)', () => {
    const inSI = unitToSi(1, 'kgf/m')
    expect(inSI).toBeCloseTo(9.80665, 10)
  })

  it('1 kN = 1000 N (exato)', () => {
    expect(unitToSi(1, 'kN')).toBe(1000)
    expect(siToUnit(1000, 'kN')).toBe(1)
  })
})
