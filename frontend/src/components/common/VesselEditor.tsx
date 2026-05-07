import { AlertTriangle, Anchor, Check, Plus, Trash2 } from 'lucide-react'
import { Controller, type Control, type Path, type UseFormSetValue, useWatch } from 'react-hook-form'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { VesselPicker } from '@/components/common/VesselPicker'
import type { VesselOutput } from '@/api/types'
import type { CaseFormValues } from '@/lib/caseSchema'

type T = CaseFormValues

export interface VesselEditorProps {
  control: Control<T>
  setValue: UseFormSetValue<T>
  /** Valor atual do vessel (vindo do useWatch ou do form). */
  vessel: CaseFormValues['vessel']
}

const VESSEL_TYPES = [
  'FPSO',
  'Semisubmersible',
  'FSO',
  'Spar',
  'TLP',
  'AHV',
  'Drillship',
  'MODU',
  'Barge',
] as const

const EMPTY_VESSEL: NonNullable<CaseFormValues['vessel']> = {
  name: 'Vessel 1',
  vessel_type: 'FPSO',
  displacement: null,
  loa: null,
  breadth: null,
  draft: null,
  heading_deg: 0,
  operator: null,
}

/**
 * Editor inline do `Vessel` (host platform / hull). Sprint 2 / Commit 15.
 *
 * Quando `vessel` é null/undefined, mostra estado vazio + botão para
 * adicionar (popula com `EMPTY_VESSEL`). Quando preenchido, mostra
 * formulário com 8 campos (1 obrigatório: name) + botão de remover.
 *
 * Inspirado no editor de AHV do QMoor 0.8.0 (imagem do usuário) mas
 * usando o schema do AncoPlat — vessel aqui é o **hull do caso**
 * (FPSO/semisub conectado ao fairlead), NÃO o AHV de instalação
 * (esse continua via LineAttachment.kind="ahv" + AttachmentsEditor).
 */
export function VesselEditor({ control, setValue, vessel }: VesselEditorProps) {
  const has = vessel != null

  const p = (suffix: keyof NonNullable<CaseFormValues['vessel']>) =>
    `vessel.${suffix}` as Path<T>

  // Sprint 6 / Q7 — rastreabilidade ao catálogo. catalog_id é
  // populado quando user escolhe via VesselPicker; qualquer override
  // manual em campo físico (loa/breadth/draft/displacement) zera o
  // catalog_id para null (modo "manual").
  const catalogId = useWatch({
    control,
    name: 'vessel.catalog_id' as Path<T>,
  }) as number | null | undefined

  function applyVesselFromCatalog(v: VesselOutput) {
    setValue(p('catalog_id'), v.id as never, { shouldDirty: true })
    setValue(p('name'), v.name as never, { shouldDirty: true })
    setValue(p('vessel_type'), v.vessel_type as never, { shouldDirty: true })
    setValue(p('loa'), v.loa as never, { shouldDirty: true })
    setValue(p('breadth'), v.breadth as never, { shouldDirty: true })
    setValue(p('draft'), v.draft as never, { shouldDirty: true })
    if (v.displacement != null) {
      setValue(p('displacement'), v.displacement as never, { shouldDirty: true })
    }
    setValue(p('heading_deg'), v.default_heading_deg as never, {
      shouldDirty: true,
    })
    if (v.operator) {
      setValue(p('operator'), v.operator as never, { shouldDirty: true })
    }
  }

  function clearCatalogLink() {
    if (catalogId != null) {
      setValue(p('catalog_id'), null as never, { shouldDirty: true })
    }
  }

  return (
    <Card className="border-primary/15 bg-primary/[0.02]">
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="flex items-center gap-2 text-sm">
          <Anchor className="h-4 w-4 text-primary/70" />
          Vessel / Plataforma
          {has && vessel?.name && (
            <span className="text-[11px] font-normal text-muted-foreground">
              · {vessel.name}
            </span>
          )}
        </CardTitle>
        {has ? (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-7 gap-1 text-[11px] text-muted-foreground hover:text-danger"
            onClick={() => setValue('vessel', null, { shouldDirty: true })}
            aria-label="Remover vessel"
          >
            <Trash2 className="h-3 w-3" /> Remover
          </Button>
        ) : (
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="h-7 gap-1 text-[11px]"
            onClick={() =>
              setValue('vessel', { ...EMPTY_VESSEL }, { shouldDirty: true })
            }
          >
            <Plus className="h-3 w-3" /> Adicionar vessel
          </Button>
        )}
      </CardHeader>
      <CardContent className="pb-3 pt-1">
        {!has ? (
          <p className="text-[11px] text-muted-foreground">
            Sem vessel. Adicione para que o casco apareça no plot
            (escalado por LOA × draft) e os dados do hull entrem no
            Memorial PDF.
          </p>
        ) : (
          <div className="space-y-3">
            {/* Sprint 6 — Picker do catálogo + badge manual/catálogo */}
            <div className="flex items-center gap-2">
              <div className="flex-1">
                <Label className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
                  Vessel do catálogo
                </Label>
                <VesselPicker
                  selectedId={catalogId ?? null}
                  onPick={applyVesselFromCatalog}
                  onClear={() => clearCatalogLink()}
                  className="h-8"
                />
              </div>
              {catalogId != null ? (
                <Badge
                  variant="outline"
                  className="mt-4 h-5 gap-1 border-primary/40 bg-primary/10 px-1.5 text-[9px] text-primary"
                  title={`Linkado ao catálogo (id=${catalogId})`}
                >
                  <Check className="h-2.5 w-2.5" />
                  do catálogo
                </Badge>
              ) : (
                <Badge
                  variant="outline"
                  className="mt-4 h-5 gap-1 border-warning/40 bg-warning/10 px-1.5 text-[9px] text-warning"
                  title="Vessel customizado / modificado do catálogo"
                >
                  <AlertTriangle className="h-2.5 w-2.5" />
                  manual
                </Badge>
              )}
            </div>
            <div className="grid grid-cols-2 gap-x-3 gap-y-2 lg:grid-cols-4">
            <Field label="Nome *">
              <Controller
                control={control}
                name={p('name')}
                render={({ field }) => (
                  <Input
                    type="text"
                    value={(field.value as string | null) ?? ''}
                    onChange={(e) => field.onChange(e.target.value)}
                    maxLength={120}
                    placeholder="ex: P-77"
                    className="h-7 text-[12px]"
                  />
                )}
              />
            </Field>
            <Field label="Tipo">
              <Controller
                control={control}
                name={p('vessel_type')}
                render={({ field }) => (
                  <Select
                    value={(field.value as string | null) ?? ''}
                    onValueChange={(v) => field.onChange(v || null)}
                  >
                    <SelectTrigger className="h-7 text-[11px]">
                      <SelectValue placeholder="—" />
                    </SelectTrigger>
                    <SelectContent>
                      {VESSEL_TYPES.map((t) => (
                        <SelectItem key={t} value={t} className="text-[12px]">
                          {t}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              />
            </Field>
            <Field label="LOA" unit="m">
              <NumberCtrl control={control} name={p('loa')} step="0.1" />
            </Field>
            <Field label="Boca" unit="m">
              <NumberCtrl control={control} name={p('breadth')} step="0.1" />
            </Field>
            <Field label="Calado" unit="m">
              <NumberCtrl control={control} name={p('draft')} step="0.1" />
            </Field>
            <Field label="Deslocamento" unit="kg">
              <NumberCtrl
                control={control}
                name={p('displacement')}
                step="1000"
              />
            </Field>
            <Field label="Heading" unit="°">
              <NumberCtrl
                control={control}
                name={p('heading_deg')}
                step="1"
                min={0}
                max={359.999}
              />
            </Field>
            <Field label="Operador">
              <Controller
                control={control}
                name={p('operator')}
                render={({ field }) => (
                  <Input
                    type="text"
                    value={(field.value as string | null) ?? ''}
                    onChange={(e) => field.onChange(e.target.value || null)}
                    maxLength={120}
                    placeholder="ex: Petrobras"
                    className="h-7 text-[12px]"
                  />
                )}
              />
            </Field>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

// ──────────────────────────────────────────────────────────────────
// Helpers locais
// ──────────────────────────────────────────────────────────────────

function Field({
  label,
  unit,
  children,
}: {
  label: string
  unit?: string
  children: React.ReactNode
}) {
  return (
    <div className="flex flex-col gap-0.5">
      <Label className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
        {label}
        {unit && (
          <span className="ml-1 font-mono text-muted-foreground/60">
            ({unit})
          </span>
        )}
      </Label>
      {children}
    </div>
  )
}

function NumberCtrl({
  control,
  name,
  step,
  min,
  max,
}: {
  control: Control<T>
  name: Path<T>
  step?: string
  min?: number
  max?: number
}) {
  return (
    <Controller
      control={control}
      name={name}
      render={({ field }) => (
        <Input
          type="number"
          step={step}
          min={min}
          max={max}
          value={(field.value as number | null) ?? ''}
          onChange={(e) => {
            const v = parseFloat(e.target.value)
            field.onChange(Number.isFinite(v) ? v : null)
          }}
          className="h-7 font-mono text-[11px]"
        />
      )}
    />
  )
}
