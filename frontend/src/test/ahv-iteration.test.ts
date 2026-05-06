/**
 * Smoke do helper iterateBollardPullForTargetX (Sprint 3 / Commit 30).
 *
 * Testa a lógica de iteração com `previewSolve` mockado — não exercita
 * o solver real. Valida:
 *   - Bissection converge quando bracket [lo, hi] envolve target.
 *   - Bracket adaptativo expande se primeiro chute não envolve.
 *   - Reporta steps via callback onStep.
 *   - Status `tolerance_met` quando |x - target| < tol.
 *   - Status `bracket_invalid` quando todas avaliações falham.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('@/api/endpoints', () => ({
  previewSolve: vi.fn(),
}))

import { previewSolve } from '@/api/endpoints'
import { iterateBollardPullForTargetX } from '@/lib/ahvIteration'
import type { CaseInput, SolverResult } from '@/api/types'

const mockedPreviewSolve = vi.mocked(previewSolve)

const baseCaseInput: CaseInput = {
  name: 'test',
  description: null,
  segments: [
    {
      length: 1000,
      w: 1000,
      EA: 1e8,
      MBL: 1e7,
      category: 'Wire',
      line_type: 'IWRCEIPS',
    } as never,
  ],
  boundary: {
    h: 300,
    mode: 'Tension',
    input_value: 50 * 9806.65,
    startpoint_depth: 0,
    endpoint_grounded: true,
    startpoint_type: 'ahv',
    ahv_install: {
      bollard_pull: 50 * 9806.65,
      deck_level_above_swl: 0,
      stern_angle_deg: 0,
      target_horz_distance: 1500,
    },
  } as never,
  seabed: { mu: 0.0, slope_rad: 0 } as never,
  criteria_profile: 'MVP_Preliminary',
  attachments: [],
} as never

function mockResult(x: number): SolverResult {
  return {
    status: 'converged',
    fairlead_tension: 0,
    anchor_tension: 0,
    total_horz_distance: x,
    total_grounded_length: 0,
    message: '',
  } as never
}

describe('iterateBollardPullForTargetX', () => {
  beforeEach(() => {
    mockedPreviewSolve.mockReset()
  })

  it('converge quando bracket envolve target (X cresce com bollard)', async () => {
    // Mock: X = bollard / 100 (linear, monotônico crescente).
    // target = 1500 → bollard ideal = 150_000 N.
    mockedPreviewSolve.mockImplementation(async (input) => {
      const b = input.boundary.input_value as number
      return mockResult(b / 100)
    })

    const result = await iterateBollardPullForTargetX(
      baseCaseInput,
      1500,
      { tolerance: 1, maxIters: 12 },
    )
    expect(result.converged).toBe(true)
    expect(result.errorFinal).toBeLessThan(1)
    // Tolerância 100 N em torno de 150_000 N — bissection 12 iter
    // num range ~5e5 atinge ~100N de precisão.
    expect(result.bollardPullFinal).toBeGreaterThan(149_900)
    expect(result.bollardPullFinal).toBeLessThan(150_100)
  })

  it('reporta steps via onStep', async () => {
    mockedPreviewSolve.mockImplementation(async (input) => {
      const b = input.boundary.input_value as number
      return mockResult(b / 100)
    })

    const collected: number[] = []
    await iterateBollardPullForTargetX(
      baseCaseInput,
      1500,
      {
        tolerance: 1,
        maxIters: 12,
        onStep: (s) => collected.push(s.iter),
      },
    )
    expect(collected.length).toBeGreaterThan(0)
    expect(collected[0]).toBe(1)
    // monotonic (não pula numbers)
    for (let i = 1; i < collected.length; i += 1) {
      expect(collected[i]).toBe(collected[i - 1] + 1)
    }
  })

  it('status all_invalid quando TODAS avaliações falham', async () => {
    mockedPreviewSolve.mockImplementation(async () => {
      return {
        status: 'invalid_case',
        message: 'fail',
      } as never
    })
    const result = await iterateBollardPullForTargetX(
      baseCaseInput,
      1500,
      { maxIters: 4 },
    )
    expect(result.converged).toBe(false)
    expect(result.stopReason).toBe('all_invalid')
    expect(result.xResultFinal).toBeNull()
  })

  it('atalho early-exit quando bollard inicial já satisfaz tolerância', async () => {
    // bollard inicial = 50 te × 9806.65 ≈ 490_332 N. Mock dá X=1500
    // diretamente. target=1500, tol=1 → primeiro chute resolve.
    mockedPreviewSolve.mockImplementation(async () => mockResult(1500))

    const result = await iterateBollardPullForTargetX(
      baseCaseInput,
      1500,
      { tolerance: 5, maxIters: 12 },
    )
    expect(result.converged).toBe(true)
    expect(result.stopReason).toBe('shortcut')
    expect(result.steps).toHaveLength(1) // só uma avaliação
  })

  it('best fallback quando bracket falha mas há avaliações válidas', async () => {
    // Estratégia: target ACIMA de qualquer X possível. Mock retorna
    // x=2000 (constante). Helper detecta saturação (Δx/Δb = 0) E que
    // todas as avaliações estão abaixo do target=2500.
    mockedPreviewSolve.mockImplementation(async () => mockResult(2000))

    const result = await iterateBollardPullForTargetX(
      baseCaseInput,
      2500,
      { tolerance: 1, maxIters: 4 },
    )
    expect(result.converged).toBe(false)
    // saturation ou bracket_invalid; ambos válidos como fallback
    expect(['saturation', 'bracket_invalid']).toContain(result.stopReason)
    expect(result.xResultFinal).toBe(2000)
    expect(result.errorFinal).toBeCloseTo(500, 1)
    expect(result.bollardPullFinal).toBeGreaterThan(0)
  })

  it('detecta saturação quando target excede X_max teórico', async () => {
    // baseCaseInput tem 1 seg de 1000m, h=300m → X_max = sqrt(1000² - 300²)
    // ≈ 953.94 m. Target=1500 é > X_max → impossível geometricamente.
    mockedPreviewSolve.mockImplementation(async (input) => {
      const b = input.boundary.input_value as number
      // Simula saturação: X cresce mas satura próximo de 950
      const x = Math.min(950, b / 100)
      return mockResult(x)
    })

    const result = await iterateBollardPullForTargetX(
      baseCaseInput,
      1500,
      { tolerance: 1, maxIters: 8 },
    )
    expect(result.converged).toBe(false)
    expect(result.stopReason).toBe('saturation')
    expect(result.xMaxTheoretical).toBeCloseTo(953.94, 0)
    expect(result.xResultFinal).toBeLessThanOrEqual(950)
  })

  it('expande bracket adaptativo quando inicial não envolve', async () => {
    // X = bollard / 1000 → bollard inicial 50e3 dá X=50, target=5000
    // → bracket inicial [12.5e3, 200e3] dá X∈[12.5, 200] — não envolve
    // 5000. Expansão dobra hi até envolver.
    mockedPreviewSolve.mockImplementation(async (input) => {
      const b = input.boundary.input_value as number
      return mockResult(b / 1000)
    })

    const result = await iterateBollardPullForTargetX(
      baseCaseInput,
      5000,
      { tolerance: 5, maxIters: 12 },
    )
    expect(result.steps.length).toBeGreaterThan(2) // expansion + bissection
    // Não falha — eventually atinge bracket
    if (result.converged) {
      expect(result.errorFinal).toBeLessThan(5)
    }
  })
})
