/**
 * Smoke tests do frontend AHV (Fase 8 / Commit 7).
 *
 * Verifica via leitura do source que:
 *  - AttachmentsEditor inclui "ahv" no Select kind.
 *  - AttachmentsEditor renderiza campos AHV (bollard_pull, heading)
 *    quando kind=ahv.
 *  - caseSchema valida AHV cross-fields.
 *  - Sample 'ahv-pull' destravado (sem requirePhase).
 *  - Verbetes glossário 'ahv' e 'bollard-pull' destravados.
 */
import { describe, expect, it } from 'vitest'
import schemaSource from '../lib/caseSchema.ts?raw'
import editorSource from '../components/common/AttachmentsEditor.tsx?raw'
import { CASE_TEMPLATES, getTemplate } from '@/lib/caseTemplates'
import { GLOSSARY, getGlossaryEntry } from '@/lib/glossary'

const schema: string = schemaSource
const editor: string = editorSource

describe('AHV frontend (Fase 8 / Commit 7)', () => {
  it('caseSchema aceita kind=ahv', () => {
    expect(schema).toMatch(/kind:.*z\.enum\(\[.*'ahv'.*\]\)/s)
  })

  it('caseSchema cross-validates ahv_bollard_pull e ahv_heading_deg', () => {
    expect(schema).toMatch(/ahv_bollard_pull/)
    expect(schema).toMatch(/ahv_heading_deg/)
    // Refines que verificam required quando kind=ahv (mensagens
    // explícitas no .refine())
    expect(schema).toMatch(/Bollard pull do AHV/i)
    expect(schema).toMatch(/Heading do AHV/i)
  })

  it('AttachmentsEditor inclui "AHV (Fase 8)" no Select de kind', () => {
    expect(editor).toMatch(/<SelectItem value="ahv"/)
    expect(editor).toMatch(/AHV.*Fase 8/)
  })

  it('AttachmentsEditor renderiza Bollard pull quando isAHV', () => {
    expect(editor).toMatch(/Bollard pull/)
    expect(editor).toMatch(/ahv_bollard_pull/)
  })

  it('AttachmentsEditor renderiza Heading com referencial em tooltip', () => {
    expect(editor).toMatch(/Heading.*°/)
    expect(editor).toMatch(/ahv_heading_deg/)
    // Tooltip com referencial X global anti-horário
    expect(editor).toMatch(/eixo X global/i)
  })
})

describe('Sample ahv-pull destravado pós-F8', () => {
  it('sample ahv-pull existe', () => {
    expect(getTemplate('ahv-pull')).toBeTruthy()
  })

  it('sample ahv-pull NÃO tem requirePhase (destravado)', () => {
    const tpl = getTemplate('ahv-pull')!
    expect(tpl.requirePhase).toBeUndefined()
  })

  it('sample ahv-pull carrega payload AHV completo', () => {
    const tpl = getTemplate('ahv-pull')!
    const ahv = (tpl.values.attachments ?? []).find(
      (a) => a.kind === 'ahv',
    )
    expect(ahv).toBeTruthy()
    expect(ahv!.ahv_bollard_pull).toBeTruthy()
    expect(ahv!.ahv_heading_deg).toBeDefined()
  })

  it('sample ahv-pull tem 2 segmentos (junção 0 viável)', () => {
    const tpl = getTemplate('ahv-pull')!
    expect(tpl.values.segments.length).toBe(2)
  })

  it('contagem de samples preview pós-F8: 0 (todos destravados)', () => {
    // Após F7 destravar anchor-uplift e F8 destravar ahv-pull,
    // não há mais samples preview no caseTemplates.
    const previews = CASE_TEMPLATES.filter((t) => t.requirePhase != null)
    expect(previews.length).toBe(0)
  })
})

describe('Verbetes glossário AHV destravados pós-F8', () => {
  it('verbete "ahv" existe e SEM requirePhase', () => {
    const ahv = getGlossaryEntry('ahv')
    expect(ahv).toBeTruthy()
    expect(ahv!.requirePhase).toBeUndefined()
  })

  it('verbete "bollard-pull" existe e SEM requirePhase', () => {
    const bp = getGlossaryEntry('bollard-pull')
    expect(bp).toBeTruthy()
    expect(bp!.requirePhase).toBeUndefined()
  })

  it('contagem de verbetes preview pós-F8: 0', () => {
    const previews = GLOSSARY.filter((g) => g.requirePhase != null)
    expect(previews.length).toBe(0)
  })

  it('verbete "ahv" cita mitigação D018 + Memorial PDF', () => {
    const ahv = getGlossaryEntry('ahv')!
    expect(ahv.definition).toMatch(/D018/)
    expect(ahv.definition).toMatch(/Memorial/)
  })
})
