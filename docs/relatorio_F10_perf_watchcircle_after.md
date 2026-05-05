# Relatório F9 — Profiling watchcircle

Profiling do `compute_watchcircle()` em sistemas mooring representativos.

**Targets:**

- Gate (AC): mediana <30s.
- Aspiracional: mediana <5s (não-bloqueante).

**Resultados** (mediana de N execuções):

| Cenário | Tipo | Linhas | n_steps | min (s) | mediana (s) | max (s) | classificação |
|---|---|---:|---:|---:|---:|---:|---|
| Spread 4× (perf baseline) | functional | 4 | 36 | 15.307 | 16.602 | 17.430 | warn (<30s gate; >5s aspirational) |
| Spread 8× (perf) | functional | 8 | 36 | 9.756 | 9.963 | 10.712 | warn (<30s gate; >5s aspirational) |
| Taut deep 4× (perf) | functional | 4 | 36 | 0.947 | 0.966 | 1.020 | ok (<5s aspirational) |
| Shallow chain 4× (perf) | functional | 4 | 36 | 24.633 | 24.797 | 25.340 | warn (<30s gate; >5s aspirational) |

## Raw JSON

```json
[
  {
    "scenario": "Spread 4\u00d7 (perf baseline)",
    "n_lines": 4,
    "n_steps": 36,
    "magnitude_n": 2000000.0,
    "min_s": 15.307170249987394,
    "median_s": 16.60178925000946,
    "max_s": 17.430120125005487,
    "mean_s": 16.44635987500078,
    "repetitions": 3,
    "n_converged_per_run": 20,
    "kind": "functional",
    "classification": "warn (<30s gate; >5s aspirational)"
  },
  {
    "scenario": "Spread 8\u00d7 (perf)",
    "n_lines": 8,
    "n_steps": 36,
    "magnitude_n": 2000000.0,
    "min_s": 9.756003666989272,
    "median_s": 9.963458125013858,
    "max_s": 10.712423374992795,
    "mean_s": 10.143961722331975,
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
    "min_s": 0.9469844999839552,
    "median_s": 0.9659379169752356,
    "max_s": 1.0197286250186153,
    "mean_s": 0.9775503473259354,
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
    "min_s": 24.633029417018406,
    "median_s": 24.79727812501369,
    "max_s": 25.34027137499652,
    "mean_s": 24.923526305676205,
    "repetitions": 3,
    "n_converged_per_run": 2,
    "kind": "functional",
    "classification": "warn (<30s gate; >5s aspirational)"
  }
]
```
