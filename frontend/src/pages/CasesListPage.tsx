import { Topbar } from '@/components/layout/Topbar'

export function CasesListPage() {
  return (
    <>
      <Topbar />
      <div className="flex-1 overflow-auto custom-scroll p-6">
        <h1 className="text-2xl font-semibold tracking-tight">Casos</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Listagem de casos virá na F3.2.
        </p>
      </div>
    </>
  )
}
