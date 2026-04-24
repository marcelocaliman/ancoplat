import { Moon, Sun } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import { useThemeStore, resolveTheme } from '@/store/theme'

export function ThemeToggle({ compact = false }: { compact?: boolean }) {
  const { theme, toggle } = useThemeStore()
  const resolved = resolveTheme(theme)

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button
          variant="ghost"
          size={compact ? 'icon' : 'sm'}
          aria-label={
            resolved === 'dark'
              ? 'Mudar para tema claro'
              : 'Mudar para tema escuro'
          }
          onClick={toggle}
          className="text-muted-foreground hover:text-foreground"
        >
          {resolved === 'dark' ? (
            <>
              <Sun className="h-4 w-4" />
              {!compact && <span className="ml-1.5">Claro</span>}
            </>
          ) : (
            <>
              <Moon className="h-4 w-4" />
              {!compact && <span className="ml-1.5">Escuro</span>}
            </>
          )}
        </Button>
      </TooltipTrigger>
      <TooltipContent side="right">
        Alternar tema ({resolved === 'dark' ? 'escuro' : 'claro'})
      </TooltipContent>
    </Tooltip>
  )
}
