/**
 * F5.7.6 — Indicadores visuais field-level de validação.
 *
 * Componentes:
 *   - `FieldValidationDot`: ponto colorido (vermelho/âmbar/sky) ao lado
 *      de um label de campo, indicando que aquele campo está envolvido
 *      em algum diagnostic atual.
 *   - `TabValidationCounter`: badge numérico colorido pra abas que têm
 *      diagnostics envolvendo seus campos (ex: "Boias ⚠ 2").
 *
 * Ambos consomem o `DiagnosticsContext` que carrega o set de fields
 * afetados + a severidade pior por field.
 */
import { createContext, useContext, useMemo } from 'react'

import type {
  DiagnosticSeverity,
  PreSolveDiagnostic,
} from '@/lib/preSolveDiagnostics'
import { buildAffectedFieldsSet } from '@/lib/preSolveDiagnostics'
import { cn } from '@/lib/utils'

import type { SolverDiagnostic } from './SolverDiagnosticsCard'

// =============================================================================
// Context
// =============================================================================

interface DiagnosticsContextValue {
  fields: Set<string>
  fieldSeverity: Map<string, DiagnosticSeverity>
}

const DiagnosticsContext = createContext<DiagnosticsContextValue>({
  fields: new Set(),
  fieldSeverity: new Map(),
})

/** Provider — o parent (form page) usa pra disponibilizar diagnostics. */
export function DiagnosticsProvider({
  diagnostics,
  children,
}: {
  diagnostics: Array<SolverDiagnostic | PreSolveDiagnostic>
  children: React.ReactNode
}) {
  const value = useMemo(
    () => buildAffectedFieldsSet(diagnostics),
    [diagnostics],
  )
  return (
    <DiagnosticsContext.Provider value={value}>
      {children}
    </DiagnosticsContext.Provider>
  )
}

export function useDiagnostics() {
  return useContext(DiagnosticsContext)
}

// =============================================================================
// FieldValidationDot
// =============================================================================

const SEVERITY_DOT: Record<DiagnosticSeverity, string> = {
  critical: 'bg-red-600',
  error: 'bg-red-500',
  warning: 'bg-amber-500',
  info: 'bg-sky-500',
}

/**
 * Pontinho colorido pra colocar ao lado de um label de field.
 * Renderiza só quando o field tem diagnostic ativo.
 */
export function FieldValidationDot({
  field,
  className,
}: {
  field: string
  className?: string
}) {
  const { fieldSeverity } = useDiagnostics()
  const sev = fieldSeverity.get(field)
  if (!sev) return null
  return (
    <span
      title={`Campo afetado por diagnóstico (${sev})`}
      className={cn(
        'ml-1 inline-block size-2 shrink-0 rounded-full',
        SEVERITY_DOT[sev],
        className,
      )}
    />
  )
}

// =============================================================================
// TabValidationCounter
// =============================================================================

const SEVERITY_BADGE: Record<DiagnosticSeverity, string> = {
  critical: 'bg-red-600 text-white',
  error: 'bg-red-500 text-white',
  warning: 'bg-amber-500 text-white',
  info: 'bg-sky-500 text-white',
}

/**
 * Conta diagnostics cujo `affected_fields` matchea um prefixo dado
 * (e.g., "attachments[" pra todos os attachments). Renderiza badge
 * colorido com a contagem se > 0.
 */
export function TabValidationCounter({
  prefix,
  className,
}: {
  prefix: string
  className?: string
}) {
  const { fields, fieldSeverity } = useDiagnostics()
  let count = 0
  let worstSev: DiagnosticSeverity | null = null
  const order: Record<DiagnosticSeverity, number> = {
    critical: 4,
    error: 3,
    warning: 2,
    info: 1,
  }
  // Conta CADA field afetado que combina com o prefix, e captura
  // a severidade mais grave do conjunto.
  fields.forEach((field) => {
    if (field.startsWith(prefix)) {
      count += 1
      const sev = fieldSeverity.get(field)
      if (sev && (!worstSev || order[sev] > order[worstSev])) {
        worstSev = sev
      }
    }
  })
  if (count === 0 || !worstSev) return null
  return (
    <span
      className={cn(
        'ml-1.5 inline-flex h-4 min-w-4 items-center justify-center rounded-full px-1 text-[10px] font-semibold leading-none',
        SEVERITY_BADGE[worstSev],
        className,
      )}
    >
      {count}
    </span>
  )
}
