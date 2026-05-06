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
import { Slider } from '@/components/ui/slider'
import { useDebounce } from '@/hooks/useDebounce'
import { cn, fmtMeters, fmtNumber } from '@/lib/utils'
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
   * de segments/attachments coerentemente com `result` (sem isso o
   * `buildPostSplitStructure` usa segs antigos e mapeia attachments na
   * junção errada).
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
   * espelhando `baseInput.segments`). Cada segmento tem seu próprio
   * slider — engenheiro varia componentes individualmente
   * (ex.: chain do trecho âncora ↔ wire do trecho médio).
   */
  segmentLengths: number[]
  /** Atrito absoluto, 0 a 1.5 (μ não escala bem com multiplicador). */
  mu: number
  /**
   * Posição em metros (s_from_anchor) do PRIMEIRO attachment.
   * Quando o caso não tem attachments, este knob é ignorado pelo
   * preview e o slider correspondente é ocultado.
   */
  attachmentS: number
}

/**
 * Painel de análise de sensibilidade — sliders que ajustam T_fl, L e μ
 * em torno do valor original do caso e dispara `solve/preview` ao vivo.
 *
 * Estado interno mínimo: 3 knobs. O resultado preview é propagado para
 * o pai via `onPreview` para que o gráfico e cards reflitam imediatamente.
 *
 * Aplicação persistente: PATCH no caso com novos valores + POST /solve
 * para criar uma nova execução.
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
  // Comprimento BASE = soma de TODOS os segmentos. O slider escala
  // todos proporcionalmente (mantém razão entre segmentos quando
  // multi-segmento — antes do fix, só o primeiro segmento entrava no
  // preview e os demais sumiam do gráfico).
  const baseSegmentLengths = useMemo(
    () => baseInput.segments.map((s) => s.length),
    [baseInput.segments],
  )
  const baseLength = baseSegmentLengths.reduce((acc, L) => acc + L, 0)
  const baseMu = baseInput.seabed?.mu ?? 0

  // Atalho para o primeiro attachment do caso (se existir). Posição
  // baseline em arc length da âncora — convertida de position_index
  // quando necessário.
  const firstAttachment = baseInput.attachments?.[0]
  const baseAttachmentS = useMemo(() => {
    if (!firstAttachment) return NaN
    if (firstAttachment.position_s_from_anchor != null) {
      return firstAttachment.position_s_from_anchor
    }
    if (firstAttachment.position_index != null) {
      // Junção j está no arc length cumulativo após j+1 segmentos.
      let cum = 0
      for (let i = 0; i <= firstAttachment.position_index; i += 1) {
        cum += baseInput.segments[i]?.length ?? 0
      }
      return cum
    }
    return NaN
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [firstAttachment, baseInput.segments])

  const [knobs, setKnobs] = useState<Knobs>({
    tFlMul: 1,
    segmentLengths: [...baseSegmentLengths],
    mu: baseMu,
    attachmentS: baseAttachmentS,
  })

  // Snapshot dos sliders após debounce — fonte da verdade para a query.
  const debouncedKnobs = useDebounce(knobs, 300)

  // Detecta se há mudança em relação ao baseline. Quando NÃO há, devolve
  // null para o pai (isto é, o componente "se desliga" e o app volta a
  // mostrar o resultado salvo).
  const hasChange = useMemo(
    () => {
      const segChanged = baseSegmentLengths.some(
        (L, i) =>
          Math.abs((debouncedKnobs.segmentLengths[i] ?? L) - L) /
            Math.max(L, 1) >
          1e-3,
      )
      const attChanged =
        firstAttachment != null &&
        !Number.isNaN(baseAttachmentS) &&
        !Number.isNaN(debouncedKnobs.attachmentS) &&
        Math.abs(debouncedKnobs.attachmentS - baseAttachmentS) > 1e-2
      return (
        Math.abs(debouncedKnobs.tFlMul - 1) > 1e-3 ||
        segChanged ||
        Math.abs(debouncedKnobs.mu - baseMu) > 1e-3 ||
        attChanged
      )
    },
    [debouncedKnobs, baseMu, baseAttachmentS, firstAttachment, baseSegmentLengths],
  )

  const previewInput = useMemo<CaseInput>(() => {
    // Aplica os comprimentos individuais de cada segmento. Cada um
    // tem seu próprio slider — engenheiro pode esticar só o trecho
    // de wire mantendo as chains; ou variar só o pendant superior.
    const newSegments = baseInput.segments.map((seg, i) => ({
      ...seg,
      length: debouncedKnobs.segmentLengths[i] ?? seg.length,
    }))
    const newTotalLen = newSegments.reduce((acc, s) => acc + s.length, 0)

    // Atualiza o primeiro attachment com a posição do slider quando
    // o usuário moveu o slider de posição da boia. Caso contrário,
    // mantém attachments no input original (eles seguem em arc length
    // ABSOLUTO; se um segmento mudou de tamanho e o attachment cair
    // num segmento diferente agora, o resolver lida com isso via
    // split automático).
    let newAttachments = baseInput.attachments ?? []
    if (
      firstAttachment != null &&
      !Number.isNaN(debouncedKnobs.attachmentS)
    ) {
      const minS = newTotalLen * 0.01
      const maxS = newTotalLen * 0.99
      const newS = Math.min(maxS, Math.max(minS, debouncedKnobs.attachmentS))
      newAttachments = newAttachments.map((att, i) =>
        i === 0
          ? { ...att, position_s_from_anchor: newS, position_index: null }
          : att,
      )
    }

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
        mu: Math.max(0, debouncedKnobs.mu),
        slope_rad: baseInput.seabed?.slope_rad ?? 0,
      },
    }
  }, [baseInput, baseTfl, debouncedKnobs, firstAttachment])

  const previewQuery = useQuery<SolverResult, ApiError>({
    queryKey: ['sensitivity-preview', caseId, debouncedKnobs],
    queryFn: () => previewSolve(previewInput),
    enabled: hasChange,
    retry: false,
    staleTime: 30_000,
  })

  // Propaga o resultado para o pai. Quando hasChange = false, devolve null
  // para que o pai volte a mostrar o resultado salvo.
  useEffect(() => {
    if (!hasChange) {
      onPreview(null, null)
      return
    }
    if (previewQuery.data) onPreview(previewQuery.data, previewInput)
    // Em erro/loading mantém o último válido para evitar flicker.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hasChange, previewQuery.data, previewInput])

  const applyMutation = useMutation({
    mutationFn: async () => {
      // 1. Atualiza o caso com os valores dos sliders.
      await updateCase(caseId, previewInput)
      // 2. Dispara solve, que persiste a execução (#N do histórico).
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
      mu: baseMu,
      attachmentS: baseAttachmentS,
    })
    onPreview(null, null)
  }

  const isFetching = previewQuery.isFetching && hasChange
  const previewResult = hasChange ? previewQuery.data : null
  const errored = previewQuery.isError && hasChange

  // Faixas dos sliders: ±50% para multiplicadores; μ vai de 0 a 1.5.
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
            Mova os sliders para ver o efeito em tempo real. As tabelas, o
            gráfico e os cards refletem o preview enquanto você ajusta. Use{' '}
            <strong>Aplicar</strong> para salvar como nova execução.
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
              !hasChange ||
              isFetching ||
              errored ||
              applyMutation.isPending ||
              !previewResult
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
        {/* Linha 1 — knobs globais (T_fl, μ, posição da boia) */}
        <div
          className={cn(
            'grid grid-cols-1 gap-5',
            firstAttachment && !Number.isNaN(baseAttachmentS)
              ? 'md:grid-cols-3'
              : 'md:grid-cols-2',
          )}
        >
          {baseInput.boundary.mode === 'Tension' && (
            <KnobSlider
              label="Tração no fairlead"
              valueLabel={fmtForce(tFlActual, system)}
              baselineLabel={`baseline ${fmtForce(baseTfl, system)}`}
              mul={knobs.tFlMul}
              onMulChange={(m) => setKnobs((k) => ({ ...k, tFlMul: m }))}
            />
          )}
          <MuSlider
            mu={knobs.mu}
            baselineLabel={`baseline ${fmtNumber(baseMu, 2)}`}
            onChange={(mu) => setKnobs((k) => ({ ...k, mu }))}
          />
          {firstAttachment && !Number.isNaN(baseAttachmentS) && (
            <AttachmentPosSlider
              kind={firstAttachment.kind}
              name={firstAttachment.name ?? null}
              valueS={knobs.attachmentS}
              baselineS={baseAttachmentS}
              totalLength={totalLengthActual}
              countOthers={(baseInput.attachments ?? []).length - 1}
              onChangeS={(s) =>
                setKnobs((k) => ({ ...k, attachmentS: s }))
              }
            />
          )}
        </div>

        {/* Linha 2 — comprimentos por segmento. Engenheiro varia
            componentes individualmente (ex.: chain do trecho âncora,
            wire do trecho médio, pendant superior). Total atual
            mostrado no header. */}
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
              total: <span className="text-foreground">{fmtMeters(totalLengthActual, 1)}</span>
              {' '}· baseline {fmtMeters(baseLength, 1)}
            </span>
          </div>
          <div
            className={cn(
              'grid grid-cols-1 gap-5',
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
        // Serve só para garantir que o badge da unidade de força fique
        // sincronizado em re-renders.
        data-unit={unitFor('force', system)}
      />
    </Card>
  )
}

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
  // Slider opera em 0 a 100 (0% a 200% do baseline = ±100%).
  // Convertemos: mul=1 → 50, mul=0.5 → 25, mul=1.5 → 75.
  // Faixa total ±50% (mul ∈ [0.5, 1.5]) usa slider 0..100 mapeado linearmente.
  const sliderValue = ((mul - 0.5) / 1.0) * 100
  const pct = ((mul - 1) * 100).toFixed(0)
  const positive = mul > 1
  return (
    <div className="space-y-2">
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

function MuSlider({
  mu,
  baselineLabel,
  onChange,
}: {
  mu: number
  baselineLabel: string
  onChange: (mu: number) => void
}) {
  // μ ∈ [0, 1.5]; slider 0..150 inteiro.
  const sliderValue = mu * 100
  return (
    <div className="space-y-2">
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-xs font-medium text-foreground">
          Coeficiente de atrito (μ)
        </span>
        <span className="font-mono text-[10px] text-muted-foreground">
          {baselineLabel}
        </span>
      </div>
      <Slider
        min={0}
        max={150}
        step={5}
        value={[sliderValue]}
        onValueChange={(v) => {
          const sv = v[0] ?? 0
          onChange(sv / 100)
        }}
      />
      <div className="flex items-baseline justify-between gap-2">
        <span className="font-mono text-sm font-semibold tabular-nums">
          {fmtNumber(mu, 2)}
        </span>
        <span className="font-mono text-[10px] text-muted-foreground">
          [0,00 — 1,50]
        </span>
      </div>
    </div>
  )
}

/**
 * Slider de posição de attachment (boia/clump). Operava em metros
 * absolutos (s_from_anchor), com range 1%–99% do comprimento total
 * atual. Só renderizado quando o caso tem ≥ 1 attachment.
 */
function AttachmentPosSlider({
  kind,
  name,
  valueS,
  baselineS,
  totalLength,
  countOthers,
  onChangeS,
}: {
  kind: 'buoy' | 'clump_weight' | 'ahv'
  name: string | null
  valueS: number
  baselineS: number
  totalLength: number
  countOthers: number
  onChangeS: (s: number) => void
}) {
  // Slider em [0, 1000] mapeando linearmente 1% a 99% de totalLength.
  const minS = totalLength * 0.01
  const maxS = totalLength * 0.99
  const range = Math.max(maxS - minS, 0.01)
  const sliderValue = ((valueS - minS) / range) * 1000
  const isChanged = Math.abs(valueS - baselineS) > 1e-2
  const labelKind = kind === 'buoy' ? 'Boia' : 'Clump weight'
  const labelName = name ? `"${name}"` : '#1'
  return (
    <div className="space-y-2">
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-xs font-medium text-foreground">
          Posição da {labelKind.toLowerCase()} {labelName}
          {countOthers > 0 && (
            <span className="ml-1 text-[10px] text-muted-foreground">
              (+{countOthers} outro{countOthers > 1 ? 's' : ''})
            </span>
          )}
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
        <span className="font-mono text-sm font-semibold tabular-nums">
          {valueS.toFixed(1)} m
          <span className="ml-1 text-[10px] font-normal text-muted-foreground">
            da âncora
          </span>
        </span>
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
 * Slider de comprimento de um único segmento. Range: 0.5×–1.5×
 * baseline. Mostra valor absoluto em metros + delta % em relação
 * ao baseline. Visualmente similar ao KnobSlider, mas operando em
 * metros absolutos em vez de multiplicador.
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
  // Range ±50% do baseline em metros absolutos.
  const minM = baselineM * 0.5
  const maxM = baselineM * 1.5
  const range = Math.max(maxM - minM, 0.001)
  const sliderValue = ((valueM - minM) / range) * 100
  const delta = valueM - baselineM
  const pctDelta = baselineM > 0 ? (delta / baselineM) * 100 : 0
  const isChanged = Math.abs(pctDelta) > 0.05
  return (
    <div className="space-y-2">
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
        <span className="font-mono text-sm font-semibold tabular-nums">
          {valueM.toFixed(1)}{' '}
          <span className="text-[10px] font-normal text-muted-foreground">
            m
          </span>
        </span>
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
