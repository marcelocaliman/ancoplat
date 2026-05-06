import { Anchor, ChevronDown, ChevronRight, Info, Waves } from 'lucide-react'
import { useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

/**
 * Tipos locais espelhando os schemas Sprint 1 / v1.1.0. A regeneração
 * de `openapi.ts` fica como follow-up — manter typings inline aqui
 * evita acoplamento com o ciclo de codegen em commits puramente de UI.
 */
export interface VesselDisplay {
  name: string
  vessel_type?: string | null
  displacement?: number | null
  loa?: number | null
  breadth?: number | null
  draft?: number | null
  heading_deg?: number | null
  operator?: string | null
}

export interface CurrentLayerDisplay {
  depth: number
  speed: number
  heading_deg?: number
}

export interface CurrentProfileDisplay {
  layers: CurrentLayerDisplay[]
  drag_coefficient?: number | null
  water_density?: number | null
}

export interface AHVInstallDisplay {
  bollard_pull: number
  deck_level_above_swl?: number | null
  stern_angle_deg?: number | null
  target_horz_distance?: number | null
}

export interface ImportedModelCardProps {
  vessel?: VesselDisplay | null
  currentProfile?: CurrentProfileDisplay | null
  metadata?: Record<string, string> | null
  ahvInstall?: AHVInstallDisplay | null
  /** Default colapsado (mostra apenas linha de header com badges).
   * Setar `true` para abrir já expandido. */
  defaultExpanded?: boolean
  className?: string
}

/**
 * Cartão consolidado para exibir dados do modelo importado (QMoor 0.8.0
 * ou similar) — vessel/plataforma, perfil de corrente V(z) e metadata
 * operacional do projeto. Sprint 1 / v1.1.0.
 *
 * READ-ONLY: editor para esses campos é Tier B do roadmap. O input
 * autoritativo veio do JSON QMoor importado e é preservado fielmente.
 *
 * Renderiza somente quando algum dos 3 blocos tem dado — caso contrário
 * retorna null para não poluir a UI de cases não-importados.
 */
export function ImportedModelCard({
  vessel,
  currentProfile,
  metadata,
  ahvInstall,
  defaultExpanded = false,
  className,
}: ImportedModelCardProps) {
  const [expanded, setExpanded] = useState(defaultExpanded)
  const hasMetadata =
    metadata &&
    Object.keys(metadata).filter((k) => !k.startsWith('source_')).length > 0
  const isImported = metadata?.['source_format'] === 'qmoor_0_8'
  const hasVessel = vessel != null
  const hasCurrent = currentProfile != null && currentProfile.layers.length > 0
  const hasAHVInstall = ahvInstall != null

  if (!hasVessel && !hasCurrent && !hasMetadata && !isImported && !hasAHVInstall)
    return null

  // Sumário compacto exibido inline ao lado dos badges (read-only).
  // Mostra os 1-3 campos mais úteis pra contexto rápido sem expandir.
  const summary: string[] = []
  if (metadata?.['rig']) summary.push(`Rig ${metadata['rig']}`)
  if (metadata?.['profile_name']) summary.push(metadata['profile_name'])
  if (vessel?.name) summary.push(`Vessel ${vessel.name}`)
  if (ahvInstall?.bollard_pull) {
    summary.push(`${(ahvInstall.bollard_pull / 9806.65).toFixed(0)} te bollard`)
  }
  const summaryText = summary.slice(0, 3).join(' · ')

  return (
    <Card className={cn('mb-2', className)}>
      <CardHeader
        className={cn(
          'cursor-pointer py-2 pr-3 transition-colors hover:bg-muted/30',
          expanded && 'pb-2',
        )}
        onClick={() => setExpanded((v) => !v)}
        role="button"
        aria-expanded={expanded}
      >
        <div className="flex items-center gap-2">
          {expanded ? (
            <ChevronDown className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
          ) : (
            <ChevronRight className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
          )}
          <Info className="h-3.5 w-3.5 shrink-0 text-primary" />
          <CardTitle className="flex flex-1 flex-wrap items-center gap-1.5 text-[12px] font-semibold">
            Modelo importado
            {isImported && (
              <Badge variant="secondary" className="h-4 px-1.5 text-[9px]">
                QMoor 0.8.0
              </Badge>
            )}
            {hasAHVInstall && (
              <Badge
                variant="outline"
                className="h-4 border-warning/40 bg-warning/10 px-1.5 text-[9px] text-warning"
              >
                AHV Install
              </Badge>
            )}
            {!expanded && summaryText && (
              <span className="ml-1 truncate text-[11px] font-normal text-muted-foreground">
                · {summaryText}
              </span>
            )}
          </CardTitle>
          {!expanded && (
            <span className="shrink-0 text-[10px] text-muted-foreground">
              clique para expandir
            </span>
          )}
        </div>
      </CardHeader>
      {expanded && (
        <CardContent className="pb-3 pt-1">
          <div className="grid gap-3 lg:grid-cols-3">
            {hasVessel && <VesselBlock vessel={vessel!} />}
            {hasAHVInstall && <AHVInstallBlock ahv={ahvInstall!} />}
            {hasCurrent && <CurrentBlock profile={currentProfile!} />}
            {(hasMetadata || isImported) && (
              <MetadataBlock metadata={metadata ?? {}} />
            )}
          </div>
        </CardContent>
      )}
    </Card>
  )
}

// ──────────────────────────────────────────────────────────────────
// Sub-blocks
// ──────────────────────────────────────────────────────────────────

function VesselBlock({ vessel }: { vessel: VesselDisplay }) {
  const allRows: Array<[string, string | null | undefined]> = [
    ['Tipo', vessel.vessel_type],
    ['LOA', vessel.loa != null ? `${vessel.loa.toFixed(1)} m` : null],
    ['Boca', vessel.breadth != null ? `${vessel.breadth.toFixed(1)} m` : null],
    ['Calado', vessel.draft != null ? `${vessel.draft.toFixed(1)} m` : null],
    [
      'Deslocamento',
      vessel.displacement != null
        ? `${(vessel.displacement / 1000).toFixed(0)} t`
        : null,
    ],
    [
      'Heading',
      vessel.heading_deg != null ? `${vessel.heading_deg.toFixed(0)}°` : null,
    ],
    ['Operador', vessel.operator],
  ]
  const rows = allRows.filter(([, v]) => v != null && v !== '') as Array<
    [string, string]
  >
  return (
    <div className="rounded-md border border-border/60 p-3">
      <div className="mb-2 flex items-center gap-1.5 text-[12px] font-semibold uppercase tracking-wide text-primary/80">
        <Anchor className="h-3 w-3" />
        Vessel · {vessel.name}
      </div>
      <dl className="space-y-0.5 text-[12px]">
        {rows.map(([k, v]) => (
          <div key={k} className="flex justify-between gap-2">
            <dt className="text-muted-foreground">{k}</dt>
            <dd className="text-foreground">{v}</dd>
          </div>
        ))}
        {rows.length === 0 && (
          <p className="text-[11px] text-muted-foreground">
            Apenas o nome registrado.
          </p>
        )}
      </dl>
    </div>
  )
}

function AHVInstallBlock({ ahv }: { ahv: AHVInstallDisplay }) {
  const rows: Array<[string, string]> = [
    ['Bollard Pull', `${(ahv.bollard_pull / 1000).toFixed(1)} kN`],
  ]
  if (ahv.bollard_pull > 0) {
    rows.push([
      '',
      `(${(ahv.bollard_pull / 9806.65).toFixed(1)} te)`,
    ])
  }
  if (ahv.target_horz_distance != null) {
    rows.push(['Target X', `${ahv.target_horz_distance.toFixed(1)} m`])
  }
  if (ahv.deck_level_above_swl != null && ahv.deck_level_above_swl > 0) {
    rows.push(['Deck above SWL', `${ahv.deck_level_above_swl.toFixed(1)} m`])
  }
  if (ahv.stern_angle_deg != null && ahv.stern_angle_deg !== 0) {
    rows.push(['Stern Angle', `${ahv.stern_angle_deg.toFixed(0)}°`])
  }
  return (
    <div className="rounded-md border border-warning/30 bg-warning/[0.04] p-3">
      <div className="mb-2 flex items-center gap-1.5 text-[12px] font-semibold uppercase tracking-wide text-warning/90">
        <Anchor className="h-3 w-3" />
        AHV Install
      </div>
      <dl className="space-y-0.5 text-[12px]">
        {rows.map(([k, v], i) => (
          <div key={i} className="flex justify-between gap-2">
            <dt className="text-muted-foreground">{k}</dt>
            <dd className="font-mono text-foreground">{v}</dd>
          </div>
        ))}
      </dl>
      <p className="mt-2 text-[10px] italic text-muted-foreground">
        Cenário temporário (Hookup / Backing Down / Load Transfer).
        X resultante depende do bollard pull aplicado.
      </p>
    </div>
  )
}


function CurrentBlock({ profile }: { profile: CurrentProfileDisplay }) {
  const layers = profile.layers
  const vMax = Math.max(...layers.map((l) => l.speed), 0.001)
  return (
    <div className="rounded-md border border-border/60 p-3">
      <div className="mb-2 flex items-center gap-1.5 text-[12px] font-semibold uppercase tracking-wide text-primary/80">
        <Waves className="h-3 w-3" />
        Corrente V(z)
        <span className="ml-1 font-normal text-muted-foreground">
          {layers.length} layer{layers.length === 1 ? '' : 's'}
        </span>
      </div>
      <div className="space-y-1">
        {layers.map((l, i) => (
          <div
            key={i}
            className="flex items-center gap-2 text-[11px] tabular-nums"
          >
            <span className="w-14 text-right text-muted-foreground">
              {l.depth.toFixed(0)} m
            </span>
            <div className="relative h-3 flex-1 rounded-sm bg-muted/40">
              <div
                className="absolute inset-y-0 left-0 rounded-sm bg-primary/40"
                style={{ width: `${(l.speed / vMax) * 100}%` }}
              />
            </div>
            <span className="w-12 text-right">{l.speed.toFixed(2)}</span>
            <span className="w-8 text-muted-foreground">m/s</span>
          </div>
        ))}
      </div>
      {(profile.drag_coefficient != null || profile.water_density != null) && (
        <div className="mt-2 flex gap-3 text-[10px] text-muted-foreground">
          {profile.drag_coefficient != null && (
            <span>Cd = {profile.drag_coefficient}</span>
          )}
          {profile.water_density != null && (
            <span>ρ = {profile.water_density} kg/m³</span>
          )}
        </div>
      )}
    </div>
  )
}

function MetadataBlock({
  metadata,
}: {
  metadata: Record<string, string>
}) {
  const visible = Object.entries(metadata).filter(
    ([k]) => !k.startsWith('source_'),
  )
  const sourceKeys = Object.entries(metadata).filter(([k]) =>
    k.startsWith('source_'),
  )
  return (
    <div className="rounded-md border border-border/60 p-3">
      <div className="mb-2 flex items-center gap-1.5 text-[12px] font-semibold uppercase tracking-wide text-primary/80">
        <Info className="h-3 w-3" />
        Metadata
      </div>
      <dl className="space-y-0.5 text-[12px]">
        {visible.map(([k, v]) => (
          <div key={k} className="flex justify-between gap-2">
            <dt className="text-muted-foreground">{k}</dt>
            <dd className="max-w-[180px] truncate text-foreground" title={v}>
              {v}
            </dd>
          </div>
        ))}
        {visible.length === 0 && (
          <p className="text-[11px] text-muted-foreground">
            Sem metadata operacional.
          </p>
        )}
      </dl>
      {sourceKeys.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {sourceKeys.map(([k, v]) => (
            <Badge
              key={k}
              variant="outline"
              className="font-mono text-[9px] tracking-tight"
            >
              {k.replace('source_', '')}: {v}
            </Badge>
          ))}
        </div>
      )}
    </div>
  )
}
