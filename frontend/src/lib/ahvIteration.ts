/**
 * Iteração automática de bollard pull AHV (Sprint 3 / Commit 30).
 *
 * Dado um CaseInput com `boundary.ahv_install.target_horz_distance`
 * setado, encontra o `bollard_pull` que produz `X ≈ target_X` quando
 * o solver roda em mode Tension.
 *
 * Algoritmo: bissection com bracket adaptativo.
 *
 * Cada iteração chama `previewSolve(caseInput_modificado)` que é
 * leve (~50ms na produção atual). 10 iterações = ~500ms total —
 * aceitável para feedback síncrono na UI.
 */
import { previewSolve } from '@/api/endpoints'
import type { CaseInput, SolverResult } from '@/api/types'

export interface IterationStep {
  iter: number
  bollardPull: number // N
  xResult: number | null // m, ou null se não convergiu
  error: number | null // |x_result - target| em metros
  status: 'converged' | 'invalid_case' | 'numerical_error' | 'pending'
  message?: string
}

export interface IterationResult {
  /** Se a iteração final atingiu tolerância. */
  converged: boolean
  /** Bollard pull final (melhor encontrado). */
  bollardPullFinal: number
  /** X resultante final. */
  xResultFinal: number | null
  /** Erro absoluto final |x - target|. */
  errorFinal: number | null
  /** Histórico completo das iterações. */
  steps: IterationStep[]
  /** Razão de parada. */
  stopReason: 'tolerance_met' | 'max_iters' | 'bracket_invalid' | 'all_invalid'
}

export interface IterationOptions {
  /** Tolerância em metros — para quando |x - target| < tolerance. */
  tolerance?: number
  /** Máximo de iterações de bissection. */
  maxIters?: number
  /** Callback opcional após cada iteração (para UI progress). */
  onStep?: (step: IterationStep) => void
}

const DEFAULT_TOLERANCE = 0.5 // m
const DEFAULT_MAX_ITERS = 10
const BRACKET_EXPANSION_LIMIT = 5 // máximo expansões de bracket adaptativo

/**
 * Build CaseInput com bollard_pull substituído (mode Tension forçado).
 */
function buildPreviewInput(base: CaseInput, bollardPull: number): CaseInput {
  return {
    ...base,
    boundary: {
      ...base.boundary,
      mode: 'Tension',
      input_value: bollardPull,
    } as CaseInput['boundary'],
  }
}

/**
 * Avalia uma única tentativa de bollard_pull e retorna o X resultante.
 */
async function evaluateBollard(
  base: CaseInput,
  bollardPull: number,
): Promise<{ x: number | null; status: IterationStep['status']; message?: string }> {
  try {
    const res: SolverResult = await previewSolve(
      buildPreviewInput(base, bollardPull),
    )
    if (res.status === 'converged') {
      return { x: res.total_horz_distance, status: 'converged' }
    }
    return {
      x: null,
      status: res.status as IterationStep['status'],
      message: res.message ?? '',
    }
  } catch (err) {
    return {
      x: null,
      status: 'numerical_error',
      message: err instanceof Error ? err.message : String(err),
    }
  }
}

/**
 * Encontra bracket [b_lo, b_hi] tal que x(b_lo) < target < x(b_hi).
 * Expansão adaptativa começando em [bollard/4, bollard×4]. Se ainda
 * não bracketear, dobra os limites até `BRACKET_EXPANSION_LIMIT` vezes.
 *
 * Convenção física: x cresce monotonicamente com bollard_pull
 * (mais força → linha mais esticada → maior X). Então:
 *   - x(b_lo) < target  → precisa aumentar bollard
 *   - x(b_hi) > target  → precisa diminuir bollard
 */
async function findBracket(
  base: CaseInput,
  bollardInitial: number,
  targetX: number,
  onStep: (step: IterationStep) => void,
  iterCounter: { value: number },
): Promise<
  | { ok: true; lo: number; hi: number; xLo: number; xHi: number }
  | { ok: false; reason: string }
> {
  let lo = Math.max(1.0, bollardInitial / 4)
  let hi = bollardInitial * 4
  for (let expansion = 0; expansion < BRACKET_EXPANSION_LIMIT; expansion += 1) {
    const evalLo = await evaluateBollard(base, lo)
    iterCounter.value += 1
    onStep({
      iter: iterCounter.value,
      bollardPull: lo,
      xResult: evalLo.x,
      error: evalLo.x != null ? Math.abs(evalLo.x - targetX) : null,
      status: evalLo.status,
      message: evalLo.message,
    })
    const evalHi = await evaluateBollard(base, hi)
    iterCounter.value += 1
    onStep({
      iter: iterCounter.value,
      bollardPull: hi,
      xResult: evalHi.x,
      error: evalHi.x != null ? Math.abs(evalHi.x - targetX) : null,
      status: evalHi.status,
      message: evalHi.message,
    })
    if (evalLo.x == null || evalHi.x == null) {
      // Não conseguimos avaliar um dos extremos — expande para fora
      lo = Math.max(1.0, lo / 2)
      hi = hi * 2
      continue
    }
    if (evalLo.x <= targetX && evalHi.x >= targetX) {
      return { ok: true, lo, hi, xLo: evalLo.x, xHi: evalHi.x }
    }
    // Não bracketou — expande no lado certo
    if (evalLo.x > targetX) {
      // Bollard mínimo já dá X grande — diminui ainda mais
      lo = Math.max(1.0, lo / 2)
    }
    if (evalHi.x < targetX) {
      // Bollard máximo dá X pequeno — aumenta ainda mais
      hi = hi * 2
    }
  }
  return {
    ok: false,
    reason: `Bracket adaptativo não envolveu target após ${BRACKET_EXPANSION_LIMIT} expansões.`,
  }
}

/**
 * Iteração principal — bissection sobre bollard_pull até X ≈ target.
 *
 * @param base CaseInput de baseline (já tem boundary.ahv_install).
 * @param targetX Target X em metros.
 * @param options Tolerância, max iters, callback.
 */
export async function iterateBollardPullForTargetX(
  base: CaseInput,
  targetX: number,
  options: IterationOptions = {},
): Promise<IterationResult> {
  const tol = options.tolerance ?? DEFAULT_TOLERANCE
  const maxIters = options.maxIters ?? DEFAULT_MAX_ITERS
  const onStep = options.onStep ?? (() => {})

  // Bollard inicial vem do ahv_install (ou fallback 50 te)
  const ahv =
    (base.boundary as unknown as {
      ahv_install?: { bollard_pull?: number } | null
    }).ahv_install
  const bollardInitial = ahv?.bollard_pull ?? 50 * 9806.65

  const steps: IterationStep[] = []
  const recordStep = (step: IterationStep) => {
    steps.push(step)
    onStep(step)
  }

  const iterCounter = { value: 0 }

  // Etapa 1: encontrar bracket
  const bracket = await findBracket(
    base, bollardInitial, targetX, recordStep, iterCounter,
  )
  if (!bracket.ok) {
    return {
      converged: false,
      bollardPullFinal: bollardInitial,
      xResultFinal: null,
      errorFinal: null,
      steps,
      stopReason: 'bracket_invalid',
    }
  }

  // Etapa 2: bissection
  let { lo, hi } = bracket
  let bestB = bollardInitial
  let bestX: number | null = null
  let bestErr = Infinity

  for (let i = 0; i < maxIters; i += 1) {
    const mid = (lo + hi) / 2
    const res = await evaluateBollard(base, mid)
    iterCounter.value += 1
    const err = res.x != null ? Math.abs(res.x - targetX) : null
    const step: IterationStep = {
      iter: iterCounter.value,
      bollardPull: mid,
      xResult: res.x,
      error: err,
      status: res.status,
      message: res.message,
    }
    recordStep(step)

    if (res.x == null) {
      // Falhou — encolhe bracket conservadoramente. Se invalidar
      // sucessivamente, eventualmente deixaremos com bestB já encontrado.
      hi = mid
      continue
    }

    if (err != null && err < bestErr) {
      bestB = mid
      bestX = res.x
      bestErr = err
    }

    if (err != null && err < tol) {
      return {
        converged: true,
        bollardPullFinal: mid,
        xResultFinal: res.x,
        errorFinal: err,
        steps,
        stopReason: 'tolerance_met',
      }
    }

    // Decide qual lado encolher
    if (res.x < targetX) {
      lo = mid
    } else {
      hi = mid
    }
  }

  return {
    converged: bestErr < tol,
    bollardPullFinal: bestB,
    xResultFinal: bestX,
    errorFinal: bestErr === Infinity ? null : bestErr,
    steps,
    stopReason: 'max_iters',
  }
}
