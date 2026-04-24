import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { Toaster } from 'sonner'
import { TooltipProvider } from '@/components/ui/tooltip'
import { applyTheme, useThemeStore } from '@/store/theme'
import { AppRouter } from './Router'
import './index.css'

// Inicializa tema antes do primeiro render (evita flash).
applyTheme(useThemeStore.getState().theme)

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
      staleTime: 15_000,
    },
  },
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <TooltipProvider delayDuration={200}>
        <AppRouter />
        <Toaster
          position="bottom-right"
          toastOptions={{
            classNames: {
              toast:
                'bg-card border border-border text-card-foreground shadow-md',
              description: 'text-muted-foreground',
            },
          }}
        />
      </TooltipProvider>
    </QueryClientProvider>
  </StrictMode>,
)
