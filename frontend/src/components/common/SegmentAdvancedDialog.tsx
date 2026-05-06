import { useId } from 'react'
import {
  Controller,
  type Control,
  type FieldValues,
  type Path,
  type UseFormRegister,
  type UseFormWatch,
} from 'react-hook-form'
import { UnitInput } from '@/components/common/UnitInput'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import type { CaseFormValues } from '@/lib/caseSchema'
import { fmtNumber } from '@/lib/utils'

export interface SegmentAdvancedDialogProps<
  T extends FieldValues = CaseFormValues,
> {
  open: boolean
  onOpenChange: (open: boolean) => void
  index: number
  total: number
  basePath?: string
  control: Control<T>
  register: UseFormRegister<T>
  watch: UseFormWatch<T>
  /** setValue não é usado dentro do modal — Controller/register fazem o trabalho. */
  setValue?: unknown
}

/**
 * Modal de configuração avançada de um segmento.
 *
 * Campos preenchidos automaticamente do catálogo (LineTypePicker) e
 * raramente editados manualmente — não precisam ocupar espaço na
 * tabela principal. Aparecem aqui para permitir override consciente.
 *
 * Campos cobertos:
 *   - Categoria (Wire / StuddedChain / StudlessChain / Polyester)
 *   - EA (rigidez axial)
 *   - MBL (Minimum Breaking Load)
 *   - Módulo elástico (Pa)
 *   - EA source (qmoor / gmoor)
 *   - μ override (atrito per-segmento, se diferente do global)
 */
export function SegmentAdvancedDialog<
  T extends FieldValues = CaseFormValues,
>({
  open,
  onOpenChange,
  index,
  total,
  basePath = 'segments',
  control,
  register,
  watch,
}: SegmentAdvancedDialogProps<T>) {
  const p = <K extends string>(name: K) =>
    `${basePath}[${index}].${name}` as unknown as Path<T>

  const positionLabel =
    total === 1
      ? 'Linha homogênea'
      : index === 0
        ? `Segmento ${index + 1} — junto à âncora`
        : index === total - 1
          ? `Segmento ${index + 1} — junto ao fairlead`
          : `Segmento ${index + 1}`

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle className="text-sm">{positionLabel}</DialogTitle>
          <DialogDescription className="text-[11px]">
            Configuração avançada — campos do catálogo. Editar manualmente
            apenas quando override deliberado é necessário.
          </DialogDescription>
        </DialogHeader>

        <div className="grid grid-cols-2 gap-x-3 gap-y-2">
          <Field label="Categoria">
            <Controller
              control={control}
              name={p('category')}
              render={({ field }) => (
                <Select
                  value={(field.value as string | undefined) ?? undefined}
                  onValueChange={field.onChange}
                >
                  <SelectTrigger className="h-7 text-[11px]">
                    <SelectValue placeholder="—" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="Wire">Wire</SelectItem>
                    <SelectItem value="StuddedChain">Studded chain</SelectItem>
                    <SelectItem value="StudlessChain">Studless chain</SelectItem>
                    <SelectItem value="Polyester">Poliéster</SelectItem>
                  </SelectContent>
                </Select>
              )}
            />
          </Field>

          <Field label="EA source">
            <Controller
              control={control}
              name={p('ea_source')}
              render={({ field }) => (
                <Select
                  value={(field.value as string | undefined) ?? 'qmoor'}
                  onValueChange={field.onChange}
                >
                  <SelectTrigger
                    className="h-7 text-[11px]"
                    title="EA estático (QMoor) ou dinâmico (GMoor — modelo NREL/MoorPy). Default QMoor."
                  >
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="qmoor">QMoor (estático)</SelectItem>
                    <SelectItem value="gmoor">GMoor (dinâmico)</SelectItem>
                  </SelectContent>
                </Select>
              )}
            />
          </Field>

          <Field label="EA (rigidez axial)">
            <Controller
              control={control}
              name={p('EA')}
              render={({ field }) => (
                <UnitInput
                  value={field.value as number}
                  onChange={field.onChange}
                  quantity="force"
                  digits={2}
                  className="h-7"
                />
              )}
            />
          </Field>

          <Field label="MBL (rotura)">
            <Controller
              control={control}
              name={p('MBL')}
              render={({ field }) => (
                <UnitInput
                  value={field.value as number}
                  onChange={field.onChange}
                  quantity="force"
                  digits={2}
                  className="h-7"
                />
              )}
            />
          </Field>

          <Field label="Módulo elástico" unit="Pa" className="col-span-2">
            <Input
              type="number"
              step="1e9"
              {...register(p('modulus') as Path<T>, { valueAsNumber: true })}
              className="h-7 font-mono"
            />
          </Field>

          <Field label="μ override" unit="" className="col-span-2">
            <Input
              type="number"
              step="0.05"
              min="0"
              placeholder={(() => {
                const cf = watch(p('seabed_friction_cf')) as number | null
                return cf != null
                  ? `Catálogo: ${fmtNumber(cf, 2)} (vazio = usa esse)`
                  : 'Vazio = usa global do seabed'
              })()}
              {...register(p('mu_override') as Path<T>, {
                setValueAs: (v) =>
                  v === '' || v == null ? null : Number(v),
              })}
              className="h-7 font-mono"
            />
          </Field>
        </div>
      </DialogContent>
    </Dialog>
  )
}

function Field({
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
  const id = useId()
  return (
    <div className={`flex flex-col gap-0.5 ${className ?? ''}`}>
      <Label
        htmlFor={id}
        className="flex items-center justify-between gap-1 text-[10px] font-medium text-muted-foreground"
      >
        <span>{label}</span>
        {unit && (
          <span className="font-mono text-[9px] font-normal">{unit}</span>
        )}
      </Label>
      {children}
    </div>
  )
}
