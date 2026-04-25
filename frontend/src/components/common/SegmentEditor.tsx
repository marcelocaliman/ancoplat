import { ArrowDown, ArrowUp, Trash2 } from 'lucide-react'
import {
  Controller,
  type Control,
  type UseFormRegister,
  type UseFormWatch,
  type UseFormSetValue,
} from 'react-hook-form'
import { LineTypePicker } from '@/components/common/LineTypePicker'
import { UnitInput } from '@/components/common/UnitInput'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import type { LineTypeOutput } from '@/api/types'
import type { CaseFormValues } from '@/lib/caseSchema'
import { cn, fmtDiameterMM, fmtNumber } from '@/lib/utils'
import { toast } from 'sonner'

export interface SegmentEditorProps {
  index: number
  total: number
  control: Control<CaseFormValues>
  register: UseFormRegister<CaseFormValues>
  watch: UseFormWatch<CaseFormValues>
  setValue: UseFormSetValue<CaseFormValues>
  onRemove?: () => void
  onMoveUp?: () => void
  onMoveDown?: () => void
}

/**
 * Editor de um único segmento dentro do form de caso. Recebe o `index`
 * para que todos os campos apontem para `segments[index].*`. Estado vive
 * no react-hook-form do pai; aqui só renderizamos.
 *
 * Convenção de ordem:
 *   - index 0 é o segmento mais próximo da âncora (chain inferior, etc.)
 *   - último index é o segmento mais próximo do fairlead
 */
export function SegmentEditor({
  index,
  total,
  control,
  register,
  watch,
  setValue,
  onRemove,
  onMoveUp,
  onMoveDown,
}: SegmentEditorProps) {
  function applyLineTypeToSegment(lt: LineTypeOutput | null) {
    if (!lt) return
    const base = `segments.${index}` as const
    setValue(`${base}.line_type`, lt.line_type, { shouldValidate: true })
    setValue(
      `${base}.category`,
      lt.category as CaseFormValues['segments'][number]['category'],
      { shouldValidate: true },
    )
    setValue(`${base}.w`, roundTo(lt.wet_weight, 2), { shouldValidate: true })
    setValue(`${base}.EA`, roundTo(lt.qmoor_ea ?? lt.gmoor_ea ?? 0, 0), {
      shouldValidate: true,
    })
    setValue(`${base}.MBL`, roundTo(lt.break_strength, 0), { shouldValidate: true })
    setValue(`${base}.diameter`, roundTo(lt.diameter, 5), { shouldValidate: true })
    setValue(`${base}.dry_weight`, roundTo(lt.dry_weight, 2), { shouldValidate: true })
    if (lt.modulus) {
      setValue(`${base}.modulus`, roundTo(lt.modulus, 0), { shouldValidate: true })
    }
    toast.success(`${lt.line_type} aplicado ao segmento ${index + 1}`, {
      description: `Ø ${fmtDiameterMM(lt.diameter, 0)} · MBL ${fmtNumber(
        lt.break_strength / 1000, 0,
      )} kN`,
    })
  }

  const positionLabel =
    total === 1
      ? 'Linha homogênea'
      : index === 0
        ? `Segmento ${index + 1} — junto à âncora`
        : index === total - 1
          ? `Segmento ${index + 1} — junto ao fairlead`
          : `Segmento ${index + 1}`

  return (
    <div
      className={cn(
        'rounded-md border border-border/60 bg-muted/10 p-2.5',
        'space-y-2',
      )}
    >
      <div className="flex items-center gap-2">
        <span className="text-[10px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">
          {positionLabel}
        </span>
        <div className="ml-auto flex items-center gap-1">
          {onMoveUp && (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="h-6 w-6 p-0"
              onClick={onMoveUp}
              title="Mover para cima (mais perto da âncora)"
            >
              <ArrowUp className="h-3 w-3" />
            </Button>
          )}
          {onMoveDown && (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="h-6 w-6 p-0"
              onClick={onMoveDown}
              title="Mover para baixo (mais perto do fairlead)"
            >
              <ArrowDown className="h-3 w-3" />
            </Button>
          )}
          {onRemove && total > 1 && (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="h-6 w-6 p-0 text-danger hover:bg-danger/10 hover:text-danger"
              onClick={onRemove}
              title="Remover este segmento"
            >
              <Trash2 className="h-3 w-3" />
            </Button>
          )}
        </div>
      </div>

      <Controller
        control={control}
        name={`segments.${index}.line_type`}
        render={({ field }) => (
          <LineTypePicker
            value={
              field.value
                ? ({
                    id: 0,
                    line_type: field.value,
                    category: watch(`segments.${index}.category`) ?? 'Wire',
                    diameter: watch(`segments.${index}.diameter`) ?? 0,
                    dry_weight: watch(`segments.${index}.dry_weight`) ?? 0,
                    wet_weight: watch(`segments.${index}.w`),
                    break_strength: watch(`segments.${index}.MBL`),
                    qmoor_ea: watch(`segments.${index}.EA`),
                    data_source: 'legacy_qmoor',
                  } as LineTypeOutput)
                : null
            }
            onChange={applyLineTypeToSegment}
          />
        )}
      />

      <div className="grid grid-cols-3 gap-2">
        <InlineLabeled label="Comp." unit="m">
          <Input
            type="number"
            step="1"
            {...register(`segments.${index}.length`, { valueAsNumber: true })}
            className="h-8 font-mono"
          />
        </InlineLabeled>
        <InlineLabeled label="Diâmetro" unit="m">
          <Input
            type="number"
            step="0.001"
            min="0"
            {...register(`segments.${index}.diameter`, { valueAsNumber: true })}
            className="h-8 font-mono"
          />
        </InlineLabeled>
        <InlineLabeled label="Categoria">
          <Controller
            control={control}
            name={`segments.${index}.category`}
            render={({ field }) => (
              <Select
                value={field.value ?? undefined}
                onValueChange={field.onChange}
              >
                <SelectTrigger className="h-8">
                  <SelectValue placeholder="—" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="Wire">Wire</SelectItem>
                  <SelectItem value="StuddedChain">Studded</SelectItem>
                  <SelectItem value="StudlessChain">Studless</SelectItem>
                  <SelectItem value="Polyester">Poliéster</SelectItem>
                </SelectContent>
              </Select>
            )}
          />
        </InlineLabeled>
        <InlineLabeled label="Peso submerso">
          <Controller
            control={control}
            name={`segments.${index}.w`}
            render={({ field }) => (
              <UnitInput
                value={field.value}
                onChange={field.onChange}
                quantity="force_per_m"
                digits={2}
                className="h-8"
              />
            )}
          />
        </InlineLabeled>
        <InlineLabeled label="Peso seco">
          <Controller
            control={control}
            name={`segments.${index}.dry_weight`}
            render={({ field }) => (
              <UnitInput
                value={field.value ?? null}
                onChange={field.onChange}
                quantity="force_per_m"
                digits={2}
                className="h-8"
              />
            )}
          />
        </InlineLabeled>
        <InlineLabeled label="EA">
          <Controller
            control={control}
            name={`segments.${index}.EA`}
            render={({ field }) => (
              <UnitInput
                value={field.value}
                onChange={field.onChange}
                quantity="force"
                digits={2}
                className="h-8"
              />
            )}
          />
        </InlineLabeled>
        <InlineLabeled label="MBL" className="col-span-2">
          <Controller
            control={control}
            name={`segments.${index}.MBL`}
            render={({ field }) => (
              <UnitInput
                value={field.value}
                onChange={field.onChange}
                quantity="force"
                digits={2}
                className="h-8"
              />
            )}
          />
        </InlineLabeled>
        <InlineLabeled label="Módulo" unit="Pa">
          <Input
            type="number"
            step="1e9"
            {...register(`segments.${index}.modulus`, { valueAsNumber: true })}
            className="h-8 font-mono"
          />
        </InlineLabeled>
      </div>
    </div>
  )
}

function InlineLabeled({
  label,
  unit,
  className,
  children,
}: {
  label: string
  unit?: string
  className?: string
  children: React.ReactNode
}) {
  return (
    <div className={cn('flex flex-col gap-0.5', className)}>
      <Label className="flex items-center justify-between gap-1 text-[10px] font-medium text-muted-foreground">
        <span className="truncate">{label}</span>
        {unit && (
          <span className="shrink-0 font-mono text-[9px] font-normal">{unit}</span>
        )}
      </Label>
      {children}
    </div>
  )
}

function roundTo(value: number, digits: number): number {
  const f = 10 ** digits
  return Math.round(value * f) / f
}
