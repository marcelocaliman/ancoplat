/**
 * LineSummaryPanel — agregados da composição da linha (Fase 3 / A1.5).
 *
 * Exibe sumário compacto com 4 campos no topo da aba Linha:
 *   - Nº de segmentos
 *   - Comprimento total (Σ length)
 *   - Peso seco total (Σ dry_weight × length)
 *   - Peso molhado total (Σ w × length)
 *
 * Replica o sumário equivalente do QMoor 0.8.5. Decisão Q5 do
 * mini-plano: 4 campos do plano literal — minimal e suficiente. MBL_min
 * e EA_min cabem melhor no memorial técnico (Fase 5), painel agregado
 * fica leve.
 *
 * Compatível com 1, 3 ou 10 segmentos. Quando dry_weight é null em
 * algum segmento, soma fica null naquele componente (não estimamos —
 * preferimos transparência).
 */
import { fmtNumber } from '@/lib/utils'
import { useUnitsStore } from '@/store/units'
import { fmtForce, fmtForcePerM } from '@/lib/units'

export interface LineSummarySegment {
  length?: number
  w?: number
  dry_weight?: number | null
}

export interface LineSummaryPanelProps {
  segments: LineSummarySegment[]
  className?: string
}

/**
 * Computa os agregados da linha. Retorna `null` quando entrada vazia.
 * Para peso seco, retorna `dryTotal: null` se algum segmento tem
 * dry_weight indefinido (não conseguimos somar parcial).
 */
export function aggregateLineSummary(
  segments: LineSummarySegment[],
): {
  count: number
  lengthTotal: number
  wetTotal: number
  dryTotal: number | null
} {
  if (segments.length === 0) {
    return { count: 0, lengthTotal: 0, wetTotal: 0, dryTotal: null }
  }
  let lengthTotal = 0
  let wetTotal = 0
  let dryTotal: number | null = 0
  for (const seg of segments) {
    const L = seg.length ?? 0
    const w = seg.w ?? 0
    lengthTotal += L
    wetTotal += w * L
    if (dryTotal !== null) {
      const d = seg.dry_weight
      if (d == null) {
        dryTotal = null
      } else {
        dryTotal += d * L
      }
    }
  }
  return { count: segments.length, lengthTotal, wetTotal, dryTotal }
}

export function LineSummaryPanel({ segments, className }: LineSummaryPanelProps) {
  const system = useUnitsStore((s) => s.system)
  const agg = aggregateLineSummary(segments)

  return (
    <div
      className={
        'flex flex-wrap items-baseline gap-x-6 gap-y-1 rounded-md border border-border/40 bg-muted/20 px-3 py-1.5 text-[11px] tabular-nums ' +
        (className ?? '')
      }
    >
      <SummaryItem label="Segmentos" value={String(agg.count)} />
      <SummaryItem
        label="Comprimento total"
        value={`${fmtNumber(agg.lengthTotal, 2)} m`}
      />
      <SummaryItem
        label="Peso molhado"
        value={fmtForce(agg.wetTotal, system)}
        secondary={`(Σ w·L; w em ${fmtForcePerM(0, system).split(' ').pop() ?? 'N/m'})`}
      />
      <SummaryItem
        label="Peso seco"
        value={
          agg.dryTotal == null
            ? '—'
            : fmtForce(agg.dryTotal, system)
        }
        secondary={agg.dryTotal == null ? 'sem dry_weight em algum seg' : ''}
      />
    </div>
  )
}

function SummaryItem({
  label,
  value,
  secondary,
}: {
  label: string
  value: string
  secondary?: string
}) {
  return (
    <div className="flex items-baseline gap-1">
      <span className="text-[10px] uppercase tracking-[0.05em] text-muted-foreground">
        {label}:
      </span>
      <span className="font-mono font-semibold">{value}</span>
      {secondary && (
        <span className="text-[9px] font-normal text-muted-foreground">
          {secondary}
        </span>
      )}
    </div>
  )
}
