/**
 * Smoke test do CatalogPage com tabs Cabos/Boias (Fase 6 / Q6).
 *
 * Verifica:
 *  - Tabs Cabos | Boias renderizam.
 *  - URL deep-linking: ?tab=buoys ativa a tab de boias.
 *  - URL ?tab=cables (ou sem tab) ativa cables.
 *  - Tab inválida cai em cables.
 */
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { CatalogPage } from '@/pages/CatalogPage'

vi.mock('@/api/endpoints', () => ({
  listLineTypes: vi
    .fn()
    .mockResolvedValue({ items: [], total: 0, page: 1, page_size: 30 }),
  listBuoys: vi
    .fn()
    .mockResolvedValue({ items: [], total: 0, page: 1, page_size: 30 }),
  createLineType: vi.fn(),
  updateLineType: vi.fn(),
  deleteLineType: vi.fn(),
  createBuoy: vi.fn(),
  updateBuoy: vi.fn(),
  deleteBuoy: vi.fn(),
}))

function withProviders(initialPath: string) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return (
    <MemoryRouter initialEntries={[initialPath]}>
      <QueryClientProvider client={qc}>
        <CatalogPage />
      </QueryClientProvider>
    </MemoryRouter>
  )
}

describe('CatalogPage tabs (Fase 6 / Q6)', () => {
  it('renderiza tabs Cabos e Boias', () => {
    render(withProviders('/catalog'))
    expect(screen.getByRole('tab', { name: /Cabos/i })).toBeTruthy()
    expect(screen.getByRole('tab', { name: /Boias/i })).toBeTruthy()
  })

  it('default (sem ?tab) ativa Cabos', () => {
    render(withProviders('/catalog'))
    const cables = screen.getByRole('tab', { name: /Cabos/i })
    expect(cables.getAttribute('data-state')).toBe('active')
  })

  it('?tab=buoys ativa Boias', () => {
    render(withProviders('/catalog?tab=buoys'))
    const buoys = screen.getByRole('tab', { name: /Boias/i })
    expect(buoys.getAttribute('data-state')).toBe('active')
  })

  it('?tab=cables ativa Cabos', () => {
    render(withProviders('/catalog?tab=cables'))
    const cables = screen.getByRole('tab', { name: /Cabos/i })
    expect(cables.getAttribute('data-state')).toBe('active')
  })

  it('tab inválida cai em Cabos', () => {
    render(withProviders('/catalog?tab=foo'))
    const cables = screen.getByRole('tab', { name: /Cabos/i })
    expect(cables.getAttribute('data-state')).toBe('active')
  })
})
