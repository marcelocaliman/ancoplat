import type {
  MooringSystemInput,
  MooringSystemResult,
} from '@/api/types'

export interface OverlaySystem {
  id: number
  name: string
  color: string
  input: MooringSystemInput
  result?: MooringSystemResult
}

export interface MooringSystemsOverlayViewProps {
  systems: OverlaySystem[]
  className?: string
}

/**
 * Overlay de vários mooring systems numa única plan view (F5.4.5d).
 * Cada sistema é desenhado com sua cor própria; plataforma do primeiro
 * sistema é a referência. Linhas com `solver_result.status !==
 * 'converged'` aparecem pontilhadas.
 *
 * Para evitar confusão visual, NÃO renderizamos vetor resultante
 * (cada sistema teria o seu) e nem grid pontilhado. Aqui é uma vista
 * comparativa, não diagnóstica.
 */
export function MooringSystemsOverlayView({
  systems,
  className,
}: MooringSystemsOverlayViewProps) {
  if (systems.length === 0) return null

  // Maior raio entre todos os sistemas — define o span do canvas.
  let maxRadius = 0
  let maxPlatform = 0
  for (const s of systems) {
    maxPlatform = Math.max(maxPlatform, s.input.platform_radius)
    if (s.result) {
      for (const lr of s.result.lines) {
        const r = Math.max(
          Math.hypot(...lr.anchor_xy),
          Math.hypot(...lr.fairlead_xy),
        )
        if (r > maxRadius) maxRadius = r
      }
    } else {
      for (const l of s.input.lines) {
        const fallback = l.fairlead_radius * 4
        if (fallback > maxRadius) maxRadius = fallback
      }
    }
  }
  const span = Math.max(maxRadius, maxPlatform) * 1.15

  const VB = 1000
  const cx = VB / 2
  const cy = VB / 2
  const scale = (VB / 2) / span

  function toSvg(x: number, y: number): [number, number] {
    return [cx + x * scale, cy - y * scale]
  }

  return (
    <svg
      viewBox={`0 0 ${VB} ${VB}`}
      preserveAspectRatio="xMidYMid meet"
      className={className}
      style={{ width: '100%', height: '100%' }}
      aria-label="Plan view comparativo de mooring systems"
    >
      {/* Anéis de referência */}
      {[0.33, 0.66, 1.0].map((frac) => (
        <circle
          key={frac}
          cx={cx}
          cy={cy}
          r={(VB / 2) * frac * 0.95}
          fill="none"
          stroke="currentColor"
          strokeOpacity={0.1}
          strokeWidth={1}
          strokeDasharray="4 4"
        />
      ))}

      {/* Eixos */}
      <line
        x1={cx - VB / 2 + 8}
        y1={cy}
        x2={cx + VB / 2 - 8}
        y2={cy}
        stroke="currentColor"
        strokeOpacity={0.18}
        strokeWidth={1}
      />
      <line
        x1={cx}
        y1={cy - VB / 2 + 8}
        x2={cx}
        y2={cy + VB / 2 - 8}
        stroke="currentColor"
        strokeOpacity={0.18}
        strokeWidth={1}
      />

      {/* Plataforma de referência (do primeiro sistema). Os demais
          podem ter raios diferentes mas optamos por uma única
          referência visual; a tabela comparativa mostra os valores. */}
      <circle
        cx={cx}
        cy={cy}
        r={maxPlatform * scale}
        fill="currentColor"
        fillOpacity={0.06}
        stroke="currentColor"
        strokeOpacity={0.4}
        strokeWidth={1.2}
      />

      {/* Linhas de cada sistema */}
      {systems.map((s) =>
        s.result
          ? s.result.lines.map((lr, i) => {
              const isInvalid = lr.solver_result.status !== 'converged'
              const [fx, fy] = toSvg(...lr.fairlead_xy)
              const [ax, ay] = toSvg(...lr.anchor_xy)
              return (
                <g key={`${s.id}-r-${i}`}>
                  <line
                    x1={fx}
                    y1={fy}
                    x2={ax}
                    y2={ay}
                    stroke={s.color}
                    strokeWidth={isInvalid ? 1.2 : 2.2}
                    strokeOpacity={isInvalid ? 0.45 : 0.85}
                    strokeDasharray={isInvalid ? '5 4' : undefined}
                    strokeLinecap="round"
                  />
                  <circle cx={fx} cy={fy} r={3} fill={s.color} />
                  <polygon
                    points={`${ax},${ay - 5} ${ax + 4},${ay + 3} ${ax - 4},${ay + 3}`}
                    fill={s.color}
                    opacity={0.9}
                  />
                </g>
              )
            })
          : s.input.lines.map((l, i) => {
              const theta = (l.fairlead_azimuth_deg * Math.PI) / 180
              const fxData = l.fairlead_radius * Math.cos(theta)
              const fyData = l.fairlead_radius * Math.sin(theta)
              const ar = l.fairlead_radius * 4
              const axData = ar * Math.cos(theta)
              const ayData = ar * Math.sin(theta)
              const [fx, fy] = toSvg(fxData, fyData)
              const [ax, ay] = toSvg(axData, ayData)
              return (
                <g key={`${s.id}-i-${i}`}>
                  <line
                    x1={fx}
                    y1={fy}
                    x2={ax}
                    y2={ay}
                    stroke={s.color}
                    strokeWidth={1.5}
                    strokeOpacity={0.5}
                    strokeDasharray="6 4"
                  />
                  <circle cx={fx} cy={fy} r={3} fill={s.color} opacity={0.7} />
                </g>
              )
            }),
      )}

      {/* Centro */}
      <circle cx={cx} cy={cy} r={2.5} fill="currentColor" fillOpacity={0.85} />
    </svg>
  )
}
