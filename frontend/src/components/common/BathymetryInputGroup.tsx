/**
 * BathymetryInputGroup — entrada primária de geometria por batimetria
 * nos 2 pontos (Fase 2 / A2.2 + A2.3).
 *
 * Substitui o `BathymetryPopover` (deletado na Fase 2) como caminho
 * principal de entrada do slope. Usuário fornece:
 *
 *   - Profundidade do seabed sob a âncora (m)
 *   - Profundidade do seabed sob o fairlead (m)
 *   - Distância horizontal âncora ↔ fairlead (m, estimada)
 *
 * Componente calcula o slope automaticamente:
 *
 *   slope_rad = atan2(depth_anchor − depth_fairlead, horizontal_distance)
 *
 * Convenção alinhada com `SeabedConfig.slope_rad`:
 *   - slope > 0 = seabed sobe ao fairlead (anchor mais profundo)
 *   - slope < 0 = seabed desce ao fairlead (anchor mais raso)
 *
 * Para o caso de uso reverso (engenheiro com slope direto + sem
 * batimetria), a aba Ambiente expõe um modo "Avançado" que aceita
 * input de slope em graus diretamente.
 *
 * Round-trip determinístico (Ajuste 2 da Fase 2):
 *   Dado um case salvo com (h, slope_rad, X_total opcional), o
 *   componente popula os 3 campos via fórmulas inversas e produz o
 *   mesmo slope_rad ao recalcular — testado em
 *   frontend/src/test/bathymetry-roundtrip.test.ts.
 */
import { useEffect, useState } from 'react'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { cn, fmtNumber } from '@/lib/utils'

export interface BathymetryInputGroupProps {
  /** Profundidade do seabed sob a âncora (m). Sincroniza com boundary.h. */
  depthAnchor: number
  setDepthAnchor: (v: number) => void
  /**
   * Slope atual em radianos. O componente calcula o novo slope a partir
   * de (depthAnchor, depthFairlead, horizontalDistance) e chama
   * onSlopeChange. Mudanças vindas de fora (ex.: load de case salvo)
   * propagam para os 3 campos via efeito.
   */
  slopeRad: number
  onSlopeChange: (rad: number) => void
  /**
   * X total do solver (preview se disponível). Usado para popular o
   * campo "Distância horizontal" em fluxos onde o usuário só conhece
   * o solve atual, não a distância à priori. Quando undefined, usuário
   * digita manualmente.
   */
  xTotalEstimate?: number
  className?: string
}

export function BathymetryInputGroup({
  depthAnchor,
  setDepthAnchor,
  slopeRad,
  onSlopeChange,
  xTotalEstimate,
  className,
}: BathymetryInputGroupProps) {
  // Distância horizontal: se xTotalEstimate disponível e nada local
  // ainda foi escrito, usa o estimate. Estado local mantém a edição
  // do usuário sem ser pisado pelo estimate de cada re-render.
  // v1.0.7: arredonda para inteiro para display limpo (em offshore,
  // distâncias em metros sem decimais é o padrão profissional).
  const [horizDistance, setHorizDistance] = useState<number>(
    xTotalEstimate && xTotalEstimate > 0 ? Math.round(xTotalEstimate) : 500,
  )

  // Estado local de prof_fairlead. Inicializa a partir da fórmula
  // inversa: depthFairlead = depthAnchor - tan(slopeRad)·X.
  // Round-trip reverso ao carregar case salvo.
  const [depthFairlead, setDepthFairleadState] = useState<number>(
    Math.max(
      0,
      Math.round(depthAnchor - Math.tan(slopeRad) * (horizDistance || 1)),
    ),
  )

  // Sincronização externa: quando o pai (form) muda h, slope ou X
  // (ex.: load de case salvo, mudança de mode), repopula os 3 campos
  // via fórmulas inversas. Evita drift silencioso.
  useEffect(() => {
    if (xTotalEstimate && xTotalEstimate > 0) {
      setHorizDistance(Math.round(xTotalEstimate))
      const derivedFairlead = Math.max(
        0,
        Math.round(depthAnchor - Math.tan(slopeRad) * xTotalEstimate),
      )
      setDepthFairleadState(derivedFairlead)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [depthAnchor, slopeRad, xTotalEstimate])

  // Quando user edita qualquer um dos 3, recomputa slope e propaga.
  function recompute(
    nextAnchor: number,
    nextFairlead: number,
    nextX: number,
  ) {
    if (nextX <= 0) return // X=0 dá divisão por zero implícita; ignora
    const dz = nextAnchor - nextFairlead
    const newSlope = Math.atan2(dz, nextX)
    if (Number.isFinite(newSlope)) {
      onSlopeChange(newSlope)
    }
  }

  function handleAnchor(v: number) {
    setDepthAnchor(v)
    recompute(v, depthFairlead, horizDistance)
  }
  function handleFairlead(v: number) {
    setDepthFairleadState(v)
    recompute(depthAnchor, v, horizDistance)
  }
  function handleHoriz(v: number) {
    setHorizDistance(v)
    recompute(depthAnchor, depthFairlead, v)
  }

  const slopeDeg = (slopeRad * 180) / Math.PI

  return (
    <div className={cn('flex flex-col gap-2', className)}>
      <FieldRow
        label="Prof. seabed sob a âncora"
        unit="m"
        value={depthAnchor}
        onChange={handleAnchor}
        min={0.1}
        step={1}
      />
      <FieldRow
        label="Prof. seabed sob o fairlead"
        unit="m"
        value={depthFairlead}
        onChange={handleFairlead}
        min={0}
        step={1}
        hint="Geralmente próxima da prof. sob a âncora; difere quando há slope"
      />
      <FieldRow
        label="Distância horizontal âncora ↔ fairlead"
        unit="m"
        value={horizDistance}
        onChange={handleHoriz}
        min={1}
        step={1}
        hint={
          xTotalEstimate && xTotalEstimate > 0
            ? `Pré-preenchido com X do solve atual (${Math.round(xTotalEstimate)} m)`
            : 'Estimativa para derivar slope; não substitui o X do solver'
        }
      />
      <div className="max-w-[180px] rounded-md border border-border/60 bg-muted/30 p-1.5">
        <div className="flex items-baseline justify-between gap-2 text-[10px]">
          <span className="text-muted-foreground">Inclinação</span>
          <span className="font-mono font-semibold tabular-nums">
            {fmtNumber(slopeDeg, 2)}°
          </span>
        </div>
        {Math.abs(slopeDeg) > 45 && (
          <p className="mt-1 text-[9px] text-warning">
            Fora de ±45°. Solver vai recusar.
          </p>
        )}
      </div>
    </div>
  )
}

function FieldRow({
  label,
  unit,
  value,
  onChange,
  min,
  step,
  hint,
}: {
  label: string
  unit: string
  value: number
  onChange: (v: number) => void
  min?: number
  step?: number
  hint?: string
}) {
  return (
    <div className="flex flex-col gap-0.5">
      <Label className="flex items-center justify-between gap-1 text-[10px] font-medium text-muted-foreground">
        <span className="truncate">{label}</span>
        <span className="shrink-0 font-mono text-[9px] font-normal">{unit}</span>
      </Label>
      <Input
        type="number"
        step={step ?? 'any'}
        min={min}
        value={Number.isFinite(value) ? value : 0}
        onChange={(e) => onChange(parseFloat(e.target.value || '0'))}
        className="h-7 max-w-[120px] font-mono text-[11px]"
      />
      {hint && <p className="text-[9px] leading-tight text-muted-foreground">{hint}</p>}
    </div>
  )
}

/**
 * Derivação reversa: dado um case salvo (h, slope_rad, X_total opcional),
 * popula os 3 campos primários do BathymetryInputGroup. Usado em testes
 * de round-trip e na inicialização do form quando o componente é
 * montado pela primeira vez.
 *
 * Quando X_total não está disponível, usa um fallback razoável (500 m).
 * Round-trip exato exige fornecer X_total real.
 */
export function deriveBathymetryFromBoundary(
  h: number,
  slopeRad: number,
  xTotal: number | undefined,
): { depthAnchor: number; depthFairlead: number; horizontalDistance: number } {
  const X = xTotal && xTotal > 0 ? xTotal : 500
  const depthFairlead = Math.max(0, h - Math.tan(slopeRad) * X)
  return {
    depthAnchor: h,
    depthFairlead,
    horizontalDistance: X,
  }
}

/**
 * Derivação direta (forward): dado os 3 valores primários, retorna o
 * slope_rad correspondente. Esta é a fórmula que `recompute` aplica
 * dentro do componente.
 */
export function deriveSlopeFromBathymetry(
  depthAnchor: number,
  depthFairlead: number,
  horizontalDistance: number,
): number {
  if (horizontalDistance <= 0) return 0
  const dz = depthAnchor - depthFairlead
  return Math.atan2(dz, horizontalDistance)
}
