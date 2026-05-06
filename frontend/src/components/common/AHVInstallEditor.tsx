import { Anchor, Plus, Sparkles, Trash2 } from 'lucide-react'
import {
  Controller,
  type Control,
  type Path,
  type UseFormSetValue,
} from 'react-hook-form'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { UnitInput } from '@/components/common/UnitInput'
import type { CaseFormValues } from '@/lib/caseSchema'

type T = CaseFormValues

export interface AHVInstallEditorProps {
  control: Control<T>
  setValue: UseFormSetValue<T>
  /** Valor atual do ahv_install (vindo do useWatch ou form). */
  ahvInstall: CaseFormValues['boundary']['ahv_install']
  /** Callback opcional quando user clica "Aplicar via Sensitivity". */
  onApplyViaSensitivity?: () => void
}

const EMPTY_AHV: NonNullable<CaseFormValues['boundary']['ahv_install']> = {
  bollard_pull: 50.0 * 9806.65, // 50 te → ~490 kN
  deck_level_above_swl: 0,
  stern_angle_deg: 0,
  target_horz_distance: null,
}

/**
 * Editor inline do `boundary.ahv_install` — Sprint 2 / Commit 26.
 *
 * Cenários AHV de instalação (Backing Down / Hookup / Load Transfer):
 * o "fairlead" virtual é o convés de um Anchor Handler Vessel (AHV)
 * na superfície, segurando a linha durante operação temporária.
 *
 * Quando importado de QMoor 0.8.0, parser popula automaticamente.
 * UI permite editar `bollard_pull` (força aplicada pelo cabo de
 * trabalho), `deck_level_above_swl` (cosmético v1.1.0),
 * `stern_angle_deg` (cosmético) e `target_horz_distance` (X target
 * informativo do QMoor original).
 *
 * Solver usa `bollard_pull` como input em mode Tension. O X
 * resultante depende do bollard pull aplicado — para iterar até
 * X≈target, use o Sensitivity Panel.
 */
export function AHVInstallEditor({
  control,
  setValue,
  ahvInstall,
  onApplyViaSensitivity,
}: AHVInstallEditorProps) {
  const has = ahvInstall != null

  const p = (suffix: keyof NonNullable<CaseFormValues['boundary']['ahv_install']>) =>
    `boundary.ahv_install.${suffix}` as Path<T>

  return (
    <Card className="border-warning/30 bg-warning/[0.04]">
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="flex items-center gap-2 text-sm">
          <Anchor className="h-4 w-4 text-warning/80" />
          AHV Install (cenário temporário)
        </CardTitle>
        {has ? (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-7 gap-1 text-[11px] text-muted-foreground hover:text-danger"
            onClick={() => {
              setValue('boundary.ahv_install', null, { shouldDirty: true })
            }}
            aria-label="Remover AHV Install"
          >
            <Trash2 className="h-3 w-3" /> Remover
          </Button>
        ) : (
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="h-7 gap-1 text-[11px]"
            onClick={() => {
              setValue('boundary.ahv_install', { ...EMPTY_AHV }, {
                shouldDirty: true,
              })
              setValue('boundary.startpoint_type', 'ahv', { shouldDirty: true })
            }}
          >
            <Plus className="h-3 w-3" /> Adicionar AHV Install
          </Button>
        )}
      </CardHeader>
      <CardContent className="pb-3 pt-1">
        {!has ? (
          <p className="text-[11px] text-muted-foreground">
            Cenário AHV de instalação (Backing Down / Hookup / Load
            Transfer). Adicione quando o "fairlead" da linha for o
            convés de um <strong>Anchor Handler Vessel</strong> na
            superfície durante operação temporária. Em modo normal
            (rig fairlead conectado), deixe vazio.
          </p>
        ) : (
          <div className="space-y-3">
            <p className="text-[10px] text-muted-foreground">
              Solver usa <strong>bollard pull</strong> como input em
              modo Tension. X resultante depende do bollard aplicado —
              use a aba Análise / Sensitivity Panel para iterar até
              X ≈ target.
            </p>
            <div className="grid grid-cols-2 gap-x-3 gap-y-2 lg:grid-cols-4">
              <Field label="Bollard Pull *">
                <Controller
                  control={control}
                  name={p('bollard_pull')}
                  render={({ field }) => (
                    <UnitInput
                      value={(field.value as number | null) ?? null}
                      onChange={(v) => field.onChange(v ?? 0)}
                      quantity="force"
                      digits={1}
                      className="h-7"
                      inputClassName="text-[11px] py-0.5"
                    />
                  )}
                />
              </Field>
              <Field label="Deck Level acima SWL" unit="m">
                <NumberCtrl
                  control={control}
                  name={p('deck_level_above_swl')}
                  step="0.1"
                  min={0}
                />
              </Field>
              <Field label="Stern Angle" unit="°">
                <NumberCtrl
                  control={control}
                  name={p('stern_angle_deg')}
                  step="1"
                />
              </Field>
              <Field label="Target X (info)" unit="m">
                <NumberCtrl
                  control={control}
                  name={p('target_horz_distance')}
                  step="1"
                  min={0}
                />
              </Field>
            </div>
            {ahvInstall?.target_horz_distance != null
              && onApplyViaSensitivity && (
                <div className="flex items-center justify-between rounded-md border border-primary/20 bg-primary/[0.04] p-2">
                  <span className="text-[11px] text-muted-foreground">
                    Atingir X ={' '}
                    <span className="font-mono text-foreground">
                      {ahvInstall.target_horz_distance.toFixed(1)} m
                    </span>{' '}
                    iterando o bollard pull?
                  </span>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="h-6 gap-1 text-[10px]"
                    onClick={onApplyViaSensitivity}
                  >
                    <Sparkles className="h-3 w-3" /> Aplicar via Sensitivity
                  </Button>
                </div>
              )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

// ──────────────────────────────────────────────────────────────────
// Helpers locais (mesmo padrão do VesselEditor)
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
