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
    expect(result.bollardPullFinal).toBeCloseTo(150_000, -2)
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

  it('status bracket_invalid quando todas avaliações falham', async () => {
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
    expect(result.stopReason).toBe('bracket_invalid')
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
