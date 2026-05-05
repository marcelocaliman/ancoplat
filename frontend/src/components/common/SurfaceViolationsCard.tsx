/**
 * SurfaceViolationsCard — card dedicado para violações de superfície
 * (Fase 4 / Q6).
 *
 * F5.7.3 introduziu detecção de "boias voadoras" (acima da água)
 * com banner amarelo no plot. A Fase 4 adiciona um CARD detalhado
 * no painel de Resultados, listando cada boia com seu
 * `height_above_surface_m` específico — informação que o engenheiro
 * precisa para corrigir (qual boia, em quanto está acima).
 *
 * O banner do plot continua existindo (alerta visual rápido); este
 * card é a referência detalhada.
 */
import { AlertTriangle } from 'lucide-react'
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { fmtNumber } from '@/lib/utils'

export interface SurfaceViolation {
  index: number
  name: string
  height_above_surface_m: number
}

export interface SurfaceViolationsCardProps {
  violations: SurfaceViolation[]
  className?: string
}

export function SurfaceViolationsCard({
  violations,
  className,
}: SurfaceViolationsCardProps) {
  if (violations.length === 0) return null

  return (
    <Card
      className={
        'border-amber-500/50 bg-amber-500/5 ' + (className ?? '')
      }
    >
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.08em] text-amber-700 dark:text-amber-400">
          <AlertTriangle className="h-3.5 w-3.5" />
          Boias acima da superfície
          <span className="ml-auto rounded-md bg-amber-500/20 px-1.5 py-0.5 text-[10px] font-bold tabular-nums">
            {violations.length}
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-1.5 text-[12px]">
        <p className="text-muted-foreground">
          Boias reais não conseguem flutuar acima da água — o empuxo
          configurado é maior do que a geometria suporta. Reduza o
          empuxo da boia, aumente T_fl, ou compense com clump weight.
        </p>
        <ul className="mt-2 space-y-0.5 font-mono">
          {violations.map((v) => (
            <li
              key={v.index}
              className="flex items-baseline justify-between gap-2 border-b border-amber-500/20 py-0.5 last:border-0"
            >
              <span className="truncate">
                <span className="text-amber-700 dark:text-amber-400">⚠</span>{' '}
                {v.name}
              </span>
              <span className="shrink-0 tabular-nums">
                +{fmtNumber(v.height_above_surface_m, 2)} m acima
              </span>
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  )
}
