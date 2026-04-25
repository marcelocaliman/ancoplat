import { useQueries } from '@tanstack/react-query'
import { ArrowLeft } from 'lucide-react'
import { useMemo } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { ApiError } from '@/api/client'
import { getMooringSystem } from '@/api/endpoints'
import type { MooringSystemOutput } from '@/api/types'
import { EmptyState } from '@/components/common/EmptyState'
import {
  MooringSystemsOverlayView,
  type OverlaySystem,
} from '@/components/common/MooringSystemsOverlayView'
import { Topbar } from '@/components/layout/Topbar'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { fmtMeters, fmtPercent } from '@/lib/utils'
import { resolveTheme, useThemeStore } from '@/store/theme'

const COLORS_LIGHT = ['#1E3A5F', '#B91C1C', '#059669']
const COLORS_DARK = ['#60A5FA', '#F87171', '#34D399']

export function MooringSystemsComparePage() {
  const [params] = useSearchParams()
  const idsRaw = params.get('ids') ?? ''
  const theme = resolveTheme(useThemeStore((s) => s.theme))
  const palette = theme === 'dark' ? COLORS_DARK : COLORS_LIGHT

  const ids = useMemo(
    () =>
      Array.from(
        new Set(
          idsRaw
            .split(',')
            .map((s) => parseInt(s.trim(), 10))
            .filter((n) => !Number.isNaN(n) && n > 0),
        ),
      ).slice(0, 3),
    [idsRaw],
  )

  const queries = useQueries({
    queries: ids.map((id) => ({
      queryKey: ['mooring-system', id],
      queryFn: () => getMooringSystem(id),
    })),
  })

  const isLoading = queries.some((q) => q.isLoading)
  const isError = queries.some((q) => q.isError)
  const firstError = queries.find((q) => q.isError)?.error

  const systems: OverlaySystem[] = useMemo(() => {
    const out: OverlaySystem[] = []
    queries.forEach((q, idx) => {
      if (q.data) {
        out.push({
          id: q.data.id,
          name: q.data.name,
          color: palette[idx % palette.length] ?? '#888888',
          input: q.data.input,
          result: q.data.latest_executions?.[0]?.result,
        })
      }
    })
    return out
  }, [queries, palette])

  const breadcrumbs = [
    { label: 'Sistemas', to: '/mooring-systems' },
    { label: 'Comparar' },
  ]

  const actions = (
    <Button asChild variant="outline" size="sm">
      <Link to="/mooring-systems">
        <ArrowLeft className="h-4 w-4" />
        Voltar
      </Link>
    </Button>
  )

  if (ids.length < 2) {
    return (
      <>
        <Topbar breadcrumbs={breadcrumbs} actions={actions} />
        <div className="flex-1 p-6">
          <EmptyState
            title="Selecione 2 ou 3 sistemas para comparar"
            description={
              'Volte à listagem, marque os checkboxes de 2-3 sistemas ' +
              'e clique em "Comparar".'
            }
            action={
              <Button asChild>
                <Link to="/mooring-systems">Voltar à listagem</Link>
              </Button>
            }
            className="border-none"
          />
        </div>
      </>
    )
  }

  if (isLoading) {
    return (
      <>
        <Topbar breadcrumbs={breadcrumbs} actions={actions} />
        <div className="flex-1 p-6">
          <Skeleton className="mb-4 h-[400px] w-full" />
          <Skeleton className="h-32 w-full" />
        </div>
      </>
    )
  }

  if (isError) {
    return (
      <>
        <Topbar breadcrumbs={breadcrumbs} actions={actions} />
        <div className="flex-1 p-6">
          <EmptyState
            title="Falha ao carregar sistemas"
            description={
              firstError instanceof ApiError
                ? firstError.message
                : 'Verifique se os IDs informados existem.'
            }
            action={
              <Button asChild>
                <Link to="/mooring-systems">Voltar</Link>
              </Button>
            }
            className="border-none"
          />
        </div>
      </>
    )
  }

  return (
    <>
      <Topbar breadcrumbs={breadcrumbs} actions={actions} />
      <div className="flex-1 overflow-auto custom-scroll p-6">
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-[2fr_1fr]">
          {/* Plan view sobreposta */}
          <Card className="overflow-hidden">
            <CardContent className="aspect-square p-3">
              <MooringSystemsOverlayView systems={systems} />
            </CardContent>
          </Card>

          {/* Legenda + agregados */}
          <Card>
            <CardContent className="space-y-2 p-4">
              <h3 className="text-[10px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">
                Legenda
              </h3>
              <div className="space-y-1.5">
                {systems.map((s) => (
                  <div
                    key={s.id}
                    className="flex items-center justify-between gap-2 text-sm"
                  >
                    <span className="flex items-center gap-2">
                      <span
                        className="inline-block h-3 w-3 rounded-sm"
                        style={{ backgroundColor: s.color }}
                      />
                      <Link
                        to={`/mooring-systems/${s.id}`}
                        className="font-medium hover:underline"
                      >
                        {s.name}
                      </Link>
                    </span>
                    <span className="text-xs text-muted-foreground">
                      {s.input.lines.length} linhas
                    </span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Tabela comparativa de agregados */}
        <Card className="mt-4 overflow-hidden">
          <div className="border-b border-border/60 bg-muted/20 px-4 py-2">
            <span className="text-[10px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">
              Comparação de agregados
            </span>
          </div>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Métrica</TableHead>
                {systems.map((s) => (
                  <TableHead key={s.id} className="text-right">
                    <span className="flex items-center justify-end gap-1.5">
                      <span
                        className="inline-block h-2.5 w-2.5 rounded-sm"
                        style={{ backgroundColor: s.color }}
                      />
                      {s.name}
                    </span>
                  </TableHead>
                ))}
              </TableRow>
            </TableHeader>
            <TableBody>
              <CompareRow
                label="Raio plataforma (m)"
                values={systems.map((s) => fmtMeters(s.input.platform_radius, 1))}
              />
              <CompareRow
                label="Nº de linhas"
                values={systems.map((s) => String(s.input.lines.length))}
              />
              <CompareRow
                label="Última execução"
                values={systems.map((s) =>
                  s.result ? '✓' : '— (não resolvido)',
                )}
              />
              <CompareRow
                label="Resultante (kN)"
                values={systems.map((s) =>
                  s.result
                    ? `${(s.result.aggregate_force_magnitude / 1000).toFixed(2)}`
                    : '—',
                )}
              />
              <CompareRow
                label="Direção (°)"
                values={systems.map((s) =>
                  s.result && s.result.aggregate_force_magnitude > 0
                    ? `${s.result.aggregate_force_azimuth_deg.toFixed(1)}°`
                    : '—',
                )}
              />
              <CompareRow
                label="Convergiram"
                values={systems.map((s) =>
                  s.result
                    ? `${s.result.n_converged}/${s.result.lines.length}`
                    : '—',
                )}
              />
              <CompareRow
                label="Máx. utilização"
                values={systems.map((s) =>
                  s.result ? fmtPercent(s.result.max_utilization, 1) : '—',
                )}
              />
              <CompareRow
                label="Pior alerta"
                values={systems.map((s) => s.result?.worst_alert_level ?? '—')}
              />
            </TableBody>
          </Table>
        </Card>
      </div>
    </>
  )
}

function CompareRow({
  label,
  values,
}: {
  label: string
  values: string[]
}) {
  return (
    <TableRow>
      <TableCell className="font-medium text-muted-foreground">
        {label}
      </TableCell>
      {values.map((v, i) => (
        <TableCell key={i} className="text-right font-mono tabular-nums">
          {v}
        </TableCell>
      ))}
    </TableRow>
  )
}

// Suprimir warning de tipo importado mas não usado em alguns paths.
type _Used = MooringSystemOutput
const _: unknown = null as unknown as _Used
void _
