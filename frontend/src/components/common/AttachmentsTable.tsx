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
import { UnitInput } from '@/components/common/UnitInput'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import type { BuoyOutput } from '@/api/types'
import type { CaseFormValues } from '@/lib/caseSchema'
import { cn } from '@/lib/utils'

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
 * Tabela de attachments (boias OU clumps) — mesmo padrão tabular do
 * SegmentsTable (estilo QMoor):
 *   - linhas = propriedades (Nome, Catálogo, Força, Posição, Pendant)
 *   - colunas = attachments individuais
 *   - "⚙ Avançado" abre modal com tipo de boia, dimensões, end_type
 *
 * Filtragem: apenas attachments com `kind` correspondente são
 * mostrados; novo attachment criado herda o `kind` da prop.
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
  const total = visibleItems.length
  const Icon = kind === 'buoy' ? Waves : Anchor
  const title = kind === 'buoy' ? 'Boias' : 'Clump weights'

  function addNew() {
    // Default sensato: posicionamento por distância (modo distance), no
    // meio da linha (totalLength/2). Pendant 0 = direto na linha.
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

  // Header: Boias (3) + ícone
  if (visibleItems.length === 0 && !hasJunctions && kind !== 'buoy') {
    return (
      <div className="rounded-md border border-border/40 bg-muted/10 p-2">
        <div className="flex items-center gap-2 text-[10px] uppercase tracking-wide text-muted-foreground">
          <Icon className="h-3.5 w-3.5" />
          <span>{title} (0)</span>
        </div>
        <p className="mt-1 px-1 text-[11px] text-muted-foreground">
          Adicione 1+ segmento para usar attachments.
        </p>
      </div>
    )
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-max border-collapse text-[11px]">
        <thead>
          <tr className="border-b border-border/40">
            <th className="sticky left-0 z-10 bg-background pr-2 text-left text-[10px] font-medium uppercase tracking-[0.05em] text-muted-foreground">
              <span className="inline-flex items-center gap-1">
                <Icon className="h-3 w-3" />
                {title} ({total})
              </span>
            </th>
            {visibleItems.map(({ field, realIdx }, displayIdx) => (
              <th
                key={field.id}
                className="min-w-[140px] px-1.5 pb-1 text-left align-bottom"
              >
                <div className="flex items-center gap-1">
                  <span className="text-[11px] font-semibold text-foreground">
                    {kind === 'buoy' ? 'Boia' : 'Clump'} {displayIdx + 1}
                  </span>
                  <div className="ml-auto flex items-center">
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      className="h-5 w-5 p-0"
                      onClick={() => setAdvancedIdx(realIdx)}
                      title="Configuração avançada (pendant, tipo de boia, dimensões)"
                    >
                      <Settings2 className="h-3 w-3" />
                    </Button>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      className="h-5 w-5 p-0 text-danger hover:bg-danger/10 hover:text-danger"
                      onClick={() => attachments.remove(realIdx)}
                      title="Remover"
                    >
                      <Trash2 className="h-3 w-3" />
                    </Button>
                  </div>
                </div>
              </th>
            ))}
            <th className="px-1.5 pb-1 align-bottom">
              {allFields.length < 20 && (
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="h-6 gap-1 border-dashed text-[10px]"
                  onClick={addNew}
                  title={`Adicionar ${kind === 'buoy' ? 'boia' : 'clump weight'}`}
                >
                  <Plus className="h-3 w-3" />
                  Adicionar
                </Button>
              )}
            </th>
          </tr>
        </thead>
        <tbody>
          {/* Nome (opcional) */}
          <PropertyRow label="Nome">
            {visibleItems.map(({ field, realIdx }) => (
              <td key={field.id} className="min-w-[140px] px-1 py-0.5">
                <Controller
                  control={control}
                  name={`${basePath}.${realIdx}.name` as Path<T>}
                  render={({ field: f }) => (
                    <Input
                      type="text"
                      value={(f.value as string | null) ?? ''}
                      onChange={(e) => f.onChange(e.target.value || null)}
                      placeholder="opcional"
                      className="h-6 text-[11px]"
                      maxLength={80}
                    />
                  )}
                />
              </td>
            ))}
            <td />
          </PropertyRow>

          {/* Catálogo (BuoyPicker) — apenas para kind=buoy */}
          {kind === 'buoy' && (
            <PropertyRow label="Catálogo">
              {visibleItems.map(({ field, realIdx }) => (
                <BuoyPickerCell
                  key={field.id}
                  realIdx={realIdx}
                  basePath={basePath}
                  control={control}
                  setValue={setValue}
                />
              ))}
              <td />
            </PropertyRow>
          )}

          {/* Força submersa */}
          <PropertyRow label={kind === 'buoy' ? 'Força (empuxo)' : 'Peso submerso'}>
            {visibleItems.map(({ field, realIdx }) => (
              <ForceCell
                key={field.id}
                realIdx={realIdx}
                basePath={basePath}
                control={control}
                setValue={setValue}
                isBuoy={kind === 'buoy'}
              />
            ))}
            <td />
          </PropertyRow>

          {/* Posição (distância do fairlead OU junção) */}
          <PropertyRow label="Posição (m do fairlead)">
            {visibleItems.map(({ field, realIdx }) => (
              <PositionCell
                key={field.id}
                realIdx={realIdx}
                basePath={basePath}
                control={control}
                setValue={setValue}
                hasJunctions={hasJunctions}
                totalLength={totalLength}
                maxJunction={maxJunctions - 1}
              />
            ))}
            <td />
          </PropertyRow>

          {/* Pendant (m) — direto na linha por default */}
          <PropertyRow label="Pendant (m)">
            {visibleItems.map(({ field, realIdx }) => (
              <td key={field.id} className="min-w-[140px] px-1 py-0.5">
                <Controller
                  control={control}
                  name={`${basePath}.${realIdx}.tether_length` as Path<T>}
                  render={({ field: f }) => (
                    <Input
                      type="number"
                      step="1"
                      min={0}
                      value={(f.value as number | null) ?? 0}
                      onChange={(e) =>
                        f.onChange(parseFloat(e.target.value || '0'))
                      }
                      placeholder="0 = direto na linha"
                      className="h-6 font-mono text-[11px]"
                    />
                  )}
                />
              </td>
            ))}
            <td />
          </PropertyRow>
        </tbody>
      </table>

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

/** Célula com BuoyPicker integrado + clear catalog link em manual edit. */
function BuoyPickerCell({
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
    <td className="min-w-[140px] px-1 py-0.5">
      <BuoyPicker
        selectedId={buoyCatalogId ?? null}
        onPick={apply}
        onClear={clear}
        className="h-6 text-[11px]"
      />
    </td>
  )
}

/** Célula da força submersa com badge MANUAL quando override do catálogo. */
function ForceCell({
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
    <td className="min-w-[140px] px-1 py-0.5">
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
              className="h-6 flex-1"
              inputClassName="text-[11px] py-0.5"
            />
          )}
        />
        {isManual && (
          <span
            title="Modo manual (sem vínculo com catálogo)"
            className="inline-flex items-center gap-0.5 rounded-sm bg-warning/15 px-1 text-[8px] font-semibold uppercase tracking-wide text-warning"
          >
            <AlertTriangle className="h-2 w-2" /> M
          </span>
        )}
      </div>
    </td>
  )
}

/** Célula de posição com toggle distance/junction. */
function PositionCell({
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
    <td className="min-w-[140px] px-1 py-0.5">
      <div className="flex items-center gap-1">
        {mode === 'distance' ? (
          <Controller
            control={control}
            name={`${basePath}.${realIdx}.position_s_from_anchor` as Path<T>}
            render={({ field }) => {
              // Storage = position_s_from_anchor (s_anc), display = s_fl
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
                  className="h-6 flex-1 font-mono text-[11px]"
                  title={
                    totalLength
                      ? `Comprimento de cabo desde o fairlead. Range válido: 0 < s_fl < ${totalLength.toFixed(1)} m`
                      : 'Comprimento de cabo (arc length) desde o fairlead'
                  }
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
                className="h-6 flex-1 font-mono text-[11px]"
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
            className="text-[8px] uppercase tracking-wide text-primary hover:underline"
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
    </td>
  )
}
