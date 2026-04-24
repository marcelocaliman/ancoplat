import { useParams } from 'react-router-dom'
import { Topbar } from '@/components/layout/Topbar'

export function CaseDetailPage() {
  const { id } = useParams()
  return (
    <>
      <Topbar />
      <div className="flex-1 overflow-auto custom-scroll p-6">
        <h1 className="text-2xl font-semibold tracking-tight">Caso #{id}</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Detalhe virá na F3.4.
        </p>
      </div>
    </>
  )
}
