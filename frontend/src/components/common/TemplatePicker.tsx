/**
 * F5.7.6 — Picker de templates de configurações testadas.
 *
 * Dropdown que carrega valores conhecidos no formulário. Cada template
 * é um starting point que sabidamente converge — engenheiro novato
 * usa pra ter um exemplo funcional, depois ajusta parâmetros.
 */
import { AlertTriangle, Anchor, BookmarkCheck, Mountain, Package, Sparkles, Waves } from 'lucide-react'

import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { CASE_TEMPLATES, type CaseTemplate } from '@/lib/caseTemplates'

const TAG_ICON: Record<CaseTemplate['tag'], typeof Anchor> = {
  classic: Anchor,
  lazyS: Waves,
  taut: BookmarkCheck,
  shallow: Waves,
  deep: Waves,
  spread: Sparkles,
  attachment: Package,
  slope: Mountain,
  preview: AlertTriangle,
}

const TAG_COLOR: Record<CaseTemplate['tag'], string> = {
  classic: 'text-blue-400',
  lazyS: 'text-violet-400',
  taut: 'text-emerald-400',
  shallow: 'text-amber-400',
  deep: 'text-indigo-400',
  spread: 'text-pink-400',
  attachment: 'text-cyan-400',
  slope: 'text-orange-400',
  preview: 'text-warning',
}

export interface TemplatePickerProps {
  /** Callback quando o usuário escolhe um template — recebe os valores. */
  onSelect: (template: CaseTemplate) => void
  /** Tamanho do botão. */
  size?: 'sm' | 'default'
  /** Label do botão. */
  label?: string
}

export function TemplatePicker({
  onSelect,
  size = 'sm',
  label = 'Carregar template',
}: TemplatePickerProps) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button size={size} variant="outline" className="gap-2">
          <Sparkles className="size-4" />
          {label}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-80">
        <DropdownMenuLabel className="text-[11px] uppercase tracking-wide text-muted-foreground">
          Configurações testadas
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        {CASE_TEMPLATES.map((tpl) => {
          const Icon = TAG_ICON[tpl.tag]
          return (
            <DropdownMenuItem
              key={tpl.id}
              onClick={() => onSelect(tpl)}
              className="flex flex-col items-start gap-1 py-2"
            >
              <div className="flex w-full items-center gap-2">
                <Icon className={`size-4 ${TAG_COLOR[tpl.tag]}`} />
                <span className="font-medium">{tpl.name}</span>
              </div>
              <p className="line-clamp-2 pl-6 text-[11px] leading-relaxed text-muted-foreground">
                {tpl.description}
              </p>
            </DropdownMenuItem>
          )
        })}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
