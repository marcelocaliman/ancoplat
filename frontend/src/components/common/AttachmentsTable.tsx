import { AlertTriangle, Anchor, Plus, Settings2, Trash2, Waves } from 'lucide-react'
import { useEffect, useState } from 'react'
import {
  Controller,
  useFieldArray,
  useWatch,
  type Control,
  type Path,
  type UseFormSetValue,
} from 'react-hook-form'
import { AttachmentAdvancedDialog } from '@/components/common/AttachmentAdvancedDialog'
import { BuoyPicker } from '@/components/common/BuoyPicker'
import { EnvCard, EnvField } from '@/components/common/EnvCard'
import { UnitInput } from '@/components/common/UnitInput'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import type { BuoyOutput } from '@/api/types'
import type { CaseFormValues } from '@/lib/caseSchema'

type T = CaseFormValues

export interface AttachmentsTableProps {
  control: Control<T>
  setValue: UseFormSetValue<T>
  /** Filtra/cria attachments deste tipo. */
  kind: 'buoy' | 'clump_weight'
  basePath?: string
  /** Total de junções entre segmentos (= n_segments − 1). */
  maxJunctions: number
  /** Comprimento total da linha (m), para validar posição. */
  totalLength?: number
  /** Reservado para futura horizontal hint (≈ X m horizontal). */
  solverResult?: import('@/api/types').SolverResult | null
}

/**
 * Lista de attachments (boias OU clumps) em layout de **cards
 * individuais** (v1.0.11), estilo aba Ambiente: cada attachment
 * é um EnvCard bordado azulado com header + campos relevantes
 * (Nome, Catálogo só boia, Força, Posição, Pendant) + botão ⚙
 * para modal avançado.
 */
export function AttachmentsTable({
  control,
  setValue,
  kind,
  basePath = 'attachments',
  maxJunctions,
  totalLength,
  solverResult: _solverResult,
}: AttachmentsTableProps) {
  const attachments = useFieldArray<T, 'attachments'>({
    control,
    name: 'attachments',
  })
  const allFields = attachments.fields
  const hasJunctions = maxJunctions > 0

  // Filtra só os attachments do kind corrente; preserva realIdx no array
  // global pra apontar pros campos certos via setValue/Controller.
  const visibleItems = allFields
    .map((field, realIdx) => ({ field, realIdx }))
    .filter(
      ({ realIdx }) =>
        ((allFields[realIdx] as unknown as { kind?: string })?.kind ?? null) ===
        kind,
    )

  const [advancedIdx, setAdvancedIdx] = useState<number | null>(null)
  const Icon = kind === 'buoy' ? Waves : Anchor
  const labelKind = kind === 'buoy' ? 'Boia' : 'Clump'

  function addNew() {
    const defaultPos =
      totalLength != null && totalLength > 0 ? totalLength / 2 : 100
    attachments.append({
      kind,
      submerged_force: kind === 'buoy' ? 30_000 : 50_000,
      position_s_from_anchor: defaultPos,
      position_index: null,
      name: null,
      tether_length: 0,
      buoy_type: null,
      buoy_end_type: null,
      buoy_outer_diameter: null,
      buoy_length: null,
      buoy_weight_in_air: null,
      buoy_catalog_id: null,
      pendant_line_type: null,
      pendant_diameter: null,
    } as never)
  }

  // Empty state com hint para casos sem junção (clump precisa de junção)
  if (visibleItems.length === 0 && !hasJunctions && kind !== 'buoy') {
    return (
      <div className="rounded-md border border-primary/20 bg-primary/[0.04] p-3 text-[11px] text-muted-foreground">
        <Icon className="mr-1.5 inline h-3.5 w-3.5" />
        Adicione 1+ segmento para usar {labelKind.toLowerCase()}s.
      </div>
    )
  }

  return (
    <div className="flex flex-wrap items-stretch justify-start gap-2">
      {visibleItems.map(({ field, realIdx }, displayIdx) => (
        <AttachmentCard
          key={field.id}
          realIdx={realIdx}
          displayIdx={displayIdx}
          basePath={basePath}
          control={control}
          setValue={setValue}
          kind={kind}
          maxJunctions={maxJunctions}
          totalLength={totalLength}
          onRemove={() => attachments.remove(realIdx)}
          onOpenAdvanced={() => setAdvancedIdx(realIdx)}
        />
      ))}

      {allFields.length < 20 && (
        <button
          type="button"
          className="flex h-auto min-h-[180px] w-[160px] shrink-0 flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed border-primary/30 bg-primary/[0.02] text-primary/70 transition-colors hover:border-primary/50 hover:bg-primary/[0.06] hover:text-primary"
          onClick={addNew}
          title={`Adicionar ${labelKind.toLowerCase()}`}
        >
          <Plus className="h-5 w-5" />
          <span className="text-center text-[10px] font-medium leading-tight">
            Adicionar
            <br />
            {labelKind.toLowerCase()}
          </span>
        </button>
      )}

      {advancedIdx != null && (
        <AttachmentAdvancedDialog
          open={advancedIdx != null}
          onOpenChange={(open) => {
            if (!open) setAdvancedIdx(null)
          }}
          index={advancedIdx}
          basePath={basePath}
          control={control}
          setValue={setValue}
          kind={kind}
        />
      )}
    </div>
  )
}

/**
 * Card individual de um attachment.
 */
function AttachmentCard({
  realIdx,
  displayIdx,
  basePath,
  control,
  setValue,
  kind,
  maxJunctions,
  totalLength,
  onRemove,
  onOpenAdvanced,
}: {
  realIdx: number
  displayIdx: number
  basePath: string
  control: Control<T>
  setValue: UseFormSetValue<T>
  kind: 'buoy' | 'clump_weight'
  maxJunctions: number
  totalLength?: number
  onRemove: () => void
  onOpenAdvanced: () => void
}) {
  const labelKind = kind === 'buoy' ? 'Boia' : 'Clump'
  return (
    <EnvCard
      title={`${labelKind} ${displayIdx + 1}`}
      className="w-[260px]"
      trailing={
        <div className="flex items-center">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-5 w-5 p-0"
            onClick={onOpenAdvanced}
            title="Configuração avançada"
          >
            <Settings2 className="h-3 w-3" />
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-5 w-5 p-0 text-danger hover:bg-danger/10 hover:text-danger"
            onClick={onRemove}
            title="Remover"
          >
            <Trash2 className="h-3 w-3" />
          </Button>
        </div>
      }
    >
      <Controller
        control={control}
        name={`${basePath}.${realIdx}.name` as Path<T>}
        render={({ field }) => (
          <Input
            type="text"
            value={(field.value as string | null) ?? ''}
            onChange={(e) => field.onChange(e.target.value || null)}
            placeholder="Nome (opcional)"
            className="h-6 text-[11px]"
            maxLength={80}
          />
        )}
      />

      {kind === 'buoy' && (
        <BuoyPickerInline
          realIdx={realIdx}
          basePath={basePath}
          control={control}
          setValue={setValue}
        />
      )}

      <ForceField
        realIdx={realIdx}
        basePath={basePath}
        control={control}
        setValue={setValue}
        isBuoy={kind === 'buoy'}
      />

      <PositionField
        realIdx={realIdx}
        basePath={basePath}
        control={control}
        setValue={setValue}
        hasJunctions={maxJunctions > 0}
        totalLength={totalLength}
        maxJunction={maxJunctions - 1}
      />

      <EnvField label="Pendant" unit="m">
        <Controller
          control={control}
          name={`${basePath}.${realIdx}.tether_length` as Path<T>}
          render={({ field }) => (
            <Input
              type="number"
              step="1"
              min={0}
              value={(field.value as number | null) ?? 0}
              onChange={(e) => field.onChange(parseFloat(e.target.value || '0'))}
              placeholder="0"
              className="h-7 w-[80px] font-mono text-[11px]"
            />
          )}
        />
      </EnvField>
    </EnvCard>
  )
}

function BuoyPickerInline({
  realIdx,
  basePath,
  control,
  setValue,
}: {
  realIdx: number
  basePath: string
  control: Control<T>
  setValue: UseFormSetValue<T>
}) {
  const buoyCatalogId = useWatch({
    control,
    name: `${basePath}.${realIdx}.buoy_catalog_id` as Path<T>,
  }) as number | null | undefined

  const apply = (buoy: BuoyOutput) => {
    const p = (suffix: string) =>
      `${basePath}.${realIdx}.${suffix}` as Path<T>
    setValue(p('submerged_force'), buoy.submerged_force as never, {
      shouldValidate: true,
    })
    setValue(p('buoy_type'), buoy.buoy_type as never, { shouldValidate: true })
    setValue(p('buoy_end_type'), buoy.end_type as never, {
      shouldValidate: true,
    })
    setValue(p('buoy_outer_diameter'), buoy.outer_diameter as never, {
      shouldValidate: true,
    })
    setValue(p('buoy_length'), buoy.length as never, { shouldValidate: true })
    setValue(p('buoy_weight_in_air'), buoy.weight_in_air as never, {
      shouldValidate: true,
    })
    setValue(p('buoy_catalog_id'), buoy.id as never, { shouldValidate: false })
  }
  const clear = () => {
    setValue(
      `${basePath}.${realIdx}.buoy_catalog_id` as Path<T>,
      null as never,
      { shouldValidate: false },
    )
  }
  return (
    <BuoyPicker
      selectedId={buoyCatalogId ?? null}
      onPick={apply}
      onClear={clear}
      className="h-7 text-[11px]"
    />
  )
}

function ForceField({
  realIdx,
  basePath,
  control,
  setValue,
  isBuoy,
}: {
  realIdx: number
  basePath: string
  control: Control<T>
  setValue: UseFormSetValue<T>
  isBuoy: boolean
}) {
  const buoyCatalogId = useWatch({
    control,
    name: `${basePath}.${realIdx}.buoy_catalog_id` as Path<T>,
  }) as number | null | undefined
  const isManual = isBuoy && buoyCatalogId == null
  return (
    <EnvField label={isBuoy ? 'Empuxo' : 'Peso submerso'}>
      <div className="flex items-center gap-1">
        <Controller
          control={control}
          name={`${basePath}.${realIdx}.submerged_force` as Path<T>}
          render={({ field }) => (
            <UnitInput
              value={field.value as number}
              onChange={(v) => {
                field.onChange(v)
                if (isBuoy && buoyCatalogId != null) {
                  setValue(
                    `${basePath}.${realIdx}.buoy_catalog_id` as Path<T>,
                    null as never,
                    { shouldValidate: false },
                  )
                }
              }}
              quantity="force"
              digits={2}
              className="h-7 w-[80px]"
              inputClassName="text-[11px] py-0.5"
            />
          )}
        />
        {isManual && (
          <span
            title="Modo manual (sem vínculo com catálogo)"
            className="inline-flex h-4 items-center gap-0.5 rounded-sm bg-warning/15 px-1 text-[8px] font-semibold uppercase text-warning"
          >
            <AlertTriangle className="h-2 w-2" /> M
          </span>
        )}
      </div>
    </EnvField>
  )
}

function PositionField({
  realIdx,
  basePath,
  control,
  setValue,
  hasJunctions,
  totalLength,
  maxJunction,
}: {
  realIdx: number
  basePath: string
  control: Control<T>
  setValue: UseFormSetValue<T>
  hasJunctions: boolean
  totalLength?: number
  maxJunction: number
}) {
  const positionS = useWatch({
    control,
    name: `${basePath}.${realIdx}.position_s_from_anchor` as Path<T>,
  })
  const mode: 'distance' | 'junction' =
    positionS != null ? 'distance' : 'junction'

  // Auto-migra para distance quando perde junções (≤1 segmento)
  useEffect(() => {
    if (!hasJunctions && mode === 'junction') {
      setValue(
        `${basePath}.${realIdx}.position_s_from_anchor` as Path<T>,
        100 as never,
        { shouldValidate: true },
      )
      setValue(
        `${basePath}.${realIdx}.position_index` as Path<T>,
        null as never,
        { shouldValidate: true },
      )
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hasJunctions])

  const setMode = (next: 'distance' | 'junction') => {
    if (next === mode) return
    if (next === 'distance') {
      setValue(
        `${basePath}.${realIdx}.position_s_from_anchor` as Path<T>,
        100 as never,
        { shouldValidate: true },
      )
      setValue(
        `${basePath}.${realIdx}.position_index` as Path<T>,
        null as never,
        { shouldValidate: true },
      )
    } else {
      setValue(
        `${basePath}.${realIdx}.position_index` as Path<T>,
        0 as never,
        { shouldValidate: true },
      )
      setValue(
        `${basePath}.${realIdx}.position_s_from_anchor` as Path<T>,
        null as never,
        { shouldValidate: true },
      )
    }
  }

  return (
    <EnvField label={mode === 'distance' ? 'Pos. (m do FL)' : 'Junção'}>
      <div className="flex items-center gap-1">
        {mode === 'distance' ? (
          <Controller
            control={control}
            name={`${basePath}.${realIdx}.position_s_from_anchor` as Path<T>}
            render={({ field }) => {
              const sAnc = (field.value as number | null) ?? 0
              const sFl =
                totalLength != null && totalLength > 0
                  ? Math.max(0, totalLength - sAnc)
                  : sAnc
              return (
                <Input
                  type="number"
                  min={0.01}
                  max={totalLength ? totalLength - 0.01 : undefined}
                  step={1}
                  value={sFl}
                  onChange={(e) => {
                    const newSfl = parseFloat(e.target.value || '0')
                    const newSanc =
                      totalLength != null && totalLength > 0
                        ? Math.max(0.01, totalLength - newSfl)
                        : newSfl
                    field.onChange(newSanc)
                  }}
                  className="h-7 w-[80px] font-mono text-[11px]"
                />
              )
            }}
          />
        ) : (
          <Controller
            control={control}
            name={`${basePath}.${realIdx}.position_index` as Path<T>}
            render={({ field }) => (
              <Input
                type="number"
                min={0}
                max={maxJunction}
                step={1}
                value={(field.value as number | null) ?? 0}
                onChange={(e) =>
                  field.onChange(parseInt(e.target.value || '0', 10))
                }
                className="h-7 w-[80px] font-mono text-[11px]"
                title={`Junção ${field.value} de ${maxJunction}`}
              />
            )}
          />
        )}
        {hasJunctions && (
          <button
            type="button"
            onClick={() =>
              setMode(mode === 'distance' ? 'junction' : 'distance')
            }
            className="text-[8px] font-medium uppercase tracking-wide text-primary hover:underline"
            title={
              mode === 'distance'
                ? 'Alternar para junção'
                : 'Alternar para distância'
            }
          >
            {mode === 'distance' ? 'm' : 'J'}
          </button>
        )}
      </div>
    </EnvField>
  )
}
