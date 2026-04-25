/**
 * F5.7.6 — Validation Log Card.
 *
 * Mostra a diferença entre o ÚLTIMO estado válido e o estado atual
 * inválido. Quando o engenheiro mexe em um valor que quebra o caso,
 * o log mostra o que mudou — facilitando o "rollback mental".
 *
 * Renderiza só quando há um lastValid armazenado E o estado atual
 * é inválido (status != CONVERGED ou tem diagnostics critical/error).
 */
import { History, Undo2 } from 'lucide-react'

import { Button } from '@/components/ui/button'
import type { CaseFormValues } from '@/lib/caseSchema'

export interface FieldDiff {
  /** Caminho dotted do campo. */
  field: string
  /** Rótulo humano. */
  label: string
  /** Valor anterior (válido). */
  prev: number | string | undefined
  /** Valor atual (inválido). */
  curr: number | string | undefined
  /** Função pra formatar valor pra exibição. */
  format?: (v: number | string | undefined) => string
}

export interface ValidationLogCardProps {
  /** Valores do form atual. */
  current: CaseFormValues
  /** Valores do form quando o solver convergiu pela última vez. */
  lastValid: CaseFormValues | null
  /** Callback de revert: o parent reseta o form pros valores válidos. */
  onRevert?: () => void
}

/**
 * Computa diffs entre os campos numéricos relevantes do form.
 */
function computeDiffs(
  current: CaseFormValues,
  lastValid: CaseFormValues,
): FieldDiff[] {
  const diffs: FieldDiff[] = []

  // Boundary
  const cBound = current.boundary
  const vBound = lastValid.boundary
  if (cBound && vBound) {
    if (cBound.h !== vBound.h) {
      diffs.push({
        field: 'boundary.h',
        label: 'Lâmina d\'água (h)',
        prev: vBound.h,
        curr: cBound.h,
        format: (v) => `${(v as number).toFixed(0)} m`,
      })
    }
    if (cBound.input_value !== vBound.input_value) {
      diffs.push({
        field: 'boundary.input_value',
        label:
          cBound.mode === 'Tension' ? 'T_fl (input)' : 'X total (input)',
        prev: vBound.input_value,
        curr: cBound.input_value,
        format: (v) =>
          cBound.mode === 'Tension'
            ? `${((v as number) / 1000).toFixed(1)} kN`
            : `${(v as number).toFixed(0)} m`,
      })
    }
    if (cBound.mode !== vBound.mode) {
      diffs.push({
        field: 'boundary.mode',
        label: 'Modo',
        prev: vBound.mode,
        curr: cBound.mode,
      })
    }
  }

  // Segments
  const minSegs = Math.min(
    current.segments?.length ?? 0,
    lastValid.segments?.length ?? 0,
  )
  for (let i = 0; i < minSegs; i += 1) {
    const cs = current.segments![i]!
    const vs = lastValid.segments![i]!
    if (cs.length !== vs.length) {
      diffs.push({
        field: `segments[${i}].length`,
        label: `Seg ${i + 1} comprimento`,
        prev: vs.length,
        curr: cs.length,
        format: (v) => `${(v as number).toFixed(0)} m`,
      })
    }
    if (cs.w !== vs.w) {
      diffs.push({
        field: `segments[${i}].w`,
        label: `Seg ${i + 1} peso submerso`,
        prev: vs.w,
        curr: cs.w,
        format: (v) => `${(v as number).toFixed(1)} N/m`,
      })
    }
    if (cs.MBL !== vs.MBL) {
      diffs.push({
        field: `segments[${i}].MBL`,
        label: `Seg ${i + 1} MBL`,
        prev: vs.MBL,
        curr: cs.MBL,
        format: (v) => `${((v as number) / 1000).toFixed(0)} kN`,
      })
    }
  }
  // Mudança no número de segmentos
  if (
    (current.segments?.length ?? 0) !== (lastValid.segments?.length ?? 0)
  ) {
    diffs.push({
      field: 'segments.length',
      label: '# de segmentos',
      prev: lastValid.segments?.length,
      curr: current.segments?.length,
    })
  }

  // Attachments
  const minAtts = Math.min(
    current.attachments?.length ?? 0,
    lastValid.attachments?.length ?? 0,
  )
  for (let i = 0; i < minAtts; i += 1) {
    const ca = current.attachments![i]!
    const va = lastValid.attachments![i]!
    if (ca.submerged_force !== va.submerged_force) {
      diffs.push({
        field: `attachments[${i}].submerged_force`,
        label: `${ca.kind === 'buoy' ? 'Boia' : 'Clump'} ${ca.name ?? `#${i + 1}`} - força`,
        prev: va.submerged_force,
        curr: ca.submerged_force,
        format: (v) => `${((v as number) / 9806.65).toFixed(2)} te`,
      })
    }
    if (ca.position_s_from_anchor !== va.position_s_from_anchor) {
      diffs.push({
        field: `attachments[${i}].position_s_from_anchor`,
        label: `${ca.kind === 'buoy' ? 'Boia' : 'Clump'} ${ca.name ?? `#${i + 1}`} - posição`,
        prev: va.position_s_from_anchor ?? '-',
        curr: ca.position_s_from_anchor ?? '-',
        format: (v) => (typeof v === 'number' ? `${v.toFixed(0)} m` : '—'),
      })
    }
  }
  if (
    (current.attachments?.length ?? 0) !==
    (lastValid.attachments?.length ?? 0)
  ) {
    diffs.push({
      field: 'attachments.length',
      label: '# de attachments',
      prev: lastValid.attachments?.length,
      curr: current.attachments?.length,
    })
  }

  return diffs
}

export function ValidationLogCard({
  current,
  lastValid,
  onRevert,
}: ValidationLogCardProps) {
  if (!lastValid) return null
  const diffs = computeDiffs(current, lastValid)
  if (diffs.length === 0) return null

  return (
    <div className="rounded-md border border-violet-500/40 bg-violet-900/15 p-3 text-sm">
      <div className="flex items-start gap-2">
        <History className="mt-0.5 size-4 shrink-0 text-violet-400" />
        <div className="flex-1 space-y-2">
          <div className="flex items-baseline gap-2">
            <span className="rounded bg-violet-700 px-1.5 py-0.5 text-[10px] font-bold tracking-wide text-white">
              MUDANÇAS
            </span>
            <span className="font-medium text-foreground">
              Diferenças desde a última configuração válida
            </span>
            <span className="ml-auto text-[10px] uppercase tracking-wide opacity-50">
              {diffs.length} alteraç{diffs.length === 1 ? 'ão' : 'ões'}
            </span>
          </div>
          <div className="space-y-1">
            {diffs.slice(0, 5).map((d) => (
              <div
                key={d.field}
                className="flex items-center justify-between gap-2 rounded bg-background/40 px-2 py-1 text-xs"
              >
                <span className="text-foreground/80">{d.label}</span>
                <span className="font-mono text-[11px]">
                  <span className="text-muted-foreground line-through opacity-60">
                    {d.format ? d.format(d.prev) : String(d.prev ?? '—')}
                  </span>
                  <span className="mx-1.5 opacity-40">→</span>
                  <span className="text-foreground">
                    {d.format ? d.format(d.curr) : String(d.curr ?? '—')}
                  </span>
                </span>
              </div>
            ))}
            {diffs.length > 5 && (
              <p className="px-2 text-[10px] text-muted-foreground">
                + {diffs.length - 5} outra{diffs.length - 5 === 1 ? '' : 's'}{' '}
                mudança{diffs.length - 5 === 1 ? '' : 's'}…
              </p>
            )}
          </div>
          {onRevert && (
            <Button
              size="sm"
              variant="outline"
              onClick={onRevert}
              className="h-7 gap-1.5 border-violet-500/50 text-xs hover:bg-violet-600/20"
            >
              <Undo2 className="size-3" />
              Reverter para última válida
            </Button>
          )}
        </div>
      </div>
    </div>
  )
}
