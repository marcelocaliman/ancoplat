import {
  ArrowLeftRight,
  ChevronsLeft,
  ChevronsRight,
  LayoutList,
  Package,
  Settings,
} from 'lucide-react'
import { NavLink } from 'react-router-dom'
import { Logo } from '@/components/common/Logo'
import { ApiStatusIndicator } from '@/components/common/ApiStatusIndicator'
import { ThemeToggle } from '@/components/common/ThemeToggle'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import { cn } from '@/lib/utils'
import { useUIStore } from '@/store/ui'

interface NavItem {
  label: string
  to: string
  icon: React.ComponentType<{ className?: string }>
}

const NAV_ITEMS: NavItem[] = [
  { label: 'Casos', to: '/cases', icon: LayoutList },
  { label: 'Catálogo', to: '/catalog', icon: Package },
  { label: 'Importar/Exportar', to: '/import-export', icon: ArrowLeftRight },
  { label: 'Configurações', to: '/settings', icon: Settings },
]

export function Sidebar() {
  const { sidebarCollapsed, toggleSidebar } = useUIStore()

  return (
    <aside
      aria-label="Navegação principal"
      className={cn(
        'flex h-screen shrink-0 flex-col border-r border-border bg-sidebar text-sidebar-foreground transition-[width] duration-200 ease-out',
        sidebarCollapsed ? 'w-16' : 'w-60',
      )}
    >
      {/* Topo: logo + toggle */}
      <div
        className={cn(
          'flex h-14 items-center border-b border-border px-3',
          sidebarCollapsed ? 'justify-center' : 'justify-between',
        )}
      >
        <Logo compact={sidebarCollapsed} />
        {!sidebarCollapsed && (
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                aria-label="Colapsar sidebar"
                onClick={toggleSidebar}
                className="text-muted-foreground hover:text-foreground"
              >
                <ChevronsLeft className="h-4 w-4" />
              </Button>
            </TooltipTrigger>
            <TooltipContent side="right">Colapsar (Cmd+B)</TooltipContent>
          </Tooltip>
        )}
      </div>

      {sidebarCollapsed && (
        <div className="flex justify-center py-2">
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                aria-label="Expandir sidebar"
                onClick={toggleSidebar}
              >
                <ChevronsRight className="h-4 w-4" />
              </Button>
            </TooltipTrigger>
            <TooltipContent side="right">Expandir</TooltipContent>
          </Tooltip>
        </div>
      )}

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto custom-scroll px-2 py-3">
        <ul className="space-y-1">
          {NAV_ITEMS.map(({ label, to, icon: Icon }) => (
            <li key={to}>
              <Tooltip>
                <TooltipTrigger asChild>
                  <NavLink
                    to={to}
                    className={({ isActive }) =>
                      cn(
                        'flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors',
                        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                        isActive
                          ? 'bg-primary/10 text-primary'
                          : 'text-sidebar-foreground hover:bg-muted/60 hover:text-foreground',
                        sidebarCollapsed && 'justify-center',
                      )
                    }
                  >
                    <Icon className="h-4 w-4 shrink-0" />
                    {!sidebarCollapsed && <span>{label}</span>}
                  </NavLink>
                </TooltipTrigger>
                {sidebarCollapsed && (
                  <TooltipContent side="right">{label}</TooltipContent>
                )}
              </Tooltip>
            </li>
          ))}
        </ul>
      </nav>

      <Separator />

      {/* Rodapé: status API + tema */}
      <div
        className={cn(
          'flex items-center gap-1 p-2',
          sidebarCollapsed && 'flex-col',
        )}
      >
        <ApiStatusIndicator compact={sidebarCollapsed} />
        <div className={cn('ml-auto', sidebarCollapsed && 'ml-0')}>
          <ThemeToggle compact={sidebarCollapsed} />
        </div>
      </div>
    </aside>
  )
}
