import { useMutation, useQuery } from '@tanstack/react-query'
import { Loader2, RotateCcw, Save, Sparkles } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { toast } from 'sonner'
import { ApiError } from '@/api/client'
import { previewSolve, solveCase, updateCase } from '@/api/endpoints'
import type { CaseInput, SolverResult } from '@/api/types'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Slider } from '@/components/ui/slider'
import { useDebounce } from '@/hooks/useDebounce'
import { cn, fmtMeters } from '@/lib/utils'
import { fmtForce, unitFor } from '@/lib/units'
import { useUnitsStore } from '@/store/units'

export interface SensitivityPanelProps {
  caseId: number
  /** Input baseline do caso (valores originalmente salvos). */
  baseInput: CaseInput
  /**
   * Notificado a cada nova predição ao vivo (ou `(null, null)` quando
   * sliders no zero). O segundo argumento entrega o `CaseInput` modificado
   * usado no preview — necessário para que o plot exiba o estado novo
   * de segments/attachments coerentemente com `result` (Sprint 2 / Commit 17).
   */
  onPreview: (result: SolverResult | null, input: CaseInput | null) => void
  /** Callback após aplicar mudanças com sucesso (recarregar dados do caso). */
  onApplied?: () => void
}

interface Knobs {
  /** Multiplicador do T_fl baseline (0.5 a 1.5). */
  tFlMul: number
  /**
   * Comprimento de cada segmento em metros (absoluto, índice
   * espelhando `baseInput.segments`).
   */
  segmentLengths: number[]
  /**
   * Posição em metros (s_from_anchor) de CADA attachment do caso —
   * Sprint 2 / Commit 18. Antes só o primeiro tinha slider; agora
   * boias, clumps e AHVs têm um slider individual cada.
   */
  attachmentS: number[]
}

/**
 * Painel de análise de sensibilidade — sliders ao vivo para T_fl,
 * comprimento por segmento e posição de cada attachment.
 *
 * Design (Sprint 2 / Commit 18):
 *   - μ removido (editável via aba Ambiente do form de edição).
 *   - Cada segmento tem seu próprio CARD com tom levemente mais claro
 *     (`bg-primary/[0.06]`) para destacar visualmente.
 *   - Cada attachment ganha slider individual (não só o primeiro).
 *   - Cada slider tem input numérico ao lado para entrada manual
 *     (digitar valor exato, complementando o slider).
 */
export function SensitivityPanel({
  caseId,
  baseInput,
  onPreview,
  onApplied,
}: SensitivityPanelProps) {
  const system = useUnitsStore((s) => s.system)
  const baseTfl =
    baseInput.boundary.mode === 'Tension'
      ? baseInput.boundary.input_value
      : 0
  const baseSegmentLengths = useMemo(
    () => baseInput.segments.map((s) => s.length),
    [baseInput.segments],
  )
  const baseLength = baseSegmentLengths.reduce((acc, L) => acc + L, 0)

  // Posição em arc-length-da-âncora baseline para CADA attachment.
  // position_index → conversão; position_s_from_anchor → direto.
  const attachments = useMemo(
    () => baseInput.attachments ?? [],
    [baseInput.attachments],
  )
  const baseAttachmentSList = useMemo(() => {
    return attachments.map((att) => {
      if (att.position_s_from_anchor != null) {
        return att.position_s_from_anchor
      }
      if (att.position_index != null) {
        let cum = 0
        for (let i = 0; i <= att.position_index; i += 1) {
          cum += baseInput.segments[i]?.length ?? 0
        }
        return cum
      }
      return NaN
    })
  }, [attachments, baseInput.segments])

  const [knobs, setKnobs] = useState<Knobs>({
    tFlMul: 1,
    segmentLengths: [...baseSegmentLengths],
    attachmentS: [...baseAttachmentSList],
  })

  // Snapshot dos sliders após debounce — fonte da verdade para a query.
  const debouncedKnobs = useDebounce(knobs, 300)

  // Detecta se há mudança em relação ao baseline.
  const hasChange = useMemo(() => {
    const segChanged = baseSegmentLengths.some(
      (L, i) =>
        Math.abs((debouncedKnobs.segmentLengths[i] ?? L) - L) /
          Math.max(L, 1) >
        1e-3,
    )
    const attChanged = baseAttachmentSList.some((s, i) => {
      const cur = debouncedKnobs.attachmentS[i]
      if (cur == null || Number.isNaN(s) || Number.isNaN(cur)) return false
      return Math.abs(cur - s) > 1e-2
    })
    return (
      Math.abs(debouncedKnobs.tFlMul - 1) > 1e-3 || segChanged || attChanged
    )
  }, [debouncedKnobs, baseAttachmentSList, baseSegmentLengths])

  const previewInput = useMemo<CaseInput>(() => {
    const newSegments = baseInput.segments.map((seg, i) => ({
      ...seg,
      length: debouncedKnobs.segmentLengths[i] ?? seg.length,
    }))
    const newTotalLen = newSegments.reduce((acc, s) => acc + s.length, 0)

    // Atualiza CADA attachment com a posição do seu slider individual,
    // clampada em [1%, 99%] do novo comprimento total.
    const minS = newTotalLen * 0.01
    const maxS = newTotalLen * 0.99
    const newAttachments = (baseInput.attachments ?? []).map((att, i) => {
      const proposedS = debouncedKnobs.attachmentS[i]
      if (proposedS == null || Number.isNaN(proposedS)) return att
      const newS = Math.min(maxS, Math.max(minS, proposedS))
      return { ...att, position_s_from_anchor: newS, position_index: null }
    })

    return {
      ...baseInput,
      segments: newSegments,
      attachments: newAttachments,
      boundary: {
        ...baseInput.boundary,
        input_value:
          baseInput.boundary.mode === 'Tension'
            ? baseTfl * debouncedKnobs.tFlMul
            : baseInput.boundary.input_value,
      },
      seabed: {
        ...baseInput.seabed,
        mu: baseInput.seabed?.mu ?? 0,
        slope_rad: baseInput.seabed?.slope_rad ?? 0,
      },
    }
  }, [baseInput, baseTfl, debouncedKnobs])

  const previewQuery = useQuery<SolverResult, ApiError>({
    queryKey: ['sensitivity-preview', caseId, debouncedKnobs],
    queryFn: () => previewSolve(previewInput),
    enabled: hasChange,
    retry: false,
    staleTime: 30_000,
  })

  // Propaga o resultado para o pai (e o input modificado, ver Commit 17).
  useEffect(() => {
    if (!hasChange) {
      onPreview(null, null)
      return
    }
    if (previewQuery.data) onPreview(previewQuery.data, previewInput)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hasChange, previewQuery.data, previewInput])

  const applyMutation = useMutation({
    mutationFn: async () => {
      await updateCase(caseId, previewInput)
      const exec = await solveCase(caseId)
      return exec
    },
    onSuccess: () => {
      toast.success('Mudanças aplicadas e nova execução salva.')
      reset()
      onApplied?.()
    },
    onError: (err: unknown) => {
      const msg = err instanceof ApiError ? err.message : String(err)
      toast.error('Falha ao aplicar mudanças', { description: msg })
    },
  })

  function reset() {
    setKnobs({
      tFlMul: 1,
      segmentLengths: [...baseSegmentLengths],
      attachmentS: [...baseAttachmentSList],
    })
    onPreview(null, null)
  }

  const isFetching = previewQuery.isFetching && hasChange
  const previewResult = hasChange ? previewQuery.data : null
  const errored = previewQuery.isError && hasChange

  const tFlActual = baseTfl * knobs.tFlMul
  const totalLengthActual = knobs.segmentLengths.reduce((a, b) => a + b, 0)

  return (
    <Card className="border-primary/20 bg-primary/[0.02]">
      <CardHeader className="flex flex-row items-start justify-between gap-3 pb-3">
        <div className="min-w-0">
          <CardTitle className="flex items-center gap-2 text-sm font-semibold">
            <Sparkles className="h-3.5 w-3.5 text-primary" />
            Análise de sensibilidade
            {isFetching && (
              <Loader2 className="h-3 w-3 animate-spin text-muted-foreground" />
            )}
            {hasChange && previewResult && !isFetching && (
              <Badge
                variant="secondary"
                className="h-5 bg-primary/15 text-[10px] text-primary"
              >
                preview ao vivo
              </Badge>
            )}
            {errored && (
              <Badge variant="danger" className="h-5 text-[10px]">
                inviável
              </Badge>
            )}
          </CardTitle>
          <p className="mt-0.5 text-[11px] text-muted-foreground">
            Mova os sliders ou digite o valor para ver o efeito em tempo
            real. Use <strong>Aplicar</strong> para salvar como nova execução.
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <Button
            size="sm"
            variant="outline"
            onClick={reset}
            disabled={!hasChange || applyMutation.isPending}
            title="Voltar todos os sliders ao baseline do caso"
          >
            <RotateCcw className="h-3.5 w-3.5" />
            Resetar
          </Button>
          <Button
            size="sm"
            onClick={() => applyMutation.mutate()}
            disabled={
              !hasChange || applyMutation.isPending || !previewResult || errored
            }
          >
            {applyMutation.isPending ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Save className="h-3.5 w-3.5" />
            )}
            Aplicar como nova execução
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-5 pb-4">
        {/* Linha 1 — knobs globais (T_fl).
            μ removido em Sprint 2 / Commit 18 — editar via aba Ambiente. */}
        {baseInput.boundary.mode === 'Tension' && (
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            <KnobSlider
              label="Tração no fairlead"
              valueLabel={fmtForce(tFlActual, system)}
              baselineLabel={`baseline ${fmtForce(baseTfl, system)}`}
              mul={knobs.tFlMul}
              onMulChange={(m) => setKnobs((k) => ({ ...k, tFlMul: m }))}
            />
          </div>
        )}

        {/* Linha 2 — comprimentos por segmento, cada um em CARD próprio
            com tom de azul levemente mais claro para distinguir do
            container pai. */}
        <div className="space-y-2 border-t border-border/40 pt-3">
          <div className="flex items-baseline justify-between gap-2">
            <span className="text-xs font-semibold text-foreground">
              Comprimento por segmento
              {baseInput.segments.length > 1 && (
                <span className="ml-1.5 text-[10px] font-normal text-muted-foreground">
                  ({baseInput.segments.length} segmentos)
                </span>
              )}
            </span>
            <span className="font-mono text-[10px] text-muted-foreground">
              total:{' '}
              <span className="text-foreground">
                {fmtMeters(totalLengthActual, 1)}
              </span>{' '}
              · baseline {fmtMeters(baseLength, 1)}
            </span>
          </div>
          <div
            className={cn(
              'grid grid-cols-1 gap-2',
              baseInput.segments.length === 2 && 'md:grid-cols-2',
              baseInput.segments.length === 3 && 'md:grid-cols-3',
              baseInput.segments.length >= 4 && 'md:grid-cols-2 xl:grid-cols-4',
            )}
          >
            {baseInput.segments.map((seg, idx) => {
              const baseL = baseSegmentLengths[idx] ?? seg.length
              const cur = knobs.segmentLengths[idx] ?? baseL
              const segLabel =
                baseInput.segments.length === 1
                  ? 'Comprimento da linha'
                  : `Seg ${idx + 1}${
                      seg.line_type
                        ? ` · ${seg.line_type}`
                        : seg.category
                          ? ` · ${seg.category}`
                          : ''
                    }`
              return (
                <SegmentLengthSlider
                  key={idx}
                  label={segLabel}
                  valueM={cur}
                  baselineM={baseL}
                  onChangeM={(m) =>
                    setKnobs((k) => {
                      const next = [...k.segmentLengths]
                      next[idx] = m
                      return { ...k, segmentLengths: next }
                    })
                  }
                />
              )
            })}
          </div>
        </div>

        {/* Linha 3 — posição de CADA attachment (Sprint 2 / Commit 18).
            Boias, clumps e AHVs ganham slider individual + input numérico. */}
        {attachments.length > 0 && (
          <div className="space-y-2 border-t border-border/40 pt-3">
            <div className="flex items-baseline justify-between gap-2">
              <span className="text-xs font-semibold text-foreground">
                Posição dos attachments
                <span className="ml-1.5 text-[10px] font-normal text-muted-foreground">
                  ({attachments.length}{' '}
                  {attachments.length === 1 ? 'item' : 'itens'})
                </span>
              </span>
            </div>
            <div
              className={cn(
                'grid grid-cols-1 gap-2',
                attachments.length === 2 && 'md:grid-cols-2',
                attachments.length === 3 && 'md:grid-cols-3',
                attachments.length >= 4 && 'md:grid-cols-2 xl:grid-cols-4',
              )}
            >
              {attachments.map((att, idx) => {
                const baseS = baseAttachmentSList[idx]
                if (baseS == null || Number.isNaN(baseS)) return null
                const cur = knobs.attachmentS[idx] ?? baseS
                return (
                  <AttachmentPosSlider
                    key={idx}
                    kind={att.kind}
                    name={att.name ?? null}
                    fallbackLabel={`#${idx + 1}`}
                    valueS={cur}
                    baselineS={baseS}
                    totalLength={totalLengthActual}
                    onChangeS={(s) =>
                      setKnobs((k) => {
                        const next = [...k.attachmentS]
                        next[idx] = s
                        return { ...k, attachmentS: next }
                      })
                    }
                  />
                )
              })}
            </div>
          </div>
        )}
      </CardContent>
      {errored && previewQuery.error && (
        <CardContent className="pt-0">
          <p className="rounded-md border border-danger/30 bg-danger/5 p-2 text-[11px] text-danger">
            {previewQuery.error.message ||
              'Caso inviável com os parâmetros atuais. Ajuste os sliders.'}
          </p>
        </CardContent>
      )}
      <input
        type="hidden"
        data-unit={unitFor('force', system)}
      />
    </Card>
  )
}

// ──────────────────────────────────────────────────────────────────
// Sub-components
// ──────────────────────────────────────────────────────────────────

function KnobSlider({
  label,
  valueLabel,
  baselineLabel,
  mul,
  onMulChange,
}: {
  label: string
  valueLabel: string
  baselineLabel: string
  mul: number
  onMulChange: (mul: number) => void
}) {
  // Slider opera em 0..100 mapeado para mul ∈ [0.5, 1.5].
  const sliderValue = ((mul - 0.5) / 1.0) * 100
  const pct = ((mul - 1) * 100).toFixed(0)
  const positive = mul > 1
  return (
    <div className="space-y-1.5 rounded-md border border-primary/15 bg-primary/[0.06] p-2.5">
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-xs font-medium text-foreground">{label}</span>
        <span className="font-mono text-[10px] text-muted-foreground">
          {baselineLabel}
        </span>
      </div>
      <Slider
        min={0}
        max={100}
        step={1}
        value={[sliderValue]}
        onValueChange={(v) => {
          const sv = v[0] ?? 50
          onMulChange(0.5 + (sv / 100) * 1.0)
        }}
      />
      <div className="flex items-baseline justify-between gap-2">
        <span className="font-mono text-sm font-semibold tabular-nums">
          {valueLabel}
        </span>
        <span
          className={`font-mono text-[10px] tabular-nums ${
            Math.abs(mul - 1) < 1e-3
              ? 'text-muted-foreground'
              : positive
                ? 'text-warning'
                : 'text-success'
          }`}
        >
          {Math.abs(mul - 1) < 1e-3 ? '—' : `${positive ? '+' : ''}${pct}%`}
        </span>
      </div>
    </div>
  )
}

/**
 * Slider + input numérico de posição de attachment (boia/clump/AHV).
 * Range: 1%–99% do `totalLength` atual.
 */
function AttachmentPosSlider({
  kind,
  name,
  fallbackLabel,
  valueS,
  baselineS,
  totalLength,
  onChangeS,
}: {
  kind: 'buoy' | 'clump_weight' | 'ahv'
  name: string | null
  fallbackLabel: string
  valueS: number
  baselineS: number
  totalLength: number
  onChangeS: (s: number) => void
}) {
  const minS = totalLength * 0.01
  const maxS = totalLength * 0.99
  const range = Math.max(maxS - minS, 0.01)
  const sliderValue = ((valueS - minS) / range) * 1000
  const isChanged = Math.abs(valueS - baselineS) > 1e-2
  const labelKind =
    kind === 'buoy' ? 'Boia' : kind === 'clump_weight' ? 'Clump' : 'AHV'
  const labelName = name ? `"${name}"` : fallbackLabel
  return (
    <div className="space-y-1.5 rounded-md border border-primary/15 bg-primary/[0.06] p-2.5">
      <div className="flex items-baseline justify-between gap-2">
        <span className="truncate text-xs font-medium text-foreground">
          {labelKind} {labelName}
        </span>
        <span className="font-mono text-[10px] text-muted-foreground">
          baseline {baselineS.toFixed(1)} m
        </span>
      </div>
      <Slider
        min={0}
        max={1000}
        step={1}
        value={[Math.max(0, Math.min(1000, sliderValue))]}
        onValueChange={(v) => {
          const sv = v[0] ?? 500
          const s = minS + (sv / 1000) * range
          onChangeS(s)
        }}
      />
      <div className="flex items-baseline justify-between gap-2">
        <NumberInput
          value={valueS}
          step={1}
          min={0}
          onChange={(n) => onChangeS(n)}
          unit="m"
        />
        <span
          className={`font-mono text-[10px] tabular-nums ${
            isChanged ? 'text-warning' : 'text-muted-foreground'
          }`}
        >
          {isChanged
            ? `${valueS > baselineS ? '+' : ''}${(valueS - baselineS).toFixed(1)} m`
            : '—'}
        </span>
      </div>
    </div>
  )
}

/**
 * Slider + input numérico de comprimento de UM segmento. Range: 0.5×–1.5×
 * baseline. Input numérico aceita valores fora do range do slider
 * (mantém valor digitado, slider trava no extremo visualmente).
 */
function SegmentLengthSlider({
  label,
  valueM,
  baselineM,
  onChangeM,
}: {
  label: string
  valueM: number
  baselineM: number
  onChangeM: (m: number) => void
}) {
  const minM = baselineM * 0.5
  const maxM = baselineM * 1.5
  const range = Math.max(maxM - minM, 0.001)
  const sliderValue = ((valueM - minM) / range) * 100
  const delta = valueM - baselineM
  const pctDelta = baselineM > 0 ? (delta / baselineM) * 100 : 0
  const isChanged = Math.abs(pctDelta) > 0.05
  return (
    <div className="space-y-1.5 rounded-md border border-primary/15 bg-primary/[0.06] p-2.5">
      <div className="flex items-baseline justify-between gap-2">
        <span className="truncate text-xs font-medium text-foreground">
          {label}
        </span>
        <span className="font-mono text-[10px] text-muted-foreground">
          baseline {baselineM.toFixed(1)} m
        </span>
      </div>
      <Slider
        min={0}
        max={100}
        step={1}
        value={[Math.max(0, Math.min(100, sliderValue))]}
        onValueChange={(v) => {
          const sv = v[0] ?? 50
          onChangeM(minM + (sv / 100) * range)
        }}
      />
      <div className="flex items-baseline justify-between gap-2">
        <NumberInput
          value={valueM}
          step={0.5}
          min={0}
          onChange={(n) => onChangeM(n)}
          unit="m"
        />
        <span
          className={`font-mono text-[10px] tabular-nums ${
            !isChanged
              ? 'text-muted-foreground'
              : delta > 0
                ? 'text-warning'
                : 'text-success'
          }`}
        >
          {!isChanged
            ? '—'
            : `${delta > 0 ? '+' : ''}${pctDelta.toFixed(0)}%`}
        </span>
      </div>
    </div>
  )
}

/**
 * Input numérico estilizado pareado com sliders. Mostra o valor com
 * uma casa decimal por padrão; aceita digitação livre e propaga via
 * onChange somente quando o número é finito.
 */
function NumberInput({
  value,
  step,
  min,
  onChange,
  unit,
}: {
  value: number
  step: number
  min?: number
  onChange: (n: number) => void
  unit?: string
}) {
  return (
    <div className="flex items-baseline gap-1">
      <Input
        type="number"
        step={step}
        min={min}
        value={Number.isFinite(value) ? value.toFixed(1) : ''}
        onChange={(e) => {
          const n = parseFloat(e.target.value)
          if (Number.isFinite(n)) onChange(n)
        }}
        className="h-7 w-24 font-mono text-sm font-semibold tabular-nums"
      />
      {unit && (
        <span className="font-mono text-[10px] text-muted-foreground">
          {unit}
        </span>
      )}
    </div>
  )
}
