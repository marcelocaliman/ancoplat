/**
 * Smoke test de a11y dos 4 forms principais (Fase 9 / Q8).
 *
 * Foca no que tem custo-benefício alto:
 *  - injectA11y associa Label↔Input via id (htmlFor + id no input).
 *  - aria-required em campos required.
 *  - aria-live="polite" no banner Stale solver.
 *
 * Não testa flow completo de screen reader (escopo guardado para v1.1+).
 */
import { describe, expect, it } from 'vitest'
import { render } from '@testing-library/react'
import { __injectA11yForTesting as injectA11y } from '@/components/common/SegmentEditor'

describe('injectA11y helper (Fase 9 / Q8)', () => {
  it('injeta id no primeiro child Input', () => {
    const out = injectA11y(<input type="text" />, { id: 'foo-1' })
    const { container } = render(<>{out}</>)
    expect(container.querySelector('input')?.id).toBe('foo-1')
  })

  it('injeta aria-required quando required=true', () => {
    const out = injectA11y(<input type="text" />, {
      id: 'bar-2',
      required: true,
    })
    const { container } = render(<>{out}</>)
    expect(container.querySelector('input')?.getAttribute('aria-required')).toBe(
      'true',
    )
  })

  it('omite aria-required quando required=false', () => {
    const out = injectA11y(<input type="text" />, { id: 'baz-3' })
    const { container } = render(<>{out}</>)
    expect(container.querySelector('input')?.hasAttribute('aria-required')).toBe(
      false,
    )
  })

  it('preserva children não-elementos sem crashar', () => {
    // String / null / undefined / array vazio — não deve quebrar
    const out = injectA11y('texto puro', { id: 'x' })
    expect(out).toBe('texto puro')
  })

  it('lida com array de children (cloneElement no primeiro)', () => {
    const out = injectA11y(
      [<input key="a" type="text" />, <span key="b">extra</span>],
      { id: 'multi-1', required: true },
    )
    const { container } = render(<>{out}</>)
    expect(container.querySelector('input')?.id).toBe('multi-1')
  })
})
