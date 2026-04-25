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
        sidebarCollapsed ? 'w-16' : 'w-56',
      )}
    >
      {/* Topo: logo + toggle — altura fixa 56px (mesma do topbar) */}
      <div
        className={cn(
          'flex h-14 shrink-0 items-center border-b border-border',
          sidebarCollapsed ? 'justify-center px-2' : 'justify-between px-3',
        )}
      >
        <Logo compact={sidebarCollapsed} />
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              aria-label={sidebarCollapsed ? 'Expandir sidebar' : 'Colapsar sidebar'}
              onClick={toggleSidebar}
              className={cn(
                'h-7 w-7 shrink-0 text-muted-foreground hover:text-foreground',
                sidebarCollapsed && 'hidden',
              )}
            >
              <ChevronsLeft className="h-4 w-4" />
            </Button>
          </TooltipTrigger>
          <TooltipContent side="right">Colapsar (Cmd+B)</TooltipContent>
        </Tooltip>
      </div>

      {sidebarCollapsed && (
        <Tooltip>
          <TooltipTrigger asChild>
            <button
              type="button"
              onClick={toggleSidebar}
              aria-label="Expandir sidebar"
              className="mx-2 my-2 inline-flex h-7 items-center justify-center rounded-md text-muted-foreground hover:bg-muted/60 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <ChevronsRight className="h-4 w-4" />
            </button>
          </TooltipTrigger>
          <TooltipContent side="right">Expandir</TooltipContent>
        </Tooltip>
      )}

      {/* Navegação */}
      <nav className="flex-1 overflow-y-auto custom-scroll px-2 py-2">
        <ul className="space-y-0.5">
          {NAV_ITEMS.map(({ label, to, icon: Icon }) => (
            <li key={to}>
              <Tooltip>
                <TooltipTrigger asChild>
                  <NavLink
                    to={to}
                    className={({ isActive }) =>
                      cn(
                        'flex h-9 items-center gap-3 rounded-md px-3 text-sm font-medium transition-colors',
                        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                        isActive
                          ? 'bg-primary/10 text-primary'
                          : 'text-sidebar-foreground hover:bg-muted/60 hover:text-foreground',
                        sidebarCollapsed && 'justify-center px-0',
                      )
                    }
                    end={to === '/cases'}
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

      {/* Rodapé: status API + toggle de tema */}
      <div
        className={cn(
          'flex shrink-0 items-center gap-1 px-2 py-2',
          sidebarCollapsed ? 'flex-col' : 'justify-between',
        )}
      >
        <ApiStatusIndicator compact={sidebarCollapsed} />
        <ThemeToggle compact={sidebarCollapsed} />
      </div>
    </aside>
  )
}
