import { Topbar } from '@/components/layout/Topbar'

export function CatalogPage() {
  return (
    <>
      <Topbar />
      <div className="flex-1 overflow-auto custom-scroll p-6">
        <h1 className="text-2xl font-semibold tracking-tight">Catálogo</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Gestão do catálogo virá na F3.6.
        </p>
      </div>
    </>
  )
}
