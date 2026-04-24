import { Topbar } from '@/components/layout/Topbar'

export function CaseFormPage() {
  return (
    <>
      <Topbar />
      <div className="flex-1 overflow-auto custom-scroll p-6">
        <h1 className="text-2xl font-semibold tracking-tight">Novo caso</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Formulário completo virá na F3.3.
        </p>
      </div>
    </>
  )
}
