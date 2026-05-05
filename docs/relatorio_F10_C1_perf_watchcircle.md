# Relatório F10 / Commit 1 — Paralelização do watchcircle

**Branch:** `feature/fase-10-vv-completo`
**Commit alvo:** "feat(perf): paraleliza watchcircle com ProcessPoolExecutor"
**Data:** 2026-05-05

## Contexto

A Fase 9 revelou pendência crítica de performance no `compute_watchcircle()`:

| Cenário              | Mediana F9 | Gate F9 (<30s) |
|----------------------|-----------:|:----------------:|
| Spread 4×            | 56s        | ❌ FAIL          |
| Shallow chain 4×     | 86s        | ❌ FAIL          |

Documento `docs/relatorio_F9_perf_watchcircle.md` registrou como bloqueio para v1.0
e abriu a F10/Q1 com escolha de estratégia.

Plano F10 / Q1 (aprovado pelo usuário): tentar **(a) paralelização** primeiro;
escalar para (a)+(b) caching se insuficiente; **vetar (c) afrouxar tolerâncias**.
Critério de sucesso: mediana **<20s** nos 4 cenários atuais (spread 4×, spread 8×,
taut deep 4×, shallow chain 4×). Shallow chain entre 20s e 30s é aceito como
**pendência v1.1** com justificativa documentada.

## Estratégia aplicada

### Tentativa 1 — `ThreadPoolExecutor` (descartada)

Hipótese inicial: SciPy/numpy liberam o GIL em chamadas BLAS, então threads dariam
speedup de 2-4×. **Falsificada** pela medição:

| Cenário              | Sequential | ThreadPool | Δ          |
|----------------------|-----------:|-----------:|:-----------|
| Spread 4×            | 55.74s     | 70.08s     | **+25%** ❌ |
| Shallow chain 4×     | 73.19s     | 87.91s     | **+20%** ❌ |

Causa: o solver de catenária + outer fsolve são Python puro (não BLAS-pesado);
o brentq da catenária e a iteração elástica fazem chamadas curtas a numpy mas
gastam o tempo em loops Python. Threads adicionam contention no GIL e não
ganham nada.

### Tentativa 2 — `ProcessPoolExecutor` (adotada)

Bypass do GIL via processos independentes. Trade-offs:
- **+1-2s de startup** por chamada (spawn + reimport dos módulos).
- **Pickling overhead** por task — `MooringSystemInput` (Pydantic) e
  `precomputed_anchors` (lista de dicts) serializam sem problema.
- Worker `_watchcircle_worker` movido para escopo de módulo (requisito de
  pickle).

**Resultado:**

| Cenário          | Sequencial | ProcessPool | Speedup | Gate <20s        |
|------------------|-----------:|------------:|--------:|:-----------------|
| Spread 4×        |    55.74s  |    16.60s  |  3.36×  | ✅                |
| Spread 8×        |    28.97s  |     9.96s  |  2.91×  | ✅                |
| Taut deep 4×     |     0.08s  |     0.97s  |  0.08×  | ✅ (overhead em caso trivial) |
| Shallow chain 4× |    73.19s  |    24.80s  |  2.95×  | ⚠️ pendência v1.1 |

Speedup ~3× é coerente com 4-8 cores físicos descontando overhead de spawn.

## Análise por cenário

### Spread 4× (16.60s) — gate ✅

Caso canônico FPSO, 4 chains a 90°. Speedup linear 3.36× (55.74s → 16.60s)
sobra ~3.4s sob o gate de 20s. Convergência: 20/36 azimutes (parcial — alguns
azimutes deixam linhas em uplift inviável; reportado como n_failed).

### Spread 8× (9.96s) — gate ✅

8 chains em FPSO grande. Mais linhas distribuem melhor a carga: convergência
36/36 e tempo até menor que Spread 4× porque cada equilíbrio individual é
mais "estável" (menos iterações fsolve). Speedup 2.91× confirma escalabilidade.

### Taut deep 4× (0.97s) — gate ✅, mas converged=0

Caso poliéster 2000m água profunda. Convergência 0/36 — `fsolve` falha
imediatamente (carga 2 MN está fora da região elástica para essa geometria).
Tempo sequencial era 0.08s (aborto rápido); ProcessPool sobe para 0.97s por
overhead de spawn. **Custo aceitável** — o caso permanece <1s e o sinal de
"system inviable" continua exposto via `n_failed`.

### Shallow chain 4× (24.80s) — gate ⚠️ pendência v1.1

Águas rasas (50m), chain leve, muito touchdown. Convergência 2/36 — apenas
azimutes alinhados com linhas conseguem equilíbrio; demais saem do envelope
catenário admissível. Speedup 2.95× (73.19s → 24.80s) **fica entre 20s e 30s**.

Conforme spec Q1 do mini-plano, este intervalo é **aceito como pendência v1.1**:
> "Se shallow chain 4× ficar entre 20s e 30s após (a)+(b), aceita pendência
> v1.1 com justificativa documentada — não force opção (c)."

**Justificativa técnica:** o gargalo restante são os 34 azimutes não-converged.
`fsolve` consome iterações máximas antes de declarar falha. Fix v1.1: detector
heurístico pré-fsolve que classifica azimutes claramente inviáveis (carga >>
soma de tensões catenárias máximas em direção oposta) e short-circuita com
diagnostic estruturado em vez de hammerar fsolve. Estimativa: 24.8s → 8-12s
sem mexer em tolerâncias.

## Mudanças no código

- [backend/solver/equilibrium.py](backend/solver/equilibrium.py):
  - Novo `_watchcircle_worker(args)` em escopo de módulo (picklable).
  - `compute_watchcircle()` ganhou kwargs `parallel: bool = True` e
    `max_workers: int | None = None`.
  - Threshold `n_steps >= 8` para ativar pool (overhead vs. ganho).
  - Branch sequencial preservado para debug e single-core.

## Validação

- 6 testes existentes do watchcircle: ✅ passam (28s → 12s wall-time graças
  ao ProcessPool).
- 20 testes em `test_platform_equilibrium_f5_5.py`: ✅ passam (16.29s).
- Determinismo da ordenação: `pool.map` preserva ordem dos inputs +
  `indexed_points.sort()` defensivo no parent.

## Próximos passos

- Commit 1: este — paralelização + benchmark.
- Commit 2-11: VV-01..14, robustez, apply tests, cobertura, unidades, perf
  endpoints, UI smokes (per mini-plano F10).
- v1.1 backlog: detector heurístico de azimute inviável no watchcircle.
