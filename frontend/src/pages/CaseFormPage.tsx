import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  AlertCircle,
  CheckCircle2,
  Info,
  Loader2,
  Save,
  Zap,
} from 'lucide-react'
import { useEffect, useMemo } from 'react'
import { Controller, useForm } from 'react-hook-form'
import { Link, useNavigate, useParams } from 'react-router-dom'
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
import type { LineTypeOutput, SolverResult } from '@/api/types'
import { CatenaryPlot } from '@/components/common/CatenaryPlot'
import { LineTypePicker } from '@/components/common/LineTypePicker'
import {
  AlertBadge,
  StatusBadge,
} from '@/components/common/StatusBadge'
import { UtilizationGauge } from '@/components/common/UtilizationGauge'
import { Topbar } from '@/components/layout/Topbar'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Separator } from '@/components/ui/separator'
import { Switch } from '@/components/ui/switch'
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
import { cn, fmtForceKN, fmtMeters, fmtNumber, fmtPercent } from '@/lib/utils'

/**
 * Tela de criação/edição com PREVIEW AO VIVO: formulário à esquerda,
 * gráfico + cards à direita. Cada mudança de input dispara, após 400ms
 * de debounce, um `POST /solve/preview` (não persiste) e atualiza a
 * visualização.
 */
export function CaseFormPage() {
  const { id } = useParams()
  const isEdit = Boolean(id)
  const navigate = useNavigate()
  const queryClient = useQueryClient()

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

  useEffect(() => {
    if (existing) {
      reset({
        name: existing.input.name,
        description: existing.input.description ?? '',
        segments: existing.input.segments,
        boundary: existing.input.boundary,
        seabed: existing.input.seabed,
        criteria_profile: existing.input.criteria_profile,
        user_defined_limits: existing.input.user_defined_limits ?? null,
      })
    }
  }, [existing, reset])

  const values = watch()
  const mode = values.boundary.mode
  const criteriaProfile = values.criteria_profile

  // Debounce os valores para não martelar o backend a cada tecla
  const debouncedValues = useDebounce(values, 400)

  const previewKey = useMemo(
    () => JSON.stringify({
      s: debouncedValues.segments,
      b: debouncedValues.boundary,
      se: debouncedValues.seabed,
      cp: debouncedValues.criteria_profile,
      u: debouncedValues.user_defined_limits,
    }),
    [debouncedValues],
  )

  const previewQuery = useQuery<SolverResult, ApiError>({
    queryKey: ['solve-preview', previewKey],
    queryFn: async () => {
      // Validação rápida: se algum campo mínimo do solver é inválido,
      // não chama o backend (evita 422 óbvio).
      if (!isValid) throw new ApiError('form_invalid', 'Formulário com erros.', 0)
      const payload = {
        ...debouncedValues,
        description:
          debouncedValues.description?.trim() || null,
      }
      return previewSolve(payload as never)
    },
    enabled: isValid,
    retry: false,
    staleTime: 30_000,
  })

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
    } catch {
      /* noop */
    }
  }

  async function onSubmitAndSolve(v: CaseFormValues) {
    try {
      const saved = await saveMutation.mutateAsync(v)
      toast.promise(solveCase(saved.id), {
        loading: 'Calculando…',
        success: 'Caso calculado com sucesso.',
        error: (err: unknown) => ({
          message:
            err instanceof ApiError ? `Solver: ${err.message}` : 'Erro no solver',
        }),
      })
      navigate(`/cases/${saved.id}`)
    } catch {
      /* noop */
    }
  }

  function applyLineTypeToSegment(lt: LineTypeOutput | null) {
    if (!lt) return
    setValue('segments.0.line_type', lt.line_type, { shouldValidate: true })
    setValue(
      'segments.0.category',
      lt.category as CaseFormValues['segments'][number]['category'],
      { shouldValidate: true },
    )
    setValue('segments.0.w', lt.wet_weight, { shouldValidate: true })
    setValue('segments.0.EA', lt.qmoor_ea ?? lt.gmoor_ea ?? 0, {
      shouldValidate: true,
    })
    setValue('segments.0.MBL', lt.break_strength, { shouldValidate: true })
    toast.success(`Propriedades de ${lt.line_type} aplicadas.`)
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
      <Button variant="outline" asChild>
        <Link to={isEdit ? `/cases/${id}` : '/cases'}>Cancelar</Link>
      </Button>
      <Button
        variant="outline"
        onClick={handleSubmit(onSubmit)}
        disabled={isSubmitting || saveMutation.isPending || !isValid}
      >
        <Save className="h-4 w-4" />
        Salvar
      </Button>
      <Button
        onClick={handleSubmit(onSubmitAndSolve)}
        disabled={isSubmitting || saveMutation.isPending || !isValid}
      >
        <Zap className="h-4 w-4" />
        Salvar e calcular
      </Button>
    </>
  )

  return (
    <>
      <Topbar breadcrumbs={breadcrumbs} actions={actions} />
      <div className="flex min-h-0 flex-1 overflow-hidden">
        {/* COLUNA ESQUERDA — Formulário */}
        <form
          onSubmit={handleSubmit(onSubmit)}
          className="flex w-full max-w-[560px] shrink-0 flex-col overflow-y-auto custom-scroll border-r border-border bg-sidebar/40 p-5"
          noValidate
        >
          <div className="space-y-4">
            {/* Identificação */}
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm">Identificação</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div>
                  <Label htmlFor="name" className="text-xs">
                    Nome <span className="text-danger">*</span>
                  </Label>
                  <Input
                    id="name"
                    {...register('name')}
                    aria-invalid={!!errors.name}
                    className="mt-1 h-8"
                    placeholder="ex.: BC-01 — catenária suspensa"
                  />
                  {errors.name && (
                    <p className="mt-1 text-xs text-danger">
                      {errors.name.message}
                    </p>
                  )}
                </div>
                <div>
                  <Label htmlFor="description" className="text-xs">
                    Descrição
                  </Label>
                  <Textarea
                    id="description"
                    {...register('description')}
                    className="mt-1"
                    rows={2}
                    placeholder="Notas sobre o caso…"
                  />
                </div>
              </CardContent>
            </Card>

            {/* Segmento */}
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm">Segmento de linha</CardTitle>
                <CardDescription className="text-[11px]">
                  Escolha do catálogo ou digite manualmente.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <Controller
                  control={control}
                  name="segments.0.line_type"
                  render={({ field }) => (
                    <LineTypePicker
                      value={
                        field.value
                          ? ({
                              id: 0,
                              line_type: field.value,
                              category: watch('segments.0.category') ?? 'Wire',
                              diameter: 0,
                              dry_weight: 0,
                              wet_weight: watch('segments.0.w'),
                              break_strength: watch('segments.0.MBL'),
                              qmoor_ea: watch('segments.0.EA'),
                              data_source: 'legacy_qmoor',
                            } as LineTypeOutput)
                          : null
                      }
                      onChange={applyLineTypeToSegment}
                    />
                  )}
                />
                <Separator />
                <div className="grid grid-cols-2 gap-2">
                  <CompactField label="Comprimento (m)">
                    <Input
                      type="number"
                      step="0.01"
                      {...register('segments.0.length', { valueAsNumber: true })}
                      className="h-8 font-mono"
                    />
                  </CompactField>
                  <CompactField label="Categoria">
                    <Controller
                      control={control}
                      name="segments.0.category"
                      render={({ field }) => (
                        <Select
                          value={field.value ?? undefined}
                          onValueChange={field.onChange}
                        >
                          <SelectTrigger className="h-8">
                            <SelectValue placeholder="—" />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="Wire">Wire</SelectItem>
                            <SelectItem value="StuddedChain">Studded</SelectItem>
                            <SelectItem value="StudlessChain">Studless</SelectItem>
                            <SelectItem value="Polyester">Poliéster</SelectItem>
                          </SelectContent>
                        </Select>
                      )}
                    />
                  </CompactField>
                  <CompactField label="Peso submerso (N/m)">
                    <Input
                      type="number"
                      step="0.01"
                      {...register('segments.0.w', { valueAsNumber: true })}
                      className="h-8 font-mono"
                    />
                  </CompactField>
                  <CompactField label="EA (N)">
                    <Input
                      type="number"
                      step="1e5"
                      {...register('segments.0.EA', { valueAsNumber: true })}
                      className="h-8 font-mono"
                    />
                  </CompactField>
                  <CompactField label="MBL (N)" className="col-span-2">
                    <Input
                      type="number"
                      step="1000"
                      {...register('segments.0.MBL', { valueAsNumber: true })}
                      className="h-8 font-mono"
                    />
                  </CompactField>
                </div>
              </CardContent>
            </Card>

            {/* Boundary */}
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm">Condições de contorno</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="grid grid-cols-2 gap-2">
                  <CompactField label="Lâmina d'água (m)">
                    <Input
                      type="number"
                      step="0.1"
                      {...register('boundary.h', { valueAsNumber: true })}
                      className="h-8 font-mono"
                    />
                  </CompactField>
                  <CompactField label="Modo">
                    <Controller
                      control={control}
                      name="boundary.mode"
                      render={({ field }) => (
                        <Select value={field.value} onValueChange={field.onChange}>
                          <SelectTrigger className="h-8">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="Tension">Tension</SelectItem>
                            <SelectItem value="Range">Range</SelectItem>
                          </SelectContent>
                        </Select>
                      )}
                    />
                  </CompactField>
                  <CompactField
                    label={mode === 'Tension' ? 'T_fl (N)' : 'X total (m)'}
                    className="col-span-2"
                  >
                    <Input
                      type="number"
                      step="any"
                      {...register('boundary.input_value', {
                        valueAsNumber: true,
                      })}
                      className="h-8 font-mono"
                    />
                  </CompactField>
                </div>
              </CardContent>
            </Card>

            {/* Seabed */}
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="flex items-center gap-1.5 text-sm">
                  Seabed
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Info className="h-3 w-3 text-muted-foreground" />
                    </TooltipTrigger>
                    <TooltipContent side="right" className="max-w-xs text-xs">
                      Atrito axial de Coulomb. Valores típicos: wire 0,3,
                      corrente 0,7, poliéster 0,25.
                    </TooltipContent>
                  </Tooltip>
                </CardTitle>
              </CardHeader>
              <CardContent>
                <CompactField label="μ (atrito)">
                  <Input
                    type="number"
                    step="0.05"
                    min="0"
                    {...register('seabed.mu', { valueAsNumber: true })}
                    className="h-8 font-mono"
                  />
                </CompactField>
              </CardContent>
            </Card>

            {/* Critério */}
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm">Critério de utilização</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <Controller
                  control={control}
                  name="criteria_profile"
                  render={({ field }) => (
                    <Select value={field.value} onValueChange={field.onChange}>
                      <SelectTrigger className="h-8">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {profiles?.map((p) => (
                          <SelectItem key={p.name} value={p.name}>
                            <div className="flex flex-col">
                              <span>{p.name}</span>
                              <span className="text-[10px] text-muted-foreground">
                                y {fmtNumber(p.yellow_ratio, 2)} · r{' '}
                                {fmtNumber(p.red_ratio, 2)} · b{' '}
                                {fmtNumber(p.broken_ratio, 2)}
                              </span>
                            </div>
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  )}
                />
                {criteriaProfile === 'UserDefined' && (
                  <div className="grid grid-cols-3 gap-2">
                    {(['yellow_ratio', 'red_ratio', 'broken_ratio'] as const).map(
                      (k) => (
                        <CompactField key={k} label={k.replace('_ratio', '')}>
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
                            className="h-8 font-mono"
                          />
                        </CompactField>
                      ),
                    )}
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Restrições v1 */}
            <div className="flex items-start gap-2 rounded-md border border-border bg-muted/30 px-3 py-2.5 text-xs text-muted-foreground">
              <Info className="mt-0.5 h-3.5 w-3.5 shrink-0 text-info" />
              <span>
                <strong className="text-foreground">MVP v1:</strong>{' '}
                fairlead na superfície, âncora no seabed, linha homogênea.
              </span>
              <Switch checked disabled className="ml-auto" />
            </div>
          </div>
        </form>

        {/* COLUNA DIREITA — Preview live */}
        <div className="flex min-w-0 flex-1 flex-col overflow-hidden bg-background">
          <div className="flex flex-1 flex-col overflow-y-auto custom-scroll p-5">
            <PreviewHeader queryState={previewQuery} />
            <div className="mt-4 flex flex-1 flex-col gap-4">
              <Card className="min-h-[380px]">
                <CardContent className="p-2">
                  {previewQuery.data ? (
                    <CatenaryPlot result={previewQuery.data} height={400} />
                  ) : previewQuery.isLoading ? (
                    <PlotPlaceholder state="loading" />
                  ) : previewQuery.isError ? (
                    <PlotPlaceholder
                      state="error"
                      message={previewQuery.error?.message}
                    />
                  ) : (
                    <PlotPlaceholder state="idle" />
                  )}
                </CardContent>
              </Card>

              {previewQuery.data && (
                <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
                  <MetricCard
                    label="Tração no fairlead"
                    value={`${fmtNumber(previewQuery.data.fairlead_tension / 1000, 1)} kN`}
                    extra={
                      <UtilizationGauge
                        value={previewQuery.data.utilization}
                        alertLevel={previewQuery.data.alert_level}
                      />
                    }
                    footer={`T/MBL = ${fmtPercent(previewQuery.data.utilization, 1)}`}
                  />
                  <MetricCard
                    label="Geometria"
                    rows={[
                      ['X total', fmtMeters(previewQuery.data.total_horz_distance, 1)],
                      ['Suspenso', fmtMeters(previewQuery.data.total_suspended_length, 1)],
                      ['Apoiado', fmtMeters(previewQuery.data.total_grounded_length, 1)],
                      ...(previewQuery.data.dist_to_first_td != null && previewQuery.data.dist_to_first_td > 0
                        ? [['Touchdown', fmtMeters(previewQuery.data.dist_to_first_td, 1)] as [string, string]]
                        : []),
                    ]}
                  />
                  <MetricCard
                    label="Forças"
                    rows={[
                      ['H', fmtForceKN(previewQuery.data.H, 1)],
                      ['T âncora', fmtForceKN(previewQuery.data.anchor_tension, 1)],
                      ['ΔL', fmtMeters(previewQuery.data.elongation, 3)],
                    ]}
                  />
                  <MetricCard
                    label="Status"
                    extra={
                      <div className="space-y-1.5">
                        <div className="flex gap-1.5">
                          <StatusBadge status={previewQuery.data.status} />
                          <AlertBadge level={previewQuery.data.alert_level} />
                        </div>
                        <p className="font-mono text-[10px] text-muted-foreground">
                          {previewQuery.data.iterations_used} iter
                        </p>
                      </div>
                    }
                  />
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </>
  )
}

function CompactField({
  label,
  children,
  className,
}: {
  label: string
  children: React.ReactNode
  className?: string
}) {
  return (
    <div className={cn('flex flex-col gap-1', className)}>
      <Label className="text-[11px] text-muted-foreground">{label}</Label>
      {children}
    </div>
  )
}

function PreviewHeader({
  queryState,
}: {
  queryState: ReturnType<typeof useQuery<SolverResult, ApiError>>
}) {
  const status: 'idle' | 'loading' | 'success' | 'error' =
    queryState.isFetching
      ? 'loading'
      : queryState.isError
        ? 'error'
        : queryState.data
          ? 'success'
          : 'idle'
  return (
    <div className="flex items-center justify-between gap-3">
      <div>
        <h2 className="text-lg font-semibold tracking-tight">Preview ao vivo</h2>
        <p className="text-xs text-muted-foreground">
          Recalculado automaticamente a cada ajuste no formulário.
          Não persiste — use "Salvar e calcular" para guardar a execução.
        </p>
      </div>
      <Badge
        variant={
          status === 'loading'
            ? 'warning'
            : status === 'error'
              ? 'danger'
              : status === 'success'
                ? 'success'
                : 'secondary'
        }
        className="shrink-0"
      >
        {status === 'loading' && (
          <Loader2 className="mr-1 h-3 w-3 animate-spin" />
        )}
        {status === 'success' && <CheckCircle2 className="mr-1 h-3 w-3" />}
        {status === 'error' && <AlertCircle className="mr-1 h-3 w-3" />}
        {status === 'loading'
          ? 'Calculando'
          : status === 'error'
            ? 'Inviável'
            : status === 'success'
              ? 'Convergiu'
              : 'Aguardando'}
      </Badge>
    </div>
  )
}

function PlotPlaceholder({
  state,
  message,
}: {
  state: 'idle' | 'loading' | 'error'
  message?: string
}) {
  return (
    <div className="flex h-[400px] flex-col items-center justify-center gap-3 rounded-md bg-muted/20 text-center text-sm">
      {state === 'loading' && (
        <>
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          <p className="text-muted-foreground">Calculando preview…</p>
        </>
      )}
      {state === 'error' && (
        <>
          <AlertCircle className="h-6 w-6 text-danger" />
          <p className="font-medium text-danger">Caso inviável</p>
          {message && (
            <p className="max-w-md text-xs text-muted-foreground">{message}</p>
          )}
          <p className="text-[11px] text-muted-foreground">
            Ajuste os inputs e o gráfico atualiza.
          </p>
        </>
      )}
      {state === 'idle' && (
        <>
          <Info className="h-6 w-6 text-muted-foreground" />
          <p className="text-muted-foreground">
            Preencha os campos à esquerda para ver o perfil calculado.
          </p>
        </>
      )}
    </div>
  )
}

function MetricCard({
  label,
  value,
  rows,
  extra,
  footer,
}: {
  label: string
  value?: string
  rows?: Array<[string, string]>
  extra?: React.ReactNode
  footer?: string
}) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-[11px] font-medium text-muted-foreground">
          {label}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-1.5 font-mono text-xs tabular-nums">
        {value && (
          <div className="text-lg font-semibold tracking-tight text-foreground">
            {value}
          </div>
        )}
        {extra}
        {rows && (
          <div className="space-y-0.5">
            {rows.map(([k, v]) => (
              <div key={k} className="flex justify-between gap-2">
                <span className="text-muted-foreground">{k}</span>
                <span className="font-medium text-foreground">{v}</span>
              </div>
            ))}
          </div>
        )}
        {footer && (
          <p className="text-[10px] text-muted-foreground">{footer}</p>
        )}
      </CardContent>
    </Card>
  )
}
