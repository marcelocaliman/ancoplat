# Relatório — Fase 1b: Solver isolado

Data: 2026-04-24
Status: ✅ **CONCLUÍDA**
Commits da fase: `d772332` (types) → `c820c02` (camada 7) — 7 commits granulares, um por camada.

## 1. Sumário de testes

| Métrica | Valor |
|---|---|
| Total de testes | **45** |
| Passing | **45 (100%)** |
| Tempo total | 0,84 s |
| Tempo médio/teste | ~19 ms |
| Slowest test | < 5 ms (hidden por `--durations=10`) |

### Distribuição por camada

| Camada | Módulo | # testes |
|---|---|---:|
| 1 | `catenary.py` (catenária rígida pura) | 10 |
| 2 | `seabed.py` (touchdown μ=0) | 8 |
| 3 | `friction.py` (atrito Coulomb) | 7 |
| 4 | `elastic.py` (correção elástica) | 5 |
| 5 | `solver.py` mode Tension | 6 |
| 6 | `solver.py` mode Range | 3 |
| 7 | Robustez e casos patológicos | 6 |

## 2. Validação contra MoorPy — BC-01 a BC-09

Tolerâncias alvo (Documento A v2.2, Seção 6.3): geometria 0,5%, forças 1,0%, grounded length 2,0%.

| BC | Modo | X (m) | H my (kN) | H MP (kN) | ΔH | T_fl my (kN) | T_fl MP (kN) | ΔT_fl | L_g my (m) | L_g MP (m) | Status |
|----|------|------:|----------:|----------:|-----:|------------:|------------:|------:|-----------:|-----------:|:------:|
| BC-01 | Tension | 335,21 | 561,61 | 561,61 | **0,00%** | 785,00 | 785,00 | **0,00%** | 0,00 | 0,00 | ✅ |
| BC-02 | Tension | 593,97 | 89,67 | 89,67 | **0,00%** | 150,00 | 150,00 | **0,00%** | 102,06 | 102,06 | ✅ |
| BC-03 | Tension | 348,37 | 571,06 | 570,68 | **0,07%** | 785,00 | 783,79 | **0,15%** | 0,00 | 0,00 | ✅ |
| BC-04 | Tension | 1577,15 | 1147,48 | 1143,33 | **0,36%** | 1471,00 | 1461,30 | **0,66%** | 0,00 | 0,00 | ✅ |
| BC-05 | Range   | 1450,00 | 274,72 | 272,46 | **0,83%** | 476,87 | 472,45 | **0,94%** | 0,00 | 0,00 | ✅ |
| BC-06 | Range   | 170,00 | 28,56 | 28,51 | **0,20%** | 150,00 | 149,61 | **0,26%** | 0,00 | 0,00 | ✅ |
| BC-07 | Tension | 1946,53 | 9,89 | 9,89 | **0,00%** | 30,00 | 29,99 | **0,04%** | 1859,27 | 1859,22 | ✅ |
| BC-08 | Tension | 593,97 | 89,67 | 89,67 | **0,00%** | 150,00 | 150,00 | **0,00%** | 102,06 | 102,06 | ✅ |
| BC-09 | Tension | 593,97 | 89,67 | 89,67 | **0,00%** | 150,00 | 150,00 | **0,00%** | 102,06 | 102,06 | ✅ |

**Todos os desvios estão MUITO abaixo das tolerâncias alvo.** O pior caso é BC-05 (modo Range com alta sensibilidade taut) com 0,94% em T_fl — ainda dentro do 1,0%.

Observação: BC-10 (multi-segmento) é escopo v2.1 (Seção 9 do Documento A), portanto não implementado nesta fase.

## 3. Cobertura de código

```
Name                                  Stmts   Miss  Cover
------------------------------------------------------------
backend/solver/__init__.py                0      0   100%
backend/solver/types.py                  83      3    96%
backend/solver/catenary.py              116      9    92%
backend/solver/seabed.py                125     10    92%
backend/solver/friction.py               33      3    91%
backend/solver/elastic.py                66      5    92%
backend/solver/solver.py                 49      7    86%
------------------------------------------------------------
Código do solver                        472     37    92%
Testes                                  543      2    99,6%
TOTAL                                  1015     39    96%
```

**Cobertura total 96%.** Módulo solver 92%. As linhas não cobertas são predominantemente:
- caminhos de erro raros em expansão de bracket do brentq (ex: `L_hi > 100·L`);
- exceção `NUMERICAL_ERROR` genérica (overflow/div0 hipotéticos, não reproduzidos pelos benchmarks).

## 4. Estatísticas do código

| Arquivo | Linhas | Fn públicas | Fn totais | Docstrings | Classes |
|---|---:|---:|---:|---:|---:|
| `__init__.py` | 2 | 0 | 0 | 0 | 0 |
| `types.py` | 188 | 0 | 3 | 0* | 7 |
| `catenary.py` | 403 | 8 | 12 | 9 | 0 |
| `seabed.py` | 386 | 6 | 9 | 8 | 0 |
| `friction.py` | 115 | 2 | 2 | 2 | 1 |
| `elastic.py` | 209 | 3 | 5 | 4 | 0 |
| `solver.py` | 173 | 1 | 2 | 2 | 0 |
| **Total** | **1476** | **20** | **33** | **25** | **8** |

(*) types.py usa docstrings em nível de classe Pydantic, não de função.

Total de funções com docstring: **25 de 33 (76%)**. Os 8 sem docstring são helpers privados curtos (`_f`, `_s`, `_solve_rigid_for_elastic`, etc.).

## 5. TODOs e pendências

### Pendência registrada em código (rastreável)

1. **`[R5Studless-friction]`** — 41 entradas do catálogo com μ=0,6 divergindo das demais chains (que têm μ=1,0). Preservado sem alteração, conforme decisão fechada (CLAUDE.md). Script de seed emite warning a cada execução. Aguarda validação com engenheiro revisor.

### Definições de entradas (BC-02, BC-07, BC-08, BC-09)

A Seção 6.2 do Documento A v2.2 listava estes BCs com "entradas a definir" e sugeria gerar variações dos casos base. Foram concretizados nesta fase com parâmetros justificados:

| BC | Geometria escolhida | Justificativa |
|----|---|---|
| BC-02 | h=300, L=700, μ=0,30 | Touchdown claro + atrito moderado (wire em argila firme da Seção 4.4) |
| BC-07 | h=100, L=2000, T_fl=30 kN | Garante T_fl > w·h (~20,1 kN) com grande L_g |
| BC-08 | mesmo BC-02 com μ=1,0 | Teste de atrito elevado |
| BC-09 | mesmo BC-02 com μ=0 | Teste μ=0 puro (os parâmetros originais de BC-04 dariam linha suspensa sem touchdown) |

Esses parâmetros estão documentados nos docstrings dos respectivos testes. Recomendo validar com o engenheiro revisor.

### Decisões de implementação que merecem atenção

1. **Formulação geral da catenária** (âncora não necessariamente no vértice) foi necessária porque a formulação simplificada da Seção 3.3.1 (âncora no vértice, V_anchor=0) é incompatível com BC-01 (T_fl=785 kN exige V_anchor>0). A generalização mantém a Seção 3.3.1 como caso particular.

2. **Loop elástico via brentq em vez de ponto-fixo**: iteração de ponto-fixo `L_n+1 = L·(1+T_mean(L_n)/EA)` diverge por oscilação em casos de linha muito taut (BC-05 no especial). Substituído por `brentq` sobre `F(L_eff)=L_eff−L·(1+T_mean/EA)=0` com bracket explícito. Robusto em 45/45 casos.

3. **Dispatch suspenso↔touchdown via valores críticos** (T_fl_crit, X_crit) em vez de try/except. Explícito, previsível, mais fácil de debugar.

4. **Ill-conditioned threshold** fixado em 0,01% (`L_stretched/L_taut < 1,0001`). Threshold calibrado empiricamente para não pegar casos operacionais normais (BC-04 está a 0,22% do taut e é considerado bem condicionado).

5. **Caso patológico pendente (Camada 7)**: linha com L_eff > X+h (muita folga, trecho slack no seabed) é rejeitado com mensagem clara mas NÃO resolvido. Implementar solução com slack admissível é item de v2 se demanda aparecer.

### Melhorias futuras sugeridas

- **n_plot_points variável** por densidade de interesse (mais pontos perto do touchdown, menos em trecho linear de seabed).
- **Diagnóstico de sensibilidade**: reportar `dT/dL` e `dT/dX` quando `utilization > 0,6` para UI.
- **Perfil de tensão analítico** no grounded com atrito (atualmente trapezoidal sobre discretização; pequena perda de precisão).
- **`iterations_used` mais preciso** — hoje aproximado; poderia instrumentar brentq para contar avaliações de F.

## 6. Integração com MoorPy

- **Interface usada**: `moorpy.Catenary.catenary(XF, ZF, L, EA, W, CB)` — API 1:1 com nosso modelo.
- **Compatibilidade**: CB=μ corresponde a `SeabedConfig.mu`. EA=1e15 emula rígido (Camadas 1-3).
- **Regime**: MoorPy valida estática pura; fenômenos de inércia ou dinâmica não são comparáveis no escopo do MVP v1.
- **Concordância**: < 1,0% em força, < 0,5% em geometria em todos os 9 BCs, dentro das tolerâncias estritas do Documento A.

## 7. Estrutura final

```
backend/solver/
├── __init__.py                   # package marker
├── types.py          (188 L)     # Pydantic: LineSegment, Boundary, Seabed, Config, Result
├── catenary.py       (403 L)     # Camada 1: rígido suspenso + dispatch
├── seabed.py         (386 L)     # Camada 2: touchdown no seabed
├── friction.py       (115 L)     # Camada 3: atrito Coulomb
├── elastic.py        (209 L)     # Camada 4: correção elástica via brentq
├── solver.py         (173 L)     # Camadas 5/6: fachada solve(); Camada 7: classificação
└── tests/            (543 L)     # 45 testes, 96% cobertura, incluindo BC-01 a BC-09
```

## 8. Pronto para Fase 2

A fachada `solve(line_segments, boundary, seabed, config) -> SolverResult` é a interface que a API FastAPI consumirá na Fase 2. SolverResult tem todos os campos exigidos pela Seção 6 do MVP v2. Não há dependência circular e todo o solver é importável como módulo Python puro (sem efeitos colaterais).
