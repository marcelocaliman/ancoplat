/**
 * Smoke do AHVInstallEditor (Sprint 2 / Commit 26).
 */
import { describe, it, expect } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { useForm } from 'react-hook-form'
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
  return (
    <AHVInstallEditor
      control={form.control}
      setValue={form.setValue}
      ahvInstall={ahv}
    />
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
})
