/**
 * F5.7.4 — Card de diagnósticos do solver com sugestões de correção.
 *
 * Renderiza erros/avisos do solver em formato estruturado, com botão
 * "Aplicar" que despacha uma callback com (field, value) para o parent
 * atualizar o formulário automaticamente.
 *
 * Padrão de mensagem (Nível 0 da auditoria UX):
 *   [Severidade] Título
 *   Causa: explicação física/matemática
 *   Sugestão: como corrigir
 *   [Aplicar X] (botão que altera o form)
 */
import { AlertTriangle, Lightbulb, XOctagon } from 'lucide-react'

import type { SolverResult } from '@/api/types'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

export interface SolverDiagnostic {
  code: string
  severity: 'error' | 'warning'
  title: string
  cause: string
  suggestion: string
  suggested_changes: Array<{
    field: string
    value: number
    label: string
  }>
}

export interface SolverDiagnosticsCardProps {
  /** Resultado do solver com `diagnostics` populado. */
  result: SolverResult | null | undefined
  /**
   * Callback quando o usuário clica "Aplicar" numa sugestão. Recebe o
   * `field` (caminho dotted tipo 'attachments[0].submerged_force') e
   * o novo `value` (em SI). O parent é responsável por chamar
   * react-hook-form `setValue(field, value)` e disparar recálculo.
   */
  onApplyChange?: (field: string, value: number) => void
  /** Esconder o card quando não houver diagnósticos. Default true. */
  hideWhenEmpty?: boolean
}

/**
 * Card que exibe diagnósticos do solver com botões de correção.
 */
export function SolverDiagnosticsCard({
  result,
  onApplyChange,
  hideWhenEmpty = true,
}: SolverDiagnosticsCardProps) {
  const diagnostics =
    (result as unknown as { diagnostics?: SolverDiagnostic[] })?.diagnostics ?? []

  if (diagnostics.length === 0) {
    if (hideWhenEmpty) return null
    return null
  }

  return (
    <div className="space-y-2">
      {diagnostics.map((diag, i) => (
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
  const isError = diagnostic.severity === 'error'
  const Icon = isError ? XOctagon : AlertTriangle

  return (
    <div
      className={cn(
        'rounded-md border p-3 text-sm',
        isError
          ? 'border-destructive/50 bg-destructive/10 text-destructive-foreground'
          : 'border-amber-500/50 bg-amber-500/10 text-amber-100',
      )}
    >
      <div className="flex items-start gap-2">
        <Icon
          className={cn(
            'mt-0.5 size-4 shrink-0',
            isError ? 'text-destructive' : 'text-amber-500',
          )}
        />
        <div className="flex-1 space-y-1.5">
          <div className="flex items-baseline gap-2">
            <span
              className={cn(
                'font-semibold',
                isError ? 'text-destructive' : 'text-amber-200',
              )}
            >
              {isError ? 'ERRO' : 'AVISO'}:
            </span>
            <span className="font-medium">{diagnostic.title}</span>
            <span className="ml-auto text-[10px] uppercase tracking-wide opacity-50">
              {diagnostic.code}
            </span>
          </div>
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
                  className={cn(
                    'h-7 gap-1.5 text-xs',
                    isError
                      ? 'border-destructive/50 hover:bg-destructive/20'
                      : 'border-amber-500/50 hover:bg-amber-500/20',
                  )}
                  onClick={() => onApplyChange(change.field, change.value)}
                >
                  <Lightbulb className="size-3" />
                  {change.label}
                </Button>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
