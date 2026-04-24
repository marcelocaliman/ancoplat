import { useQuery } from '@tanstack/react-query'
import { Check, ChevronDown, Search, X } from 'lucide-react'
import { useMemo, useState } from 'react'
import { listLineTypes } from '@/api/endpoints'
import type { LineTypeOutput } from '@/api/types'
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

export interface LineTypePickerProps {
  value: LineTypeOutput | null
  onChange: (lt: LineTypeOutput | null) => void
  className?: string
  disabled?: boolean
}

export function LineTypePicker({
  value,
  onChange,
  className,
  disabled,
}: LineTypePickerProps) {
  const [open, setOpen] = useState(false)
  const [search, setSearch] = useState('')
  const debounced = useDebounce(search, 250)

  const { data, isLoading } = useQuery({
    queryKey: ['line-types', 'picker', debounced],
    queryFn: () =>
      listLineTypes({
        page: 1,
        page_size: 50,
        search: debounced || undefined,
      }),
    enabled: open,
  })

  const items = useMemo(() => data?.items ?? [], [data])

  function pick(item: LineTypeOutput) {
    onChange(item)
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
            !value && 'text-muted-foreground',
            className,
          )}
        >
          {value ? (
            <span className="flex items-center gap-2 truncate">
              <span className="font-mono text-xs">{value.line_type}</span>
              <span className="text-xs text-muted-foreground">
                Ø {fmtNumber(value.diameter, 3)} m · MBL{' '}
                {fmtNumber(value.break_strength / 1000, 0)} kN
              </span>
            </span>
          ) : (
            'Escolher do catálogo…'
          )}
          <ChevronDown className="ml-auto h-4 w-4 shrink-0 opacity-60" />
        </Button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-[420px] p-0">
        <div className="flex items-center border-b border-border px-3">
          <Search className="h-3.5 w-3.5 text-muted-foreground" />
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Buscar por nome (ex: IWRCEIPS)…"
            className="h-10 border-0 bg-transparent px-2 shadow-none focus-visible:ring-0"
            autoFocus
          />
          {value && (
            <Button
              type="button"
              variant="ghost"
              size="icon"
              aria-label="Limpar seleção"
              onClick={() => {
                onChange(null)
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
              Nenhum tipo encontrado.
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
                    value?.id === it.id
                      ? 'border-primary bg-primary text-primary-foreground'
                      : 'border-border',
                  )}
                  aria-hidden
                >
                  {value?.id === it.id && <Check className="h-3 w-3" />}
                </span>
                <span className="flex min-w-0 flex-1 flex-col gap-0.5">
                  <span className="flex items-center gap-2">
                    <span className="font-mono text-xs">{it.line_type}</span>
                    <Badge variant="outline" className="text-[10px]">
                      {it.category}
                    </Badge>
                    <span className="ml-auto text-[10px] text-muted-foreground">
                      {it.data_source}
                    </span>
                  </span>
                  <span className="font-mono text-[11px] text-muted-foreground">
                    Ø {fmtNumber(it.diameter, 4)} m · w{' '}
                    {fmtNumber(it.wet_weight, 1)} N/m · MBL{' '}
                    {fmtNumber(it.break_strength / 1000, 0)} kN
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
