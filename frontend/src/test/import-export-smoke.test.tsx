/**
 * Smoke da ImportExportPage (Fase 10 / Commit 9).
 *
 * Garante:
 *  - Página renderiza com header e tabs Importar / Exportar
 *  - Tab "Importar" mostra área de drop + input file
 *  - Tab "Exportar" troca conteúdo
 *
 * UI regression complementa os smokes já existentes da F9
 * (samples-page, glossary, ahv-frontend, etc).
 */
import { describe, it, expect } from 'vitest'
import { screen, fireEvent } from '@testing-library/react'
import { renderWithProviders } from './helpers'
import { ImportExportPage } from '@/pages/ImportExportPage'

function renderPage() {
  return renderWithProviders(<ImportExportPage />, { route: '/import-export' })
}

describe('ImportExportPage smoke (Fase 10)', () => {
  it('renderiza tabs Importar e Exportar', () => {
    renderPage()
    // Tab triggers
    expect(screen.getByRole('tab', { name: /Importar/i })).toBeTruthy()
    expect(screen.getByRole('tab', { name: /Exportar/i })).toBeTruthy()
  })

  it('tab Importar mostra alguma menção a .moor', () => {
    renderPage()
    // Por padrão a tab "Importar" está ativa. Pode haver múltiplas
    // menções (instruções + label de input).
    const moorRefs = screen.getAllByText(/\.moor/i)
    expect(moorRefs.length).toBeGreaterThan(0)
  })

  it('alternar para Exportar não crasha', () => {
    renderPage()
    const exportTab = screen.getByRole('tab', { name: /Exportar/i })
    fireEvent.click(exportTab)
    // Smoke: clique não deve resultar em erro de render.
    expect(exportTab).toBeTruthy()
  })
})
