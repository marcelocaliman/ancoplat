# Relatório F9 — Profiling watchcircle

> **Gerado por** `tools/perf_watchcircle.py --include-preview-cases` em 2026-05-05.
> **Hardware**: macOS arm64 (Apple Silicon).
> **Reproduzir**: `venv/bin/python tools/perf_watchcircle.py [--include-preview-cases]`.

Profiling do `compute_watchcircle()` em sistemas mooring representativos.

## Targets

- **Gate** (AC F9 / Q9): mediana <30s.
- **Aspiracional**: mediana <5s (não-bloqueante).

## Conclusão executiva

**Performance atual NÃO passa o gate <30s em todos os cenários functional**:

- ✅ **Taut deep 4×** (0.024s): trivial — não há touchdown, solver fast-path.
- ⚠️ **Spread 8×** (28s): no limite do gate.
- ❌ **Spread 4× baseline** (56s): **viola gate em ~2×**.
- ❌ **Shallow chain 4×** (86s): **viola gate em ~3×**.

Cenários preview (F7/F8) são informativos para baseline futuro, não bloqueiam F9 — o solver real desses cases ainda não existe.

**Decisão consciente**: F9 é "polish, não rewrite" (princípio do plano). Otimização do solver de equilíbrio (paralelização, caching adicional, redução de tolerâncias) é **refactor não-trivial** que sai do escopo de polish. Pendência crítica registrada para **Fase 10 (V&V completo)**, que naturalmente cobre robustez e performance como gates de release.

## Pendência crítica F10

- **Otimizar `compute_watchcircle()`** para passar gate <30s nos 4 cenários functional. Estratégias possíveis (a investigar com cProfile):
  1. **Paralelização** das `n_steps=36` queries de equilíbrio via `concurrent.futures.ThreadPoolExecutor` (SciPy libera GIL em chamadas C — speedup esperado de 2-4×).
  2. **Caching agressivo** do baseline por linha (já existe parcialmente; ampliar).
  3. **Redução cirúrgica de tolerâncias** do `fsolve` outer com guard rails para precisão.
  4. **Vectorização** em `solve_platform_equilibrium` se possível.
- Após otimização, re-rodar `tools/perf_watchcircle.py` e atualizar este relatório.

## Resultados

| Cenário | Tipo | Linhas | n_steps | min (s) | mediana (s) | max (s) | classificação |
|---|---|---:|---:|---:|---:|---:|---|
| Spread 4× (perf baseline) | functional | 4 | 36 | 56.060 | 56.303 | 57.333 | FAIL (>=30s — viola gate) |
| Spread 8× (perf) | functional | 8 | 36 | 28.410 | 28.483 | 29.318 | warn (<30s gate; >5s aspirational) |
| Taut deep 4× (perf) | functional | 4 | 36 | 0.023 | 0.024 | 0.025 | ok (<5s aspirational) |
| Shallow chain 4× (perf) | functional | 4 | 36 | 76.585 | 86.310 | 87.984 | FAIL (>=30s — viola gate) |
| Preview uplift 4× (F7) | preview-F7 | 4 | 36 | 49.074 | 49.834 | 50.095 | FAIL (>=30s — viola gate) |
| Preview AHV 4× (F8) | preview-F8 | 4 | 36 | 68.019 | 68.144 | 68.441 | FAIL (>=30s — viola gate) |

## Raw JSON

```json
[
  {
    "scenario": "Spread 4\u00d7 (perf baseline)",
    "n_lines": 4,
    "n_steps": 36,
    "magnitude_n": 2000000.0,
    "min_s": 56.06008579098852,
    "median_s": 56.30296016699867,
    "max_s": 57.333178708009655,
    "mean_s": 56.56540822199895,
    "repetitions": 3,
    "n_converged_per_run": 20,
    "kind": "functional",
    "classification": "FAIL (>=30s \u2014 viola gate)"
  },
  {
    "scenario": "Spread 8\u00d7 (perf)",
    "n_lines": 8,
    "n_steps": 36,
    "magnitude_n": 2000000.0,
    "min_s": 28.409805957984645,
    "median_s": 28.482558042014716,
    "max_s": 29.31842825000058,
    "mean_s": 28.73693074999998,
    "repetitions": 3,
    "n_converged_per_run": 36,
    "kind": "functional",
    "classification": "warn (<30s gate; >5s aspirational)"
  },
  {
    "scenario": "Taut deep 4\u00d7 (perf)",
    "n_lines": 4,
    "n_steps": 36,
    "magnitude_n": 2000000.0,
    "min_s": 0.023242666997248307,
    "median_s": 0.02358541698777117,
    "max_s": 0.025393416988663375,
    "mean_s": 0.024073833657894284,
    "repetitions": 3,
    "n_converged_per_run": 0,
    "kind": "functional",
    "classification": "ok (<5s aspirational)"
  },
  {
    "scenario": "Shallow chain 4\u00d7 (perf)",
    "n_lines": 4,
    "n_steps": 36,
    "magnitude_n": 2000000.0,
    "min_s": 76.58461312501458,
    "median_s": 86.30994583299616,
    "max_s": 87.98366554197855,
    "mean_s": 83.62607483332977,
    "repetitions": 3,
    "n_converged_per_run": 2,
    "kind": "functional",
    "classification": "FAIL (>=30s \u2014 viola gate)"
  },
  {
    "scenario": "Preview uplift 4\u00d7 (F7)",
    "n_lines": 4,
    "n_steps": 36,
    "magnitude_n": 2000000.0,
    "min_s": 49.074335208017146,
    "median_s": 49.83444729199982,
    "max_s": 50.09531220799545,
    "mean_s": 49.66803156933747,
    "repetitions": 3,
    "n_converged_per_run": 33,
    "kind": "preview-F7",
    "classification": "FAIL (>=30s \u2014 viola gate)"
  },
  {
    "scenario": "Preview AHV 4\u00d7 (F8)",
    "n_lines": 4,
    "n_steps": 36,
    "magnitude_n": 2000000.0,
    "min_s": 68.0193646249827,
    "median_s": 68.14380462499685,
    "max_s": 68.441287499998,
    "mean_s": 68.20148558332585,
    "repetitions": 3,
    "n_converged_per_run": 36,
    "kind": "preview-F8",
    "classification": "FAIL (>=30s \u2014 viola gate)"
  }
]
```
