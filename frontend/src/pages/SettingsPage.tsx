import { Topbar } from '@/components/layout/Topbar'

export function SettingsPage() {
  return (
    <>
      <Topbar />
      <div className="flex-1 overflow-auto custom-scroll p-6">
        <h1 className="text-2xl font-semibold tracking-tight">Configurações</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Configurações virão na F3.8.
        </p>
      </div>
    </>
  )
}
