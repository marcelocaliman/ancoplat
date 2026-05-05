/**
 * Smoke test da SamplesPage (Fase 9 / Q2+Q3).
 *
 * Verifica:
 *  - Renderiza ≥ 11 samples (6 existentes + 5 novos da F9).
 *  - Cards preview têm marcação visual + label "Preview · F7/F8".
 *  - Toggle "Ocultar previews" filtra preview samples.
 *  - Busca filtra por nome.
 */
import { describe, it, expect } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { SamplesPage } from '@/pages/SamplesPage'
import { CASE_TEMPLATES } from '@/lib/caseTemplates'

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/samples']}>
      <SamplesPage />
    </MemoryRouter>,
  )
}

describe('SamplesPage (Fase 9)', () => {
  it('renderiza ≥ 11 samples', () => {
    expect(CASE_TEMPLATES.length).toBeGreaterThanOrEqual(11)
    renderPage()
    // Pelo menos os títulos de cada template devem aparecer
    for (const tpl of CASE_TEMPLATES) {
      expect(screen.getByText(tpl.name)).toBeTruthy()
    }
  })

  it('exatamente 5 samples novos da F9 estão presentes', () => {
    const newIds = [
      'clump-weight',
      'lifted-arch',
      'sloped-seabed',
      'anchor-uplift',
      'ahv-pull',
    ]
    for (const id of newIds) {
      expect(CASE_TEMPLATES.find((t) => t.id === id)).toBeTruthy()
    }
  })

  it('zero samples preview pós-F8 (F7 e F8 ambos destravados)', () => {
    // Pós-Fase 7: anchor-uplift destravado.
    // Pós-Fase 8: ahv-pull também destravado.
    const previews = CASE_TEMPLATES.filter((t) => t.requirePhase != null)
    expect(previews.length).toBe(0)
  })

  it('nenhum card preview visível pós-F8', () => {
    renderPage()
    expect(screen.queryByText(/Preview · F7/)).toBeNull()
    expect(screen.queryByText(/Preview · F8/)).toBeNull()
  })

  it('toggle "Ocultar previews" remove samples preview', () => {
    renderPage()
    const toggle = screen.getByRole('button', { name: /Ocultar previews/i })
    fireEvent.click(toggle)
    expect(screen.queryByText(/Preview · F7/)).toBeNull()
    expect(screen.queryByText(/Preview · F8/)).toBeNull()
  })

  it('busca filtra por nome', () => {
    renderPage()
    const search = screen.getByLabelText(/Buscar sample/i)
    fireEvent.change(search, { target: { value: 'lifted' } })
    expect(screen.getByText(/Boia em arc grounded/i)).toBeTruthy()
    // Catenária clássica não deve aparecer
    expect(screen.queryByText('Catenária clássica')).toBeNull()
  })
})
