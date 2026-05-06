import { Anchor, CheckCircle2, Loader2, Plus, Sparkles, Trash2, XCircle } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'
import {
  Controller,
  type Control,
  type Path,
  type UseFormSetValue,
  type UseFormGetValues,
} from 'react-hook-form'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { UnitInput } from '@/components/common/UnitInput'
import {
  iterateBollardPullForTargetX,
  type IterationStep,
  type IterationResult,
} from '@/lib/ahvIteration'
import type { CaseFormValues } from '@/lib/caseSchema'
import type { CaseInput } from '@/api/types'

type T = CaseFormValues

export interface AHVInstallEditorProps {
  control: Control<T>
  setValue: UseFormSetValue<T>
  /** Necessário para ler o caseInput completo durante iteração. */
  getValues?: UseFormGetValues<T>
  /** Valor atual do ahv_install (vindo do useWatch ou form). */
  ahvInstall: CaseFormValues['boundary']['ahv_install']
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
  getValues,
  ahvInstall,
}: AHVInstallEditorProps) {
  const has = ahvInstall != null

  const p = (suffix: keyof NonNullable<CaseFormValues['boundary']['ahv_install']>) =>
    `boundary.ahv_install.${suffix}` as Path<T>

  // Sprint 3 / Commit 30 — estado da iteração automática.
  const [iterRunning, setIterRunning] = useState(false)
  const [iterSteps, setIterSteps] = useState<IterationStep[]>([])
  const [iterResult, setIterResult] = useState<IterationResult | null>(null)

  const handleApplyViaSensitivity = async () => {
    if (!getValues || !ahvInstall?.target_horz_distance) return
    const formValues = getValues()
    // Constrói CaseInput-like a partir do form. Preserve ahv_install
    // pra que o solver use bollard_pull em mode Tension.
    const caseInput = formValues as unknown as CaseInput
    const targetX = ahvInstall.target_horz_distance

    setIterRunning(true)
    setIterSteps([])
    setIterResult(null)

    try {
      const result = await iterateBollardPullForTargetX(
        caseInput,
        targetX,
        {
          tolerance: 0.5,
          maxIters: 12,
          onStep: (step) => setIterSteps((prev) => [...prev, step]),
        },
      )
      setIterResult(result)
      if (result.converged) {
        // Aplica o bollard_pull encontrado ao form
        setValue('boundary.ahv_install.bollard_pull', result.bollardPullFinal, {
          shouldDirty: true,
        })
        toast.success(
          `Convergiu: bollard pull = ${(result.bollardPullFinal / 9806.65).toFixed(1)} te ` +
            `(X = ${result.xResultFinal?.toFixed(1)} m, erro ${result.errorFinal?.toFixed(2)} m)`,
        )
      } else {
        // Não convergiu na tolerância — mostra resultado mas NÃO aplica.
        // User pode clicar "Aplicar mesmo assim" no botão da tabela
        // de progresso (handleApplyBestFound).
        const errStr = result.errorFinal?.toFixed(1) ?? '—'
        const errPct =
          result.errorFinal != null && targetX > 0
            ? ((result.errorFinal / targetX) * 100).toFixed(1)
            : null
        toast.warning(
          `Não convergiu (${result.stopReason}). Melhor: ` +
            `${(result.bollardPullFinal / 9806.65).toFixed(1)} te, ` +
            `erro ${errStr} m${errPct ? ` (${errPct}%)` : ''}. ` +
            'Veja tabela e aplique se OK.',
        )
      }
    } catch (err) {
      toast.error(
        'Iteração falhou: ' + (err instanceof Error ? err.message : String(err)),
      )
    } finally {
      setIterRunning(false)
    }
  }

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
            {ahvInstall?.target_horz_distance != null && getValues && (
              <div className="space-y-2">
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
                    onClick={handleApplyViaSensitivity}
                    disabled={iterRunning}
                  >
                    {iterRunning ? (
                      <Loader2 className="h-3 w-3 animate-spin" />
                    ) : (
                      <Sparkles className="h-3 w-3" />
                    )}
                    {iterRunning ? 'Iterando…' : 'Aplicar via Sensitivity'}
                  </Button>
                </div>
                {(iterRunning || iterSteps.length > 0) && (
                  <IterationProgress
                    steps={iterSteps}
                    result={iterResult}
                    targetX={ahvInstall.target_horz_distance}
                    running={iterRunning}
                    onApplyAnyway={() => {
                      if (iterResult && iterResult.bollardPullFinal > 0) {
                        setValue(
                          'boundary.ahv_install.bollard_pull',
                          iterResult.bollardPullFinal,
                          { shouldDirty: true },
                        )
                        toast.info(
                          `Aplicado: ${(iterResult.bollardPullFinal / 9806.65).toFixed(1)} te ` +
                            `(erro ${iterResult.errorFinal?.toFixed(1) ?? '—'} m)`,
                        )
                      }
                    }}
                  />
                )}
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

function IterationProgress({
  steps,
  result,
  targetX,
  running,
  onApplyAnyway,
}: {
  steps: IterationStep[]
  result: IterationResult | null
  targetX: number
  running: boolean
  onApplyAnyway?: () => void
}) {
  const bestErr = steps
    .filter((s) => s.error != null)
    .reduce<number>((min, s) => Math.min(min, s.error!), Infinity)
  return (
    <div className="rounded-md border border-border/60 bg-muted/20 p-2 text-[10px]">
      <div className="mb-1.5 flex items-center justify-between gap-2">
        <span className="font-medium text-foreground">
          Iteração de bollard pull
          {running && (
            <Loader2 className="ml-2 inline h-3 w-3 animate-spin" />
          )}
          {!running && result?.converged && (
            <CheckCircle2 className="ml-2 inline h-3 w-3 text-success" />
          )}
          {!running && result && !result.converged && (
            <XCircle className="ml-2 inline h-3 w-3 text-warning" />
          )}
        </span>
        <span className="font-mono text-muted-foreground">
          target = {targetX.toFixed(1)} m
        </span>
      </div>
      <div className="max-h-40 overflow-y-auto rounded border border-border/40 bg-background/40">
        <table className="w-full text-[10px] tabular-nums">
          <thead>
            <tr className="border-b border-border/40 text-left text-muted-foreground">
              <th className="px-1.5 py-0.5">#</th>
              <th className="px-1.5 py-0.5">bollard (te)</th>
              <th className="px-1.5 py-0.5">X (m)</th>
              <th className="px-1.5 py-0.5">erro (m)</th>
              <th className="px-1.5 py-0.5">status</th>
            </tr>
          </thead>
          <tbody>
            {steps.map((s) => {
              const isBest = s.error != null && s.error === bestErr
              return (
                <tr
                  key={s.iter}
                  className={
                    isBest
                      ? 'bg-success/10 font-medium'
                      : s.status !== 'converged'
                      ? 'text-muted-foreground'
                      : ''
                  }
                >
                  <td className="px-1.5 py-0.5">{s.iter}</td>
                  <td className="px-1.5 py-0.5 font-mono">
                    {(s.bollardPull / 9806.65).toFixed(1)}
                  </td>
                  <td className="px-1.5 py-0.5 font-mono">
                    {s.xResult != null ? s.xResult.toFixed(1) : '—'}
                  </td>
                  <td className="px-1.5 py-0.5 font-mono">
                    {s.error != null ? s.error.toFixed(2) : '—'}
                  </td>
                  <td className="px-1.5 py-0.5 text-[9px]">
                    {s.status === 'converged'
                      ? '✓'
                      : s.status === 'pending'
                      ? '…'
                      : s.status}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      {result && !running && (
        <div className="mt-1.5">
          {result.converged ? (
            <p className="text-[10px] text-muted-foreground">
              ✓ Convergiu em {steps.length} avaliações.{' '}
              <strong>
                Bollard final = {(result.bollardPullFinal / 9806.65).toFixed(1)} te
              </strong>{' '}
              (aplicado ao form). X = {result.xResultFinal?.toFixed(1)} m,
              erro = {result.errorFinal?.toFixed(2)} m.
            </p>
          ) : (
            <div className="flex items-center justify-between gap-2">
              <p className="flex-1 text-[10px] text-muted-foreground">
                Não convergiu na tolerância 0.5m ({result.stopReason}).{' '}
                <strong>
                  Melhor: {(result.bollardPullFinal / 9806.65).toFixed(1)} te
                </strong>
                {result.errorFinal != null && (
                  <>
                    {' '}— erro {result.errorFinal.toFixed(1)} m
                    {targetX > 0 && (
                      <>{' '}({((result.errorFinal / targetX) * 100).toFixed(1)}%)</>
                    )}
                  </>
                )}
                .
              </p>
              {onApplyAnyway && result.bollardPullFinal > 0 && (
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="h-6 shrink-0 gap-1 text-[10px]"
                  onClick={onApplyAnyway}
                >
                  <CheckCircle2 className="h-3 w-3" /> Aplicar mesmo assim
                </Button>
              )}
            </div>
          )}
        </div>
      )}
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
