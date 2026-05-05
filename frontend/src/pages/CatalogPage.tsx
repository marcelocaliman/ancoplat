import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Copy,
  Lock,
  Pencil,
  Plus,
  RefreshCw,
  Search,
  Trash2,
  Unlock,
  X,
} from 'lucide-react'
import { useMemo, useState } from 'react'
import { Controller, useForm } from 'react-hook-form'
import { toast } from 'sonner'
import { z } from 'zod'
import { ApiError } from '@/api/client'
import {
  createLineType,
  deleteLineType,
  listLineTypes,
  updateLineType,
} from '@/api/endpoints'
import type { LineTypeOutput } from '@/api/types'
import { EmptyState } from '@/components/common/EmptyState'
import { CategoryBadge } from '@/components/common/StatusBadge'
import { Topbar } from '@/components/layout/Topbar'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useDebounce } from '@/hooks/useDebounce'
import { cn, fmtNumber } from '@/lib/utils'
import { MoreHorizontal } from 'lucide-react'
import { useSearchParams } from 'react-router-dom'
import { BuoysTab } from '@/pages/BuoysTab'

const lineTypeSchema = z.object({
  line_type: z.string().trim().min(1).max(50),
  category: z.enum(['Wire', 'StuddedChain', 'StudlessChain', 'Polyester']),
  diameter: z.number().positive(),
  dry_weight: z.number().positive(),
  wet_weight: z.number().positive(),
  break_strength: z.number().positive(),
  modulus: z.number().positive().optional().nullable(),
  qmoor_ea: z.number().positive().optional().nullable(),
  gmoor_ea: z.number().positive().optional().nullable(),
  seabed_friction_cf: z.number().min(0),
  manufacturer: z.string().max(200).optional().nullable(),
  serial_number: z.string().max(100).optional().nullable(),
  comments: z.string().max(2000).optional().nullable(),
  base_unit_system: z.enum(['imperial', 'metric']).default('metric'),
})
type LineTypeForm = z.infer<typeof lineTypeSchema>

const EMPTY_LT: LineTypeForm = {
  line_type: '',
  category: 'Wire',
  diameter: 0.076,
  dry_weight: 240,
  wet_weight: 201,
  break_strength: 3.78e6,
  modulus: null,
  qmoor_ea: 3.425e7,
  gmoor_ea: null,
  seabed_friction_cf: 0.3,
  manufacturer: null,
  serial_number: null,
  comments: null,
  base_unit_system: 'metric',
}

const PAGE_SIZE = 30

/**
 * F6 / Q6: tabs Cabos | Boias com URL deep-linking via `?tab=`.
 * - tab=cables (default)
 * - tab=buoys
 */
type CatalogTab = 'cables' | 'buoys'
const VALID_TABS: readonly CatalogTab[] = ['cables', 'buoys']

export function CatalogPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const tabParam = searchParams.get('tab')
  const activeTab: CatalogTab = (
    VALID_TABS as readonly string[]
  ).includes(tabParam ?? '') ? (tabParam as CatalogTab) : 'cables'

  function setActiveTab(tab: CatalogTab) {
    const next = new URLSearchParams(searchParams)
    if (tab === 'cables') next.delete('tab')
    else next.set('tab', tab)
    setSearchParams(next, { replace: true })
  }

  return (
    <>
      <Topbar />
      <div className="flex-1 overflow-auto custom-scroll p-6">
        <Tabs
          value={activeTab}
          onValueChange={(v) => setActiveTab(v as CatalogTab)}
        >
          <TabsList className="mb-4">
            <TabsTrigger value="cables">Cabos</TabsTrigger>
            <TabsTrigger value="buoys">Boias</TabsTrigger>
          </TabsList>
          <TabsContent value="cables">
            <CablesTab />
          </TabsContent>
          <TabsContent value="buoys">
            <BuoysTab />
          </TabsContent>
        </Tabs>
      </div>
    </>
  )
}

function CablesTab() {
  const queryClient = useQueryClient()

  const [search, setSearch] = useState('')
  const debounced = useDebounce(search, 300)
  const [categoryFilter, setCategoryFilter] = useState<string>('all')
  const [sourceFilter, setSourceFilter] = useState<string>('all')
  const [page, setPage] = useState(1)

  const [editing, setEditing] = useState<LineTypeOutput | null>(null)
  const [creating, setCreating] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<LineTypeOutput | null>(null)

  const { data, isLoading, isFetching, refetch } = useQuery({
    queryKey: ['line-types', 'list', page, debounced, categoryFilter],
    queryFn: () =>
      listLineTypes({
        page,
        page_size: PAGE_SIZE,
        search: debounced || undefined,
        category: categoryFilter === 'all' ? undefined : categoryFilter,
      }),
  })

  const rows = useMemo(() => {
    const items = data?.items ?? []
    return sourceFilter === 'all'
      ? items
      : items.filter((i) => i.data_source === sourceFilter)
  }, [data, sourceFilter])

  const deleteMutation = useMutation({
    mutationFn: (id: number) => deleteLineType(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['line-types'] })
      setDeleteTarget(null)
      toast.success('Tipo removido.')
    },
    onError: (err: unknown) => {
      toast.error('Falha ao remover', {
        description: err instanceof ApiError ? err.message : String(err),
      })
    },
  })

  const actions = (
    <>
      <Button
        variant="outline"
        size="sm"
        onClick={() => refetch()}
        disabled={isFetching}
      >
        <RefreshCw className={`h-4 w-4 ${isFetching ? 'animate-spin' : ''}`} />
      </Button>
      <Button size="sm" onClick={() => setCreating(true)}>
        <Plus className="h-4 w-4" />
        Novo tipo
      </Button>
    </>
  )

  return (
    <>
      <div className="mb-4 flex items-center justify-end gap-2">
        {actions}
      </div>
      <>
        {/* Filtros */}
        <div className="mb-5 flex flex-wrap items-end gap-3">
          <div className="min-w-64 flex-1">
            <Label htmlFor="cat-search" className="mb-1.5 block text-xs text-muted-foreground">
              Buscar
            </Label>
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
              <Input
                id="cat-search"
                value={search}
                onChange={(e) => {
                  setSearch(e.target.value)
                  setPage(1)
                }}
                placeholder="Nome do tipo (ex: IWRCEIPS)…"
                className="pl-8"
              />
              {search && (
                <button
                  type="button"
                  onClick={() => setSearch('')}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                  aria-label="Limpar busca"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              )}
            </div>
          </div>
          <div className="w-40">
            <Label className="mb-1.5 block text-xs text-muted-foreground">Categoria</Label>
            <Select value={categoryFilter} onValueChange={setCategoryFilter}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Todas</SelectItem>
                <SelectItem value="Wire">Wire</SelectItem>
                <SelectItem value="StuddedChain">Studded</SelectItem>
                <SelectItem value="StudlessChain">Studless</SelectItem>
                <SelectItem value="Polyester">Poliéster</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="w-40">
            <Label className="mb-1.5 block text-xs text-muted-foreground">Origem</Label>
            <Select value={sourceFilter} onValueChange={setSourceFilter}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Todas</SelectItem>
                <SelectItem value="legacy_qmoor">Legacy QMoor</SelectItem>
                <SelectItem value="user_input">Custom</SelectItem>
                <SelectItem value="manufacturer">Fabricante</SelectItem>
                <SelectItem value="certificate">Certificado</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="ml-auto text-xs text-muted-foreground">
            {isLoading ? 'Carregando…' : `${rows.length} de ${data?.total ?? 0} tipos`}
          </div>
        </div>

        {/* Tabela */}
        <div className="rounded-lg border border-border bg-card">
          {isLoading ? (
            <div className="space-y-2 p-4">
              {Array.from({ length: 8 }).map((_, i) => (
                <Skeleton key={i} className="h-10 w-full" />
              ))}
            </div>
          ) : rows.length === 0 ? (
            <EmptyState
              title="Nenhum tipo encontrado"
              description="Ajuste os filtros ou cadastre um novo tipo."
              className="m-4 border-none"
              action={
                <Button size="sm" onClick={() => setCreating(true)}>
                  <Plus className="h-4 w-4" />
                  Novo tipo
                </Button>
              }
            />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Nome</TableHead>
                  <TableHead>Categoria</TableHead>
                  <TableHead className="text-right">Ø (m)</TableHead>
                  <TableHead className="text-right">MBL (kN)</TableHead>
                  <TableHead className="text-right">w submerso (N/m)</TableHead>
                  <TableHead>μ</TableHead>
                  <TableHead>Origem</TableHead>
                  <TableHead className="w-10" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((lt) => {
                  const isLegacy = lt.data_source === 'legacy_qmoor'
                  return (
                    <TableRow key={lt.id}>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          {isLegacy && (
                            <Tooltip>
                              <TooltipTrigger asChild>
                                <Lock className="h-3 w-3 text-muted-foreground" />
                              </TooltipTrigger>
                              <TooltipContent side="right">
                                Imutável (legacy_qmoor)
                              </TooltipContent>
                            </Tooltip>
                          )}
                          {!isLegacy && (
                            <Tooltip>
                              <TooltipTrigger asChild>
                                <Unlock className="h-3 w-3 text-muted-foreground" />
                              </TooltipTrigger>
                              <TooltipContent side="right">Editável</TooltipContent>
                            </Tooltip>
                          )}
                          <span className="font-mono text-sm">{lt.line_type}</span>
                        </div>
                        {lt.manufacturer && (
                          <span className="ml-5 block text-[10px] text-muted-foreground">
                            {lt.manufacturer}
                          </span>
                        )}
                      </TableCell>
                      <TableCell>
                        <CategoryBadge category={lt.category} />
                      </TableCell>
                      <TableCell className="text-right font-mono tabular-nums">
                        {fmtNumber(lt.diameter, 4)}
                      </TableCell>
                      <TableCell className="text-right font-mono tabular-nums">
                        {fmtNumber(lt.break_strength / 1000, 0)}
                      </TableCell>
                      <TableCell className="text-right font-mono tabular-nums">
                        {fmtNumber(lt.wet_weight, 1)}
                      </TableCell>
                      <TableCell className="font-mono tabular-nums">
                        {fmtNumber(lt.seabed_friction_cf, 2)}
                      </TableCell>
                      <TableCell>
                        <Badge
                          variant={isLegacy ? 'secondary' : 'info'}
                          className="font-mono text-[10px]"
                        >
                          {lt.data_source}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right">
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button variant="ghost" size="icon" className="h-8 w-8">
                              <MoreHorizontal className="h-4 w-4" />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuItem onSelect={() => setEditing(lt)}>
                              {isLegacy ? (
                                <>
                                  <Copy className="h-4 w-4" />
                                  Duplicar como custom
                                </>
                              ) : (
                                <>
                                  <Pencil className="h-4 w-4" />
                                  Editar
                                </>
                              )}
                            </DropdownMenuItem>
                            {!isLegacy && (
                              <>
                                <DropdownMenuSeparator />
                                <DropdownMenuItem
                                  className="text-danger focus:text-danger"
                                  onSelect={() => setDeleteTarget(lt)}
                                >
                                  <Trash2 className="h-4 w-4" />
                                  Excluir
                                </DropdownMenuItem>
                              </>
                            )}
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          )}
        </div>

        {/* Paginação simples */}
        {data && data.total > PAGE_SIZE && (
          <div className="mt-4 flex items-center justify-between text-sm">
            <span className="text-muted-foreground">
              Página {page} de {Math.max(1, Math.ceil(data.total / PAGE_SIZE))}
            </span>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
              >
                Anterior
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() =>
                  setPage((p) =>
                    Math.min(Math.ceil(data.total / PAGE_SIZE), p + 1),
                  )
                }
                disabled={page >= Math.ceil(data.total / PAGE_SIZE)}
              >
                Próxima
              </Button>
            </div>
          </div>
        )}
      </>

      {/* Dialog de criar/editar/duplicar */}
      {(creating || editing) && (
        <LineTypeDialog
          open={creating || editing != null}
          initial={editing ?? undefined}
          mode={
            creating
              ? 'create'
              : editing?.data_source === 'legacy_qmoor'
                ? 'duplicate'
                : 'edit'
          }
          onClose={() => {
            setCreating(false)
            setEditing(null)
          }}
          onSaved={() => {
            queryClient.invalidateQueries({ queryKey: ['line-types'] })
            setCreating(false)
            setEditing(null)
          }}
        />
      )}

      {/* Dialog de confirmação de exclusão */}
      <Dialog
        open={deleteTarget != null}
        onOpenChange={(o) => !o && setDeleteTarget(null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Excluir tipo {deleteTarget?.line_type}?</DialogTitle>
            <DialogDescription>
              Esta ação não pode ser desfeita. Casos que referenciam este tipo
              por nome continuarão com os valores atuais.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setDeleteTarget(null)}>
              Cancelar
            </Button>
            <Button
              variant="destructive"
              onClick={() => deleteTarget && deleteMutation.mutate(deleteTarget.id)}
              disabled={deleteMutation.isPending}
            >
              <Trash2 className="h-4 w-4" />
              Excluir
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}

interface LineTypeDialogProps {
  open: boolean
  initial?: LineTypeOutput
  mode: 'create' | 'edit' | 'duplicate'
  onClose: () => void
  onSaved: () => void
}

function LineTypeDialog({
  open,
  initial,
  mode,
  onClose,
  onSaved,
}: LineTypeDialogProps) {
  const defaults: LineTypeForm = initial
    ? {
        line_type:
          mode === 'duplicate' ? `${initial.line_type}-copy` : initial.line_type,
        category: initial.category as LineTypeForm['category'],
        diameter: initial.diameter,
        dry_weight: initial.dry_weight,
        wet_weight: initial.wet_weight,
        break_strength: initial.break_strength,
        modulus: initial.modulus ?? null,
        qmoor_ea: initial.qmoor_ea ?? null,
        gmoor_ea: initial.gmoor_ea ?? null,
        seabed_friction_cf: initial.seabed_friction_cf,
        manufacturer: initial.manufacturer ?? null,
        serial_number: initial.serial_number ?? null,
        comments: initial.comments ?? null,
        base_unit_system: (initial.base_unit_system ??
          'metric') as 'imperial' | 'metric',
      }
    : EMPTY_LT

  const form = useForm<LineTypeForm>({
    resolver: zodResolver(lineTypeSchema) as never,
    defaultValues: defaults,
  })
  const {
    register,
    handleSubmit,
    control,
    formState: { errors, isSubmitting },
  } = form

  const mutation = useMutation({
    mutationFn: async (v: LineTypeForm) => {
      const payload = {
        ...v,
        modulus: v.modulus ?? null,
        qmoor_ea: v.qmoor_ea ?? null,
        gmoor_ea: v.gmoor_ea ?? null,
        manufacturer: v.manufacturer ?? null,
        serial_number: v.serial_number ?? null,
        comments: v.comments ?? null,
      }
      if (mode === 'edit' && initial) {
        return updateLineType(initial.id, payload as never)
      }
      return createLineType(payload as never)
    },
    onSuccess: () => {
      toast.success(
        mode === 'edit' ? 'Tipo atualizado' : 'Tipo cadastrado',
      )
      onSaved()
    },
    onError: (err: unknown) => {
      toast.error('Falha ao salvar', {
        description: err instanceof ApiError ? err.message : String(err),
      })
    },
  })

  const onSubmit = (v: LineTypeForm) => mutation.mutate(v)

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>
            {mode === 'edit'
              ? `Editar ${initial?.line_type}`
              : mode === 'duplicate'
                ? `Duplicar ${initial?.line_type}`
                : 'Novo tipo de linha'}
          </DialogTitle>
          <DialogDescription>
            Valores em SI (m, N, N/m, Pa). O campo base_unit_system é apenas
            metadado de origem — não converte unidades.
          </DialogDescription>
        </DialogHeader>

        <form
          onSubmit={handleSubmit(onSubmit)}
          className="grid gap-4 sm:grid-cols-2"
          noValidate
        >
          <div className="sm:col-span-2">
            <Label htmlFor="lt-name">Identificador</Label>
            <Input
              id="lt-name"
              {...register('line_type')}
              className="mt-1 font-mono"
              aria-invalid={!!errors.line_type}
            />
          </div>

          <div>
            <Label>Categoria</Label>
            <Controller
              control={control}
              name="category"
              render={({ field }) => (
                <Select value={field.value} onValueChange={field.onChange}>
                  <SelectTrigger className="mt-1">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="Wire">Wire</SelectItem>
                    <SelectItem value="StuddedChain">StuddedChain</SelectItem>
                    <SelectItem value="StudlessChain">StudlessChain</SelectItem>
                    <SelectItem value="Polyester">Polyester</SelectItem>
                  </SelectContent>
                </Select>
              )}
            />
          </div>

          <div>
            <Label htmlFor="lt-diameter">Diâmetro (m)</Label>
            <Input
              id="lt-diameter"
              type="number"
              step="0.0001"
              {...register('diameter', { valueAsNumber: true })}
              className="mt-1 font-mono"
            />
          </div>

          <div>
            <Label htmlFor="lt-dry">Peso seco (N/m)</Label>
            <Input
              id="lt-dry"
              type="number"
              step="0.1"
              {...register('dry_weight', { valueAsNumber: true })}
              className="mt-1 font-mono"
            />
          </div>
          <div>
            <Label htmlFor="lt-wet">Peso submerso (N/m)</Label>
            <Input
              id="lt-wet"
              type="number"
              step="0.1"
              {...register('wet_weight', { valueAsNumber: true })}
              className="mt-1 font-mono"
            />
          </div>

          <div>
            <Label htmlFor="lt-mbl">MBL (N)</Label>
            <Input
              id="lt-mbl"
              type="number"
              step="1000"
              {...register('break_strength', { valueAsNumber: true })}
              className="mt-1 font-mono"
            />
          </div>
          <div>
            <Label htmlFor="lt-mu">μ seabed</Label>
            <Input
              id="lt-mu"
              type="number"
              step="0.05"
              {...register('seabed_friction_cf', { valueAsNumber: true })}
              className="mt-1 font-mono"
            />
          </div>

          <div>
            <Label htmlFor="lt-qmoorEA">EA (N) — qmoor</Label>
            <Input
              id="lt-qmoorEA"
              type="number"
              step="1e6"
              {...register('qmoor_ea', { valueAsNumber: true })}
              className="mt-1 font-mono"
            />
          </div>
          <div>
            <Label htmlFor="lt-modulus">Módulo (Pa)</Label>
            <Input
              id="lt-modulus"
              type="number"
              step="1e9"
              {...register('modulus', { valueAsNumber: true })}
              className="mt-1 font-mono"
            />
          </div>

          <div className="sm:col-span-2">
            <Label htmlFor="lt-manu">Fabricante (opcional)</Label>
            <Input
              id="lt-manu"
              {...register('manufacturer')}
              className="mt-1"
            />
          </div>

          <DialogFooter className="gap-2 sm:col-span-2">
            <Button variant="outline" type="button" onClick={onClose}>
              Cancelar
            </Button>
            <Button
              type="submit"
              disabled={isSubmitting || mutation.isPending}
              className={cn(mutation.isPending && 'opacity-60')}
            >
              {mode === 'edit' ? 'Salvar' : 'Cadastrar'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
