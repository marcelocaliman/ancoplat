/**
 * Smoke do AHVInstallEditor (Sprint 2 / Commit 26 + Sprint 4 / Commit 39).
 */
import { describe, it, expect } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { useForm } from 'react-hook-form'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AHVInstallEditor } from '@/components/common/AHVInstallEditor'
import { EMPTY_CASE, type CaseFormValues } from '@/lib/caseSchema'

function Harness({ initial }: { initial?: CaseFormValues['boundary']['ahv_install'] }) {
  const form = useForm<CaseFormValues>({
    defaultValues: {
      ...EMPTY_CASE,
      boundary: { ...EMPTY_CASE.boundary, ahv_install: initial ?? null },
    },
  })
  const ahv = form.watch('boundary.ahv_install')
  // QueryClient necessário pelo LineTypePicker do WorkWireSubcard.
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  })
  return (
    <QueryClientProvider client={qc}>
      <AHVInstallEditor
        control={form.control}
        setValue={form.setValue}
        ahvInstall={ahv}
      />
    </QueryClientProvider>
  )
}

describe('AHVInstallEditor', () => {
  it('estado vazio mostra "Adicionar AHV Install"', () => {
    render(<Harness />)
    expect(
      screen.getByRole('button', { name: /Adicionar AHV Install/i }),
    ).toBeTruthy()
    expect(screen.getByText(/Cenário AHV de instalação/i)).toBeTruthy()
  })

  it('click "Adicionar" popula com defaults', () => {
    render(<Harness />)
    fireEvent.click(
      screen.getByRole('button', { name: /Adicionar AHV Install/i }),
    )
    // Após popular, formulário aparece com 4 campos
    expect(screen.getByText('Bollard Pull *')).toBeTruthy()
    expect(screen.getByText(/Deck Level/i)).toBeTruthy()
    expect(screen.getByText('Stern Angle')).toBeTruthy()
    expect(screen.getByText(/Target X/i)).toBeTruthy()
  })

  it('estado preenchido mostra valores corretos', () => {
    render(
      <Harness
        initial={{
          bollard_pull: 1_470_000.0, // 150 te
          deck_level_above_swl: 5.0,
          stern_angle_deg: 12.0,
          target_horz_distance: 1828.8,
        }}
      />,
    )
    expect(screen.getByDisplayValue('5')).toBeTruthy() // deck_level
    expect(screen.getByDisplayValue('12')).toBeTruthy() // stern_angle
    expect(screen.getByDisplayValue('1828.8')).toBeTruthy()
  })

  it('botão Remover zera o ahv_install', () => {
    render(
      <Harness
        initial={{
          bollard_pull: 100_000,
          deck_level_above_swl: 0,
          stern_angle_deg: 0,
          target_horz_distance: null,
        }}
      />,
    )
    fireEvent.click(
      screen.getByRole('button', { name: /Remover AHV Install/i }),
    )
    expect(
      screen.getByRole('button', { name: /Adicionar AHV Install/i }),
    ).toBeTruthy()
  })

  // ────────────────────────────────────────────────────────────────
  // Sprint 4 / Commit 39 — WorkWireSubcard (Tier C)
  // ────────────────────────────────────────────────────────────────
  it('estado AHV exibe subcard Work Wire colapsado por default', () => {
    render(
      <Harness
        initial={{
          bollard_pull: 100_000,
          deck_level_above_swl: 0,
          stern_angle_deg: 0,
          target_horz_distance: 1500.0,
        }}
      />,
    )
    expect(screen.getByText(/Work Wire físico/i)).toBeTruthy()
    expect(screen.getByText(/clique para habilitar/i)).toBeTruthy()
  })

  it('expandir Work Wire e habilitar Tier C ativa o subcard', () => {
    render(
      <Harness
        initial={{
          bollard_pull: 100_000,
          deck_level_above_swl: 0,
          stern_angle_deg: 0,
          target_horz_distance: 1500.0,
        }}
      />,
    )
    // Click no botão para expandir
    fireEvent.click(screen.getByText(/Work Wire físico/i))
    // Botão "Ativar Tier C" deve aparecer
    const ativarBtn = screen.getByRole('button', { name: /Ativar Tier C/i })
    fireEvent.click(ativarBtn)
    // Após ativar, badge ATIVO aparece e campos físicos visíveis
    expect(screen.getByText('ATIVO')).toBeTruthy()
    expect(screen.getByText(/Modelo do cabo/i)).toBeTruthy()
    expect(screen.getByText('Comprimento')).toBeTruthy()
    expect(screen.getByText('EA')).toBeTruthy()
    expect(screen.getByText(/Peso submerso/i)).toBeTruthy()
    expect(screen.getByText('MBL')).toBeTruthy()
  })

  it('Work Wire habilitado mostra botão Desativar', () => {
    render(
      <Harness
        initial={{
          bollard_pull: 100_000,
          deck_level_above_swl: 0,
          stern_angle_deg: 0,
          target_horz_distance: 1500.0,
          work_wire: {
            length: 200,
            EA: 5.5e8,
            w: 170,
            MBL: 6.5e6,
            category: 'Wire',
            n_segs: 1,
            line_type_id: null,
            line_type: null,
            diameter: 0.076,
            dry_weight: null,
          },
        }}
      />,
    )
    // Badge ATIVO já visível
    expect(screen.getByText('ATIVO')).toBeTruthy()
    // Expande e verifica botão Desativar
    fireEvent.click(screen.getByText(/Work Wire físico/i))
    expect(screen.getByRole('button', { name: /Desativar Tier C/i })).toBeTruthy()
  })
})
