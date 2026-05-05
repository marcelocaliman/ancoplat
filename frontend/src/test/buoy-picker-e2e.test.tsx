/**
 * E2E do popover BuoyPicker (Fase 9 / pendência F6).
 *
 * Smoke tests anteriores em `buoy-picker-smoke.test.tsx` cobrem render
 * + fallback id + callbacks. Este arquivo cobre o flow real do popover
 * Radix usando @testing-library/user-event:
 *   1. Abrir popover via clique no trigger.
 *   2. Lista de boias renderiza (mocked listBuoys).
 *   3. Digitar busca filtra resultados.
 *   4. Clicar em uma entry chama onPick com a boia correta.
 *   5. Botão X (clear) chama onClear quando habilitado.
 *
 * Pendência F6 fechada.
 */
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BuoyPicker } from '@/components/common/BuoyPicker'

// Boias mock
const MOCK_BUOYS = [
  {
    id: 1,
    legacy_id: 1,
    name: 'GEN-Hemi-D2.0',
    buoy_type: 'submersible',
    end_type: 'hemispherical',
    base_unit_system: 'metric',
    outer_diameter: 2.0,
    length: 3.0,
    weight_in_air: 5000,
    submerged_force: 60000,
    data_source: 'generic_offshore',
    manufacturer: null,
    serial_number: null,
    comments: null,
    created_at: '2026-05-05T00:00:00',
    updated_at: '2026-05-05T00:00:00',
  },
  {
    id: 2,
    legacy_id: 2,
    name: 'GEN-Flat-D1.5',
    buoy_type: 'submersible',
    end_type: 'flat',
    base_unit_system: 'metric',
    outer_diameter: 1.5,
    length: 2.5,
    weight_in_air: 2500,
    submerged_force: 40000,
    data_source: 'generic_offshore',
    manufacturer: null,
    serial_number: null,
    comments: null,
    created_at: '2026-05-05T00:00:00',
    updated_at: '2026-05-05T00:00:00',
  },
]

const listBuoysMock = vi.fn()
vi.mock('@/api/endpoints', () => ({
  listBuoys: (...args: unknown[]) => listBuoysMock(...args),
}))

beforeEach(() => {
  listBuoysMock.mockReset()
  listBuoysMock.mockResolvedValue({
    items: MOCK_BUOYS,
    total: MOCK_BUOYS.length,
    page: 1,
    page_size: 50,
  })
})

function setup(props: {
  selectedId?: number | null
  // Tipo flexível: BuoyOutput tem legacy_id: number|null no schema gerado;
  // MOCK_BUOYS tem number sem null. `Function` é genérico o bastante para
  // permitir os dois — testes e2e não precisam de verificação estrita aqui.
  // eslint-disable-next-line @typescript-eslint/ban-types
  onPick?: Function
  onClear?: () => void
}) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  const user = userEvent.setup()
  const onPick = props.onPick ?? vi.fn()
  const onClear = props.onClear ?? vi.fn()
  render(
    <QueryClientProvider client={qc}>
      <BuoyPicker
        selectedId={props.selectedId ?? null}
        onPick={onPick as never}
        onClear={onClear}
      />
    </QueryClientProvider>,
  )
  return { user, onPick, onClear }
}

describe('BuoyPicker popover E2E (Fase 9 / pendência F6)', () => {
  it('clique no trigger abre popover e lista boias', async () => {
    const { user } = setup({})
    const trigger = screen.getByRole('combobox')
    await user.click(trigger)
    // Aguarda fetch resolver e cards aparecerem
    await waitFor(() => {
      expect(screen.getByText('GEN-Hemi-D2.0')).toBeTruthy()
      expect(screen.getByText('GEN-Flat-D1.5')).toBeTruthy()
    })
  })

  it('digitar na busca dispara request com `search` param (debounce)', async () => {
    const { user } = setup({})
    await user.click(screen.getByRole('combobox'))
    const search = screen.getByPlaceholderText(/Buscar por nome/i)
    await user.type(search, 'Hemi')
    // Debounce de 250ms — esperar e verificar que listBuoys foi chamado
    // com search='Hemi' em algum momento
    await waitFor(
      () => {
        const calls = listBuoysMock.mock.calls
        expect(
          calls.some((c) => c[0]?.search === 'Hemi'),
        ).toBe(true)
      },
      { timeout: 1500 },
    )
  })

  it('clicar numa entry chama onPick com a boia selecionada', async () => {
    const { user, onPick } = setup({})
    await user.click(screen.getByRole('combobox'))
    await waitFor(() =>
      expect(screen.getByText('GEN-Hemi-D2.0')).toBeTruthy(),
    )
    await user.click(screen.getByText('GEN-Hemi-D2.0'))
    expect(onPick).toHaveBeenCalledTimes(1)
    expect(onPick).toHaveBeenCalledWith(
      expect.objectContaining({ id: 1, name: 'GEN-Hemi-D2.0' }),
    )
  })

  it('selectedId destaca o item correspondente com classe bg-primary', async () => {
    const { user } = setup({ selectedId: 2 })
    await user.click(screen.getByRole('combobox'))
    // Aguarda a popover lista carregar
    await waitFor(() =>
      expect(
        screen.getByPlaceholderText(/Buscar por nome/i),
      ).toBeTruthy(),
    )
    // Coleta todos os botões da lista (entries)
    const allButtons = screen.getAllByRole('button')
    const itemButtons = allButtons.filter((el) =>
      el.textContent?.match(/GEN-(Hemi|Flat)-D/),
    )
    expect(itemButtons.length).toBeGreaterThanOrEqual(2)
    // Item com nome GEN-Flat-D1.5 deve ter span com bg-primary
    const itemSelected = itemButtons.find((el) =>
      el.textContent?.includes('GEN-Flat-D1.5'),
    )
    expect(itemSelected).toBeDefined()
    expect(itemSelected!.querySelector('.bg-primary')).toBeTruthy()
  })

  it('botão X (clear) só aparece quando selectedId está setado', async () => {
    // Sem selectedId: botão X não deve estar no popover
    const sutA = setup({ selectedId: null })
    await sutA.user.click(screen.getByRole('combobox'))
    await waitFor(() => screen.getByPlaceholderText(/Buscar por nome/i))
    expect(screen.queryByLabelText(/Desvincular boia/i)).toBeNull()
  })

  it('botão X chama onClear e fecha o popover quando clicado', async () => {
    const { user, onClear } = setup({ selectedId: 1 })
    await user.click(screen.getByRole('combobox'))
    await waitFor(() => screen.getByPlaceholderText(/Buscar por nome/i))
    const clearBtn = screen.getByLabelText(/Desvincular boia/i)
    await user.click(clearBtn)
    expect(onClear).toHaveBeenCalledTimes(1)
    // Popover fechou: search input não deve mais estar visível
    await waitFor(() =>
      expect(screen.queryByPlaceholderText(/Buscar por nome/i)).toBeNull(),
    )
  })
})
