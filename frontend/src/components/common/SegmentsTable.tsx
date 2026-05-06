import { ArrowLeft, ArrowRight, Plus, Settings2, Trash2 } from 'lucide-react'
import { useState } from 'react'
import {
  Controller,
  type Control,
  type Path,
  type UseFormRegister,
  type UseFormWatch,
  type UseFormSetValue,
  type UseFieldArrayReturn,
} from 'react-hook-form'
import { LineTypePicker } from '@/components/common/LineTypePicker'
import { SegmentAdvancedDialog } from '@/components/common/SegmentAdvancedDialog'
import { UnitInput } from '@/components/common/UnitInput'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import type { LineTypeOutput } from '@/api/types'
import type { CaseFormValues } from '@/lib/caseSchema'
import { cn, fmtNumber } from '@/lib/utils'
import { toast } from 'sonner'

// Tipos concretos para CaseFormValues — react-hook-form generics com
// ArrayPath não casam bem em todas as combinações de basePath, então
// fixamos para 'segments' do CaseFormValues. Para outros use cases
// (e.g. mooring system multi-line), criar variante dedicada.
type T = CaseFormValues

export interface SegmentsTableProps {
  control: Control<T>
  register: UseFormRegister<T>
  watch: UseFormWatch<T>
  setValue: UseFormSetValue<T>
  segmentsArray: UseFieldArrayReturn<T, 'segments'>
  basePath?: string
}

/**
 * Tabela de segmentos — layout tabular estilo QMoor:
 *   - linhas = propriedades (Catálogo, Comprimento, Diâmetro, Pesos)
 *   - colunas = segmentos individuais
 *
 * Ordem visual: fairlead (esquerda) → âncora (direita), espelhando
 * leitura do plot. Implementação via [...].slice().reverse() na
 * iteração; data array mantém ordem original (idx 0 = âncora,
 * idx N-1 = fairlead) para preservar semântica do solver.
 *
 * Configuração avançada (EA, MBL, Módulo, EA source, μ override,
 * Categoria) abre em modal — não expande inline para não empurrar
 * o gráfico abaixo.
 */
export function SegmentsTable({
  control,
  register,
  watch,
  setValue,
  segmentsArray,
  basePath = 'segments',
}: SegmentsTableProps) {
  const [advancedIdx, setAdvancedIdx] = useState<number | null>(null)
  // Helper para construir o path do form a partir do índice + nome do campo
  const p = <K extends string>(idx: number, name: K) =>
    `${basePath}[${idx}].${name}` as unknown as Path<T>

  // Lista de fields renderizados em ordem REVERSA (fairlead primeiro)
  const reversed = segmentsArray.fields
    .slice()
    .map((field, originalIdx) => ({ field, realIdx: originalIdx }))
    .reverse()

  const total = segmentsArray.fields.length

  const applyLineTypeToSegment = (
    realIdx: number,
    lt: LineTypeOutput | null,
  ): void => {
    if (!lt) {
      setValue(p(realIdx, 'line_type'), null as never, {
        shouldValidate: true,
        shouldDirty: true,
      })
      return
    }
    const eaSource =
      (watch(p(realIdx, 'ea_source')) as 'qmoor' | 'gmoor' | undefined) ??
      'qmoor'
    const ea = eaSource === 'gmoor' ? lt.gmoor_ea ?? lt.qmoor_ea : lt.qmoor_ea
    const updates: Array<[string, unknown]> = [
      ['line_type', lt.line_type],
      ['category', lt.category],
      ['diameter', lt.diameter],
      ['w', lt.wet_weight],
      ['dry_weight', lt.dry_weight],
      ['EA', ea],
      ['MBL', lt.break_strength],
      ['seabed_friction_cf', lt.seabed_friction_cf ?? null],
    ]
    if (lt.modulus != null) updates.push(['modulus', lt.modulus])
    for (const [k, v] of updates) {
      setValue(p(realIdx, k), v as never, {
        shouldValidate: true,
        shouldDirty: true,
      })
    }
    toast.success(`${lt.line_type} aplicado ao segmento ${realIdx + 1}`)
  }

  const positionLabel = (realIdx: number): string => {
    if (total === 1) return 'Linha homogênea'
    if (realIdx === 0) return 'âncora'
    if (realIdx === total - 1) return 'fairlead'
    return ''
  }

  return (
    <div className="overflow-x-auto">
      {/* Wrapper grid horizontal — labels + N colunas de segmento + Add */}
      <table className="w-max border-collapse text-[11px]">
        <thead>
          <tr className="border-b border-border/40">
            <th className="sticky left-0 z-10 bg-background pr-2 text-left text-[10px] font-medium uppercase tracking-[0.05em] text-muted-foreground">
              {/* placeholder para alinhar com label column */}
            </th>
            {reversed.map(({ field, realIdx }) => (
              <th
                key={field.id}
                className="min-w-[140px] px-1.5 pb-1 text-left align-bottom"
              >
                <div className="flex items-center gap-1">
                  <span className="text-[11px] font-semibold text-foreground">
                    Segmento {realIdx + 1}
                  </span>
                  {positionLabel(realIdx) && (
                    <span className="text-[9px] uppercase tracking-wide text-muted-foreground">
                      {positionLabel(realIdx)}
                    </span>
                  )}
                  <div className="ml-auto flex items-center">
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      className="h-5 w-5 p-0"
                      onClick={() => setAdvancedIdx(realIdx)}
                      title="Configuração avançada"
                    >
                      <Settings2 className="h-3 w-3" />
                    </Button>
                    {realIdx > 0 && (
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="h-5 w-5 p-0"
                        onClick={() => segmentsArray.move(realIdx, realIdx - 1)}
                        title="Mover em direção à âncora"
                      >
                        <ArrowRight className="h-3 w-3" />
                      </Button>
                    )}
                    {realIdx < total - 1 && (
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="h-5 w-5 p-0"
                        onClick={() => segmentsArray.move(realIdx, realIdx + 1)}
                        title="Mover em direção ao fairlead"
                      >
                        <ArrowLeft className="h-3 w-3" />
                      </Button>
                    )}
                    {total > 1 && (
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="h-5 w-5 p-0 text-danger hover:bg-danger/10 hover:text-danger"
                        onClick={() => segmentsArray.remove(realIdx)}
                        title="Remover este segmento"
                      >
                        <Trash2 className="h-3 w-3" />
                      </Button>
                    )}
                  </div>
                </div>
              </th>
            ))}
            <th className="px-1.5 pb-1 align-bottom">
              {total < 10 && (
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="h-6 gap-1 border-dashed text-[10px]"
                  onClick={() => {
                    const first = segmentsArray.fields[
                      0
                    ] as unknown as T['segments'][number]
                    segmentsArray.prepend({ ...first, length: 100 } as never)
                  }}
                  title="Adicionar próximo da âncora"
                >
                  <Plus className="h-3 w-3" />
                  Adicionar
                </Button>
              )}
            </th>
          </tr>
        </thead>
        <tbody>
          {/* ─── Linha 1: Catálogo (LineTypePicker compacto) ───────── */}
          <PropertyRow label="Catálogo">
            {reversed.map(({ field, realIdx }) => (
              <td
                key={field.id}
                className="min-w-[140px] px-1 py-0.5 align-top"
              >
                <Controller
                  control={control}
                  name={p(realIdx, 'line_type')}
                  render={({ field: f }) => (
                    <LineTypePicker
                      value={
                        f.value
                          ? ({
                              id: 0,
                              line_type: f.value as string,
                              category:
                                (watch(p(realIdx, 'category')) as string | null) ??
                                'Wire',
                              diameter:
                                (watch(p(realIdx, 'diameter')) as number) ?? 0,
                              dry_weight:
                                (watch(p(realIdx, 'dry_weight')) as number) ?? 0,
                              wet_weight: watch(p(realIdx, 'w')) as number,
                              break_strength: watch(p(realIdx, 'MBL')) as number,
                              qmoor_ea: watch(p(realIdx, 'EA')) as number,
                              data_source: 'legacy_qmoor',
                            } as LineTypeOutput)
                          : null
                      }
                      onChange={(lt) => applyLineTypeToSegment(realIdx, lt)}
                      className="text-[11px]"
                    />
                  )}
                />
              </td>
            ))}
            <td />
          </PropertyRow>

          {/* ─── Linha 2: Comprimento (m) ──────────────────────────── */}
          <PropertyRow label="Comp. (m) *">
            {reversed.map(({ field, realIdx }) => (
              <td
                key={field.id}
                className="min-w-[140px] px-1 py-0.5"
              >
                <Input
                  type="number"
                  step="1"
                  {...register(p(realIdx, 'length') as Path<T>, {
                    valueAsNumber: true,
                  })}
                  className="h-6 font-mono text-[11px]"
                />
              </td>
            ))}
            <td />
          </PropertyRow>

          {/* ─── Linha 3: Diâmetro (m) ─────────────────────────────── */}
          <PropertyRow label="Diâm. (m)">
            {reversed.map(({ field, realIdx }) => (
              <td
                key={field.id}
                className="min-w-[140px] px-1 py-0.5"
              >
                <Input
                  type="number"
                  step="0.001"
                  min="0"
                  {...register(p(realIdx, 'diameter') as Path<T>, {
                    valueAsNumber: true,
                  })}
                  className="h-6 font-mono text-[11px]"
                />
              </td>
            ))}
            <td />
          </PropertyRow>

          {/* ─── Linha 4: Peso submerso (w) — UnitInput ────────────── */}
          <PropertyRow label="Peso submerso *">
            {reversed.map(({ field, realIdx }) => (
              <td
                key={field.id}
                className="min-w-[140px] px-1 py-0.5"
              >
                <Controller
                  control={control}
                  name={p(realIdx, 'w')}
                  render={({ field: f }) => (
                    <UnitInput
                      value={f.value as number}
                      onChange={f.onChange}
                      quantity="force_per_m"
                      digits={2}
                      className="h-6"
                      inputClassName="text-[11px] py-0.5"
                    />
                  )}
                />
              </td>
            ))}
            <td />
          </PropertyRow>

          {/* ─── Linha 5: Peso seco (dry_weight) ───────────────────── */}
          <PropertyRow label="Peso seco">
            {reversed.map(({ field, realIdx }) => (
              <td
                key={field.id}
                className="min-w-[140px] px-1 py-0.5"
              >
                <Controller
                  control={control}
                  name={p(realIdx, 'dry_weight')}
                  render={({ field: f }) => (
                    <UnitInput
                      value={(f.value as number | null) ?? null}
                      onChange={f.onChange}
                      quantity="force_per_m"
                      digits={2}
                      className="h-6"
                      inputClassName="text-[11px] py-0.5"
                    />
                  )}
                />
              </td>
            ))}
            <td />
          </PropertyRow>

          {/* ─── Linha 6: Resumo do catálogo + ⚙ Avançado link ─────── */}
          <PropertyRow label="">
            {reversed.map(({ field, realIdx }) => {
              const ea = watch(p(realIdx, 'EA')) as number | null
              const mbl = watch(p(realIdx, 'MBL')) as number | null
              return (
                <td
                  key={field.id}
                  className="min-w-[140px] px-1 py-1 text-[9.5px] text-muted-foreground"
                >
                  <div className="flex items-center gap-1">
                    <span className="truncate font-mono">
                      EA {ea != null ? fmtNumber(ea / 1000, 0) : '—'} kN ·
                      MBL {mbl != null ? fmtNumber(mbl / 1000, 0) : '—'} kN
                    </span>
                    <button
                      type="button"
                      className="ml-auto inline-flex h-4 items-center gap-0.5 rounded px-1 text-[9px] font-medium uppercase tracking-wide text-primary hover:bg-primary/10"
                      onClick={() => setAdvancedIdx(realIdx)}
                      title="Editar EA, MBL, Módulo, EA source, μ override, Categoria"
                    >
                      ⚙ Avançado
                    </button>
                  </div>
                </td>
              )
            })}
            <td />
          </PropertyRow>
        </tbody>
      </table>

      {advancedIdx != null && (
        <SegmentAdvancedDialog
          open={advancedIdx != null}
          onOpenChange={(open) => {
            if (!open) setAdvancedIdx(null)
          }}
          index={advancedIdx}
          total={total}
          basePath={basePath}
          control={control}
          register={register}
          watch={watch}
          setValue={setValue}
        />
      )}
    </div>
  )
}

function PropertyRow({
  label,
  children,
}: {
  label: string
  children: React.ReactNode
}) {
  return (
    <tr className={cn(label && 'border-b border-border/30')}>
      <th
        scope="row"
        className="sticky left-0 z-10 bg-background pr-2 py-0.5 text-right align-middle text-[10px] font-medium text-muted-foreground"
      >
        {label}
      </th>
      {children}
    </tr>
  )
}
