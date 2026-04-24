import { useQuery } from '@tanstack/react-query'
import { fetchHealth } from '@/api/endpoints'
import { cn } from '@/lib/utils'
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip'

/**
 * Polling a cada 30s no /health. Indicador visual de status da API.
 *
 * verde    = 200 ok
 * amarelo  = loading inicial
 * vermelho = erro de rede ou 503
 */
export function ApiStatusIndicator({ compact = false }: { compact?: boolean }) {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['health'],
    queryFn: fetchHealth,
    refetchInterval: 30_000,
    refetchIntervalInBackground: true,
    retry: 1,
    staleTime: 20_000,
  })

  let status: 'ok' | 'loading' | 'error' = 'loading'
  let label = 'Verificando API…'
  let bg = 'bg-warning'
  if (!isLoading) {
    if (isError || !data) {
      status = 'error'
      label = error instanceof Error ? `API offline: ${error.message}` : 'API offline'
      bg = 'bg-danger'
    } else {
      status = 'ok'
      label = `API online (${data.db} db)`
      bg = 'bg-success'
    }
  }

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <div
          className={cn(
            'flex items-center gap-2 rounded-md px-2 py-1 text-xs font-medium transition-colors hover:bg-muted/60',
            compact && 'justify-center px-1',
          )}
          role="status"
          aria-live="polite"
        >
          <span
            className={cn(
              'inline-block h-2 w-2 rounded-full',
              bg,
              status === 'ok' && 'animate-pulse',
            )}
          />
          {!compact && (
            <span className="text-muted-foreground">
              {status === 'ok' ? 'API' : status === 'loading' ? '…' : 'Off'}
            </span>
          )}
        </div>
      </TooltipTrigger>
      <TooltipContent side="right">{label}</TooltipContent>
    </Tooltip>
  )
}
