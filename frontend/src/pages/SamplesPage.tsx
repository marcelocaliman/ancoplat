/**
 * Página /samples (Fase 9 / Q2).
 *
 * Grid visual com os 11 case templates registrados em `caseTemplates.ts`.
 * Cada card mostra nome + descrição + tag colorida + (quando aplicável)
 * banner "preview — requires Phase X". Botão "Carregar caso" navega
 * para /cases/new com o template no `state.template` da rota; o
 * CaseFormPage detecta e popula o form via `reset()`.
 *
 * Forward-compat: futuras adições de samples (mooring system templates
 * em v1.1+, novos casos canônicos em F10) entram como entries no mesmo
 * array CASE_TEMPLATES, sem refactor desta página.
 */
import { AlertTriangle, ArrowRight, Sparkles } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { CASE_TEMPLATES, type CaseTemplate } from '@/lib/caseTemplates'
import { Topbar } from '@/components/layout/Topbar'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'

const TAG_LABELS: Record<CaseTemplate['tag'], string> = {
  classic: 'Clássico',
  lazyS: 'Lazy-S',
  taut: 'Taut',
  shallow: 'Águas rasas',
  deep: 'Águas profundas',
  spread: 'Spread',
  attachment: 'Attachment',
  slope: 'Seabed inclinado',
  preview: 'Preview',
}

const TAG_TONE: Record<CaseTemplate['tag'], string> = {
  classic: 'bg-primary/10 text-primary',
  lazyS: 'bg-info/10 text-info',
  taut: 'bg-warning/10 text-warning',
  shallow: 'bg-success/10 text-success',
  deep: 'bg-secondary/30 text-secondary-foreground',
  spread: 'bg-muted text-foreground',
  attachment: 'bg-info/10 text-info',
  slope: 'bg-warning/10 text-warning',
  preview: 'bg-warning/15 text-warning',
}

export function SamplesPage() {
  const [search, setSearch] = useState('')
  const [showPreview, setShowPreview] = useState(true)

  const filtered = CASE_TEMPLATES.filter((tpl) => {
    if (!showPreview && tpl.requirePhase != null) return false
    if (!search) return true
    const haystack = `${tpl.name} ${tpl.description} ${tpl.tag}`.toLowerCase()
    return haystack.includes(search.toLowerCase())
  })

  const counts = {
    total: CASE_TEMPLATES.length,
    visible: filtered.length,
    preview: CASE_TEMPLATES.filter((t) => t.requirePhase != null).length,
  }

  return (
    <>
      <Topbar />
      <div className="flex-1 overflow-auto custom-scroll p-6">
        <div className="mx-auto max-w-6xl">
          <header className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <h1 className="flex items-center gap-2 text-2xl font-semibold">
                <Sparkles className="h-5 w-5 text-primary" aria-hidden />
                Samples canônicos
              </h1>
              <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
                Configurações testadas que cobrem os principais regimes de
                mooring estático. Cada sample carrega no formulário de novo
                caso pronto para solve.
              </p>
            </div>
            <div className="flex gap-2">
              <Input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Buscar sample…"
                className="w-56"
                aria-label="Buscar sample"
              />
              <Button
                variant={showPreview ? 'outline' : 'secondary'}
                size="sm"
                onClick={() => setShowPreview((v) => !v)}
                aria-pressed={showPreview}
                title={
                  showPreview
                    ? 'Ocultar samples preview (F7/F8)'
                    : 'Mostrar samples preview (F7/F8)'
                }
              >
                {showPreview ? 'Ocultar previews' : 'Mostrar previews'}
              </Button>
            </div>
          </header>

          <p className="mb-4 text-xs text-muted-foreground">
            {counts.visible} de {counts.total} samples visíveis
            {counts.preview > 0 && (
              <span className="ml-2">
                · {counts.preview} preview de fases em desenvolvimento
              </span>
            )}
          </p>

          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {filtered.map((tpl) => (
              <SampleCard key={tpl.id} template={tpl} />
            ))}
          </div>
          {filtered.length === 0 && (
            <p className="mt-12 text-center text-sm text-muted-foreground">
              Nenhum sample combina com a busca.
            </p>
          )}
        </div>
      </div>
    </>
  )
}

function SampleCard({ template }: { template: CaseTemplate }) {
  const isPreview = template.requirePhase != null
  return (
    <article
      className={cn(
        'flex flex-col gap-3 rounded-lg border border-border bg-card p-4 transition-shadow hover:shadow-md',
        isPreview && 'border-warning/50',
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <h2 className="text-sm font-semibold leading-tight">{template.name}</h2>
        <Badge
          variant="outline"
          className={cn('shrink-0 text-[10px]', TAG_TONE[template.tag])}
        >
          {TAG_LABELS[template.tag]}
        </Badge>
      </div>

      <p className="flex-1 text-xs leading-relaxed text-muted-foreground">
        {template.description}
      </p>

      {isPreview && (
        <div className="flex items-start gap-2 rounded-md border border-warning/40 bg-warning/5 p-2">
          <AlertTriangle
            className="mt-0.5 h-3.5 w-3.5 shrink-0 text-warning"
            aria-hidden
          />
          <p className="text-[11px] leading-tight text-warning">
            <span className="font-semibold">Preview · {template.requirePhase}</span>
            {' — '}
            {template.previewMessage ??
              `Feature em desenvolvimento (Fase ${template.requirePhase}). Solve retornará erro até implementação.`}
          </p>
        </div>
      )}

      <Button
        asChild
        variant={isPreview ? 'outline' : 'default'}
        size="sm"
        className="w-full"
      >
        <Link
          to="/cases/new"
          state={{ templateId: template.id }}
          aria-label={`Carregar sample ${template.name}`}
        >
          Carregar caso
          <ArrowRight className="ml-1 h-3 w-3" />
        </Link>
      </Button>
    </article>
  )
}
