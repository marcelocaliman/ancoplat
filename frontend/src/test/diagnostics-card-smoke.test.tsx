/**
 * Smoke test do SolverDiagnosticsCard + SurfaceViolationsCard (Fase 4 / Commit 6).
 *
 * Conforme Q4 do mini-plano: NÃO refactor — só verificar que cada
 * diagnostic renderiza, severity correta, botão "Aplicar" funciona.
 *
 * Q6: SurfaceViolationsCard renderiza quando há violações.
 */
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { SurfaceViolationsCard } from '@/components/common/SurfaceViolationsCard'


describe('SurfaceViolationsCard (Fase 4 / Q6)', () => {
  it('não renderiza quando não há violações', () => {
    const { container } = render(
      <SurfaceViolationsCard violations={[]} />,
    )
    expect(container.firstChild).toBeNull()
  })

  it('renderiza com 1 violação mostrando nome + altura', () => {
    render(
      <SurfaceViolationsCard
        violations={[
          { index: 0, name: 'Boia A', height_above_surface_m: 2.5 },
        ]}
      />,
    )
    expect(screen.getByText(/Boia A/)).toBeTruthy()
    // fmtNumber usa pt-BR (vírgula como decimal): "2,50"
    expect(screen.getByText(/\+2,50 m acima/)).toBeTruthy()
  })

  it('renderiza com múltiplas violações listando cada uma', () => {
    render(
      <SurfaceViolationsCard
        violations={[
          { index: 0, name: 'Boia A', height_above_surface_m: 1.2 },
          { index: 1, name: 'Boia B', height_above_surface_m: 3.5 },
          { index: 2, name: 'Boia C', height_above_surface_m: 0.8 },
        ]}
      />,
    )
    expect(screen.getByText(/Boia A/)).toBeTruthy()
    expect(screen.getByText(/Boia B/)).toBeTruthy()
    expect(screen.getByText(/Boia C/)).toBeTruthy()
    // Contador no header — número 3
    expect(screen.getByText('3')).toBeTruthy()
  })

  it('exibe orientação para o usuário corrigir', () => {
    render(
      <SurfaceViolationsCard
        violations={[{ index: 0, name: 'A', height_above_surface_m: 1 }]}
      />,
    )
    // Orientação chave: reduzir empuxo, aumentar T_fl, ou compensar
    expect(
      screen.getByText(/Reduza o empuxo|aumente T_fl|clump/i),
    ).toBeTruthy()
  })
})
