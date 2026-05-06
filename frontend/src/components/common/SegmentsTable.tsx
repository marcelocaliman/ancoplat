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
import { EnvCard, EnvField } from '@/components/common/EnvCard'
import { LineTypePicker } from '@/components/common/LineTypePicker'
import { SegmentAdvancedDialog } from '@/components/common/SegmentAdvancedDialog'
import { UnitInput } from '@/components/common/UnitInput'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import type { LineTypeOutput } from '@/api/types'
import type { CaseFormValues } from '@/lib/caseSchema'
import { fmtNumber } from '@/lib/utils'
import { toast } from 'sonner'

// Tipo concreto: react-hook-form generics com ArrayPath não casam bem
// em todas as combinações. Para mooring system multi-line use variante
// dedicada.
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
 * Lista de segmentos em layout de **cards individuais** (v1.0.11),
 * estilo aba Ambiente: cada segmento é um EnvCard bordado azulado
 * com header + LineTypePicker + 4 campos visíveis (Comprimento,
 * Diâmetro, Peso submerso, Peso seco) + resumo EA/MBL + botão
 * ⚙ que abre modal com config avançada.
 *
 * Ordem visual fairlead → âncora (esquerda → direita) via
 * [...].slice().reverse() na iteração. Botão "+ Adicionar"
 * fica no fim do row, sempre visível à direita.
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
  const p = <K extends string>(idx: number, name: K) =>
    `${basePath}[${idx}].${name}` as unknown as Path<T>

  // Render em ordem inversa do array (fairlead primeiro visualmente)
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

  return (
    <div className="flex flex-wrap items-stretch justify-start gap-2">
      {reversed.map(({ field, realIdx }) => {
        const positionLabel =
          total === 1
            ? `Segmento ${realIdx + 1}`
            : realIdx === 0
              ? `Segmento ${realIdx + 1} — junto à âncora`
              : realIdx === total - 1
                ? `Segmento ${realIdx + 1} — junto ao fairlead`
                : `Segmento ${realIdx + 1}`

        const ea = watch(p(realIdx, 'EA')) as number | null
        const mbl = watch(p(realIdx, 'MBL')) as number | null

        return (
          <EnvCard
            key={field.id}
            title={positionLabel}
            className="w-[260px]"
            trailing={
              <div className="flex items-center">
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
            }
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

            <EnvField label="Comprimento" unit="m">
              <Input
                type="number"
                step="1"
                {...register(p(realIdx, 'length') as Path<T>, {
                  valueAsNumber: true,
                })}
                className="h-7 w-[80px] font-mono text-[11px]"
              />
            </EnvField>

            <EnvField label="Diâmetro" unit="m">
              <Input
                type="number"
                step="0.001"
                min="0"
                {...register(p(realIdx, 'diameter') as Path<T>, {
                  valueAsNumber: true,
                })}
                className="h-7 w-[80px] font-mono text-[11px]"
              />
            </EnvField>

            <EnvField label="Peso submerso">
              <Controller
                control={control}
                name={p(realIdx, 'w')}
                render={({ field: f }) => (
                  <UnitInput
                    value={f.value as number}
                    onChange={f.onChange}
                    quantity="force_per_m"
                    digits={2}
                    className="h-7 w-[80px]"
                    inputClassName="text-[11px] py-0.5"
                  />
                )}
              />
            </EnvField>

            <EnvField label="Peso seco">
              <Controller
                control={control}
                name={p(realIdx, 'dry_weight')}
                render={({ field: f }) => (
                  <UnitInput
                    value={(f.value as number | null) ?? null}
                    onChange={f.onChange}
                    quantity="force_per_m"
                    digits={2}
                    className="h-7 w-[80px]"
                    inputClassName="text-[11px] py-0.5"
                  />
                )}
              />
            </EnvField>

            <p className="pt-0.5 text-[9px] text-muted-foreground">
              EA {ea != null ? fmtNumber(ea / 1000, 0) : '—'} kN ·
              MBL {mbl != null ? fmtNumber(mbl / 1000, 0) : '—'} kN
            </p>
          </EnvCard>
        )
      })}

      {/* Card "+ Adicionar" — mesmo estilo, dashed border */}
      {total < 10 && (
        <button
          type="button"
          className="flex h-auto min-h-[200px] w-[160px] shrink-0 flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed border-primary/30 bg-primary/[0.02] text-primary/70 transition-colors hover:border-primary/50 hover:bg-primary/[0.06] hover:text-primary"
          onClick={() => {
            const first = segmentsArray.fields[
              0
            ] as unknown as T['segments'][number]
            segmentsArray.prepend({ ...first, length: 100 } as never)
          }}
          title="Adicionar próximo da âncora"
        >
          <Plus className="h-5 w-5" />
          <span className="text-center text-[10px] font-medium leading-tight">
            Adicionar
            <br />
            (próximo da âncora)
          </span>
        </button>
      )}

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
