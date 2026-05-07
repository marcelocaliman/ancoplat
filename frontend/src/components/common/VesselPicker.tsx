/**
 * Picker de vessels do catálogo (Sprint 6 / Commit 53).
 *
 * Estilo idêntico a BuoyPicker: popover com busca server-side
 * (debounced) e marcação check do selecionado.
 *
 * Quando o user escolhe, chama `onPick(vessel)`. Quem decide o que
 * fazer com o vessel (popular form fields, gravar catalog_id, etc)
 * é o caller (VesselEditor).
 */
import { useQuery } from '@tanstack/react-query'
import { Check, ChevronDown, Search, X } from 'lucide-react'
import { useMemo, useState } from 'react'
import { listVessels } from '@/api/endpoints'
import type { VesselOutput } from '@/api/types'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover'
import { useDebounce } from '@/hooks/useDebounce'
import { cn } from '@/lib/utils'

export interface VesselPickerProps {
  selectedId: number | null
  onPick: (v: VesselOutput) => void
  onClear?: () => void
  className?: string
  disabled?: boolean
}

export function VesselPicker({
  selectedId,
  onPick,
  onClear,
  className,
  disabled,
}: VesselPickerProps) {
  const [open, setOpen] = useState(false)
  const [search, setSearch] = useState('')
  const debounced = useDebounce(search, 250)

  const { data, isLoading } = useQuery({
    queryKey: ['vessels', 'picker', debounced],
    queryFn: () =>
      listVessels({
        page: 1,
        page_size: 50,
        search: debounced || undefined,
      }),
    enabled: open,
  })

  const items = useMemo(() => data?.items ?? [], [data])
  const selectedItem = useMemo(
    () => items.find((it) => it.id === selectedId) ?? null,
    [items, selectedId],
  )

  function handlePick(v: VesselOutput) {
    onPick(v)
    setOpen(false)
    setSearch('')
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild disabled={disabled}>
        <Button
          type="button"
          variant="outline"
          role="combobox"
          aria-expanded={open}
          className={cn(
            'w-full justify-between gap-2 text-left font-normal',
            !selectedId && 'text-muted-foreground',
            className,
          )}
        >
          {selectedItem ? (
            <span className="flex items-center gap-2 truncate">
              <span className="font-medium">{selectedItem.name}</span>
              <Badge variant="outline" className="text-[10px]">
                {selectedItem.vessel_type}
              </Badge>
              <span className="text-xs text-muted-foreground">
                LOA {selectedItem.loa.toFixed(0)} m · draft{' '}
                {selectedItem.draft.toFixed(0)} m
              </span>
            </span>
          ) : selectedId ? (
            <span className="font-mono text-xs">id={selectedId}</span>
          ) : (
            'Escolher vessel do catálogo…'
          )}
          <ChevronDown className="ml-auto h-4 w-4 shrink-0 opacity-60" />
        </Button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-[460px] p-0">
        <div className="flex items-center border-b border-border px-3">
          <Search className="h-3.5 w-3.5 text-muted-foreground" />
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Buscar por nome (ex: P-77, Atlanta, AHV)…"
            className="h-10 border-0 bg-transparent px-2 shadow-none focus-visible:ring-0"
            autoFocus
          />
          {selectedId && onClear && (
            <Button
              type="button"
              variant="ghost"
              size="icon"
              aria-label="Limpar seleção"
              onClick={() => {
                onClear()
                setOpen(false)
              }}
              className="h-8 w-8"
            >
              <X className="h-3.5 w-3.5" />
            </Button>
          )}
        </div>
        <div className="max-h-72 overflow-auto custom-scroll p-1">
          {isLoading ? (
            <div className="px-3 py-6 text-center text-xs text-muted-foreground">
              Carregando catálogo…
            </div>
          ) : items.length === 0 ? (
            <div className="px-3 py-6 text-center text-xs text-muted-foreground">
              Nenhum vessel encontrado.
            </div>
          ) : (
            items.map((it) => (
              <button
                key={it.id}
                type="button"
                onClick={() => handlePick(it)}
                className="flex w-full items-start gap-3 rounded-md px-2 py-1.5 text-left text-sm transition-colors hover:bg-muted focus-visible:bg-muted focus-visible:outline-none"
              >
                <span
                  className={cn(
                    'mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full border',
                    selectedId === it.id
                      ? 'border-primary bg-primary text-primary-foreground'
                      : 'border-border',
                  )}
                  aria-hidden
                >
                  {selectedId === it.id && <Check className="h-3 w-3" />}
                </span>
                <span className="flex min-w-0 flex-1 flex-col gap-0.5">
                  <span className="flex items-center gap-2">
                    <span className="font-medium">{it.name}</span>
                    <Badge variant="outline" className="text-[10px]">
                      {it.vessel_type}
                    </Badge>
                    <span className="ml-auto text-[10px] text-muted-foreground">
                      {it.data_source}
                    </span>
                  </span>
                  <span className="font-mono text-[11px] text-muted-foreground">
                    LOA {it.loa.toFixed(1)} m · breadth{' '}
                    {it.breadth.toFixed(1)} m · draft {it.draft.toFixed(1)} m
                    {it.operator && ` · ${it.operator}`}
                  </span>
                </span>
              </button>
            ))
          )}
        </div>
      </PopoverContent>
    </Popover>
  )
}
