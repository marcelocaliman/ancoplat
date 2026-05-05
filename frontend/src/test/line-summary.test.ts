/**
 * Unit test do aggregateLineSummary (Fase 3 / A1.5).
 *
 * Cobre 1, 3, 10 segmentos com valores conhecidos e edge cases:
 *   - dry_weight null em algum segmento → dryTotal = null
 *   - segmentos vazios ([]) → todos zerados
 *   - somatórios em diferentes ordens de grandeza
 */
import { describe, it, expect } from 'vitest'
import { aggregateLineSummary } from '@/components/common/LineSummaryPanel'

describe('aggregateLineSummary', () => {
  it('1 segmento — soma direta', () => {
    const r = aggregateLineSummary([
      { length: 500, w: 200, dry_weight: 250 },
    ])
    expect(r.count).toBe(1)
    expect(r.lengthTotal).toBe(500)
    expect(r.wetTotal).toBe(500 * 200) // 100_000
    expect(r.dryTotal).toBe(500 * 250) // 125_000
  })

  it('3 segmentos — multi-segmento típico (chain + wire + chain)', () => {
    const r = aggregateLineSummary([
      { length: 200, w: 1058, dry_weight: 1240 },  // chain pesada
      { length: 600, w: 22.4, dry_weight: 27 },    // wire leve
      { length: 200, w: 1058, dry_weight: 1240 },  // chain pesada
    ])
    expect(r.count).toBe(3)
    expect(r.lengthTotal).toBe(1000)
    expect(r.wetTotal).toBeCloseTo(200 * 1058 + 600 * 22.4 + 200 * 1058, 6)
    expect(r.dryTotal).toBeCloseTo(200 * 1240 + 600 * 27 + 200 * 1240, 6)
  })

  it('10 segmentos — máximo do schema', () => {
    const segs = Array.from({ length: 10 }, (_, i) => ({
      length: 100 + i * 10,
      w: 200,
      dry_weight: 250,
    }))
    const r = aggregateLineSummary(segs)
    expect(r.count).toBe(10)
    expect(r.lengthTotal).toBe(
      segs.reduce((acc, s) => acc + s.length, 0), // 100+110+...+190 = 1450
    )
    expect(r.wetTotal).toBe(r.lengthTotal * 200)
    expect(r.dryTotal).toBe(r.lengthTotal * 250)
  })

  it('lista vazia — agregados zerados, dryTotal=null', () => {
    const r = aggregateLineSummary([])
    expect(r.count).toBe(0)
    expect(r.lengthTotal).toBe(0)
    expect(r.wetTotal).toBe(0)
    expect(r.dryTotal).toBe(null)
  })

  it('segmento com dry_weight null → dryTotal vira null', () => {
    const r = aggregateLineSummary([
      { length: 200, w: 1058, dry_weight: 1240 },
      { length: 600, w: 22.4, dry_weight: null },  // null!
      { length: 200, w: 1058, dry_weight: 1240 },
    ])
    expect(r.dryTotal).toBe(null)
    // Mas length e wet continuam calculáveis
    expect(r.lengthTotal).toBe(1000)
    expect(r.wetTotal).toBeCloseTo(200 * 1058 + 600 * 22.4 + 200 * 1058, 6)
  })

  it('campos undefined são tratados como 0 (não quebra a soma)', () => {
    const r = aggregateLineSummary([
      { length: 500, w: 200 }, // dry_weight ausente
    ])
    expect(r.dryTotal).toBe(null) // ausente trata como null
    expect(r.lengthTotal).toBe(500)
  })

  it('unidades SI consistentes (Σw·L em N)', () => {
    // w em N/m, L em m → wetTotal em N
    const r = aggregateLineSummary([
      { length: 1000, w: 1000, dry_weight: null },
    ])
    expect(r.wetTotal).toBe(1_000_000) // 1 MN
  })
})
