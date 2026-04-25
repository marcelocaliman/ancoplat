import { AlertTriangle, RefreshCw } from 'lucide-react'
import * as React from 'react'
import { Button } from '@/components/ui/button'

interface ErrorBoundaryState {
  hasError: boolean
  error: Error | null
}

interface ErrorBoundaryProps {
  children: React.ReactNode
}

/**
 * Error boundary global. Captura exceções de render/lifecycle dos
 * descendentes e mostra uma tela de fallback com ações de recuperação
 * (recarregar, voltar). O console.error preserva stack para debug.
 *
 * Não captura: erros de event handler async (rejected promises) — esses
 * caem em onError dos hooks de query/mutation, ou em window.onerror.
 */
export class ErrorBoundary extends React.Component<
  ErrorBoundaryProps,
  ErrorBoundaryState
> {
  state: ErrorBoundaryState = { hasError: false, error: null }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, info: React.ErrorInfo): void {
    // Em dev: stack visível no console. Em prod: poderia ir para um
    // serviço de telemetria; por enquanto fica só no console.
    // eslint-disable-next-line no-console
    console.error('ErrorBoundary capturou:', error, info.componentStack)
  }

  reset = () => {
    this.setState({ hasError: false, error: null })
  }

  render(): React.ReactNode {
    if (!this.state.hasError) return this.props.children

    return (
      <div className="flex h-full min-h-[60vh] flex-col items-center justify-center gap-4 p-6 text-center">
        <div className="flex h-12 w-12 items-center justify-center rounded-full bg-danger/10 text-danger">
          <AlertTriangle className="h-6 w-6" />
        </div>
        <div className="max-w-md space-y-1">
          <h1 className="text-lg font-semibold">Algo quebrou ao renderizar</h1>
          <p className="text-sm text-muted-foreground">
            A interface encontrou um erro inesperado e foi pausada para evitar
            corromper seus dados. Os dados no banco continuam intactos.
          </p>
          {this.state.error?.message && (
            <p className="mt-2 rounded-md border border-border bg-muted/30 p-2 text-left font-mono text-[11px] text-muted-foreground">
              {this.state.error.message}
            </p>
          )}
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={this.reset}>
            Tentar novamente
          </Button>
          <Button size="sm" onClick={() => window.location.reload()}>
            <RefreshCw className="h-3.5 w-3.5" />
            Recarregar a página
          </Button>
        </div>
      </div>
    )
  }
}
