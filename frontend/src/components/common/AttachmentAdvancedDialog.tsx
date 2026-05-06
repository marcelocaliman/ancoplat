import { useId } from 'react'
import {
  Controller,
  type Control,
  type Path,
  type UseFormSetValue,
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

type T = CaseFormValues

export interface AttachmentAdvancedDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  index: number
  basePath?: string
  control: Control<T>
  setValue: UseFormSetValue<T>
  kind: 'buoy' | 'clump_weight'
}

/**
 * Modal de configuração avançada de attachment (boia ou clump weight).
 *
 * Para BOIA, expõe campos profissionais que vêm do BuoyPicker mas
 * podem ser editados manualmente:
 *   - tipo (surface/submersible)
 *   - end_type (flat/hemispherical/elliptical/semi_conical)
 *   - outer_diameter, length, weight_in_air (dimensões)
 *   - pendant_line_type, pendant_diameter (cabo de conexão)
 *
 * Para CLUMP WEIGHT, expõe apenas pendant — clump não tem
 * dimensões/tipo profissional no schema atual.
 */
export function AttachmentAdvancedDialog({
  open,
  onOpenChange,
  index,
  basePath = 'attachments',
  control,
  setValue,
  kind,
}: AttachmentAdvancedDialogProps) {
  const p = (suffix: string) =>
    `${basePath}.${index}.${suffix}` as Path<T>

  const clearCatalogLink = () => {
    setValue(p('buoy_catalog_id'), null as never, { shouldValidate: false })
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle className="text-sm">
            {kind === 'buoy' ? 'Boia' : 'Clump weight'} — configuração avançada
          </DialogTitle>
          <DialogDescription className="text-[11px]">
            {kind === 'buoy'
              ? 'Tipo, dimensões e cabo de conexão. Para boia profissional do catálogo, esses valores vêm preenchidos automaticamente; editar manualmente quebra o vínculo.'
              : 'Cabo de conexão (pendant) entre o clump e a linha principal.'}
          </DialogDescription>
        </DialogHeader>

        <div className="grid grid-cols-2 gap-x-3 gap-y-2">
          {kind === 'buoy' && (
            <>
              <Field label="Tipo de boia">
                <Controller
                  control={control}
                  name={p('buoy_type')}
                  render={({ field }) => (
                    <Select
                      value={(field.value as string | null) ?? ''}
                      onValueChange={(v) => {
                        field.onChange(v || null)
                        clearCatalogLink()
                      }}
                    >
                      <SelectTrigger className="h-7 text-[11px]">
                        <SelectValue placeholder="—" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="surface">Superfície</SelectItem>
                        <SelectItem value="submersible">Submergível</SelectItem>
                      </SelectContent>
                    </Select>
                  )}
                />
              </Field>

              <Field label="End type">
                <Controller
                  control={control}
                  name={p('buoy_end_type')}
                  render={({ field }) => (
                    <Select
                      value={(field.value as string | null) ?? ''}
                      onValueChange={(v) => {
                        field.onChange(v || null)
                        clearCatalogLink()
                      }}
                    >
                      <SelectTrigger className="h-7 text-[11px]">
                        <SelectValue placeholder="—" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="flat">Flat</SelectItem>
                        <SelectItem value="hemispherical">Hemispherical</SelectItem>
                        <SelectItem value="elliptical">Elliptical</SelectItem>
                        <SelectItem value="semi_conical">Semi-conical</SelectItem>
                      </SelectContent>
                    </Select>
                  )}
                />
              </Field>

              <Field label="Diâmetro externo" unit="m">
                <Controller
                  control={control}
                  name={p('buoy_outer_diameter')}
                  render={({ field }) => (
                    <Input
                      type="number"
                      step="0.01"
                      min="0"
                      value={(field.value as number | null) ?? ''}
                      onChange={(e) => {
                        const v = parseFloat(e.target.value)
                        field.onChange(Number.isFinite(v) ? v : null)
                        clearCatalogLink()
                      }}
                      className="h-7 font-mono"
                    />
                  )}
                />
              </Field>

              <Field label="Comprimento" unit="m">
                <Controller
                  control={control}
                  name={p('buoy_length')}
                  render={({ field }) => (
                    <Input
                      type="number"
                      step="0.1"
                      min="0"
                      value={(field.value as number | null) ?? ''}
                      onChange={(e) => {
                        const v = parseFloat(e.target.value)
                        field.onChange(Number.isFinite(v) ? v : null)
                        clearCatalogLink()
                      }}
                      className="h-7 font-mono"
                    />
                  )}
                />
              </Field>

              <Field label="Peso ao ar" className="col-span-2">
                <Controller
                  control={control}
                  name={p('buoy_weight_in_air')}
                  render={({ field }) => (
                    <UnitInput
                      value={(field.value as number | null) ?? null}
                      onChange={(v) => {
                        field.onChange(v)
                        clearCatalogLink()
                      }}
                      quantity="force"
                      digits={2}
                      className="h-7"
                    />
                  )}
                />
              </Field>
            </>
          )}

          <Field label="Pendant — material">
            <Controller
              control={control}
              name={p('pendant_line_type')}
              render={({ field }) => (
                <Input
                  type="text"
                  value={(field.value as string | null) ?? ''}
                  onChange={(e) => field.onChange(e.target.value || null)}
                  placeholder="ex: IWRCEIPS"
                  className="h-7 text-[11px]"
                  maxLength={80}
                />
              )}
            />
          </Field>

          <Field label="Pendant — diâmetro" unit="m">
            <Controller
              control={control}
              name={p('pendant_diameter')}
              render={({ field }) => (
                <Input
                  type="number"
                  step="0.001"
                  min="0"
                  value={(field.value as number | null) ?? ''}
                  onChange={(e) => {
                    const v = parseFloat(e.target.value)
                    field.onChange(Number.isFinite(v) ? v : null)
                  }}
                  className="h-7 font-mono"
                />
              )}
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
