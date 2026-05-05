/**
 * Página /help/glossary (Fase 9 / Q5+Q6).
 *
 * Lista os ~40 verbetes de `glossary.ts` agrupados por categoria, com
 * busca textual e filtro por categoria. Verbetes preview (uplift,
 * AHV, bollard pull) ganham badge "F7" / "F8" indicando feature em
 * desenvolvimento.
 *
 * Estrutura forward-compat: F11 (lançamento 1.0) expandirá `/help/*`
 * com manual de usuário em rotas adjacentes.
 */
import { Search, X } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Topbar } from '@/components/layout/Topbar'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  CATEGORY_LABELS,
  GLOSSARY,
  searchGlossary,
  type GlossaryCategory,
  type GlossaryEntry,
} from '@/lib/glossary'
import { cn } from '@/lib/utils'

const ALL_CATEGORIES: (GlossaryCategory | 'all')[] = [
  'all',
  'geometria',
  'fisico',
  'componentes',
  'operacional',
  'boia',
]

export function HelpGlossaryPage() {
  const [search, setSearch] = useState('')
  const [category, setCategory] = useState<GlossaryCategory | 'all'>('all')

  const results = useMemo(
    () =>
      searchGlossary(search, category === 'all' ? undefined : category),
    [search, category],
  )

  // Agrupa por categoria para exibição (mesmo quando filtro=all).
  const grouped = useMemo(() => {
    const map = new Map<GlossaryCategory, GlossaryEntry[]>()
    for (const entry of results) {
      const list = map.get(entry.category) ?? []
      list.push(entry)
      map.set(entry.category, list)
    }
    return map
  }, [results])

  return (
    <>
      <Topbar />
      <div className="flex-1 overflow-auto custom-scroll p-6">
        <div className="mx-auto max-w-4xl">
          <header className="mb-6">
            <h1 className="text-2xl font-semibold">Glossário</h1>
            <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
              Vocabulário técnico do AncoPlat. {GLOSSARY.length} termos
              cobrindo geometria de catenária, propriedades físicas,
              componentes e diagnostics.
            </p>
          </header>

          <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-end">
            <div className="flex-1">
              <label
                htmlFor="glossary-search"
                className="mb-1.5 block text-xs text-muted-foreground"
              >
                Buscar
              </label>
              <div className="relative">
                <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
                <Input
                  id="glossary-search"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Buscar termo ou definição (ex: catenária, MBL, AHV)…"
                  className="pl-8"
                  aria-label="Buscar no glossário"
                />
                {search && (
                  <button
                    type="button"
                    onClick={() => setSearch('')}
                    className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                    aria-label="Limpar busca"
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                )}
              </div>
            </div>
            <div className="flex flex-wrap gap-1">
              {ALL_CATEGORIES.map((cat) => {
                const isActive = category === cat
                return (
                  <Button
                    key={cat}
                    type="button"
                    variant={isActive ? 'secondary' : 'outline'}
                    size="sm"
                    onClick={() => setCategory(cat)}
                    aria-pressed={isActive}
                    className="text-[11px]"
                  >
                    {cat === 'all'
                      ? 'Todas'
                      : CATEGORY_LABELS[cat as GlossaryCategory]}
                  </Button>
                )
              })}
            </div>
          </div>

          <p className="mb-4 text-xs text-muted-foreground">
            {results.length} de {GLOSSARY.length} verbetes visíveis
          </p>

          {results.length === 0 ? (
            <p className="mt-12 text-center text-sm text-muted-foreground">
              Nenhum verbete combina com o filtro.
            </p>
          ) : (
            <div className="space-y-8">
              {Array.from(grouped.entries()).map(([cat, entries]) => (
                <section key={cat} aria-labelledby={`section-${cat}`}>
                  <h2
                    id={`section-${cat}`}
                    className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground"
                  >
                    {CATEGORY_LABELS[cat]}
                    <span className="ml-2 text-[11px] font-normal opacity-70">
                      ({entries.length})
                    </span>
                  </h2>
                  <dl className="space-y-3">
                    {entries.map((entry) => (
                      <GlossaryItem key={entry.id} entry={entry} />
                    ))}
                  </dl>
                </section>
              ))}
            </div>
          )}
        </div>
      </div>
    </>
  )
}

function GlossaryItem({ entry }: { entry: GlossaryEntry }) {
  return (
    <div
      id={`term-${entry.id}`}
      className={cn(
        'rounded-md border border-border bg-card p-4',
        entry.requirePhase && 'border-warning/40 bg-warning/[0.03]',
      )}
    >
      <dt className="mb-1 flex flex-wrap items-center gap-2">
        <span className="font-mono text-sm font-semibold">{entry.term}</span>
        {entry.requirePhase && (
          <Badge
            variant="outline"
            className="border-warning/50 bg-warning/10 text-[10px] text-warning"
            title={`Feature em desenvolvimento (Fase ${entry.requirePhase})`}
          >
            Preview · {entry.requirePhase}
          </Badge>
        )}
      </dt>
      <dd className="text-sm leading-relaxed text-muted-foreground">
        {entry.definition}
      </dd>
      {entry.seeAlso && entry.seeAlso.length > 0 && (
        <p className="mt-2 text-[11px] text-muted-foreground/70">
          Ver também:{' '}
          {entry.seeAlso.map((id, i) => (
            <span key={id}>
              {i > 0 && ' · '}
              <a
                href={`#term-${id}`}
                className="text-primary hover:underline"
              >
                {GLOSSARY.find((g) => g.id === id)?.term ?? id}
              </a>
            </span>
          ))}
        </p>
      )}
    </div>
  )
}
