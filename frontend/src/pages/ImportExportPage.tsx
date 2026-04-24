import { Topbar } from '@/components/layout/Topbar'

export function ImportExportPage() {
  return (
    <>
      <Topbar />
      <div className="flex-1 overflow-auto custom-scroll p-6">
        <h1 className="text-2xl font-semibold tracking-tight">
          Importar/Exportar
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Import/Export virá na F3.7.
        </p>
      </div>
    </>
  )
}
