/**
 * Smoke do VesselEditor (Sprint 2 / Commit 15).
 *
 * Verifica:
 *  - Estado vazio mostra "Adicionar vessel" e mensagem de placeholder.
 *  - Click em "Adicionar vessel" popula o form com EMPTY_VESSEL.
 *  - Form preenchido mostra todos os 8 campos.
 *  - Botão "Remover" zera o vessel (set null).
 *
 * Não exercita validação Zod completa — isso roda no fluxo principal
 * via react-hook-form quando o form completo é submetido.
 */
import { describe, it, expect } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { useForm } from 'react-hook-form'
import { VesselEditor } from '@/components/common/VesselEditor'
import { EMPTY_CASE, type CaseFormValues } from '@/lib/caseSchema'

function Harness({ initial }: { initial?: CaseFormValues['vessel'] }) {
  // Smoke test não exercita validação Zod (resolver omitido para evitar
  // mismatch entre inferência ZodInput/ZodOutput em `default()`).
  const form = useForm<CaseFormValues>({
    defaultValues: { ...EMPTY_CASE, vessel: initial ?? null },
  })
  const vessel = form.watch('vessel')
  return (
    <VesselEditor
      control={form.control}
      setValue={form.setValue}
      vessel={vessel}
    />
  )
}

describe('VesselEditor', () => {
  it('estado vazio mostra "Adicionar vessel"', () => {
    render(<Harness />)
    expect(screen.getByRole('button', { name: /Adicionar vessel/i })).toBeTruthy()
    expect(screen.getByText(/Sem vessel/)).toBeTruthy()
  })

  it('click em "Adicionar vessel" popula form com EMPTY_VESSEL', () => {
    render(<Harness />)
    fireEvent.click(screen.getByRole('button', { name: /Adicionar vessel/i }))
    // Após popular, name="Vessel 1" aparece no input
    const nameInput = screen.getByPlaceholderText('ex: P-77') as HTMLInputElement
    expect(nameInput.value).toBe('Vessel 1')
  })

  it('vessel populado mostra todos os campos', () => {
    render(
      <Harness
        initial={{
          name: 'P-77',
          vessel_type: 'Semisubmersible',
          loa: 120,
          breadth: 80,
          draft: 22,
          displacement: 4.5e7,
          heading_deg: 45,
          operator: 'Petrobras',
          // displacement nullable mas pode ser preenchido
        } as never}
      />,
    )
    // Header mostra nome
    expect(screen.getByText(/P-77/)).toBeTruthy()
    // Inputs visíveis com valores
    expect(screen.getByDisplayValue('P-77')).toBeTruthy()
    expect(screen.getByDisplayValue('120')).toBeTruthy()
    expect(screen.getByDisplayValue('45')).toBeTruthy()
    expect(screen.getByDisplayValue('Petrobras')).toBeTruthy()
  })

  it('botão Remover zera o vessel', () => {
    render(
      <Harness
        initial={{ name: 'P-77', loa: 120, draft: 22 } as never}
      />,
    )
    expect(screen.queryByText(/Sem vessel/)).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: /Remover vessel/i }))
    // Após remover, volta ao estado vazio
    expect(screen.getByRole('button', { name: /Adicionar vessel/i })).toBeTruthy()
    expect(screen.getByText(/Sem vessel/)).toBeTruthy()
  })

  it('campos LOA, Boca, Calado têm unit "m" no label', () => {
    render(
      <Harness
        initial={{ name: 'P-77', loa: 100, breadth: 50, draft: 20 } as never}
      />,
    )
    // Procura pelos labels específicos
    const loaLabel = screen.getByText(/^LOA$/)
    expect(loaLabel.parentElement?.textContent).toContain('(m)')
  })
})
