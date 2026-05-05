/**
 * Smoke do print stylesheet (Fase 9 / Q7).
 *
 * Verifica:
 *  - CaseDetailPage marca o wrapper raiz com class `print-area`
 *    (regression test contra remoção acidental).
 *
 * Validação do CSS em si (regras @media print, @page A4, etc.) fica
 * pendente para v1.1+ — não automatizável sem Puppeteer/Playwright.
 * vitest tem `css: false` no config para evitar processar CSS no
 * runtime de teste, então grepar regex de CSS em runtime não é
 * viável aqui sem mexer no config global.
 *
 * O CSS está em `src/index.css` na seção marcada "F9 / Q7 — Print
 * stylesheet A4 portrait". Validar visualmente: DevTools → Print preview.
 */
import { describe, expect, it } from 'vitest'
// `?raw` carrega o source como string em build time; vitest com
// plugin react já transforma .tsx, então essa import funciona aqui.
// O CSS NÃO funciona com ?raw quando `css: false` está no config —
// por isso o smoke do CSS foi movido para validação manual em DevTools.
import pageSource from '../pages/CaseDetailPage.tsx?raw'

const page: string = pageSource

describe('Print stylesheet (Fase 9 / Q7)', () => {
  it('CaseDetailPage usa class `print-area` no wrapper', () => {
    expect(page).toMatch(/className=["'][^"']*print-area/)
  })

  it('CaseDetailPage tem comentário de referência F9 / Q7', () => {
    // Garante que ninguém remove a marca print-area por acidente
    // sem entender o contexto.
    expect(page).toMatch(/print-area.*ativa.*stylesheet|F9 \/ Q7/)
  })
})
