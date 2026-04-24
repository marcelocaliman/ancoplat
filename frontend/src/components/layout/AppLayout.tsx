import { Outlet } from 'react-router-dom'
import { Sidebar } from './Sidebar'

/**
 * Shell da aplicação: sidebar + área central (topbar + outlet).
 * Páginas providenciam seu próprio <Topbar /> para customizar breadcrumbs/ações.
 */
export function AppLayout() {
  return (
    <div className="flex h-screen w-screen overflow-hidden bg-background">
      <Sidebar />
      <main className="flex min-w-0 flex-1 flex-col">
        <Outlet />
      </main>
    </div>
  )
}
