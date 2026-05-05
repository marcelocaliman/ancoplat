/**
 * Tab "Boias" da página /catalog (F6 / Q6).
 *
 * Espelha o padrão de listagem de tipos de linha: tabela com filtros,
 * busca debounced, edição/criação user_input, proteção de seed.
 *
 * URL deep-linking é gerenciado pelo CatalogPage via search params
 * (`?tab=buoys`) — esta tab apenas renderiza o conteúdo.
 */
import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Lock,
  Pencil,
  Plus,
  Search,
  Trash2,
  Unlock,
  X,
  MoreHorizontal,
  Copy,
} from 'lucide-react'
import { useMemo, useState } from 'react'
import { Controller, useForm } from 'react-hook-form'
import { toast } from 'sonner'
import { z } from 'zod'
import { ApiError } from '@/api/client'
import { createBuoy, deleteBuoy, listBuoys, updateBuoy } from '@/api/endpoints'
import type { BuoyOutput } from '@/api/types'
import { EmptyState } from '@/components/common/EmptyState'
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
import { useDebounce } from '@/hooks/useDebounce'
import { cn, fmtNumber } from '@/lib/utils'

const buoySchema = z.object({
  name: z.string().trim().min(1).max(120),
  buoy_type: z.enum(['surface', 'submersible']),
  end_type: z.enum(['flat', 'hemispherical', 'elliptical', 'semi_conical']),
  outer_diameter: z.number().positive(),
  length: z.number().positive(),
  weight_in_air: z.number().min(0),
  submerged_force: z.number(), // pode ser negativo (clump)
  manufacturer: z.string().max(200).optional().nullable(),
  serial_number: z.string().max(100).optional().nullable(),
  comments: z.string().max(2000).optional().nullable(),
  base_unit_system: z.enum(['imperial', 'metric']).default('metric'),
})
type BuoyForm = z.infer<typeof buoySchema>

const EMPTY_BUOY: BuoyForm = {
  name: '',
  buoy_type: 'submersible',
  end_type: 'elliptical',
  outer_diameter: 2.0,
  length: 3.0,
  weight_in_air: 4900,
  submerged_force: 60000,
  manufacturer: null,
  serial_number: null,
  comments: null,
  base_unit_system: 'metric',
}

const PAGE_SIZE = 30

const IMMUTABLE_SOURCES = new Set([
  'excel_buoy_calc_v1',
  'generic_offshore',
])
function isImmutable(b: BuoyOutput) {
  return (
    IMMUTABLE_SOURCES.has(b.data_source) ||
    b.data_source.startsWith('manufacturer')
  )
}

export function BuoysTab() {
  const queryClient = useQueryClient()

  const [search, setSearch] = useState('')
  const debounced = useDebounce(search, 300)
  const [endTypeFilter, setEndTypeFilter] = useState<string>('all')
  const [buoyTypeFilter, setBuoyTypeFilter] = useState<string>('all')
  const [page, setPage] = useState(1)

  const [editing, setEditing] = useState<BuoyOutput | null>(null)
  const [creating, setCreating] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<BuoyOutput | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: [
      'buoys', 'list', page, debounced, endTypeFilter, buoyTypeFilter,
    ],
    queryFn: () =>
      listBuoys({
        page,
        page_size: PAGE_SIZE,
        search: debounced || undefined,
        end_type: endTypeFilter === 'all'
          ? undefined
          : (endTypeFilter as 'flat' | 'hemispherical' | 'elliptical' | 'semi_conical'),
        buoy_type: buoyTypeFilter === 'all'
          ? undefined
          : (buoyTypeFilter as 'surface' | 'submersible'),
      }),
  })

  const rows = useMemo(() => data?.items ?? [], [data])

  const deleteMutation = useMutation({
    mutationFn: (id: number) => deleteBuoy(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['buoys'] })
      setDeleteTarget(null)
      toast.success('Boia removida.')
    },
    onError: (err: unknown) => {
      toast.error('Falha ao remover', {
        description: err instanceof ApiError ? err.message : String(err),
      })
    },
  })

  return (
    <>
      <div className="mb-4 flex items-center justify-end">
        <Button size="sm" onClick={() => setCreating(true)}>
          <Plus className="h-4 w-4" />
          Nova boia
        </Button>
      </div>
      <div className="mb-5 flex flex-wrap items-end gap-3">
        <div className="min-w-64 flex-1">
          <Label htmlFor="buoy-search" className="mb-1.5 block text-xs text-muted-foreground">
            Buscar
          </Label>
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
            <Input
              id="buoy-search"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value)
                setPage(1)
              }}
              placeholder="Nome (ex: GEN-Hemi)…"
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
        <div className="w-44">
          <Label className="mb-1.5 block text-xs text-muted-foreground">Formato</Label>
          <Select value={endTypeFilter} onValueChange={setEndTypeFilter}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Todos</SelectItem>
              <SelectItem value="flat">Plano</SelectItem>
              <SelectItem value="hemispherical">Hemisférico</SelectItem>
              <SelectItem value="elliptical">Elíptico</SelectItem>
              <SelectItem value="semi_conical">Semi-cônico</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="w-40">
          <Label className="mb-1.5 block text-xs text-muted-foreground">Tipo</Label>
          <Select value={buoyTypeFilter} onValueChange={setBuoyTypeFilter}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Todos</SelectItem>
              <SelectItem value="surface">Superfície</SelectItem>
              <SelectItem value="submersible">Submergível</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="ml-auto text-xs text-muted-foreground">
          {isLoading ? 'Carregando…' : `${rows.length} de ${data?.total ?? 0} boias`}
        </div>
      </div>

      <div className="rounded-lg border border-border bg-card">
        {isLoading ? (
          <div className="space-y-2 p-4">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-10 w-full" />
            ))}
          </div>
        ) : rows.length === 0 ? (
          <EmptyState
            title="Nenhuma boia encontrada"
            description="Ajuste os filtros ou cadastre uma nova."
            className="m-4 border-none"
            action={
              <Button size="sm" onClick={() => setCreating(true)}>
                <Plus className="h-4 w-4" />
                Nova boia
              </Button>
            }
          />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Nome</TableHead>
                <TableHead>Tipo</TableHead>
                <TableHead>Formato</TableHead>
                <TableHead className="text-right">Ø (m)</TableHead>
                <TableHead className="text-right">L (m)</TableHead>
                <TableHead className="text-right">W ar (kN)</TableHead>
                <TableHead className="text-right">F_b (kN)</TableHead>
                <TableHead>Origem</TableHead>
                <TableHead className="w-10" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((b) => {
                const immutable = isImmutable(b)
                return (
                  <TableRow key={b.id}>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        {immutable ? (
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <Lock className="h-3 w-3 text-muted-foreground" />
                            </TooltipTrigger>
                            <TooltipContent side="right">
                              Imutável ({b.data_source})
                            </TooltipContent>
                          </Tooltip>
                        ) : (
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <Unlock className="h-3 w-3 text-muted-foreground" />
                            </TooltipTrigger>
                            <TooltipContent side="right">Editável</TooltipContent>
                          </Tooltip>
                        )}
                        <span className="font-mono text-sm">{b.name}</span>
                      </div>
                      {b.manufacturer && (
                        <span className="ml-5 block text-[10px] text-muted-foreground">
                          {b.manufacturer}
                        </span>
                      )}
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline" className="text-[10px]">
                        {b.buoy_type}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline" className="text-[10px]">
                        {b.end_type}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right font-mono tabular-nums">
                      {fmtNumber(b.outer_diameter, 2)}
                    </TableCell>
                    <TableCell className="text-right font-mono tabular-nums">
                      {fmtNumber(b.length, 2)}
                    </TableCell>
                    <TableCell className="text-right font-mono tabular-nums">
                      {fmtNumber(b.weight_in_air / 1000, 1)}
                    </TableCell>
                    <TableCell className="text-right font-mono tabular-nums">
                      {fmtNumber(b.submerged_force / 1000, 1)}
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant={immutable ? 'secondary' : 'info'}
                        className="font-mono text-[10px]"
                      >
                        {b.data_source}
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
                          <DropdownMenuItem onSelect={() => setEditing(b)}>
                            {immutable ? (
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
                          {!immutable && (
                            <>
                              <DropdownMenuSeparator />
                              <DropdownMenuItem
                                className="text-danger focus:text-danger"
                                onSelect={() => setDeleteTarget(b)}
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

      {data && data.total > PAGE_SIZE && (
        <div className="mt-4 flex items-center justify-between text-sm">
          <span className="text-muted-foreground">
            Página {page} de {Math.max(1, Math.ceil(data.total / PAGE_SIZE))}
          </span>
          <div className="flex gap-2">
            <Button
              variant="outline" size="sm"
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
            >
              Anterior
            </Button>
            <Button
              variant="outline" size="sm"
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

      {(creating || editing) && (
        <BuoyDialog
          open={creating || editing != null}
          initial={editing ?? undefined}
          mode={
            creating
              ? 'create'
              : editing && isImmutable(editing)
                ? 'duplicate'
                : 'edit'
          }
          onClose={() => {
            setCreating(false)
            setEditing(null)
          }}
          onSaved={() => {
            queryClient.invalidateQueries({ queryKey: ['buoys'] })
            setCreating(false)
            setEditing(null)
          }}
        />
      )}

      <Dialog
        open={deleteTarget != null}
        onOpenChange={(o) => !o && setDeleteTarget(null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Excluir boia {deleteTarget?.name}?</DialogTitle>
            <DialogDescription>
              Esta ação não pode ser desfeita. Attachments referenciando esta
              boia mantêm os valores físicos atuais; `buoy_catalog_id` ficará
              órfão (rastreabilidade quebrada).
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setDeleteTarget(null)}>
              Cancelar
            </Button>
            <Button
              variant="destructive"
              onClick={() =>
                deleteTarget && deleteMutation.mutate(deleteTarget.id)
              }
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

interface BuoyDialogProps {
  open: boolean
  initial?: BuoyOutput
  mode: 'create' | 'edit' | 'duplicate'
  onClose: () => void
  onSaved: () => void
}

function BuoyDialog({ open, initial, mode, onClose, onSaved }: BuoyDialogProps) {
  const defaults: BuoyForm = initial
    ? {
        name: mode === 'duplicate' ? `${initial.name}-copy` : initial.name,
        buoy_type: initial.buoy_type as BuoyForm['buoy_type'],
        end_type: initial.end_type as BuoyForm['end_type'],
        outer_diameter: initial.outer_diameter,
        length: initial.length,
        weight_in_air: initial.weight_in_air,
        submerged_force: initial.submerged_force,
        manufacturer: initial.manufacturer ?? null,
        serial_number: initial.serial_number ?? null,
        comments: initial.comments ?? null,
        base_unit_system: (initial.base_unit_system ?? 'metric') as
          | 'imperial'
          | 'metric',
      }
    : EMPTY_BUOY

  const form = useForm<BuoyForm>({
    resolver: zodResolver(buoySchema) as never,
    defaultValues: defaults,
  })
  const {
    register,
    handleSubmit,
    control,
    formState: { errors, isSubmitting },
  } = form

  const mutation = useMutation({
    mutationFn: async (v: BuoyForm) => {
      const payload = {
        ...v,
        manufacturer: v.manufacturer ?? null,
        serial_number: v.serial_number ?? null,
        comments: v.comments ?? null,
      }
      if (mode === 'edit' && initial) {
        return updateBuoy(initial.id, payload as never)
      }
      return createBuoy(payload as never)
    },
    onSuccess: () => {
      toast.success(mode === 'edit' ? 'Boia atualizada' : 'Boia cadastrada')
      onSaved()
    },
    onError: (err: unknown) => {
      toast.error('Falha ao salvar', {
        description: err instanceof ApiError ? err.message : String(err),
      })
    },
  })

  const onSubmit = (v: BuoyForm) => mutation.mutate(v)

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>
            {mode === 'edit'
              ? `Editar ${initial?.name}`
              : mode === 'duplicate'
                ? `Duplicar ${initial?.name}`
                : 'Nova boia'}
          </DialogTitle>
          <DialogDescription>
            Valores em SI (m, N). `submerged_force` é o empuxo líquido
            (V·ρ·g − weight_in_air). Pode ser negativo se o peso domina
            o empuxo (objeto se torna clump_weight).
          </DialogDescription>
        </DialogHeader>

        <form
          onSubmit={handleSubmit(onSubmit)}
          className="grid gap-4 sm:grid-cols-2"
          noValidate
        >
          <div className="sm:col-span-2">
            <Label htmlFor="b-name">Identificador</Label>
            <Input
              id="b-name"
              {...register('name')}
              className="mt-1 font-mono"
              aria-invalid={!!errors.name}
            />
          </div>

          <div>
            <Label>Tipo</Label>
            <Controller
              control={control}
              name="buoy_type"
              render={({ field }) => (
                <Select value={field.value} onValueChange={field.onChange}>
                  <SelectTrigger className="mt-1">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="surface">Superfície</SelectItem>
                    <SelectItem value="submersible">Submergível</SelectItem>
                  </SelectContent>
                </Select>
              )}
            />
          </div>

          <div>
            <Label>Formato dos terminais</Label>
            <Controller
              control={control}
              name="end_type"
              render={({ field }) => (
                <Select value={field.value} onValueChange={field.onChange}>
                  <SelectTrigger className="mt-1">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="flat">Plano</SelectItem>
                    <SelectItem value="hemispherical">Hemisférico</SelectItem>
                    <SelectItem value="elliptical">Elíptico</SelectItem>
                    <SelectItem value="semi_conical">Semi-cônico</SelectItem>
                  </SelectContent>
                </Select>
              )}
            />
          </div>

          <div>
            <Label htmlFor="b-d">Diâmetro D (m)</Label>
            <Input
              id="b-d" type="number" step="0.01"
              {...register('outer_diameter', { valueAsNumber: true })}
              className="mt-1 font-mono"
            />
          </div>
          <div>
            <Label htmlFor="b-l">Comprimento L (m)</Label>
            <Input
              id="b-l" type="number" step="0.01"
              {...register('length', { valueAsNumber: true })}
              className="mt-1 font-mono"
            />
          </div>
          <div>
            <Label htmlFor="b-w">Peso no ar (N)</Label>
            <Input
              id="b-w" type="number" step="100"
              {...register('weight_in_air', { valueAsNumber: true })}
              className="mt-1 font-mono"
            />
          </div>
          <div>
            <Label htmlFor="b-fb">Empuxo líquido F_b (N)</Label>
            <Input
              id="b-fb" type="number" step="1000"
              {...register('submerged_force', { valueAsNumber: true })}
              className="mt-1 font-mono"
              title="V · ρ · g − weight_in_air. Pode ser negativo (clump)."
            />
          </div>

          <div className="sm:col-span-2">
            <Label htmlFor="b-manu">Fabricante (opcional)</Label>
            <Input id="b-manu" {...register('manufacturer')} className="mt-1" />
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
