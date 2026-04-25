import { Info } from 'lucide-react'
import { cn } from '@/lib/utils'

/**
 * Disclaimer obrigatório (Seção 10 do Documento A v2.2).
 * Versão compacta em uma única linha; hover/title expõe texto completo.
 */
export function Disclaimer({ className }: { className?: string }) {
  const full =
    'Os resultados apresentados são estimativas de análise estática simplificada e não substituem análise de engenharia realizada com ferramenta validada, dados certificados, premissas aprovadas e revisão por responsável técnico habilitado.'
  return (
    <footer
      className={cn(
        'flex shrink-0 items-center gap-2 border-t border-border bg-muted/20 px-4 py-1.5 text-[10px] text-muted-foreground',
        className,
      )}
      title={full}
    >
      <Info className="h-3 w-3 shrink-0" aria-hidden />
      <span className="truncate">
        <strong className="font-medium text-foreground">Disclaimer:</strong>{' '}
        Estimativa estática simplificada — não substitui análise de engenharia
        com ferramenta validada e revisão por responsável técnico habilitado.
      </span>
    </footer>
  )
}
