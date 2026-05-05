import { useQuery } from '@tanstack/react-query'
import { Check, ChevronDown, Search, X } from 'lucide-react'
import { useMemo, useState } from 'react'
import { listBuoys } from '@/api/endpoints'
import type { BuoyOutput } from '@/api/types'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover'
import { useDebounce } from '@/hooks/useDebounce'
import { cn, fmtNumber } from '@/lib/utils'

export interface BuoyPickerProps {
  /** Boia atualmente "ligada" ao attachment (via `buoy_catalog_id`). */
  selectedId: number | null
  onPick: (b: BuoyOutput) => void
  onClear?: () => void
  className?: string
  disabled?: boolean
}

/**
 * Picker de boias do catálogo (F6 / Q1+Q7).
 *
 * Estilo idêntico a LineTypePicker: popover com busca server-side
 * (debounced) e marcação check do selecionado.
 *
 * Quando o usuário escolhe uma boia, o componente NÃO escreve nada
 * direto no form — só dispara `onPick(boia)`. Quem decide quais campos
 * preencher é o caller (AttachmentsEditor). Isso desacopla a lógica
 * de escrita (override seta `buoy_catalog_id=null` se algum campo
 * físico mudar — Q7 ajustado pelo usuário).
 */
export function BuoyPicker({
  selectedId,
  onPick,
  onClear,
  className,
  disabled,
}: BuoyPickerProps) {
  const [open, setOpen] = useState(false)
  const [search, setSearch] = useState('')
  const debounced = useDebounce(search, 250)

  const { data, isLoading } = useQuery({
    queryKey: ['buoys', 'picker', debounced],
    queryFn: () =>
      listBuoys({
        page: 1,
        page_size: 50,
        search: debounced || undefined,
      }),
    enabled: open,
  })

  const items = useMemo(() => data?.items ?? [], [data])
  const selectedItem = useMemo(
    () => items.find((b) => b.id === selectedId) ?? null,
    [items, selectedId],
  )

  function pick(item: BuoyOutput) {
    onPick(item)
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
            !selectedItem && 'text-muted-foreground',
            className,
          )}
        >
          {selectedItem ? (
            <span className="flex items-center gap-2 truncate">
              <span className="font-mono text-xs">{selectedItem.name}</span>
              <span className="text-xs text-muted-foreground">
                F_b {fmtNumber(selectedItem.submerged_force / 1000, 0)} kN
              </span>
            </span>
          ) : selectedId ? (
            // ID setado mas catálogo ainda não carregou → fallback
            <span className="font-mono text-xs">id={selectedId}</span>
          ) : (
            'Escolher boia do catálogo…'
          )}
          <ChevronDown className="ml-auto h-4 w-4 shrink-0 opacity-60" />
        </Button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-[440px] p-0">
        <div className="flex items-center border-b border-border px-3">
          <Search className="h-3.5 w-3.5 text-muted-foreground" />
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Buscar por nome (ex: GEN-Hemi)…"
            className="h-10 border-0 bg-transparent px-2 shadow-none focus-visible:ring-0"
            autoFocus
          />
          {selectedId !== null && onClear && (
            <Button
              type="button"
              variant="ghost"
              size="icon"
              aria-label="Desvincular boia"
              onClick={() => {
                onClear()
                setOpen(false)
              }}
              className="h-8 w-8"
              title="Modo manual (desvincula do catálogo)"
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
              Nenhuma boia encontrada.
            </div>
          ) : (
            items.map((it) => (
              <button
                key={it.id}
                type="button"
                onClick={() => pick(it)}
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
                    <span className="font-mono text-xs">{it.name}</span>
                    <Badge variant="outline" className="text-[10px]">
                      {it.end_type}
                    </Badge>
                    <Badge variant="outline" className="text-[10px]">
                      {it.buoy_type}
                    </Badge>
                    <span className="ml-auto text-[10px] text-muted-foreground">
                      {it.data_source}
                    </span>
                  </span>
                  <span className="font-mono text-[11px] text-muted-foreground">
                    D {fmtNumber(it.outer_diameter, 2)} m · L{' '}
                    {fmtNumber(it.length, 2)} m · F_b{' '}
                    {fmtNumber(it.submerged_force / 1000, 1)} kN
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
