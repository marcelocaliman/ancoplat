import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Info, Save, Zap } from 'lucide-react'
import { useEffect } from 'react'
import { Controller, useForm } from 'react-hook-form'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { toast } from 'sonner'
import { ApiError } from '@/api/client'
import {
  createCase,
  fetchCriteriaProfiles,
  getCase,
  solveCase,
  updateCase,
} from '@/api/endpoints'
import type { LineTypeOutput } from '@/api/types'
import { LineTypePicker } from '@/components/common/LineTypePicker'
import { Topbar } from '@/components/layout/Topbar'
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
import {
  EMPTY_CASE,
  caseInputSchema,
  type CaseFormValues,
} from '@/lib/caseSchema'
import { cn, fmtNumber } from '@/lib/utils'

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
    // Cast: zodResolver retorna um tipo genérico que o RHF strict-mode tem
    // dificuldade de casar com schemas que usam .refine() (ZodEffects).
    // Runtime behavior é correto; o cast é só p/ compilação.
    resolver: zodResolver(caseInputSchema) as never,
    defaultValues: EMPTY_CASE,
    mode: 'onBlur',
  })
  const {
    register,
    control,
    handleSubmit,
    watch,
    setValue,
    reset,
    formState: { errors, isSubmitting },
  } = form

  // Hidrata formulário ao carregar caso existente
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

  const criteriaProfile = watch('criteria_profile')
  const mode = watch('boundary.mode')

  const saveMutation = useMutation({
    mutationFn: async (values: CaseFormValues) => {
      const payload = {
        ...values,
        description: values.description?.trim() || null,
      } as unknown as Parameters<typeof createCase>[0]
      return isEdit
        ? updateCase(Number(id), payload)
        : createCase(payload)
    },
    onSuccess: (out) => {
      queryClient.invalidateQueries({ queryKey: ['cases'] })
      queryClient.invalidateQueries({ queryKey: ['case', String(out.id)] })
      return out
    },
    onError: (err) => {
      const msg = err instanceof ApiError ? err.message : String(err)
      toast.error('Falha ao salvar caso', { description: msg })
    },
  })

  async function onSubmit(values: CaseFormValues) {
    try {
      const saved = await saveMutation.mutateAsync(values)
      toast.success(isEdit ? 'Caso atualizado.' : 'Caso criado.')
      navigate(`/cases/${saved.id}`)
    } catch {
      /* onError handler já notificou */
    }
  }

  async function onSubmitAndSolve(values: CaseFormValues) {
    try {
      const saved = await saveMutation.mutateAsync(values)
      toast.promise(solveCase(saved.id), {
        loading: 'Calculando…',
        success: 'Caso calculado com sucesso.',
        error: (err: unknown) => ({
          message:
            err instanceof ApiError
              ? `Solver: ${err.message}`
              : 'Erro no solver',
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
    // Preenche propriedades técnicas a partir do catálogo
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

  return (
    <>
      <Topbar breadcrumbs={breadcrumbs} />
      <div className="flex-1 overflow-auto custom-scroll p-6 pb-16">
        <form
          onSubmit={handleSubmit(onSubmit)}
          className="mx-auto flex max-w-3xl flex-col gap-6"
          noValidate
        >
          {/* Identificação */}
          <Card>
            <CardHeader>
              <CardTitle>Identificação</CardTitle>
              <CardDescription>
                Nome descritivo e uma descrição opcional para localizar o caso depois.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <Label htmlFor="name">
                  Nome <span className="text-danger">*</span>
                </Label>
                <Input
                  id="name"
                  {...register('name')}
                  aria-invalid={!!errors.name}
                  className="mt-1.5"
                  placeholder="ex.: BC-01 — catenária pura suspensa"
                />
                {errors.name && (
                  <p className="mt-1 text-xs text-danger">{errors.name.message}</p>
                )}
              </div>
              <div>
                <Label htmlFor="description">Descrição</Label>
                <Textarea
                  id="description"
                  {...register('description')}
                  className="mt-1.5"
                  rows={3}
                  placeholder="Notas sobre o caso, condições de projeto, premissas…"
                />
              </div>
            </CardContent>
          </Card>

          {/* Segmento */}
          <Card>
            <CardHeader>
              <CardTitle>Segmento de linha</CardTitle>
              <CardDescription>
                Propriedades do tipo de linha. Escolha do catálogo para preencher
                automaticamente, ou edite manualmente (override). MVP v1 suporta
                apenas 1 segmento (multi-segmento em v2.1).
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <Label>Tipo de linha (catálogo)</Label>
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
                      className="mt-1.5"
                    />
                  )}
                />
              </div>

              <Separator />

              <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
                <div className="col-span-2 sm:col-span-1">
                  <Label htmlFor="length">Comprimento (m)</Label>
                  <Input
                    id="length"
                    type="number"
                    step="0.01"
                    {...register('segments.0.length', { valueAsNumber: true })}
                    className="mt-1.5 font-mono"
                  />
                  {errors.segments?.[0]?.length && (
                    <p className="mt-1 text-xs text-danger">
                      {errors.segments[0]?.length?.message}
                    </p>
                  )}
                </div>
                <div>
                  <Label htmlFor="w">Peso submerso (N/m)</Label>
                  <Input
                    id="w"
                    type="number"
                    step="0.01"
                    {...register('segments.0.w', { valueAsNumber: true })}
                    className="mt-1.5 font-mono"
                  />
                </div>
                <div>
                  <Label htmlFor="EA">EA (N)</Label>
                  <Input
                    id="EA"
                    type="number"
                    step="1e5"
                    {...register('segments.0.EA', { valueAsNumber: true })}
                    className="mt-1.5 font-mono"
                  />
                </div>
                <div>
                  <Label htmlFor="MBL">MBL (N)</Label>
                  <Input
                    id="MBL"
                    type="number"
                    step="1000"
                    {...register('segments.0.MBL', { valueAsNumber: true })}
                    className="mt-1.5 font-mono"
                  />
                </div>
                <div className="col-span-2">
                  <Label htmlFor="category">Categoria</Label>
                  <Controller
                    control={control}
                    name="segments.0.category"
                    render={({ field }) => (
                      <Select
                        value={field.value ?? undefined}
                        onValueChange={(v) => field.onChange(v)}
                      >
                        <SelectTrigger id="category" className="mt-1.5">
                          <SelectValue placeholder="Selecione…" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="Wire">Wire rope</SelectItem>
                          <SelectItem value="StuddedChain">Studded chain</SelectItem>
                          <SelectItem value="StudlessChain">Studless chain</SelectItem>
                          <SelectItem value="Polyester">Poliéster</SelectItem>
                        </SelectContent>
                      </Select>
                    )}
                  />
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Boundary */}
          <Card>
            <CardHeader>
              <CardTitle>Condições de contorno</CardTitle>
              <CardDescription>
                Geometria do sistema e modo de solução.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label htmlFor="h">Lâmina d'água (m)</Label>
                  <Input
                    id="h"
                    type="number"
                    step="0.1"
                    {...register('boundary.h', { valueAsNumber: true })}
                    className="mt-1.5 font-mono"
                  />
                  {errors.boundary?.h && (
                    <p className="mt-1 text-xs text-danger">
                      {errors.boundary.h.message}
                    </p>
                  )}
                </div>
                <div>
                  <Label htmlFor="mode">Modo</Label>
                  <Controller
                    control={control}
                    name="boundary.mode"
                    render={({ field }) => (
                      <Select value={field.value} onValueChange={field.onChange}>
                        <SelectTrigger id="mode" className="mt-1.5">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="Tension">Tension (T_fl dado)</SelectItem>
                          <SelectItem value="Range">Range (X dado)</SelectItem>
                        </SelectContent>
                      </Select>
                    )}
                  />
                </div>
                <div className="col-span-2">
                  <Label htmlFor="input_value">
                    {mode === 'Tension'
                      ? 'Tração no fairlead (N)'
                      : 'Distância horizontal total (m)'}
                  </Label>
                  <Input
                    id="input_value"
                    type="number"
                    step="any"
                    {...register('boundary.input_value', { valueAsNumber: true })}
                    className="mt-1.5 font-mono"
                  />
                  <p className="mt-1 text-[11px] text-muted-foreground">
                    {mode === 'Tension'
                      ? 'Ex.: 785_000 para 785 kN'
                      : 'Distância entre âncora e fairlead'}
                  </p>
                </div>
              </div>
              {/* v1: fairlead na superfície, âncora no seabed (not editable) */}
            </CardContent>
          </Card>

          {/* Seabed */}
          <Card>
            <CardHeader>
              <CardTitle>Seabed</CardTitle>
              <CardDescription>
                Coeficiente de atrito axial. Seção 4.4 do Documento A: corrente em
                argila ≈ 0,5–1,0; wire rope ≈ 0,25–0,50; poliéster ≈ 0,15–0,40.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex items-center gap-3">
                <div className="flex-1">
                  <Label htmlFor="mu" className="flex items-center gap-1">
                    μ
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Info
                          className="h-3 w-3 text-muted-foreground"
                          aria-label="Faixas típicas"
                        />
                      </TooltipTrigger>
                      <TooltipContent side="right" className="max-w-xs">
                        μ=0 para análise sem atrito. Valores típicos: wire 0,3,
                        corrente 0,7, poliéster 0,25.
                      </TooltipContent>
                    </Tooltip>
                  </Label>
                  <Input
                    id="mu"
                    type="number"
                    step="0.05"
                    min="0"
                    {...register('seabed.mu', { valueAsNumber: true })}
                    className="mt-1.5 font-mono"
                  />
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Critério de utilização */}
          <Card>
            <CardHeader>
              <CardTitle>Critério de utilização</CardTitle>
              <CardDescription>
                Perfil que classifica T_fl/MBL como ok / amarelo / vermelho /
                rompido. Ver Seção 5 do Documento A.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <Controller
                control={control}
                name="criteria_profile"
                render={({ field }) => (
                  <Select value={field.value} onValueChange={field.onChange}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {profiles?.map((p) => (
                        <SelectItem key={p.name} value={p.name}>
                          <div className="flex flex-col">
                            <span className="font-medium">{p.name}</span>
                            <span className="text-[10px] text-muted-foreground">
                              yellow {fmtNumber(p.yellow_ratio, 2)} · red{' '}
                              {fmtNumber(p.red_ratio, 2)} · broken{' '}
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
                <div
                  className={cn(
                    'grid grid-cols-3 gap-3 rounded-md border border-dashed border-border p-3',
                  )}
                >
                  {(['yellow_ratio', 'red_ratio', 'broken_ratio'] as const).map(
                    (k) => (
                      <div key={k}>
                        <Label className="text-xs">{k.replace('_ratio', '')}</Label>
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
                          className="mt-1 font-mono"
                        />
                      </div>
                    ),
                  )}
                  {errors.user_defined_limits && (
                    <p className="col-span-3 text-xs text-danger">
                      {errors.user_defined_limits.message as string}
                    </p>
                  )}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Restrições MVP v1 (visuais) */}
          <Card className="bg-muted/40">
            <CardContent className="flex items-start gap-3 p-4 text-sm">
              <Info className="mt-0.5 h-4 w-4 shrink-0 text-info" />
              <div className="flex-1 text-muted-foreground">
                MVP v1: fairlead assumido na superfície (startpoint_depth = 0) e
                âncora no seabed (endpoint_grounded = true). Suporte para âncora
                elevada e fairlead afundado virá em v2+.
              </div>
              <Switch checked disabled aria-label="Âncora no seabed (v1)" />
            </CardContent>
          </Card>

          {/* Actions */}
          <div className="flex flex-col-reverse items-stretch gap-2 sm:flex-row sm:justify-end">
            <Button variant="outline" asChild>
              <Link to={isEdit ? `/cases/${id}` : '/cases'}>Cancelar</Link>
            </Button>
            <Button
              variant="outline"
              type="submit"
              disabled={isSubmitting || saveMutation.isPending}
            >
              <Save className="h-4 w-4" />
              Salvar
            </Button>
            <Button
              type="button"
              onClick={handleSubmit(onSubmitAndSolve)}
              disabled={isSubmitting || saveMutation.isPending}
            >
              <Zap className="h-4 w-4" />
              Salvar e calcular
            </Button>
          </div>
        </form>
      </div>
    </>
  )
}
