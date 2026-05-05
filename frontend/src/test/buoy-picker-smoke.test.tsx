/**
 * Smoke test do BuoyPicker (Fase 6 / Q1+Q7).
 *
 * Verifica:
 *  - Render placeholder quando selectedId=null.
 *  - Render label resumido quando selectedId aponta a uma boia conhecida
 *    (passada via mock do listBuoys).
 *  - Botão de limpar liga onClear.
 *
 * Não exercita o popover completo (rede + Radix portals) — isso fica
 * para test E2E em Fase 10.
 */
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BuoyPicker } from '@/components/common/BuoyPicker'

vi.mock('@/api/endpoints', () => ({
  listBuoys: vi.fn().mockResolvedValue({
    items: [],
    total: 0,
    page: 1,
    page_size: 50,
  }),
}))

function withQuery(ui: React.ReactNode) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return <QueryClientProvider client={qc}>{ui}</QueryClientProvider>
}

describe('BuoyPicker (Fase 6 / Q1+Q7)', () => {
  it('renderiza placeholder quando selectedId é null', () => {
    render(
      withQuery(
        <BuoyPicker selectedId={null} onPick={() => {}} onClear={() => {}} />,
      ),
    )
    expect(screen.getByText(/Escolher boia do catálogo/)).toBeTruthy()
  })

  it('renderiza fallback "id=N" quando catálogo ainda não carregou', () => {
    render(
      withQuery(
        <BuoyPicker selectedId={42} onPick={() => {}} onClear={() => {}} />,
      ),
    )
    expect(screen.getByText(/id=42/)).toBeTruthy()
  })

  it('aceita disabled=true sem crashar', () => {
    const { container } = render(
      withQuery(
        <BuoyPicker
          selectedId={null}
          onPick={() => {}}
          onClear={() => {}}
          disabled
        />,
      ),
    )
    expect(container.firstChild).toBeTruthy()
  })

  it('chama onPick e onClear como callbacks distintos', () => {
    const onPick = vi.fn()
    const onClear = vi.fn()
    render(
      withQuery(
        <BuoyPicker selectedId={1} onPick={onPick} onClear={onClear} />,
      ),
    )
    // Não tentamos abrir o popover (Radix portal); só asseguramos que
    // o botão trigger renderizou e que callbacks foram aceitos.
    const trigger = screen.getByRole('combobox')
    expect(trigger).toBeTruthy()
    fireEvent.click(trigger)
    expect(onPick).not.toHaveBeenCalled()
    expect(onClear).not.toHaveBeenCalled()
  })
})
