import { ArrowDown, ArrowUp, Trash2 } from 'lucide-react'
import { Children, cloneElement, isValidElement, useId, type ReactNode } from 'react'
import {
  Controller,
  type Control,
  type FieldValues,
  type Path,
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

export interface SegmentEditorProps<T extends FieldValues = CaseFormValues> {
  index: number
  total: number
  control: Control<T>
  register: UseFormRegister<T>
  watch: UseFormWatch<T>
  setValue: UseFormSetValue<T>
  /**
   * Caminho-base para os segmentos no form (default `'segments'`).
   * Use, por exemplo, `'lines.0.segments'` para reusar este editor
   * dentro de um sistema multi-linha onde cada linha tem seu próprio
   * array de segmentos.
   */
  basePath?: string
  onRemove?: () => void
  onMoveUp?: () => void
  onMoveDown?: () => void
}

/**
 * Editor de um único segmento. Recebe o `index` e um `basePath` para
 * que todos os campos apontem para `${basePath}[index].*`. Estado vive
 * no react-hook-form do pai; aqui só renderizamos.
 *
 * Convenção de ordem:
 *   - index 0 é o segmento mais próximo da âncora (chain inferior, etc.)
 *   - último index é o segmento mais próximo do fairlead
 */
export function SegmentEditor<T extends FieldValues = CaseFormValues>({
  index,
  total,
  control,
  register,
  watch,
  setValue,
  basePath = 'segments',
  onRemove,
  onMoveUp,
  onMoveDown,
}: SegmentEditorProps<T>) {
  // Helper: junta basePath + índice + sufixo, com cast de tipo confinado
  // (Path<T> em runtime é só uma string; o react-hook-form despacha por
  // string interna). Mantém o boundary do componente tipado.
  const p = (suffix: string): Path<T> =>
    `${basePath}.${index}.${suffix}` as Path<T>

  /**
   * Aplica os campos do catálogo (`LineTypeOutput`) ao segmento.
   *
   * Fase 1: aceita `eaSource` para escolher entre coluna `qmoor_ea`
   * (estática, default) ou `gmoor_ea` (dinâmica, modelo NREL/MoorPy
   * — ver CLAUDE.md). Quando `gmoor` é solicitado mas o catálogo tem
   * `gmoor_ea = null`, faz fallback para `qmoor_ea` com toast de aviso
   * (defesa em UI alinhada com a validação 422 do backend Q4).
   *
   * Também popula `seabed_friction_cf` automaticamente — passa a ser
   * a fonte de verdade do atrito quando o usuário não fizer override.
   */
  function applyLineTypeToSegment(
    lt: LineTypeOutput | null,
    eaSource: 'qmoor' | 'gmoor' = 'qmoor',
  ) {
    if (!lt) return

    // Resolve EA conforme ea_source pedido
    let chosenEA: number
    let appliedSource: 'qmoor' | 'gmoor' = eaSource
    if (eaSource === 'gmoor') {
      if (lt.gmoor_ea != null) {
        chosenEA = lt.gmoor_ea
      } else {
        // Fallback silencioso para qmoor + toast de aviso
        chosenEA = lt.qmoor_ea ?? 0
        appliedSource = 'qmoor'
        toast.warning(
          `${lt.line_type}: catálogo não tem GMoor EA. Aplicando QMoor.`,
        )
      }
    } else {
      chosenEA = lt.qmoor_ea ?? lt.gmoor_ea ?? 0
    }

    setValue(p('line_type'), lt.line_type as never, { shouldValidate: true })
    setValue(p('category'), lt.category as never, { shouldValidate: true })
    setValue(p('w'), roundTo(lt.wet_weight, 2) as never, { shouldValidate: true })
    setValue(p('EA'), roundTo(chosenEA, 0) as never, { shouldValidate: true })
    setValue(p('ea_source'), appliedSource as never, { shouldValidate: true })
    setValue(p('MBL'), roundTo(lt.break_strength, 0) as never, { shouldValidate: true })
    setValue(p('diameter'), roundTo(lt.diameter, 5) as never, { shouldValidate: true })
    setValue(p('dry_weight'), roundTo(lt.dry_weight, 2) as never, { shouldValidate: true })
    if (lt.modulus) {
      setValue(p('modulus'), roundTo(lt.modulus, 0) as never, { shouldValidate: true })
    }
    // Atrito do catálogo (Fase 1 / B3) — populado quando line_type é
    // aplicado. mu_override do usuário (se houver) tem precedência.
    if (lt.seabed_friction_cf != null) {
      setValue(
        p('seabed_friction_cf'),
        lt.seabed_friction_cf as never,
        { shouldValidate: true },
      )
    }

    toast.success(`${lt.line_type} aplicado ao segmento ${index + 1}`, {
      description: `Ø ${fmtDiameterMM(lt.diameter, 0)} · MBL ${fmtNumber(
        lt.break_strength / 1000, 0,
      )} kN · EA ${appliedSource.toUpperCase()}`,
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
        name={p('line_type')}
        render={({ field }) => (
          <LineTypePicker
            value={
              field.value
                ? ({
                    id: 0,
                    line_type: field.value as string,
                    category:
                      (watch(p('category')) as string | null) ?? 'Wire',
                    diameter: (watch(p('diameter')) as number) ?? 0,
                    dry_weight: (watch(p('dry_weight')) as number) ?? 0,
                    wet_weight: watch(p('w')) as number,
                    break_strength: watch(p('MBL')) as number,
                    qmoor_ea: watch(p('EA')) as number,
                    data_source: 'legacy_qmoor',
                  } as LineTypeOutput)
                : null
            }
            onChange={(lt) =>
              applyLineTypeToSegment(
                lt,
                (watch(p('ea_source')) as 'qmoor' | 'gmoor' | undefined) ??
                  'qmoor',
              )
            }
          />
        )}
      />

      <div className="grid grid-cols-2 gap-x-2 gap-y-1.5">
        <InlineLabeled label="Comprimento" unit="m" required>
          <Input
            type="number"
            step="1"
            {...register(p('length'), { valueAsNumber: true })}
            className="h-7 font-mono"
          />
        </InlineLabeled>
        <InlineLabeled label="Diâmetro" unit="m">
          <Input
            type="number"
            step="0.001"
            min="0"
            {...register(p('diameter'), { valueAsNumber: true })}
            className="h-7 font-mono"
          />
        </InlineLabeled>
        <InlineLabeled label="Categoria" className="col-span-2">
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
        </InlineLabeled>
        <InlineLabeled label="Peso submerso" required>
          <Controller
            control={control}
            name={p('w')}
            render={({ field }) => (
              <UnitInput
                value={field.value as number}
                onChange={field.onChange}
                quantity="force_per_m"
                digits={2}
                className="h-7"
              />
            )}
          />
        </InlineLabeled>
        <InlineLabeled label="Peso seco">
          <Controller
            control={control}
            name={p('dry_weight')}
            render={({ field }) => (
              <UnitInput
                value={(field.value as number | null) ?? null}
                onChange={field.onChange}
                quantity="force_per_m"
                digits={2}
                className="h-7"
              />
            )}
          />
        </InlineLabeled>
        <InlineLabeled label="EA">
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
        </InlineLabeled>
        <InlineLabeled label="MBL">
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
        </InlineLabeled>
        <InlineLabeled label="Módulo" unit="Pa" className="col-span-2">
          <Input
            type="number"
            step="1e9"
            {...register(p('modulus'), { valueAsNumber: true })}
            className="h-7 font-mono"
          />
        </InlineLabeled>
        {/* ─── Fase 1: EA source + atrito per-segmento (lado a lado) ─ */}
        <InlineLabeled label="EA source">
          <Controller
            control={control}
            name={p('ea_source')}
            render={({ field }) => (
              <Select
                value={(field.value as string | undefined) ?? 'qmoor'}
                onValueChange={field.onChange}
              >
                <SelectTrigger className="h-7 text-[11px]" title="EA estático (QMoor) ou dinâmico (GMoor — modelo NREL/MoorPy). Default QMoor.">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="qmoor">QMoor (estático)</SelectItem>
                  <SelectItem value="gmoor">GMoor (dinâmico)</SelectItem>
                </SelectContent>
              </Select>
            )}
          />
        </InlineLabeled>
        <InlineLabeled label="μ override" unit="">
          <Input
            type="number"
            step="0.05"
            min="0"
            placeholder={(() => {
              const cf = watch(p('seabed_friction_cf')) as number | null
              return cf != null
                ? `Catálogo: ${fmtNumber(cf, 2)} (deixe vazio p/ usar)`
                : 'Vazio = usa global do seabed'
            })()}
            {...register(p('mu_override'), {
              setValueAs: (v) =>
                v === '' || v == null ? null : Number(v),
            })}
            className="h-7 font-mono"
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
  required,
}: {
  label: string
  unit?: string
  className?: string
  children: React.ReactNode
  /** Marca o campo como obrigatório — adiciona `aria-required` no input. */
  required?: boolean
}) {
  // F9 / Q8 — a11y: gera id determinístico para associar Label↔Input
  // sem precisar mexer em todos os call sites. Children pode ser
  // <Input> direto ou um <Controller render={...}> — em ambos os casos,
  // cloneElement injeta `id` (e `aria-required` se aplicável) no primeiro
  // child renderizado.
  const id = useId()
  const enhancedChild = injectA11y(children, { id, required })
  return (
    <div className={cn('flex flex-col gap-0.5', className)}>
      <Label
        htmlFor={id}
        className="flex items-center justify-between gap-1 text-[10px] font-medium text-muted-foreground"
      >
        <span className="truncate">
          {label}
          {required && (
            <span aria-hidden className="text-danger">
              {' '}
              *
            </span>
          )}
        </span>
        {unit && (
          <span className="shrink-0 font-mono text-[9px] font-normal">{unit}</span>
        )}
      </Label>
      {enhancedChild}
    </div>
  )
}

function roundTo(value: number, digits: number): number {
  const f = 10 ** digits
  return Math.round(value * f) / f
}

/**
 * F9 / Q8 — Injeta `id` (para Label↔Input via htmlFor) e `aria-required`
 * no primeiro child concreto. Lida com:
 *   - Input direto: cloneElement adiciona props.
 *   - Controller render: criança é tipicamente um Fragment ou wrapper —
 *     cloneElement aplica no primeiro nível; props passam via spread.
 *   - Wrappers customizados (UnitInput): se o componente aceita id /
 *     aria-* via spread, herda automaticamente.
 *
 * Quando o tipo do children não suporta esses props (raro), o id ainda
 * fica registrado no Label — Tab para o input continua funcionando via
 * sequência DOM, e screen readers leem o label associado pela proximidade.
 */
function injectA11y(
  children: ReactNode,
  props: { id: string; required?: boolean },
): ReactNode {
  const onlyChild = Children.toArray(children)[0]
  if (!isValidElement(onlyChild)) return children
  const extra: Record<string, unknown> = { id: props.id }
  if (props.required) extra['aria-required'] = true
  return cloneElement(
    onlyChild as React.ReactElement<Record<string, unknown>>,
    extra,
  )
}

export { injectA11y as __injectA11yForTesting }
