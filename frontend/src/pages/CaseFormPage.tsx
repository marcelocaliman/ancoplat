import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  AlertCircle,
  AlertTriangle,
  Anchor,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  FileText,
  Info,
  Loader2,
  Mountain,
  Save,
  Sigma,
  Waves,
  Wrench,
  Zap,
} from 'lucide-react'
import {
  Children,
  cloneElement,
  isValidElement,
  useEffect,
  useId,
  useMemo,
  useState,
} from 'react'
import { Controller, useFieldArray, useForm } from 'react-hook-form'
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom'
import { toast } from 'sonner'
import { ApiError } from '@/api/client'
import {
  createCase,
  fetchCriteriaProfiles,
  getCase,
  previewSolve,
  solveCase,
  updateCase,
} from '@/api/endpoints'
import type { SolverResult } from '@/api/types'
import { AttachmentsTable } from '@/components/common/AttachmentsTable'
import { BathymetryInputGroup } from '@/components/common/BathymetryInputGroup'
import { LineSummaryPanel } from '@/components/common/LineSummaryPanel'
import { CatenaryPlot } from '@/components/common/CatenaryPlot'
import {
  DiagnosticsProvider,
  TabValidationCounter,
} from '@/components/common/FieldValidation'
import { SegmentsTable } from '@/components/common/SegmentsTable'
import {
  SEVERITY_STYLES,
  SolverDiagnosticsCard,
  type SolverDiagnostic,
} from '@/components/common/SolverDiagnosticsCard'
import { TemplatePicker } from '@/components/common/TemplatePicker'
import { getTemplate, type CaseTemplate } from '@/lib/caseTemplates'
import { UnitInput } from '@/components/common/UnitInput'
import { ValidationLogCard } from '@/components/common/ValidationLogCard'
import {
  type DiagnosticSeverity,
  runPreSolveDiagnostics,
  worstSeverity,
} from '@/lib/preSolveDiagnostics'
import {
  AlertBadge,
  StatusBadge,
} from '@/components/common/StatusBadge'
import { UtilizationGauge } from '@/components/common/UtilizationGauge'
import { Topbar } from '@/components/layout/Topbar'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from '@/components/ui/tabs'
import { Textarea } from '@/components/ui/textarea'
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import { useDebounce } from '@/hooks/useDebounce'
import {
  EMPTY_CASE,
  caseInputSchema,
  type CaseFormValues,
} from '@/lib/caseSchema'
import {
  cn,
  fmtAngleDeg,
  fmtMeters,
  fmtNumber,
  fmtPercent,
  resolveSeabedDepths,
} from '@/lib/utils'
import { fmtForce, fmtForcePair as fmtForcePairUnits } from '@/lib/units'
import { useUnitsStore } from '@/store/units'

/**
 * Layout vertical: form compacto no topo (3 blocos em grid) +
 * gráfico preenchendo o espaço restante + métricas em faixa no rodapé.
 * Preview live via POST /solve/preview, 600ms debounce.
 */
export function CaseFormPage() {
  const { id } = useParams()
  const isEdit = Boolean(id)
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  // F9 / Q2 — sample carregado via state da rota (vindo de /samples).
  const location = useLocation() as { state: { templateId?: string } | null }
  const initialTemplateId = location.state?.templateId
  const [activeTemplate, setActiveTemplate] = useState<CaseTemplate | null>(
    initialTemplateId ? getTemplate(initialTemplateId) ?? null : null,
  )

  const { data: existing, isLoading: loadingExisting } = useQuery({
    queryKey: ['case', id],
    queryFn: () => getCase(Number(id)),
    enabled: isEdit,
  })

  const { data: profiles } = useQuery({
    queryKey: ['criteria-profiles'],
    queryFn: fetchCriteriaProfiles,
    staleTime: 5 * 60_000,
  })

  const form = useForm<CaseFormValues>({
    resolver: zodResolver(caseInputSchema) as never,
    defaultValues: EMPTY_CASE,
    mode: 'onChange',
  })
  const {
    register,
    control,
    handleSubmit,
    watch,
    setValue,
    reset,
    formState: { errors, isValid, isSubmitting },
  } = form

  // Lista dinâmica de segmentos (F5.1). useFieldArray cuida do estado.
  const segmentsArray = useFieldArray({ control, name: 'segments' })
  // attachmentsArray (boias/clumps) agora é gerenciado internamente
  // pela AttachmentsTable em cada aba — não precisa do array no escopo
  // do CaseFormPage. F5.2 / v1.0.6.

  useEffect(() => {
    if (existing) {
      reset({
        name: existing.input.name,
        description: existing.input.description ?? '',
        segments: existing.input.segments,
        boundary: existing.input.boundary,
        seabed: {
          mu: existing.input.seabed?.mu ?? 0,
          slope_rad: existing.input.seabed?.slope_rad ?? 0,
        },
        criteria_profile: existing.input.criteria_profile,
        user_defined_limits: existing.input.user_defined_limits ?? null,
        attachments: existing.input.attachments ?? [],
      })
    }
  }, [existing, reset])

  // F9 / Q2 — quando o usuário chega via /samples com um templateId,
  // popula o form com os valores do sample (apenas em modo new, não edit).
  useEffect(() => {
    if (!isEdit && activeTemplate) {
      reset(activeTemplate.values)
      toast.success(`Sample "${activeTemplate.name}" carregado.`)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTemplate?.id, isEdit])

  const values = watch()
  const mode = values.boundary.mode
  const criteriaProfile = values.criteria_profile
  const [notesOpen, setNotesOpen] = useState(false)
  const hasNotes = (values.description?.trim().length ?? 0) > 0

  // Contadores por tipo para os badges das abas Boias/Clumps. useFieldArray
  // só nos dá `id`s e índices; a fonte da verdade do `kind` é o watch.
  const watchedAttachments = (values.attachments ?? []) as Array<{
    kind: 'buoy' | 'clump_weight'
  }>
  const buoyCount = watchedAttachments.filter((a) => a.kind === 'buoy').length
  const clumpCount = watchedAttachments.filter(
    (a) => a.kind === 'clump_weight',
  ).length

  const debouncedValues = useDebounce(values, 600)
  const previewKey = useMemo(
    () =>
      JSON.stringify({
        s: debouncedValues.segments,
        b: debouncedValues.boundary,
        se: debouncedValues.seabed,
        cp: debouncedValues.criteria_profile,
        u: debouncedValues.user_defined_limits,
        a: debouncedValues.attachments,
      }),
    [debouncedValues],
  )

  /**
   * Preview-ready: somente os campos que entram no solver. Evita que o
   * gráfico fique bloqueado só porque o usuário ainda não preencheu o
   * nome do caso (que é exigência só pra persistir).
   */
  const previewReady = useMemo(() => {
    const seg = debouncedValues.segments?.[0]
    const b = debouncedValues.boundary
    if (!seg || !b) return false
    if (!(seg.length > 0) || !(seg.w > 0) || !(seg.EA > 0) || !(seg.MBL > 0))
      return false
    if (!(b.h > 0) || !(b.input_value > 0)) return false
    if ((debouncedValues.seabed?.mu ?? -1) < 0) return false
    if (
      debouncedValues.criteria_profile === 'UserDefined' &&
      !debouncedValues.user_defined_limits
    )
      return false
    return true
  }, [debouncedValues])

  const previewQuery = useQuery<SolverResult, ApiError>({
    queryKey: ['solve-preview', previewKey],
    queryFn: () => {
      const payload = {
        ...debouncedValues,
        // Backend exige name não vazio mesmo no preview — usa placeholder.
        name: debouncedValues.name?.trim() || 'preview',
        description: debouncedValues.description?.trim() || null,
      }
      return previewSolve(payload as never)
    },
    enabled: previewReady,
    retry: false,
    staleTime: 30_000,
  })

  // F5.7.6 — pre-solve diagnostics (rodam ANTES do backend).
  // Detectam erros óbvios em ms: cabo curto, empuxo > peso, posições
  // inválidas, T_fl baixo. Concatenam com diagnostics post-solve.
  const preSolveDiagnostics = useMemo(
    () => runPreSolveDiagnostics(debouncedValues),
    [debouncedValues],
  )
  const allDiagnostics: SolverDiagnostic[] = useMemo(() => {
    const post =
      ((previewQuery.data as unknown as {
        diagnostics?: SolverDiagnostic[]
      })?.diagnostics ?? []) as SolverDiagnostic[]
    return [...preSolveDiagnostics, ...post]
  }, [preSolveDiagnostics, previewQuery.data])

  // F5.7.6 — track última configuração que CONVERGIU pra mostrar diff
  // quando o estado atual fica inválido. Atualiza só quando o solver
  // retorna CONVERGED com geometria não-vazia.
  const [lastValidValues, setLastValidValues] = useState<CaseFormValues | null>(
    null,
  )
  useEffect(() => {
    const data = previewQuery.data
    if (!data) return
    const hasGeom = (data.coords_x?.length ?? 0) > 1
    const hasCriticalDiag = allDiagnostics.some(
      (d) => d.severity === 'critical',
    )
    if (data.status === 'converged' && hasGeom && !hasCriticalDiag) {
      setLastValidValues(structuredClone(debouncedValues))
    }
  }, [previewQuery.data, debouncedValues, allDiagnostics])

  // Severidade pior dos diagnostics ativos — alimenta o plot border.
  const diagWorst: DiagnosticSeverity | null = useMemo(
    () => worstSeverity(allDiagnostics),
    [allDiagnostics],
  )

  const saveMutation = useMutation({
    mutationFn: async (v: CaseFormValues) => {
      const payload = {
        ...v,
        description: v.description?.trim() || null,
      } as unknown as Parameters<typeof createCase>[0]
      return isEdit ? updateCase(Number(id), payload) : createCase(payload)
    },
    onSuccess: (out) => {
      queryClient.invalidateQueries({ queryKey: ['cases'] })
      queryClient.invalidateQueries({ queryKey: ['case', String(out.id)] })
      return out
    },
    onError: (err) => {
      toast.error('Falha ao salvar caso', {
        description: err instanceof ApiError ? err.message : String(err),
      })
    },
  })

  async function onSubmit(v: CaseFormValues) {
    try {
      const saved = await saveMutation.mutateAsync(v)
      toast.success(isEdit ? 'Caso atualizado.' : 'Caso criado.')
      navigate(`/cases/${saved.id}`)
    } catch { /* noop */ }
  }

  async function onSubmitAndSolve(v: CaseFormValues) {
    try {
      const saved = await saveMutation.mutateAsync(v)
      // Aguarda o solve antes de navegar para garantir que o detail
      // page já encontre a execução nova no cache da query (que será
      // invalidada logo abaixo). Antes do fix, o navigate disparava
      // ANTES do solve terminar e o detail mostrava dados antigos até
      // o usuário clicar em "Recalcular" manualmente.
      const solvePromise = solveCase(saved.id)
      toast.promise(solvePromise, {
        loading: 'Calculando…',
        success: 'Caso calculado com sucesso.',
        error: (err: unknown) => ({
          message:
            err instanceof ApiError ? `Solver: ${err.message}` : 'Erro no solver',
        }),
      })
      try {
        await solvePromise
      } catch {
        // Mesmo que o solve falhe, navegamos para o detail — usuário
        // verá o caso salvo + última execução (anterior, se houver) +
        // toast de erro do solver.
      }
      // Invalida a query do caso pra que o detail page busque a versão
      // atualizada (com a nova execução).
      queryClient.invalidateQueries({ queryKey: ['case', String(saved.id)] })
      queryClient.invalidateQueries({ queryKey: ['cases'] })
      navigate(`/cases/${saved.id}`)
    } catch { /* noop */ }
  }

  if (isEdit && loadingExisting) {
    return (
      <>
        <Topbar />
        <div className="p-6 text-sm text-muted-foreground">Carregando caso…</div>
      </>
    )
  }

  const breadcrumbs = [
    { label: 'Casos', to: '/cases' },
    { label: isEdit ? `#${id} Editar` : 'Novo' },
  ]

  const actions = (
    <>
      <PreviewStatusChip
        isFetching={previewQuery.isFetching}
        result={previewQuery.data}
        previewReady={previewReady}
      />
      {/* F5.7.6 — Template picker: starting points testados */}
      {!isEdit && (
        <TemplatePicker
          onSelect={(tpl) => {
            reset(tpl.values)
            toast.success(`Template "${tpl.name}" carregado.`)
          }}
        />
      )}
      <Button variant="ghost" size="sm" asChild>
        <Link to={isEdit ? `/cases/${id}` : '/cases'}>Cancelar</Link>
      </Button>
      <Button
        variant="outline"
        size="sm"
        onClick={handleSubmit(onSubmit)}
        disabled={isSubmitting || saveMutation.isPending || !isValid}
      >
        <Save className="h-4 w-4" />
        Salvar
      </Button>
      <Button
        size="sm"
        onClick={handleSubmit(onSubmitAndSolve)}
        disabled={isSubmitting || saveMutation.isPending || !isValid}
      >
        <Zap className="h-4 w-4" />
        Salvar e calcular
      </Button>
    </>
  )

  return (
    <DiagnosticsProvider diagnostics={allDiagnostics}>
      <Topbar breadcrumbs={breadcrumbs} actions={actions} />
      <div className="flex min-h-0 flex-1 flex-col gap-2 overflow-hidden p-3">
        {/* F9 / Q2 — banner explicativo quando sample preview foi
            carregado via /samples (state.templateId aponta para um
            template com requirePhase). Solver vai retornar erro
            INVALID_CASE até a fase fechar. */}
        {activeTemplate?.requirePhase && (
          <div
            role="status"
            aria-live="polite"
            className="flex items-start gap-3 rounded-md border border-warning/50 bg-warning/5 p-3"
          >
            <AlertTriangle
              className="mt-0.5 h-4 w-4 shrink-0 text-warning"
              aria-hidden
            />
            <div className="flex-1">
              <p className="text-xs font-semibold text-warning">
                Sample preview · {activeTemplate.requirePhase} em desenvolvimento
              </p>
              <p className="mt-0.5 text-[11px] leading-relaxed text-muted-foreground">
                {activeTemplate.previewMessage ??
                  `Esta configuração depende de feature da Fase ${activeTemplate.requirePhase}. Você pode visualizar e editar, mas o solve retornará erro até a feature ser implementada.`}
              </p>
            </div>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => setActiveTemplate(null)}
              className="h-7 px-2 text-[10px]"
              title="Ocultar este aviso"
            >
              Fechar
            </Button>
          </div>
        )}
        {/* ───── Linha 1: Metadados (compacta) — Nome + Notas ───── */}
        <Card className="shrink-0 overflow-hidden">
          <CardContent className="grid grid-cols-[minmax(0,560px)_auto] items-end gap-3 p-3">
            <InlineField
              label="Nome do caso"
              required
              error={errors.name?.message}
            >
              <Input
                {...register('name')}
                placeholder="ex.: BC-01 catenária suspensa"
                className="h-7"
              />
            </InlineField>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setNotesOpen((v) => !v)}
              className="h-7 gap-1.5 text-[11px]"
              title={hasNotes ? 'Notas preenchidas' : 'Adicionar notas'}
            >
              <FileText
                className={cn(
                  'h-3.5 w-3.5',
                  hasNotes ? 'text-primary' : 'text-muted-foreground',
                )}
              />
              Notas
              {notesOpen ? (
                <ChevronUp className="h-3 w-3" />
              ) : (
                <ChevronDown className="h-3 w-3" />
              )}
            </Button>
          </CardContent>
          {notesOpen && (
            <div className="border-t border-border/60 px-3 pb-3 pt-2">
              <Textarea
                {...register('description')}
                rows={2}
                placeholder="Notas sobre o caso, condições de projeto, premissas, datas…"
                className="resize-none text-sm"
              />
            </div>
          )}
        </Card>

        {/* ═════════════════════════════════════════════════════════════
            Layout horizontal-on-top:
              Top    — Tabs + conteúdo da aba ativa em row horizontal
                       scroll. Cada aba tem altura compacta (~280px) com
                       cards em flex-row para muitos segmentos/boias/clumps.
              Bottom — Plot dominante (flex-1) + Metrics (240px) lado a lado,
                       ocupando todo o espaço vertical restante.
            Decisão de design: forms HORIZONTAIS no topo (não em coluna
            estreita à esquerda) para múltiplos segmentos serem visíveis
            simultaneamente; metrics fica DIRETAMENTE ao lado do plot.
        ═════════════════════════════════════════════════════════════ */}
        {/* ───── Top: Tabs com inputs físicos (altura compacta) ───── */}
        <Card className="w-full shrink-0 overflow-hidden">
          <Tabs defaultValue="linha" className="flex flex-col">
            <TabsList className="mx-2 mt-1.5 h-auto w-fit p-0.5">
              <TabsTrigger value="linha" className="h-6 gap-1 px-2 text-[11px]">
                <Wrench className="h-3.5 w-3.5" />
                Linha
                {segmentsArray.fields.length > 1 && (
                  <Badge
                    variant="secondary"
                    className="ml-0.5 h-4 px-1 text-[10px]"
                  >
                    {segmentsArray.fields.length}
                  </Badge>
                )}
                <TabValidationCounter prefix="segments[" />
              </TabsTrigger>
              <TabsTrigger value="boias" className="h-6 gap-1 px-2 text-[11px]">
                <Waves className="h-3.5 w-3.5" />
                Boias
                {buoyCount > 0 && (
                  <Badge
                    variant="secondary"
                    className="ml-0.5 h-4 px-1 text-[10px]"
                  >
                    {buoyCount}
                  </Badge>
                )}
                <TabValidationCounter prefix="attachments[" />
              </TabsTrigger>
              <TabsTrigger value="clumps" className="h-6 gap-1 px-2 text-[11px]">
                <Anchor className="h-3.5 w-3.5" />
                Clumps
                {clumpCount > 0 && (
                  <Badge
                    variant="secondary"
                    className="ml-0.5 h-4 px-1 text-[10px]"
                  >
                    {clumpCount}
                  </Badge>
                )}
              </TabsTrigger>
              <TabsTrigger value="ambiente" className="h-6 gap-1 px-2 text-[11px]">
                <Mountain className="h-3.5 w-3.5" />
                Ambiente
                <TabValidationCounter prefix="boundary." />
                <TabValidationCounter prefix="seabed." />
              </TabsTrigger>
              <TabsTrigger value="analise" className="h-6 gap-1 px-2 text-[11px]">
                <Sigma className="h-3.5 w-3.5" />
                Análise
              </TabsTrigger>
            </TabsList>

            {/*
             * Stack das abas: todos os <TabsContent> são forceMount + grid
             * stacked (col/row-start-1) para preservar estado do form ao
             * trocar de aba. Altura máxima limitada (max-h-[300px]) com
             * scroll interno se conteúdo exceder — garante que plot
             * abaixo SEMPRE tem ≥ 60% da altura da viewport.
             */}
            <div className="grid max-h-[340px] overflow-y-auto">
              {/* ───────── Aba Linha: agregados + segmentos ───────── */}
              <TabsContent
                forceMount
                value="linha"
                className="col-start-1 row-start-1 m-0 px-3 pb-3 pt-2 data-[state=inactive]:invisible data-[state=inactive]:pointer-events-none"
              >
              {/* Fase 3 / A1.5: painel agregado no topo da aba Linha. */}
              <div className="mb-2">
                <LineSummaryPanel segments={values.segments ?? []} />
              </div>
              {/*
               * Layout tabular v1.0.5 (estilo QMoor):
               *   - linhas = propriedades (Catálogo, Comprimento, Diâmetro,
               *     Peso submerso, Peso seco)
               *   - colunas = segmentos individuais
               *   - Avançado (EA, MBL, Módulo, EA source, μ override,
               *     Categoria) abre em modal (não expande inline)
               * Ordem visual fairlead → âncora preservada via reverse
               * interno em SegmentsTable. Card de altura compacta
               * (~150-180px), nunca empurra o gráfico abaixo.
               */}
              <SegmentsTable
                control={control}
                register={register}
                watch={watch}
                setValue={setValue}
                segmentsArray={segmentsArray}
              />
            </TabsContent>

              {/* ───────── Aba Boias (layout tabular v1.0.6) ───────── */}
              <TabsContent
                forceMount
                value="boias"
                className="col-start-1 row-start-1 m-0 px-3 pb-3 pt-2 data-[state=inactive]:invisible data-[state=inactive]:pointer-events-none"
              >
                <AttachmentsTable
                  control={control}
                  setValue={setValue}
                  kind="buoy"
                  maxJunctions={Math.max(0, segmentsArray.fields.length - 1)}
                  totalLength={(values.segments ?? []).reduce(
                    (acc, s) => acc + (s.length ?? 0),
                    0,
                  )}
                  solverResult={previewQuery.data}
                />
              </TabsContent>

              {/* ───────── Aba Clumps (layout tabular v1.0.6) ───────── */}
              <TabsContent
                forceMount
                value="clumps"
                className="col-start-1 row-start-1 m-0 px-3 pb-3 pt-2 data-[state=inactive]:invisible data-[state=inactive]:pointer-events-none"
              >
                <AttachmentsTable
                  control={control}
                  setValue={setValue}
                  kind="clump_weight"
                  maxJunctions={Math.max(0, segmentsArray.fields.length - 1)}
                  totalLength={(values.segments ?? []).reduce(
                    (acc, s) => acc + (s.length ?? 0),
                    0,
                  )}
                  solverResult={previewQuery.data}
                />
              </TabsContent>

              {/* ───────── Aba Ambiente: batimetria 2-pontos + fairlead + seabed (Fase 2) ───────── */}
              <TabsContent
                forceMount
                value="ambiente"
                className="col-start-1 row-start-1 m-0 px-3 pb-3 pt-2 data-[state=inactive]:invisible data-[state=inactive]:pointer-events-none"
              >
              {/* 4 cards bordados alinhados à esquerda. Cada card tem
                  conteúdo inline (label flex-1 + input + unit grudada) e
                  destaque visual via tom azulado sutil sobre o fundo
                  externo — visual compacto e profissional. */}
              <div className="flex flex-wrap justify-start gap-2">

                {/* Grupo 1 — Geometria (batimetria 2-pontos primária) */}
                <EnvCard title="Geometria">
                  <Controller
                    control={control}
                    name="boundary.h"
                    render={({ field: hField }) => (
                      <Controller
                        control={control}
                        name="seabed.slope_rad"
                        render={({ field: slopeField }) => (
                          <BathymetryInputGroup
                            depthAnchor={(hField.value as number) ?? 0}
                            setDepthAnchor={(v) => hField.onChange(v)}
                            slopeRad={(slopeField.value as number) ?? 0}
                            onSlopeChange={(rad) => slopeField.onChange(rad)}
                            xTotalEstimate={
                              previewQuery.data?.total_horz_distance ?? undefined
                            }
                          />
                        )}
                      />
                    )}
                  />
                </EnvCard>

                {/* Grupo 2 — Fairlead */}
                <EnvCard title="Fairlead">
                  <EnvField label="Prof. abaixo da água" unit="m">
                    <Input
                      type="number"
                      step="1"
                      min="0"
                      {...register('boundary.startpoint_depth', {
                        valueAsNumber: true,
                      })}
                      className="h-7 w-[80px] font-mono text-[11px]"
                    />
                  </EnvField>
                  <EnvField label="Tipo">
                    <Controller
                      control={control}
                      name="boundary.startpoint_type"
                      render={({ field }) => (
                        <Select
                          value={(field.value as string | undefined) ?? 'semisub'}
                          onValueChange={field.onChange}
                        >
                          <SelectTrigger className="h-7 w-[80px] text-[11px]">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="semisub">Semi-Sub</SelectItem>
                            <SelectItem value="ahv">AHV</SelectItem>
                            <SelectItem value="barge">Barge</SelectItem>
                            <SelectItem value="none">—</SelectItem>
                          </SelectContent>
                        </Select>
                      )}
                    />
                  </EnvField>
                  <EnvField label="Offset horizontal" unit="m">
                    <Input
                      type="number"
                      step="1"
                      {...register('boundary.startpoint_offset_horz', {
                        valueAsNumber: true,
                      })}
                      className="h-7 w-[80px] font-mono text-[11px]"
                    />
                  </EnvField>
                  <EnvField label="Offset vertical" unit="m">
                    <Input
                      type="number"
                      step="0.5"
                      {...register('boundary.startpoint_offset_vert', {
                        valueAsNumber: true,
                      })}
                      className="h-7 w-[80px] font-mono text-[11px]"
                    />
                  </EnvField>
                </EnvCard>

                {/* Grupo 3 — Anchor (Fase 7 — uplift) */}
                <EnvCard title="Âncora">
                  <Controller
                    control={control}
                    name="boundary.endpoint_grounded"
                    render={({ field: groundedField }) => (
                      <Controller
                        control={control}
                        name="boundary.endpoint_depth"
                        render={({ field: depthField }) => (
                          <>
                            <fieldset className="space-y-0.5">
                              <legend className="mb-0.5 text-[10px] font-medium text-muted-foreground">
                                Tipo de fixação
                              </legend>
                              <label className="flex cursor-pointer items-center gap-1.5 text-[11px]">
                                <input
                                  type="radio"
                                  name="endpoint_grounded_radio"
                                  checked={groundedField.value === true}
                                  onChange={() => {
                                    groundedField.onChange(true)
                                    depthField.onChange(null)
                                  }}
                                  className="h-3 w-3"
                                />
                                <span>Cravada (grounded)</span>
                              </label>
                              <label className="flex cursor-pointer items-center gap-1.5 text-[11px]">
                                <input
                                  type="radio"
                                  name="endpoint_grounded_radio"
                                  checked={groundedField.value === false}
                                  onChange={() => {
                                    groundedField.onChange(false)
                                    // Default sensato: anchor 50m acima do seabed
                                    const h = (values.boundary?.h as number) ?? 300
                                    depthField.onChange(
                                      depthField.value ?? Math.max(1, h - 50),
                                    )
                                  }}
                                  className="h-3 w-3"
                                />
                                <span>Elevada (suspended)</span>
                              </label>
                            </fieldset>
                            {groundedField.value === false && (
                              <EnvField label="Prof. do anchor" unit="m">
                                <Input
                                  type="number"
                                  step="1"
                                  min="0"
                                  value={(depthField.value as number | null) ?? ''}
                                  onChange={(e) => {
                                    const v = parseFloat(e.target.value)
                                    depthField.onChange(
                                      Number.isFinite(v) && v > 0 ? v : null,
                                    )
                                  }}
                                  className="h-7 w-[80px] font-mono text-[11px]"
                                />
                              </EnvField>
                            )}
                          </>
                        )}
                      />
                    )}
                  />
                </EnvCard>

                {/* Grupo 4 — Seabed (μ + details slope direto) */}
                <EnvCard title="Seabed">
                  <EnvField label="μ (atrito) global">
                    <Input
                      type="number"
                      step="0.05"
                      min="0"
                      {...register('seabed.mu', { valueAsNumber: true })}
                      className="h-7 w-[80px] font-mono text-[11px]"
                    />
                  </EnvField>
                  {/* Slope direto: sempre visível em vez de collapsible —
                      espaço sobra no card e edição direta é mais
                      profissional. Sobrescreve o slope da Geometria. */}
                  <Controller
                    control={control}
                    name="seabed.slope_rad"
                    render={({ field }) => (
                      <EnvField label="Slope direto" unit="°">
                        <Input
                          type="number"
                          step={0.5}
                          min={-45}
                          max={45}
                          value={
                            field.value != null
                              ? ((field.value * 180) / Math.PI).toFixed(2)
                              : '0'
                          }
                          onChange={(e) => {
                            const deg = parseFloat(e.target.value)
                            field.onChange(
                              Number.isFinite(deg) ? (deg * Math.PI) / 180 : 0,
                            )
                          }}
                          className="h-7 w-[80px] font-mono text-[11px]"
                        />
                      </EnvField>
                    )}
                  />
                  <p className="text-[9px] leading-tight text-muted-foreground">
                    Sobrescreve o slope derivado da Geometria.
                  </p>
                </EnvCard>
              </div>
            </TabsContent>

              {/* ───────── Aba Análise: modo + input + critério ───────── */}
              <TabsContent
                forceMount
                value="analise"
                className="col-start-1 row-start-1 m-0 px-3 pb-3 pt-2 data-[state=inactive]:invisible data-[state=inactive]:pointer-events-none"
              >
              {/* Aba Análise: 3 campos numa linha + UserDefined limits abaixo */}
              <div className="flex flex-col gap-3">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
                  <InlineField label="Modo de cálculo">
                    <Controller
                      control={control}
                      name="boundary.mode"
                      render={({ field }) => (
                        <Select value={field.value} onValueChange={field.onChange}>
                          <SelectTrigger className="h-7 text-[11px]">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="Tension">
                              Tension (T_fl → X)
                            </SelectItem>
                            <SelectItem value="Range">
                              Range (X → T_fl)
                            </SelectItem>
                          </SelectContent>
                        </Select>
                      )}
                    />
                  </InlineField>
                  <InlineField
                    label={mode === 'Tension' ? 'T_fl no fairlead' : 'X total'}
                    unit={mode === 'Tension' ? undefined : 'm'}
                    tooltip={
                      mode === 'Tension'
                        ? 'Tração total no fairlead. Solver computa X.'
                        : 'Distância horizontal fairlead → âncora. Solver computa T_fl.'
                    }
                  >
                    {mode === 'Tension' ? (
                      <Controller
                        control={control}
                        name="boundary.input_value"
                        render={({ field }) => (
                          <UnitInput
                            value={field.value}
                            onChange={field.onChange}
                            quantity="force"
                            digits={2}
                            className="h-7"
                          />
                        )}
                      />
                    ) : (
                      <Input
                        type="number"
                        step="any"
                        {...register('boundary.input_value', {
                          valueAsNumber: true,
                        })}
                        className="h-7 font-mono"
                      />
                    )}
                  </InlineField>
                {/* Critério na mesma linha (3a coluna) */}
                <InlineField label="Critério de utilização">
                  <Controller
                    control={control}
                    name="criteria_profile"
                    render={({ field }) => (
                      <Select value={field.value} onValueChange={field.onChange}>
                        <SelectTrigger className="h-7 text-[11px]">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {profiles?.map((p) => (
                            <SelectItem key={p.name} value={p.name}>
                              <span className="flex items-center gap-2">
                                <span>{p.name}</span>
                                <span className="text-[10px] text-muted-foreground">
                                  y{fmtNumber(p.yellow_ratio, 2)} · r
                                  {fmtNumber(p.red_ratio, 2)} · b
                                  {fmtNumber(p.broken_ratio, 2)}
                                </span>
                              </span>
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    )}
                  />
                </InlineField>
                </div>
                {criteriaProfile === 'UserDefined' && (
                  <div className="grid grid-cols-3 gap-2">
                    {(
                      ['yellow_ratio', 'red_ratio', 'broken_ratio'] as const
                    ).map((k) => (
                      <InlineField
                        key={k}
                        label={k.replace('_ratio', '')}
                      >
                        <Input
                          type="number"
                          step="0.05"
                          defaultValue={
                            watch(`user_defined_limits.${k}`) ??
                            (k === 'yellow_ratio'
                              ? 0.5
                              : k === 'red_ratio'
                                ? 0.6
                                : 1.0)
                          }
                          onChange={(e) =>
                            setValue(
                              `user_defined_limits.${k}`,
                              parseFloat(e.target.value),
                              { shouldValidate: true },
                            )
                          }
                          className="h-7 font-mono"
                        />
                      </InlineField>
                    ))}
                  </div>
                )}
              </div>
            </TabsContent>
            </div>
          </Tabs>
        </Card>

        {/* ───── Bottom: Plot dominante (centro) + Metrics (direita) ───── */}
        <div className="flex min-h-0 flex-1 gap-2">
          <Card className="min-h-0 flex-1 overflow-hidden">
            <CardContent className="h-full p-1">
              <PlotArea
                isFetching={previewQuery.isFetching}
                result={previewQuery.data}
                previewReady={previewReady}
                attachments={debouncedValues.attachments ?? []}
                seabedSlopeRad={debouncedValues.seabed?.slope_rad ?? 0}
                segments={debouncedValues.segments ?? []}
                startpointType={
                  debouncedValues.boundary?.startpoint_type ?? 'semisub'
                }
                preSolveDiagnostics={preSolveDiagnostics}
                worstSeverity={diagWorst}
                lastValidValues={lastValidValues}
                currentValues={debouncedValues}
                onRevertToLastValid={() => {
                  if (lastValidValues) {
                    reset(lastValidValues)
                  }
                }}
                onApplyChange={(field, value) => {
                  // F5.7.4 — aplica sugestão do diagnóstico no form.
                  setValue(
                    field as Parameters<typeof setValue>[0],
                    value as Parameters<typeof setValue>[1],
                    { shouldValidate: true, shouldDirty: true },
                  )
                }}
              />
            </CardContent>
          </Card>
          {/* KPIs/metrics colados ao lado direito do plot */}
          <MetricsColumn
            result={previewQuery.data}
            previewReady={previewReady}
            fallbackH={debouncedValues.boundary?.h ?? 0}
            slopeRad={debouncedValues.seabed?.slope_rad ?? 0}
          />
        </div>
      </div>
    </DiagnosticsProvider>
  )
}

/* ───────────────────────── Helpers visuais ─────────────────────────── */

/**
 * EnvCard — card bordado para um grupo da aba Ambiente
 * (Geometria, Fairlead, Âncora, Seabed). Largura fixa para
 * alinhamento estável entre cards.
 *
 * Visual v1.0.9: tom azulado sutil (bg-primary/5) sobre o fundo
 * externo + border-primary/20 + sombra leve. Diferencia visualmente
 * o card sem competir com o conteúdo.
 */
function EnvCard({
  title,
  children,
}: {
  title: string
  children: React.ReactNode
}) {
  return (
    <Card className="w-[260px] shrink-0 border-primary/20 bg-primary/[0.04] shadow-sm">
      <CardContent className="space-y-1.5 p-2.5">
        <h4 className="text-[10px] font-semibold uppercase tracking-[0.08em] text-primary/80">
          {title}
        </h4>
        {children}
      </CardContent>
    </Card>
  )
}

/**
 * EnvField — linha horizontal de input dentro de um EnvCard:
 *   [label flex-1] [input w-fixa] [unit]
 * Resolve o "unit solto à direita" do v1.0.7 — agora unit fica grudado
 * no input, alinhamento estável entre cards.
 */
function EnvField({
  label,
  unit,
  children,
}: {
  label: string
  unit?: string
  children: React.ReactNode
}) {
  return (
    <div className="flex items-center gap-2">
      <Label className="flex-1 truncate text-[10px] font-medium text-muted-foreground">
        {label}
      </Label>
      {children}
      <span
        className={cn(
          'w-3 shrink-0 font-mono text-[9px] text-muted-foreground',
          !unit && 'invisible',
        )}
      >
        {unit ?? '—'}
      </span>
    </div>
  )
}

function InlineField({
  label,
  unit,
  required,
  error,
  className,
  tooltip,
  children,
}: {
  label: string
  unit?: string
  required?: boolean
  error?: string
  className?: string
  tooltip?: string
  children: React.ReactNode
}) {
  // F9 / Q8 — a11y: id determinístico Label↔Input + aria-required + aria-invalid
  // + aria-describedby quando há mensagem de erro.
  const id = useId()
  const errorId = error ? `${id}-error` : undefined
  const enhancedChild = injectFieldA11y(children, {
    id,
    required,
    invalid: !!error,
    describedBy: errorId,
  })
  return (
    <div className={cn('flex flex-col gap-0.5', className)}>
      <Label
        htmlFor={id}
        className="flex items-center justify-between gap-1 text-[10px] font-medium text-muted-foreground"
      >
        <span className="flex items-center gap-1 truncate">
          {label}
          {required && (
            <span aria-hidden className="text-danger">
              *
            </span>
          )}
          {tooltip && (
            <Tooltip>
              <TooltipTrigger asChild>
                <Info className="h-2.5 w-2.5 text-muted-foreground" />
              </TooltipTrigger>
              <TooltipContent side="top" className="max-w-xs text-xs">
                {tooltip}
              </TooltipContent>
            </Tooltip>
          )}
        </span>
        {unit && (
          <span className="shrink-0 font-mono text-[9px] font-normal">{unit}</span>
        )}
      </Label>
      {enhancedChild}
      {error && (
        <p id={errorId} role="alert" className="text-[10px] text-danger">
          {error}
        </p>
      )}
    </div>
  )
}

// Helper local — espelha SegmentEditor.injectA11y mas adiciona
// aria-invalid e aria-describedby para mensagens de erro inline.
function injectFieldA11y(
  children: React.ReactNode,
  props: { id: string; required?: boolean; invalid?: boolean; describedBy?: string },
): React.ReactNode {
  const arr = Children.toArray(children)
  const onlyChild = arr[0]
  if (!isValidElement(onlyChild)) return children
  const extra: Record<string, unknown> = { id: props.id }
  if (props.required) extra['aria-required'] = true
  if (props.invalid) extra['aria-invalid'] = true
  if (props.describedBy) extra['aria-describedby'] = props.describedBy
  return cloneElement(
    onlyChild as React.ReactElement<Record<string, unknown>>,
    extra,
  )
}

function PreviewStatusChip({
  isFetching,
  result,
  previewReady,
}: {
  isFetching: boolean
  result?: SolverResult
  previewReady: boolean
}) {
  let variant: 'success' | 'warning' | 'danger' | 'secondary' = 'secondary'
  let icon: React.ReactNode = null
  let label = 'Aguardando'

  if (!previewReady) {
    label = 'Preencha os parâmetros'
    icon = <Info className="mr-1 h-3 w-3" />
  } else if (isFetching) {
    variant = 'warning'
    icon = <Loader2 className="mr-1 h-3 w-3 animate-spin" />
    label = 'Calculando'
  } else if (result) {
    if (result.alert_level === 'broken' || result.status === 'invalid_case') {
      variant = 'danger'
      icon = <AlertCircle className="mr-1 h-3 w-3" />
      label = 'Inviável'
    } else if (
      result.alert_level === 'red' ||
      result.status === 'ill_conditioned'
    ) {
      variant = 'warning'
      icon = <AlertCircle className="mr-1 h-3 w-3" />
      label = 'Atenção'
    } else {
      variant = 'success'
      icon = <CheckCircle2 className="mr-1 h-3 w-3" />
      label = 'Convergiu'
    }
  }

  return (
    <Badge variant={variant} className="h-7 px-2 text-[11px]">
      {icon}
      {label}
    </Badge>
  )
}

function PlotArea({
  isFetching,
  result,
  previewReady,
  attachments,
  seabedSlopeRad,
  segments,
  startpointType = 'semisub',
  preSolveDiagnostics,
  worstSeverity: worstSev,
  lastValidValues,
  currentValues,
  onRevertToLastValid,
  onApplyChange,
}: {
  isFetching: boolean
  result?: SolverResult
  previewReady: boolean
  attachments?: import('@/api/types').LineAttachment[]
  seabedSlopeRad?: number
  segments?: Array<{
    category?: 'Wire' | 'StuddedChain' | 'StudlessChain' | 'Polyester' | null
    line_type?: string | null
  }>
  startpointType?: 'semisub' | 'ahv' | 'barge' | 'none'
  preSolveDiagnostics?: SolverDiagnostic[]
  worstSeverity?: DiagnosticSeverity | null
  lastValidValues?: CaseFormValues | null
  currentValues?: CaseFormValues
  onRevertToLastValid?: () => void
  /** F5.7.4 — callback do botão "Aplicar" no card de diagnósticos. */
  onApplyChange?: (field: string, value: number) => void
}) {
  if (!previewReady && !result) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 text-center">
        <Info className="h-6 w-6 text-muted-foreground" />
        <p className="text-sm text-muted-foreground">
          Preencha os parâmetros do segmento e contorno para ver o perfil
          calculado.
        </p>
      </div>
    )
  }
  if (!result && isFetching) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 text-center">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        <p className="text-sm text-muted-foreground">Calculando preview…</p>
      </div>
    )
  }
  if (!result) {
    return (
      <div className="flex h-full items-center justify-center">
        <p className="text-sm text-muted-foreground">Aguardando dados</p>
      </div>
    )
  }
  const hasGeom = (result.coords_x?.length ?? 0) > 1
  const totalDiagsCount =
    (preSolveDiagnostics?.length ?? 0) +
    ((result as { diagnostics?: unknown[] }).diagnostics?.length ?? 0)

  // F5.7.6 — plot border colored by worst severity. Critical/error =
  // vermelho grosso, warning = âmbar, info = azul. Sem diagnostics =
  // border padrão (cinza translúcido).
  const borderClass = worstSev
    ? SEVERITY_STYLES[worstSev].container
    : 'border-border/30'
  const borderWidthClass =
    worstSev === 'critical' || worstSev === 'error'
      ? 'border-2'
      : 'border'

  if (!hasGeom) {
    return (
      <div
        className={cn(
          'flex h-full flex-col gap-3 overflow-y-auto rounded-md p-4',
          borderClass,
          borderWidthClass,
        )}
      >
        <div className="flex items-center justify-center gap-2 text-center">
          <AlertCircle className="h-6 w-6 text-danger" />
          <p className="text-sm font-medium text-danger">
            Sem geometria calculada
          </p>
        </div>
        <div className="space-y-2 text-left">
          <SolverDiagnosticsCard
            result={result}
            extraDiagnostics={preSolveDiagnostics}
            onApplyChange={onApplyChange}
          />
          {/* Validation log — mostra diff vs último válido (se houver). */}
          {lastValidValues && currentValues && (
            <ValidationLogCard
              current={currentValues}
              lastValid={lastValidValues}
              onRevert={onRevertToLastValid}
            />
          )}
        </div>
        {/* Mensagem fallback só quando NÃO houver diagnósticos estruturados */}
        {result.message && totalDiagsCount === 0 && (
          <p className="text-center text-xs text-muted-foreground">
            {result.message}
          </p>
        )}
      </div>
    )
  }
  return (
    <div
      className={cn(
        'flex h-full flex-col gap-2 rounded-md p-1',
        borderClass,
        borderWidthClass,
      )}
    >
      {totalDiagsCount > 0 && (
        <div className="max-h-[40%] shrink-0 space-y-2 overflow-y-auto px-1">
          <SolverDiagnosticsCard
            result={result}
            extraDiagnostics={preSolveDiagnostics}
            onApplyChange={onApplyChange}
          />
          {lastValidValues && currentValues && (
            <ValidationLogCard
              current={currentValues}
              lastValid={lastValidValues}
              onRevert={onRevertToLastValid}
            />
          )}
        </div>
      )}
      <div className="min-h-0 flex-1">
        <CatenaryPlot
          result={result}
          attachments={attachments}
          seabedSlopeRad={seabedSlopeRad}
          segments={segments}
          startpointType={startpointType}
        />
      </div>
    </div>
  )
}

function MetricsColumn({
  result,
  previewReady,
  fallbackH,
  slopeRad,
}: {
  result?: SolverResult
  previewReady: boolean
  fallbackH: number
  slopeRad: number
}) {
  const system = useUnitsStore((s) => s.system)

  if (!previewReady || !result) {
    return (
      <div className="flex h-full w-[240px] shrink-0 flex-col gap-1.5 xl:w-[260px]">
        {Array.from({ length: 4 }).map((_, i) => (
          <Card key={i} className="flex-1 bg-muted/10">
            <CardContent className="flex h-full flex-col justify-center gap-1 p-2.5">
              <div className="h-2.5 w-16 rounded bg-muted/40" />
              <div className="h-5 w-24 rounded bg-muted/30" />
              <div className="h-2 w-20 rounded bg-muted/30" />
            </CardContent>
          </Card>
        ))}
      </div>
    )
  }
  const hasTouchdown =
    result.dist_to_first_td != null && result.dist_to_first_td > 0
  const vFairlead = result.fairlead_tension
    ? Math.sqrt(
        Math.max(result.fairlead_tension ** 2 - result.H ** 2, 0),
      )
    : 0
  const vAnchor = result.anchor_tension
    ? Math.sqrt(Math.max(result.anchor_tension ** 2 - result.H ** 2, 0))
    : 0

  // Formatador "primário (te) + secundário (kN)" para o card principal de tração.
  const tFlPair = fmtForcePairUnits(result.fairlead_tension, system)
  // Compatibilidade legacy: para execuções persistidas antes da F5.3.z,
  // depth_at_anchor/depth_at_fairlead vinham 0. Recompõe via fórmula
  // do backend (h − tan(slope)·X_total).
  const seabedDepths = resolveSeabedDepths(result, fallbackH, slopeRad)

  // Auxiliares para abreviar dentro das linhas dos demais cards.
  const F = (v: number): string => fmtForce(v, system)
  const Fpair = (v: number): string => {
    const p = fmtForcePairUnits(v, system)
    return `${p.primary} · ${p.secondary}`
  }

  return (
    <div className="flex h-full w-[240px] shrink-0 flex-col gap-1.5 pr-1 xl:w-[260px]">
      {/* Tração — primário com gauge */}
      <MetricCard
        label="Tração no fairlead"
        primary={tFlPair.primary}
        secondary={`≈ ${tFlPair.secondary}`}
        rows={[
          ['V vertical', F(vFairlead)],
          [
            'Ângulo (horiz.)',
            fmtAngleDeg(result.angle_wrt_horz_fairlead, 1),
          ],
        ]}
        extra={
          <UtilizationGauge
            value={result.utilization}
            alertLevel={result.alert_level}
            className="mt-1.5"
          />
        }
      />

      {/* Geometria — completa */}
      <MetricCard
        label="Geometria"
        rows={[
          ['X total', fmtMeters(result.total_horz_distance, 1)],
          ['L suspenso', fmtMeters(result.total_suspended_length, 1)],
          ['L apoiado', fmtMeters(result.total_grounded_length, 1)],
          hasTouchdown
            ? ['Dist. touchdown', fmtMeters(result.dist_to_first_td!, 1)]
            : ['Touchdown', '—'],
          ['L esticado', fmtMeters(result.stretched_length, 2)],
          ['ΔL', fmtMeters(result.elongation, 3)],
          // Batimetria: profundidades nos dois pontos críticos. Útil em
          // casos com seabed inclinado (slope_rad ≠ 0); para horizontal
          // ambos são iguais a h.
          ['Prof. seabed @ âncora', fmtMeters(seabedDepths.atAnchor, 1)],
          ['Prof. seabed @ fairlead', fmtMeters(seabedDepths.atFairlead, 1)],
        ]}
      />

      {/* Forças — primário + secundário juntos */}
      <MetricCard
        label="Forças"
        rows={[
          ['H (horizontal)', Fpair(result.H)],
          ['T âncora', Fpair(result.anchor_tension)],
          ['V âncora', Fpair(vAnchor)],
          [
            'Ângulo âncora',
            fmtAngleDeg(result.angle_wrt_horz_anchor, 1),
          ],
        ]}
      />

      {/* Status + critério */}
      <MetricCard
        label="Status do solver"
        extra={
          <div className="flex flex-wrap gap-1.5">
            <StatusBadge status={result.status} />
            <AlertBadge level={result.alert_level} />
          </div>
        }
        rows={[
          ['Utilização', fmtPercent(result.utilization, 2) + ' MBL'],
          ['Iterações', String(result.iterations_used)],
          ['H (param.)', F(result.H)],
        ]}
        footer={result.message || undefined}
      />
    </div>
  )
}

function MetricCard({
  label,
  primary,
  secondary,
  rows,
  extra,
  footer,
}: {
  label: string
  primary?: string
  secondary?: string
  rows?: Array<[string, string]>
  extra?: React.ReactNode
  footer?: string
}) {
  return (
    <Card className="flex-1">
      <CardContent className="flex h-full min-h-[120px] flex-col gap-1 p-2.5">
        <p className="text-[10px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">
          {label}
        </p>
        {primary && (
          <div className="flex items-baseline gap-1 font-mono tabular-nums leading-none">
            <span className="text-[15px] font-semibold tracking-tight">
              {primary}
            </span>
            {secondary && (
              <span className="text-[9.5px] font-normal text-muted-foreground">
                {secondary}
              </span>
            )}
          </div>
        )}
        {extra}
        {rows && (
          <div className="mt-auto space-y-[2px] font-mono text-[10px] leading-tight tabular-nums">
            {rows.map(([k, v]) => (
              <div
                key={k}
                className="flex items-baseline justify-between gap-2"
              >
                <span className="shrink-0 text-muted-foreground">{k}</span>
                <span className="truncate text-right font-medium text-foreground">
                  {v}
                </span>
              </div>
            ))}
          </div>
        )}
        {footer && (
          <p
            className="mt-1 line-clamp-2 font-mono text-[9.5px] leading-tight text-muted-foreground"
            title={footer}
          >
            {footer}
          </p>
        )}
      </CardContent>
    </Card>
  )
}

