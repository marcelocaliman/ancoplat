/**
 * Smoke test do glossário (Fase 9 / Q5+Q6).
 *
 * Verifica:
 *  - GLOSSARY tem ≥ 30 verbetes (Q6 ajustado: ~34 com uplift/AHV/bollard).
 *  - Verbetes preview F7 (anchor-uplift) e F8 (AHV, bollard-pull) presentes.
 *  - searchGlossary() filtra por termo.
 *  - HelpGlossaryPage renderiza com filtros funcionais.
 */
import { describe, it, expect } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { HelpGlossaryPage } from '@/pages/HelpGlossaryPage'
import {
  GLOSSARY,
  getGlossaryEntry,
  searchGlossary,
} from '@/lib/glossary'

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/help/glossary']}>
      <HelpGlossaryPage />
    </MemoryRouter>,
  )
}

describe('Glossary data', () => {
  it('tem ≥ 30 verbetes', () => {
    expect(GLOSSARY.length).toBeGreaterThanOrEqual(30)
  })

  it('verbete F7 (anchor-uplift) destravado pós-F7 + F8 ainda preview', () => {
    // Pós-Fase 7: anchor-uplift implementado → sem requirePhase
    expect(getGlossaryEntry('anchor-uplift')?.requirePhase).toBeUndefined()
    // F8 ainda em desenvolvimento
    expect(getGlossaryEntry('ahv')?.requirePhase).toBe('F8')
    expect(getGlossaryEntry('bollard-pull')?.requirePhase).toBe('F8')
  })

  it('cobre 5 categorias canônicas', () => {
    const cats = new Set(GLOSSARY.map((g) => g.category))
    expect(cats).toEqual(
      new Set(['geometria', 'fisico', 'componentes', 'operacional', 'boia']),
    )
  })

  it('verbetes principais presentes (catenária, MBL, ProfileType)', () => {
    expect(getGlossaryEntry('catenaria')).toBeTruthy()
    expect(getGlossaryEntry('mbl')).toBeTruthy()
    expect(getGlossaryEntry('profile-type')).toBeTruthy()
  })

  it('searchGlossary filtra case-insensitive em term + definition', () => {
    const r1 = searchGlossary('CATENÁRIA')
    expect(r1.length).toBeGreaterThan(0)
    expect(r1.some((g) => g.id === 'catenaria')).toBe(true)
    // Busca em definição:
    const r2 = searchGlossary('moorpy')
    expect(r2.length).toBeGreaterThan(0)
  })

  it('searchGlossary respeita filtro de categoria', () => {
    const r = searchGlossary('', 'boia')
    expect(r.every((g) => g.category === 'boia')).toBe(true)
    expect(r.length).toBeGreaterThanOrEqual(4)
  })
})

describe('HelpGlossaryPage smoke (Fase 9)', () => {
  it('renderiza título e contador', () => {
    renderPage()
    expect(screen.getByRole('heading', { name: /Glossário/i })).toBeTruthy()
    expect(screen.getByText(/de \d+ verbetes visíveis/)).toBeTruthy()
  })

  it('busca filtra resultados', () => {
    renderPage()
    const input = screen.getByLabelText(/Buscar no glossário/i)
    fireEvent.change(input, { target: { value: 'AHV' } })
    expect(screen.getAllByText(/AHV/).length).toBeGreaterThan(0)
  })

  it('verbetes preview F8 têm badge "Preview · F8" (F7 destravado)', () => {
    renderPage()
    // Pós-F7: F7 não é mais preview. F8 (AHV/bollard-pull) ainda é.
    expect(screen.queryAllByText(/Preview · F7/).length).toBe(0)
    expect(screen.getAllByText(/Preview · F8/).length).toBeGreaterThan(0)
  })
})
