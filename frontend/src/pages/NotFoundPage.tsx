import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Topbar } from '@/components/layout/Topbar'

export function NotFoundPage() {
  return (
    <>
      <Topbar breadcrumbs={[{ label: '404' }]} />
      <div className="flex flex-1 flex-col items-center justify-center gap-4 p-10 text-center">
        <span className="font-mono text-5xl font-bold text-muted-foreground">
          404
        </span>
        <h1 className="text-xl font-semibold">Página não encontrada</h1>
        <p className="max-w-md text-sm text-muted-foreground">
          O caminho que você procura não existe ou foi movido. Retorne à lista
          de casos para continuar.
        </p>
        <Button asChild>
          <Link to="/cases">Voltar para Casos</Link>
        </Button>
      </div>
    </>
  )
}
