import { lazy, Suspense, useMemo } from 'react'
import type { SolverResult } from '@/api/types'
import { Skeleton } from '@/components/ui/skeleton'
import { useThemeStore, resolveTheme } from '@/store/theme'

/**
 * Plotly é pesado — lazy-load no client-side.
 *
 * Vite + React 19 + react-plotly.js (CJS) tem um interop ruim com
 * `lazy(() => import('react-plotly.js'))` direto: o `default` vem como
 * um Module Namespace Object em vez de React component. Usamos o
 * factory explícito para construir o componente a partir de plotly.js-dist-min.
 */
function resolveDefault<T>(mod: unknown): T {
  let cur: unknown = mod
  for (let i = 0; i < 3; i += 1) {
    if (typeof cur === 'function') return cur as T
    if (cur && typeof cur === 'object' && 'default' in cur) {
      cur = (cur as { default: unknown }).default
    } else break
  }
  return cur as T
}

const Plot = lazy(async () => {
  const [plotlyMod, factoryMod] = await Promise.all([
    import('plotly.js-dist-min'),
    import('react-plotly.js/factory'),
  ])
  const Plotly = resolveDefault<unknown>(plotlyMod)
  const factory = resolveDefault<(p: unknown) => unknown>(factoryMod)
  if (typeof factory !== 'function') {
    throw new Error(
      'react-plotly.js/factory não retornou uma função após interop. ' +
        `Tipo recebido: ${typeof factory}`,
    )
  }
  const Comp = factory(Plotly)
  return { default: Comp as unknown as React.ComponentType<Record<string, unknown>> }
})

/**
 * Passo "bonito" para eixo dado um range e nº alvo de ticks.
 * Retorna 1, 2, 5, 10, 20, 50, 100, 200, 500, ... (escala 1-2-5).
 */
function niceDtick(range: number, targetTicks = 8): number {
  if (range <= 0 || !Number.isFinite(range)) return 1
  const raw = range / targetTicks
  const exp = Math.floor(Math.log10(raw))
  const pow = 10 ** exp
  const mantissa = raw / pow
  let niceM: number
  if (mantissa < 1.5) niceM = 1
  else if (mantissa < 3.5) niceM = 2
  else if (mantissa < 7.5) niceM = 5
  else niceM = 10
  return niceM * pow
}

export interface CatenaryPlotProps {
  result: SolverResult
  height?: number
  /** Força aspect ratio 1:1 (representação geométrica fiel). Default: false. */
  equalAspect?: boolean
}

/**
 * Perfil 2D da linha. Separa visualmente trecho grounded (seabed) do
 * trecho suspenso (catenária). Markers em âncora, touchdown e fairlead.
 * Hover exibe x/y/|T| em kN.
 *
 * Por padrão, cada eixo ajusta sua escala ao espaço disponível (`aspect
 * livre`). Passe `equalAspect` para travar 1:1. `dtick` é sempre
 * calculado via niceDtick() para evitar ticks absurdos (ex: 5000 em
 * 5000 m) quando escala e container têm proporções distintas.
 */
export function CatenaryPlot({
  result,
  height = 360,
  equalAspect = false,
}: CatenaryPlotProps) {
  const theme = resolveTheme(useThemeStore((s) => s.theme))

  const xs = useMemo(() => result.coords_x ?? [], [result.coords_x])
  const ys = useMemo(() => result.coords_y ?? [], [result.coords_y])
  const ts = useMemo(
    () => result.tension_magnitude ?? [],
    [result.tension_magnitude],
  )

  // Ranges dos dados para escolha de ticks
  const ranges = useMemo(() => {
    const xMin = 0
    const xMax = xs.length > 0 ? Math.max(...xs) : 1
    const yMin = ys.length > 0 ? Math.min(0, ...ys) : 0
    const yMax = ys.length > 0 ? Math.max(...ys) : 1
    // Padding visual ~5% em cada eixo
    const xPad = (xMax - xMin) * 0.05
    const yPad = (yMax - yMin) * 0.08
    const xRange = [xMin - xPad, xMax + xPad]
    const yRange = [yMin - yPad, yMax + yPad]
    const xDtick = niceDtick(xRange[1]! - xRange[0]!, 8)
    const yDtick = niceDtick(yRange[1]! - yRange[0]!, 6)
    return { xRange, yRange, xDtick, yDtick }
  }, [xs, ys])

  const layout = useMemo(() => {
    const yAxis: Record<string, unknown> = {
      title: { text: 'y — Elevação (m)' },
      showgrid: true,
      gridcolor: theme === 'dark' ? '#334155' : '#e2e8f0',
      zerolinecolor: theme === 'dark' ? '#475569' : '#94a3b8',
      range: ranges.yRange,
      dtick: ranges.yDtick,
      tickformat: ',.0f',
    }
    if (equalAspect) {
      yAxis.scaleanchor = 'x'
      yAxis.scaleratio = 1
    }

    return {
      autosize: true,
      height,
      margin: { t: 18, r: 18, b: 48, l: 60 },
      paper_bgcolor: 'transparent',
      plot_bgcolor: 'transparent',
      font: {
        family: 'Inter, system-ui, sans-serif',
        size: 12,
        color: theme === 'dark' ? '#cbd5e1' : '#334155',
      },
      xaxis: {
        title: { text: 'x — Distância horizontal (m)' },
        showgrid: true,
        gridcolor: theme === 'dark' ? '#334155' : '#e2e8f0',
        zerolinecolor: theme === 'dark' ? '#475569' : '#94a3b8',
        range: ranges.xRange,
        dtick: ranges.xDtick,
        tickformat: ',.0f',
      },
      yaxis: yAxis,
      hoverlabel: {
        bgcolor: theme === 'dark' ? '#1e293b' : '#ffffff',
        bordercolor: theme === 'dark' ? '#334155' : '#e2e8f0',
        font: { family: 'Inter' },
      },
      showlegend: true,
      legend: {
        orientation: 'h' as const,
        yanchor: 'bottom' as const,
        y: 1.02,
        xanchor: 'center' as const,
        x: 0.5,
      },
    }
  }, [theme, height, equalAspect, ranges])

  const data = useMemo(() => {
    const td = result.dist_to_first_td ?? 0
    const groundedX: number[] = []
    const groundedY: number[] = []
    const groundedT: number[] = []
    const suspendedX: number[] = []
    const suspendedY: number[] = []
    const suspendedT: number[] = []

    for (let i = 0; i < xs.length; i += 1) {
      const x = xs[i]!
      const y = ys[i]!
      const t = ts[i]!
      if (td > 0 && x <= td + 1e-6 && y < 0.01) {
        groundedX.push(x)
        groundedY.push(y)
        groundedT.push(t)
      } else {
        suspendedX.push(x)
        suspendedY.push(y)
        suspendedT.push(t)
      }
    }

    if (groundedX.length > 0 && suspendedX.length > 0) {
      suspendedX.unshift(groundedX[groundedX.length - 1]!)
      suspendedY.unshift(groundedY[groundedY.length - 1]!)
      suspendedT.unshift(groundedT[groundedT.length - 1]!)
    }

    const traces: Plotly.Data[] = []

    // Seabed line pontilhada até o fim do gráfico
    if (xs.length > 0) {
      const xMax = Math.max(...xs)
      traces.push({
        type: 'scatter',
        mode: 'lines',
        x: [0, xMax * 1.02],
        y: [0, 0],
        line: {
          color: theme === 'dark' ? '#64748B' : '#94A3B8',
          width: 1,
          dash: 'dot',
        },
        name: 'Seabed',
        hoverinfo: 'skip',
        showlegend: false,
      })
    }

    if (groundedX.length > 0) {
      traces.push({
        type: 'scatter',
        mode: 'lines',
        x: groundedX,
        y: groundedY,
        line: {
          color: theme === 'dark' ? '#FBBF24' : '#D97706',
          width: 3,
        },
        name: 'Trecho apoiado',
        text: groundedT.map((t) => `|T| = ${(t / 1000).toFixed(1)} kN`),
        hovertemplate:
          'x = %{x:.2f} m<br>y = %{y:.2f} m<br>%{text}<extra></extra>',
      })
    }

    traces.push({
      type: 'scatter',
      mode: 'lines',
      x: suspendedX.length > 0 ? suspendedX : xs,
      y: suspendedX.length > 0 ? suspendedY : ys,
      line: {
        color: theme === 'dark' ? '#60A5FA' : '#1E3A5F',
        width: 3,
      },
      name: suspendedX.length > 0 ? 'Trecho suspenso' : 'Linha',
      text: (suspendedX.length > 0 ? suspendedT : ts).map(
        (t) => `|T| = ${(t / 1000).toFixed(1)} kN`,
      ),
      hovertemplate: 'x = %{x:.2f} m<br>y = %{y:.2f} m<br>%{text}<extra></extra>',
    })

    traces.push({
      type: 'scatter',
      mode: 'markers',
      x: [0],
      y: [0],
      marker: {
        symbol: 'triangle-up',
        size: 12,
        color: theme === 'dark' ? '#94A3B8' : '#475569',
      },
      name: 'Âncora',
      hovertemplate: 'Âncora<br>x = 0<br>y = 0<extra></extra>',
    })

    if (td > 0.5) {
      traces.push({
        type: 'scatter',
        mode: 'markers',
        x: [td],
        y: [0],
        marker: {
          symbol: 'diamond',
          size: 11,
          color: theme === 'dark' ? '#FBBF24' : '#D97706',
        },
        name: 'Touchdown',
        hovertemplate: 'Touchdown<br>x = %{x:.2f} m<br>y = 0<extra></extra>',
      })
    }

    traces.push({
      type: 'scatter',
      mode: 'markers',
      x: [result.total_horz_distance],
      y: [result.endpoint_depth],
      marker: {
        symbol: 'circle',
        size: 12,
        color: theme === 'dark' ? '#60A5FA' : '#1E3A5F',
      },
      name: 'Fairlead',
      hovertemplate: `Fairlead<br>x = %{x:.2f} m<br>y = %{y:.2f} m<br>T_fl = ${(result.fairlead_tension / 1000).toFixed(1)} kN<extra></extra>`,
    })

    return traces
  }, [xs, ys, ts, result, theme])

  const config = useMemo<Partial<Plotly.Config>>(
    () => ({
      displaylogo: false,
      responsive: true,
      modeBarButtonsToRemove: [
        'lasso2d',
        'select2d',
        'autoScale2d',
      ] as Plotly.ModeBarDefaultButtons[],
    }),
    [],
  )

  return (
    <Suspense fallback={<Skeleton style={{ width: '100%', height }} />}>
      <Plot
        data={data}
        layout={layout}
        config={config}
        style={{ width: '100%', height }}
        useResizeHandler
      />
    </Suspense>
  )
}
