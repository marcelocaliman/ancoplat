/**
 * F5.7.4 + F5.7.6 — Card de diagnósticos do solver com sugestões de
 * correção. Suporta 4 níveis de severidade com tratamento visual
 * consistente em toda a UI:
 *
 *   critical: caso não pode ser computado (sem geometria)
 *   error:    geometria existe mas viola física (boia voadora)
 *   warning:  geometria válida mas ill-conditioned (uplift alto)
 *   info:     observação útil (margem de segurança apertada)
 *
 * Cada diagnóstico pode listar `affected_fields` que a UI usa pra
 * destacar campos do form (FieldValidationDot) e contar issues por
 * tab (TabValidationCounter).
 */
import { AlertTriangle, ChevronDown, ChevronRight, Info, Lightbulb, XOctagon } from 'lucide-react'
import { useState } from 'react'

import type { SolverResult } from '@/api/types'
import type { DiagnosticSeverity } from '@/lib/preSolveDiagnostics'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

export interface SolverDiagnostic {
  code: string
  severity: DiagnosticSeverity
  title: string
  cause: string
  suggestion: string
  suggested_changes: Array<{
    field: string
    value: number
    label: string
  }>
  affected_fields: string[]
}

export interface SolverDiagnosticsCardProps {
  /** Resultado do solver com `diagnostics` populado. */
  result?: SolverResult | null
  /**
   * Diagnósticos extras (e.g., pre-solve do frontend) pra concatenar
   * com os do result. Útil quando a UI roda checagens locais antes
   * de chamar o backend.
   */
  extraDiagnostics?: SolverDiagnostic[]
  /**
   * Callback quando o usuário clica "Aplicar" numa sugestão. Recebe o
   * `field` (caminho dotted) e o novo `value` (em SI). O parent chama
   * react-hook-form `setValue(field, value)`.
   */
  onApplyChange?: (field: string, value: number) => void
  /** Esconder o card quando não houver diagnósticos. Default true. */
  hideWhenEmpty?: boolean
  /** Classe extra no container externo. */
  className?: string
}

/** Cores e ícones consistentes por severidade. */
export const SEVERITY_STYLES: Record<
  DiagnosticSeverity,
  {
    label: string
    Icon: typeof AlertTriangle
    container: string
    icon: string
    badge: string
    badgeText: string
    button: string
  }
> = {
  critical: {
    label: 'CRÍTICO',
    Icon: XOctagon,
    container: 'border-red-600/60 bg-red-900/30',
    icon: 'text-red-500',
    badge: 'bg-red-700 text-white',
    badgeText: 'text-red-400',
    button: 'border-red-500/60 hover:bg-red-700/30',
  },
  error: {
    label: 'ERRO',
    Icon: XOctagon,
    container: 'border-red-500/50 bg-red-900/20',
    icon: 'text-red-400',
    badge: 'bg-red-600 text-white',
    badgeText: 'text-red-300',
    button: 'border-red-500/50 hover:bg-red-600/20',
  },
  warning: {
    label: 'AVISO',
    Icon: AlertTriangle,
    container: 'border-amber-500/50 bg-amber-900/15',
    icon: 'text-amber-400',
    badge: 'bg-amber-600 text-white',
    badgeText: 'text-amber-300',
    button: 'border-amber-500/50 hover:bg-amber-600/20',
  },
  info: {
    label: 'INFO',
    Icon: Info,
    container: 'border-sky-500/50 bg-sky-900/15',
    icon: 'text-sky-400',
    badge: 'bg-sky-600 text-white',
    badgeText: 'text-sky-300',
    button: 'border-sky-500/50 hover:bg-sky-600/20',
  },
}

/**
 * Card que exibe diagnósticos do solver com botões de correção.
 */
export function SolverDiagnosticsCard({
  result,
  extraDiagnostics,
  onApplyChange,
  hideWhenEmpty = true,
  className,
}: SolverDiagnosticsCardProps) {
  const fromResult =
    (result as unknown as { diagnostics?: SolverDiagnostic[] })?.diagnostics ?? []
  const all: SolverDiagnostic[] = [...(extraDiagnostics ?? []), ...fromResult]

  if (all.length === 0 && hideWhenEmpty) return null
  if (all.length === 0) return null

  // Ordena por severidade (mais grave primeiro)
  const order: Record<DiagnosticSeverity, number> = {
    critical: 0,
    error: 1,
    warning: 2,
    info: 3,
  }
  const sorted = [...all].sort((a, b) => order[a.severity] - order[b.severity])

  return (
    <div className={cn('space-y-2', className)}>
      {sorted.map((diag, i) => (
        <DiagnosticItem
          key={`${diag.code}-${i}`}
          diagnostic={diag}
          onApplyChange={onApplyChange}
        />
      ))}
    </div>
  )
}

function DiagnosticItem({
  diagnostic,
  onApplyChange,
}: {
  diagnostic: SolverDiagnostic
  onApplyChange?: (field: string, value: number) => void
}) {
  const style = SEVERITY_STYLES[diagnostic.severity]
  const Icon = style.Icon
  // Default colapsado — usuário expande para ler causa + sugestão.
  // Critical/error sobem como expanded por padrão (engenheiro precisa
  // ver imediatamente; clicar pra fechar é OK).
  const defaultExpanded =
    diagnostic.severity === 'critical' || diagnostic.severity === 'error'
  const [expanded, setExpanded] = useState(defaultExpanded)

  return (
    <div className={cn('rounded-md border text-sm', style.container)}>
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        aria-expanded={expanded}
        className={cn(
          'flex w-full items-start gap-2 p-3 text-left transition-colors',
          'hover:bg-foreground/[0.02]',
        )}
      >
        {expanded ? (
          <ChevronDown className="mt-0.5 size-3.5 shrink-0 opacity-60" />
        ) : (
          <ChevronRight className="mt-0.5 size-3.5 shrink-0 opacity-60" />
        )}
        <Icon className={cn('mt-0.5 size-4 shrink-0', style.icon)} />
        <div className="flex flex-1 items-baseline gap-2">
          <span
            className={cn(
              'rounded px-1.5 py-0.5 text-[10px] font-bold tracking-wide',
              style.badge,
            )}
          >
            {style.label}
          </span>
          <span className="font-medium text-foreground">{diagnostic.title}</span>
          <span className="ml-auto text-[10px] uppercase tracking-wide opacity-50">
            {diagnostic.code}
          </span>
        </div>
      </button>
      {expanded && (
        <div className="space-y-1.5 px-3 pb-3 pl-9">
          <p className="text-xs leading-relaxed text-foreground/90">
            <span className="font-medium opacity-80">Causa:</span>{' '}
            {diagnostic.cause}
          </p>
          {diagnostic.suggestion && (
            <p className="flex items-start gap-1.5 text-xs leading-relaxed text-foreground/90">
              <Lightbulb className="mt-0.5 size-3 shrink-0 text-amber-500" />
              <span>
                <span className="font-medium opacity-80">Sugestão:</span>{' '}
                {diagnostic.suggestion}
              </span>
            </p>
          )}
          {diagnostic.suggested_changes.length > 0 && onApplyChange && (
            <div className="flex flex-wrap gap-2 pt-1">
              {diagnostic.suggested_changes.map((change, j) => (
                <Button
                  key={j}
                  size="sm"
                  variant="outline"
                  className={cn('h-7 gap-1.5 text-xs', style.button)}
                  onClick={() => onApplyChange(change.field, change.value)}
                >
                  <Lightbulb className="size-3" />
                  {change.label}
                </Button>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
