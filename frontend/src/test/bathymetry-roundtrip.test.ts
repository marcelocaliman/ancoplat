/**
 * Round-trip determinístico do BathymetryInputGroup (Ajuste 2 da Fase 2).
 *
 * Hipótese a defender: dado um case salvo com (h, slope_rad, X_total),
 * a derivação reversa (boundary → 3 campos) seguida da derivação
 * direta (3 campos → slope) reproduz EXATAMENTE o slope_rad original.
 *
 * Sem isso, há risco de drift silencioso: o engenheiro abre um case,
 * não altera nada, salva, e o slope_rad muda por erro de aproximação
 * — corrompendo a regressão `cases_baseline_2026-05-04.json`.
 */
import { describe, it, expect } from 'vitest'
import {
  deriveBathymetryFromBoundary,
  deriveSlopeFromBathymetry,
} from '@/components/common/BathymetryInputGroup'

const TOL = 1e-9

describe('Bathymetry round-trip (Ajuste 2 da Fase 2)', () => {
  // Matriz de cases físicamente plausíveis (depthFairlead ≥ 0 sempre).
  // Geometrias onde tan(slope)·X excede h produziriam seabed acima da
  // superfície — caso impossível, não exercitado aqui (clamp a 0 é
  // o comportamento correto e quebra intencionalmente o round-trip).
  it.each([
    { h: 300, slope_deg: 0, x: 500 },          // case típico horizontal
    { h: 200, slope_deg: 5, x: 600 },          // pequena inclinação
    { h: 1500, slope_deg: -3.5, x: 2400 },     // deepwater descendente
    { h: 800, slope_deg: -15, x: 1200 },       // descendente forte
    { h: 50, slope_deg: 0, x: 100 },           // shallow water
    { h: 3000, slope_deg: 0.5, x: 5000 },      // ultra-deep + slope leve
    { h: 500, slope_deg: 10, x: 1000 },        // ascendente moderado (tan·X=176 < h=500)
  ])(
    'h=$h, slope=$slope_deg°, X=$x — slope reproduz após reverse + forward',
    ({ h, slope_deg, x }) => {
      const slopeRadOrig = (slope_deg * Math.PI) / 180

      // 1. Reverse: boundary → 3 campos primários
      const { depthAnchor, depthFairlead, horizontalDistance } =
        deriveBathymetryFromBoundary(h, slopeRadOrig, x)

      // 2. Forward: 3 campos → slope_rad recalculado
      const slopeRadRoundtrip = deriveSlopeFromBathymetry(
        depthAnchor, depthFairlead, horizontalDistance,
      )

      expect(Math.abs(slopeRadRoundtrip - slopeRadOrig)).toBeLessThan(TOL)
    },
  )

  it('depthAnchor sempre igual a h (identidade direta)', () => {
    const { depthAnchor } = deriveBathymetryFromBoundary(427.5, 0.123, 800)
    expect(depthAnchor).toBe(427.5)
  })

  it('horizontalDistance sempre igual a X quando fornecido', () => {
    const { horizontalDistance } = deriveBathymetryFromBoundary(
      300, 0.05, 1234.5,
    )
    expect(horizontalDistance).toBe(1234.5)
  })

  it('depthFairlead = h - tan(slope)·X (fórmula explícita)', () => {
    const h = 300, slope = 0.1, X = 800
    const { depthFairlead } = deriveBathymetryFromBoundary(h, slope, X)
    const expected = h - Math.tan(slope) * X
    expect(Math.abs(depthFairlead - expected)).toBeLessThan(TOL)
  })

  it('depthFairlead clamped a 0 quando seria negativo (rampa íngreme)', () => {
    // h=100, slope=45° → tan(45)·X=X. Para X=200, depthFairlead = 100-200 = -100
    // → clampa a 0 para evitar profundidade negativa absurda no UI.
    const { depthFairlead } = deriveBathymetryFromBoundary(
      100, Math.PI / 4, 200,
    )
    expect(depthFairlead).toBe(0)
  })

  it('horizontalDistance=undefined usa fallback 500m', () => {
    const { horizontalDistance } = deriveBathymetryFromBoundary(
      300, 0.05, undefined,
    )
    expect(horizontalDistance).toBe(500)
  })

  it('slope=0 e quaisquer profundidades iguais → slope recalculado=0', () => {
    const slope = deriveSlopeFromBathymetry(300, 300, 1000)
    expect(slope).toBe(0)
  })

  it('depth_anchor > depth_fairlead → slope > 0 (sobe ao fairlead)', () => {
    const slope = deriveSlopeFromBathymetry(300, 250, 1000)
    expect(slope).toBeGreaterThan(0)
  })

  it('depth_anchor < depth_fairlead → slope < 0 (desce ao fairlead)', () => {
    const slope = deriveSlopeFromBathymetry(300, 350, 1000)
    expect(slope).toBeLessThan(0)
  })
})
