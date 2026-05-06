import type { ReactNode } from 'react'
import { Card, CardContent } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { cn } from '@/lib/utils'

export interface EnvCardProps {
  title: string
  /** Slot opcional à direita do título (botões de ação, badges). */
  trailing?: ReactNode
  className?: string
  children: ReactNode
}

/**
 * Card bordado para grupos de configuração — usado nas abas
 * Ambiente, Linha, Boias e Clumps. Tom azulado sutil sobre o
 * fundo externo (bg-primary/[0.04]) + border-primary/20 + sombra
 * leve, header em text-primary/80.
 *
 * Largura padrão: 260px (configurável via className).
 */
export function EnvCard({ title, trailing, className, children }: EnvCardProps) {
  return (
    <Card
      className={cn(
        'shrink-0 border-primary/20 bg-primary/[0.04] shadow-sm',
        'w-[300px]',
        className,
      )}
    >
      <CardContent className="space-y-1.5 p-2.5">
        <div className="flex items-center gap-1">
          <h4 className="flex-1 text-[10px] font-semibold uppercase tracking-[0.08em] text-primary/80">
            {title}
          </h4>
          {trailing}
        </div>
        {children}
      </CardContent>
    </Card>
  )
}

export interface EnvFieldProps {
  label: string
  unit?: string
  children: ReactNode
}

/**
 * Linha horizontal de input dentro de um EnvCard:
 *   [label flex-1] [input w-fixa] [unit]
 *
 * Unit fica grudada no input (não solta no canto direito).
 * Alinhamento estável entre cards garantido pela largura fixa
 * do card + width-fixa do input do consumidor.
 */
export function EnvField({ label, unit, children }: EnvFieldProps) {
  return (
    <div className="flex items-center gap-2">
      <Label className="flex-1 truncate text-[10px] font-medium text-muted-foreground">
        {label}
      </Label>
      {children}
      <span
        className={cn(
          'w-3 shrink-0 font-mono text-[9px] text-muted-foreground',
          !unit && 'invisible',
        )}
      >
        {unit ?? '—'}
      </span>
    </div>
  )
}
