/**
 * Smoke do CatenaryPlot com anchor uplift (Fase 7 / Q7).
 *
 * Verifica via leitura do source que:
 *  - CatenaryPlot usa `endpoint_depth` (não water_depth) para anchorY.
 *  - A translação plot_y aplica `endpoint_depth`.
 *  - Frame solver (anchor em y=0) preservado.
 */
import { describe, expect, it } from 'vitest'
import plotSource from '../components/common/CatenaryPlot.tsx?raw'

const src: string = plotSource

describe('CatenaryPlot uplift support (Fase 7 / Q7)', () => {
  it('usa endpoint_depth para anchorY (deslocamento vertical)', () => {
    expect(src).toMatch(/anchorY\s*=\s*-endpointDepth/)
  })

  it('translação plot_y usa endpointDepth (não waterDepth)', () => {
    expect(src).toMatch(/plotY\.push\(sy\s*-\s*endpointDepth\)/)
  })

  it('endpointDepth lê de result.endpoint_depth com fallback waterDepth', () => {
    expect(src).toMatch(/endpointDepth\s*=\s*result\.endpoint_depth\s*\?\?\s*waterDepth/)
  })
})
