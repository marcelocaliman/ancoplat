import { Navigate, createBrowserRouter, RouterProvider } from 'react-router-dom'
import { AppLayout } from '@/components/layout/AppLayout'
import { CaseDetailPage } from '@/pages/CaseDetailPage'
import { CaseFormPage } from '@/pages/CaseFormPage'
import { CasesListPage } from '@/pages/CasesListPage'
import { CatalogPage } from '@/pages/CatalogPage'
import { ImportExportPage } from '@/pages/ImportExportPage'
import { NotFoundPage } from '@/pages/NotFoundPage'
import { SettingsPage } from '@/pages/SettingsPage'

const router = createBrowserRouter([
  {
    path: '/',
    element: <AppLayout />,
    children: [
      { index: true, element: <Navigate to="/cases" replace /> },
      { path: 'cases', element: <CasesListPage /> },
      { path: 'cases/new', element: <CaseFormPage /> },
      { path: 'cases/:id', element: <CaseDetailPage /> },
      { path: 'cases/:id/edit', element: <CaseFormPage /> },
      { path: 'cases/compare', element: <NotFoundPage /> },
      { path: 'catalog', element: <CatalogPage /> },
      { path: 'import-export', element: <ImportExportPage /> },
      { path: 'settings', element: <SettingsPage /> },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
])

export function AppRouter() {
  return <RouterProvider router={router} />
}
