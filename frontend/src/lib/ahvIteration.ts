/**
 * Iteração automática de bollard pull AHV (Sprint 3 / Commit 30,
 * hotfix Sprint 3.1).
 *
 * Dado um CaseInput com `boundary.ahv_install.target_horz_distance`
 * setado, encontra o `bollard_pull` que produz `X ≈ target_X` quando
 * o solver roda em mode Tension.
 *
 * Algoritmo: bissection com bracket adaptativo + atalho early-exit
 * + cache de avaliações para fallback robusto.
 *
 * Cada avaliação chama `previewSolve(caseInput_modificado)` (~50ms na
 * produção atual). 12 iterações máx + ~5 chutes de bracket adaptativo
 * = ~700ms-1s total. Aceitável para feedback síncrono.
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
  stopReason:
    | 'tolerance_met'
    | 'max_iters'
    | 'bracket_invalid'
    | 'all_invalid'
    | 'shortcut'
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
const DEFAULT_MAX_ITERS = 12
const BRACKET_EXPANSION_LIMIT = 8 // máximo expansões de bracket adaptativo
                                  // 8 dobras: bollard varia em 256× (ex.: 70te → 0.27 a 17920 te)

/** Cache de avaliações já feitas, ordenado por bollard. */
interface EvalRecord {
  bollardPull: number
  xResult: number | null
  status: IterationStep['status']
}

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
 * Procura par (lo, hi) no cache que envolve o target. Útil quando
 * bracket search falha em encontrar [lo, hi] adjacentes mas o cache
 * já tem pontos válidos suficientes.
 */
function findBracketInCache(
  cache: EvalRecord[],
  targetX: number,
): { lo: EvalRecord; hi: EvalRecord } | null {
  const valid = cache
    .filter((e) => e.xResult != null)
    .sort((a, b) => a.bollardPull - b.bollardPull)
  let lo: EvalRecord | null = null
  let hi: EvalRecord | null = null
  for (const e of valid) {
    if (e.xResult! <= targetX) {
      lo = e // último com x <= target
    }
    if (e.xResult! >= targetX && hi == null) {
      hi = e // primeiro com x >= target
    }
  }
  if (lo && hi && lo.bollardPull < hi.bollardPull) return { lo, hi }
  return null
}

/**
 * Acha o ponto válido mais próximo do target no cache (fallback).
 */
function bestInCache(
  cache: EvalRecord[],
  targetX: number,
): EvalRecord | null {
  const valid = cache.filter((e) => e.xResult != null)
  if (valid.length === 0) return null
  return valid.reduce((best, e) =>
    Math.abs(e.xResult! - targetX) < Math.abs(best.xResult! - targetX) ? e : best,
  )
}

/**
 * Iteração principal — atalho → bracket adaptativo → bissection.
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

  const ahv =
    (base.boundary as unknown as {
      ahv_install?: { bollard_pull?: number } | null
    }).ahv_install
  const bollardInitial = ahv?.bollard_pull ?? 50 * 9806.65

  const steps: IterationStep[] = []
  const cache: EvalRecord[] = []
  let iterCounter = 0

  const recordEvaluation = (
    bollardPull: number,
    res: { x: number | null; status: IterationStep['status']; message?: string },
  ) => {
    iterCounter += 1
    const err = res.x != null ? Math.abs(res.x - targetX) : null
    const step: IterationStep = {
      iter: iterCounter,
      bollardPull,
      xResult: res.x,
      error: err,
      status: res.status,
      message: res.message,
    }
    steps.push(step)
    onStep(step)
    cache.push({ bollardPull, xResult: res.x, status: res.status })
  }

  // ── Etapa 0: atalho — avalia bollard inicial primeiro. ──
  // Se já está dentro da tolerância, retorna imediato.
  const evalInit = await evaluateBollard(base, bollardInitial)
  recordEvaluation(bollardInitial, evalInit)
  if (evalInit.x != null && Math.abs(evalInit.x - targetX) < tol) {
    return {
      converged: true,
      bollardPullFinal: bollardInitial,
      xResultFinal: evalInit.x,
      errorFinal: Math.abs(evalInit.x - targetX),
      steps,
      stopReason: 'shortcut',
    }
  }

  // ── Etapa 1: bracket adaptativo. ──
  // Inicial [bollard/4, bollard×4]. Expande até 5 vezes.
  let lo = Math.max(1.0, bollardInitial / 4)
  let hi = bollardInitial * 4
  let bracketed: { lo: number; hi: number; xLo: number; xHi: number } | null = null

  for (let expansion = 0; expansion < BRACKET_EXPANSION_LIMIT; expansion += 1) {
    const evalLo = await evaluateBollard(base, lo)
    recordEvaluation(lo, evalLo)
    const evalHi = await evaluateBollard(base, hi)
    recordEvaluation(hi, evalHi)

    // Verifica se o cache já envolve o target (incluindo pontos prévios)
    const fromCache = findBracketInCache(cache, targetX)
    if (fromCache) {
      bracketed = {
        lo: fromCache.lo.bollardPull,
        hi: fromCache.hi.bollardPull,
        xLo: fromCache.lo.xResult!,
        xHi: fromCache.hi.xResult!,
      }
      break
    }

    // Sem bracket — decide direção da expansão
    if (evalLo.x == null && evalHi.x == null) {
      // Ambos extremos falharam — encolhe lo (regime mais favorável) e
      // dobra hi pra explorar mais
      lo = Math.max(1.0, lo / 2)
      hi = hi * 2
    } else if (evalLo.x != null && evalLo.x > targetX) {
      // bollard mínimo já dá X grande — diminui lo
      lo = Math.max(1.0, lo / 2)
    } else if (evalHi.x != null && evalHi.x < targetX) {
      // bollard máximo dá X pequeno — aumenta hi
      hi = hi * 2
    } else if (evalLo.x == null) {
      // lo falhou, hi convergiu mas não envolve target — encolhe lo
      lo = Math.max(1.0, lo / 2)
    } else if (evalHi.x == null) {
      // hi falhou, lo convergiu mas não envolve target — dobra hi
      hi = hi * 2
    }
  }

  // ── Etapa 2: bissection se bracketou; senão, retorna best do cache. ──
  if (!bracketed) {
    const best = bestInCache(cache, targetX)
    if (best) {
      const err = Math.abs(best.xResult! - targetX)
      return {
        converged: err < tol,
        bollardPullFinal: best.bollardPull,
        xResultFinal: best.xResult,
        errorFinal: err,
        steps,
        stopReason: err < tol ? 'tolerance_met' : 'bracket_invalid',
      }
    }
    return {
      converged: false,
      bollardPullFinal: bollardInitial,
      xResultFinal: null,
      errorFinal: null,
      steps,
      stopReason: 'all_invalid',
    }
  }

  // Bissection
  let { lo: bLo, hi: bHi } = bracketed
  const initBest = bestInCache(cache, targetX)!
  let bestB = initBest.bollardPull
  let bestX: number | null = initBest.xResult
  let bestErr = Math.abs(initBest.xResult! - targetX)

  for (let i = 0; i < maxIters; i += 1) {
    const mid = (bLo + bHi) / 2
    const res = await evaluateBollard(base, mid)
    recordEvaluation(mid, res)

    if (res.x == null) {
      // Encolhe bracket conservadoramente do lado que falhou
      bHi = mid
      continue
    }

    const err = Math.abs(res.x - targetX)
    if (err < bestErr) {
      bestB = mid
      bestX = res.x
      bestErr = err
    }

    if (err < tol) {
      return {
        converged: true,
        bollardPullFinal: mid,
        xResultFinal: res.x,
        errorFinal: err,
        steps,
        stopReason: 'tolerance_met',
      }
    }

    if (res.x < targetX) {
      bLo = mid
    } else {
      bHi = mid
    }
  }

  return {
    converged: bestErr < tol,
    bollardPullFinal: bestB,
    xResultFinal: bestX,
    errorFinal: bestErr,
    steps,
    stopReason: 'max_iters',
  }
}
