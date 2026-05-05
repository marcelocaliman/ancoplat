/**
 * Tour de boas-vindas (Fase 9 / Q1+Q10).
 *
 * Implementação DIY com Dialog do shadcn — sem dependência nova
 * (princípio do protocolo). 5 etapas lineares cobrindo:
 *   1. Bem-vindo
 *   2. Samples canônicos
 *   3. Primeiro caso (form)
 *   4. Glossário
 *   5. Configurações & atalhos
 *
 * Skip persistente em localStorage:
 *   key: `ancoplat:onboarding-completed`
 *   value: '1' (presente = não mostrar de novo)
 *
 * Reset disponível em /settings via botão "Refazer tour de boas-vindas".
 */
import { ChevronLeft, ChevronRight, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { cn } from '@/lib/utils'

const STORAGE_KEY = 'ancoplat:onboarding-completed'

interface TourStep {
  title: string
  body: React.ReactNode
  cta?: { to: string; label: string }
}

const STEPS: TourStep[] = [
  {
    title: 'Bem-vindo ao AncoPlat',
    body: (
      <>
        <p>
          AncoPlat é a sua ferramenta de análise estática de linhas de
          ancoragem offshore. Vamos te mostrar 4 caminhos rápidos para
          começar.
        </p>
        <p className="text-xs text-muted-foreground">
          O tour leva ~2 min. Você pode fechar a qualquer momento — não
          aparecerá de novo.
        </p>
      </>
    ),
  },
  {
    title: 'Samples canônicos',
    body: (
      <>
        <p>
          A página <strong>/samples</strong> tem 11 configurações testadas
          cobrindo regimes catenários típicos: catenária clássica, taut
          leg, lazy-S, multi-segmento, com boia/clump, seabed inclinado,
          e dois previews das Fases 7 e 8 (anchor uplift e AHV).
        </p>
        <p className="text-xs text-muted-foreground">
          Use samples como ponto de partida em vez de configurar do zero.
        </p>
      </>
    ),
    cta: { to: '/samples', label: 'Abrir Samples' },
  },
  {
    title: 'Crie seu primeiro caso',
    body: (
      <>
        <p>
          Em <strong>Casos → Novo caso</strong>, configure boundary
          conditions (lâmina d'água, T_fl), segmentos da linha (com EA
          QMoor/GMoor por segmento), seabed e attachments. O preview
          live recalcula a cada 600ms.
        </p>
        <p className="text-xs text-muted-foreground">
          Solver retorna ProfileType, alert level, diagnostics estruturados
          + Memorial PDF, CSV, Excel via export.
        </p>
      </>
    ),
    cta: { to: '/cases/new', label: 'Novo caso' },
  },
  {
    title: 'Glossário e ajuda',
    body: (
      <>
        <p>
          Em dúvida sobre algum termo técnico? <strong>/help/glossary</strong>{' '}
          tem 40 verbetes cobrindo geometria, propriedades físicas,
          componentes e diagnostics.
        </p>
        <p className="text-xs text-muted-foreground">
          Termos como ProfileType, lifted arch, anchor uplift, EA dinâmico
          (gmoor) e bollard pull estão todos documentados.
        </p>
      </>
    ),
    cta: { to: '/help/glossary', label: 'Abrir Glossário' },
  },
  {
    title: 'Configurações e atalhos',
    body: (
      <>
        <p>
          Em <strong>Configurações</strong> você troca o sistema de unidades
          (SI / Imperial), tema (claro/escuro) e refaz este tour. Atalhos
          úteis: <kbd className="rounded bg-muted px-1.5 py-0.5 text-[10px]">⌘K</kbd>{' '}
          abre o command palette para navegar rápido.
        </p>
        <p className="text-xs text-muted-foreground">
          Tudo pronto para começar. Feliz mooring!
        </p>
      </>
    ),
    cta: { to: '/cases', label: 'Ir para Casos' },
  },
]

export interface OnboardingTourProps {
  /**
   * Quando `true`, força exibição mesmo se o usuário já completou.
   * Usado pelo botão "Refazer tour" em /settings.
   */
  forceShow?: boolean
  /** Callback quando o tour é completado ou pulado. */
  onComplete?: () => void
}

export function OnboardingTour({ forceShow, onComplete }: OnboardingTourProps) {
  const [open, setOpen] = useState(false)
  const [step, setStep] = useState(0)

  useEffect(() => {
    if (forceShow) {
      setOpen(true)
      setStep(0)
      return
    }
    // Primeira visita?
    try {
      const completed = localStorage.getItem(STORAGE_KEY)
      if (!completed) setOpen(true)
    } catch {
      // localStorage indisponível (privacy mode, SSR) → não mostra tour.
    }
  }, [forceShow])

  function close(markCompleted: boolean) {
    if (markCompleted) {
      try {
        localStorage.setItem(STORAGE_KEY, '1')
      } catch {
        /* noop */
      }
    }
    setOpen(false)
    onComplete?.()
  }

  function next() {
    if (step < STEPS.length - 1) setStep(step + 1)
    else close(true)
  }
  function prev() {
    if (step > 0) setStep(step - 1)
  }

  const current = STEPS[step]
  if (!current) return null

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        if (!o) close(true)
      }}
    >
      <DialogContent
        className="max-w-md"
        onEscapeKeyDown={() => close(true)}
        aria-labelledby="onboarding-title"
        aria-describedby="onboarding-body"
      >
        <DialogHeader>
          <div className="flex items-start justify-between gap-2">
            <DialogTitle id="onboarding-title">{current.title}</DialogTitle>
            <button
              type="button"
              aria-label="Pular tour de boas-vindas"
              onClick={() => close(true)}
              className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
          <DialogDescription asChild>
            <div id="onboarding-body" className="space-y-2 pt-2 text-sm">
              {current.body}
            </div>
          </DialogDescription>
        </DialogHeader>

        {/* Progresso visual */}
        <div className="flex justify-center gap-1.5 py-1" aria-hidden>
          {STEPS.map((_, i) => (
            <span
              key={i}
              className={cn(
                'h-1.5 w-6 rounded-full transition-colors',
                i === step ? 'bg-primary' : 'bg-muted',
              )}
            />
          ))}
        </div>

        <div className="flex items-center justify-between gap-2">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={prev}
            disabled={step === 0}
            aria-label="Etapa anterior"
          >
            <ChevronLeft className="h-3 w-3" />
            Anterior
          </Button>

          <span className="text-[10px] text-muted-foreground">
            {step + 1} de {STEPS.length}
          </span>

          <div className="flex items-center gap-2">
            {current.cta && (
              <Button
                type="button"
                variant="outline"
                size="sm"
                asChild
                onClick={() => close(true)}
              >
                <Link to={current.cta.to}>{current.cta.label}</Link>
              </Button>
            )}
            <Button
              type="button"
              size="sm"
              onClick={next}
              aria-label={
                step === STEPS.length - 1 ? 'Concluir tour' : 'Próxima etapa'
              }
            >
              {step === STEPS.length - 1 ? 'Concluir' : 'Próximo'}
              {step < STEPS.length - 1 && <ChevronRight className="h-3 w-3" />}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}

/** Programaticamente reabre o tour (usado pelo botão em /settings). */
export function resetOnboardingTour(): void {
  try {
    localStorage.removeItem(STORAGE_KEY)
  } catch {
    /* noop */
  }
}

/** Verifica se já foi completado (sem disparar render). */
export function isOnboardingCompleted(): boolean {
  try {
    return localStorage.getItem(STORAGE_KEY) === '1'
  } catch {
    return false
  }
}

export const ONBOARDING_STORAGE_KEY = STORAGE_KEY
