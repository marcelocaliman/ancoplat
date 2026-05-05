/**
 * Smoke test do OnboardingTour (Fase 9 / Q1+Q10).
 *
 * Verifica:
 *  - Tour aparece na primeira visita (localStorage vazio).
 *  - Tour NÃO aparece quando localStorage tem `ancoplat:onboarding-completed=1`.
 *  - Skip persistente funciona após fechar.
 *  - resetOnboardingTour() limpa a flag.
 *  - Navegação Próximo/Anterior funciona.
 *  - Conclusão grava a flag.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import {
  ONBOARDING_STORAGE_KEY,
  OnboardingTour,
  isOnboardingCompleted,
  resetOnboardingTour,
} from '@/components/common/OnboardingTour'

function renderTour(props: { forceShow?: boolean } = {}) {
  return render(
    <MemoryRouter>
      <OnboardingTour {...props} />
    </MemoryRouter>,
  )
}

beforeEach(() => {
  localStorage.clear()
})
afterEach(() => {
  vi.restoreAllMocks()
})

describe('OnboardingTour (Fase 9 / Q1+Q10)', () => {
  it('aparece na primeira visita (localStorage vazio)', () => {
    renderTour()
    expect(screen.getByText('Bem-vindo ao AncoPlat')).toBeTruthy()
  })

  it('NÃO aparece quando flag de completed existe', () => {
    localStorage.setItem(ONBOARDING_STORAGE_KEY, '1')
    renderTour()
    expect(screen.queryByText('Bem-vindo ao AncoPlat')).toBeNull()
  })

  it('forceShow=true ignora a flag (botão Refazer tour)', () => {
    localStorage.setItem(ONBOARDING_STORAGE_KEY, '1')
    renderTour({ forceShow: true })
    expect(screen.getByText('Bem-vindo ao AncoPlat')).toBeTruthy()
  })

  it('Próximo avança step e Anterior retrocede', () => {
    renderTour()
    expect(screen.getByText('Bem-vindo ao AncoPlat')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: /Próxima etapa/i }))
    expect(screen.getByText('Samples canônicos')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: /Etapa anterior/i }))
    expect(screen.getByText('Bem-vindo ao AncoPlat')).toBeTruthy()
  })

  it('botão de pular grava a flag', () => {
    renderTour()
    fireEvent.click(screen.getByLabelText(/Pular tour de boas-vindas/i))
    expect(isOnboardingCompleted()).toBe(true)
  })

  it('resetOnboardingTour() limpa a flag', () => {
    localStorage.setItem(ONBOARDING_STORAGE_KEY, '1')
    expect(isOnboardingCompleted()).toBe(true)
    resetOnboardingTour()
    expect(isOnboardingCompleted()).toBe(false)
  })

  it('Concluir no último step grava a flag', () => {
    renderTour()
    // 5 etapas: clica "Próximo" 4× para chegar na última, depois "Concluir"
    for (let i = 0; i < 4; i += 1) {
      fireEvent.click(screen.getByRole('button', { name: /Próxima etapa/i }))
    }
    fireEvent.click(screen.getByRole('button', { name: /Concluir tour/i }))
    expect(isOnboardingCompleted()).toBe(true)
  })

  it('progresso visual mostra 5 dots', () => {
    renderTour()
    // Dots têm aria-hidden, contamos via DOM
    const dots = document.querySelectorAll('.h-1\\.5.w-6')
    expect(dots.length).toBe(5)
  })
})
