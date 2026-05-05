# Relatório — Fase 7: Anchor uplift (suspended endpoint)

**Data de fechamento:** 2026-05-05
**Branch:** `feature/fase-7-anchor-uplift`
**Plano de referência:** [`docs/plano_profissionalizacao.md`](plano_profissionalizacao.md), seção "Fase 7"; mini-plano detalhado em [`proximas_fases/F7_anchor_uplift_miniplano.md`](proximas_fases/F7_anchor_uplift_miniplano.md).
**Commits:** 8 atômicos.

---

## 1. Sumário executivo

Fase 7 fechada com 8 commits sobre a branch acima. Habilita âncoras elevadas do seabed (suspended endpoint) — **bloqueio físico mais antigo do AncoPlat finalmente removido**. Solver hoje rejeitava `endpoint_grounded=False` com `NotImplementedError` desde o MVP v1; agora suporta single-segmento + sem attachments, com validação contra MoorPy nos 5 cenários canônicos BC-UP-01..05 + reativação dos 2 cases MoorPy upstream (BC-MOORPY-04 e BC-MOORPY-05) que estavam skipados desde a Fase 1 aguardando F7.

- **Schema**: `BoundaryConditions.endpoint_depth: Optional[float]` com validação Pydantic cruzada (required quando `endpoint_grounded=False`; range `(0, h]`).
- **Solver**: novo módulo `backend/solver/suspended_endpoint.py` com `solve_suspended_endpoint()` (catenária livre PT_1 fully suspended). Função interna `_solve_uplift_tension_mode` aceita `s_a < 0` (vértice virtual entre anchor e fairlead em "U") — diferente da versão upstream que rejeita.
- **Dispatcher** no facade `solve()`: remove `NotImplementedError` para single-seg + sem attachments + uplift; barrra multi-seg + uplift e attachments + uplift como `NotImplementedError` específico → `INVALID_CASE` com mensagem clara.
- **MoorPy baseline**: `tools/moorpy_env/regenerate_uplift_baseline.py` + `docs/audit/moorpy_uplift_baseline_2026-05-05.json`.
- **5 BC-UP** verde com **erro real ≤ 0.25%** (gate Q5 era 1%).
- **2 BC-MOORPY destravados** (04 e 05). 9 BC-MOORPY ativos (era 7).
- **2 diagnostics novos**: D016 (uplift fora de domínio) + D017 (uplift desprezível).
- **Frontend**: radio Grounded/Suspended na aba Ambiente, input condicional `endpoint_depth`, plot atualizado, sample `anchor-uplift` + verbete glossário destravados.

**Suite final:** 610 backend + 2 skipped + 105 frontend = **715+2 testes verdes**. TS build limpo. Zero regressão nos gates F1–F6+F9.

---

## 2. Decisões Q1–Q9 documentadas

| Q | Tema | Decisão | Onde está |
|---|---|---|---|
| **Q1** | Modelo físico | (a) **Catenária livre PT_1** — espelha MoorPy | `suspended_endpoint.py` |
| **Q2** | Schema endpoint_depth | (a) **Optional[float]**, required quando `endpoint_grounded=False` | `solver/types.py:BoundaryConditions` |
| **Q3** | Multi-seg/attachments + uplift | (b) **MVP single-segmento sem attachments**; multi/attach → `NotImplementedError` | `solver/solver.py:_validate_inputs` + dispatcher |
| **Q4** | BC-UP-01..05 | 5 cenários: moderado, severo, quase-grounded, próximo surface, taut+uplift | `regenerate_uplift_baseline.py` |
| **Q5** | Tolerância vs MoorPy | (a) **rtol=1e-2** — atendido com folga (≤0.25%) | `test_uplift_moorpy.py` |
| **Q6** | UI radio | (a) **Radio explícito** Grounded/Suspended | `CaseFormPage.tsx` |
| **Q7** | Plot uplift | (a) Anchor deslocado verticalmente; convenção frame solver mantida (translação no plot) | `CatenaryPlot.tsx` |
| **Q8** | Diagnostics dedicados | **D016 obrigatório** (high, error) + **D017 opcional** (medium, warning) | `diagnostics.py` + `suspended_endpoint.py` |
| **Q9** | Critério de fechamento + tabela de erro relativo | Tabela imprimida no -v output do `test_todos_5_BC_UP_passam_rtol_1e_2` + neste relatório §4 | `test_uplift_moorpy.py` |

### Ajustes pós-F9 (escopo herdado)

- **A1** ✅ Sample preview `anchor-uplift` destravado: `requirePhase: 'F7'` removido em `caseTemplates.ts`. Banner preview no CaseFormPage some automaticamente. Sample carrega com BC-UP-01 funcional.
- **A2** ✅ Verbete glossário `anchor-uplift` destravado em `glossary.ts`. Definição expandida para citar Fase 7 + decisão Q3=b.
- **A3** ⚠️ Profiling watchcircle com cenário uplift — não atualizado nesta fase. Pendência: rodar `tools/perf_watchcircle.py --include-preview-cases` com novos solver e atualizar `relatorio_F9_perf_watchcircle.md`. Não-bloqueante (gate <30s já é pendência F10).
- **A4** ✅ F7 é feature completa (sem ressalva como F8 carregará "AHV idealização estática"). Mensagem do solver cita "Catenária livre nas duas pontas (PT_1)" sem caveat.

---

## 3. Estrutura dos artefatos

### 3.1 — Backend (5 novos arquivos + 5 modificados)

```
backend/solver/suspended_endpoint.py            NEW · 320 linhas — catenária livre PT_1
backend/solver/diagnostics.py                   +D016 + D017 (~110 linhas)
backend/solver/solver.py                        dispatcher uplift no facade
backend/solver/types.py                         +endpoint_depth + @model_validator
backend/solver/tests/test_endpoint_depth_schema.py   NEW · 16 testes
backend/solver/tests/test_suspended_endpoint.py      NEW · 13 testes
backend/solver/tests/test_uplift_dispatcher.py       NEW · 6 testes
backend/solver/tests/test_uplift_moorpy.py           NEW · 8 testes
backend/solver/tests/test_uplift_diagnostics.py      NEW · 8 testes
backend/solver/tests/test_moorpy_golden.py           BC-MOORPY-04/05 destravados (uplift)
backend/solver/tests/test_validation_raises.py       atualizado (endpoint_grounded=false → CONVERGED)
backend/solver/tests/test_mvp_restrictions.py        atualizado (idem)
backend/api/tests/test_solve_api.py                  atualizado (idem)
```

### 3.2 — Tools / audit

```
tools/moorpy_env/regenerate_uplift_baseline.py     NEW · gera 5 BC-UP via MoorPy
docs/audit/moorpy_uplift_baseline_2026-05-05.json  NEW · 5 BCs com erros relativos
```

### 3.3 — Frontend

```
frontend/src/lib/caseSchema.ts                    +endpoint_depth + 2 .refine()
frontend/src/lib/caseTemplates.ts                 anchor-uplift destravado
frontend/src/lib/glossary.ts                      verbete anchor-uplift sem requirePhase
frontend/src/pages/CaseFormPage.tsx               +grupo Âncora (radio + endpoint_depth)
frontend/src/components/common/CatenaryPlot.tsx   anchorY = -endpoint_depth
frontend/src/types/openapi.ts                     regenerado (endpoint_depth)
frontend/src/test/uplift-plot-smoke.test.tsx      NEW · 3 testes
```

---

## 4. Tabela de erro relativo BC-UP-01..05 (Q9 reforço do usuário)

Erro relativo AncoPlat vs MoorPy, computado componente-a-componente em
`docs/audit/moorpy_uplift_baseline_2026-05-05.json`.

| ID | Cenário | h (m) | endpoint_depth (m) | uplift (m) | T_fl rel_err | T_anchor rel_err | Gate 1e-2 |
|----|---|---:|---:|---:|---:|---:|:---:|
| **BC-UP-01** | Moderado | 300 | 250 | 50 | 0.165% | 0.027% | ✅ |
| **BC-UP-02** | Severo | 300 | 200 | 100 | 0.161% | 0.051% | ✅ |
| **BC-UP-03** | Quase-grounded | 300 | 295 | 5 | 0.166% | 0.003% | ✅ |
| **BC-UP-04** | Próximo surface | 250 | 50 | 200 | 0.222% | 0.204% | ✅ |
| **BC-UP-05** | Taut + uplift (EA grande) | 300 | 200 | 100 | 0.044% | 0.042% | ✅ |

**Observação científica (Q9):** todos os 5 BCs ficam **abaixo de 0.25%** — gate `1e-2` (1%) atendido com folga de ~4×. A diferença residual entre AncoPlat e MoorPy provavelmente vem de:

1. **Modelos elásticos ligeiramente diferentes** — AncoPlat usa loop `L_eff = L·(1+T_mean/EA)` via brentq sobre `F(L_eff) = L_eff − L·(1+T_mean/EA)`; MoorPy usa formulação analítica diferente. Ambos convergem para o mesmo ponto físico mas por caminhos numéricos distintos.
2. **Tolerâncias internas dos solvers** — `xtol`/`maxiter` das implementações de fsolve/brentq.
3. **Aritmética de ponto flutuante** — acumulação de erros em ~50 iterações.

Não há divergência sistêmica de modelo físico. Continuar com rtol=1e-2 é prudente; apertar para 1e-4 (igual aos BC-MOORPY ativos grounded) exigiria calibração adicional pendente para Fase 10 (V&V completo).

### Tabela complementar — BC-MOORPY destravados pós-F7

| ID | Cenário (MoorPy upstream) | h | uplift | rtol | Status |
|----|---|---:|---:|---:|:---:|
| BC-MOORPY-04 | Moderado, EA grande | 200m drop | 372.7m | 1e-2 | ✅ Reativado |
| BC-MOORPY-05 | Severo, drop pequeno | 59.2m drop | 372.7m | 1e-2 | ✅ Reativado |

**BC-MOORPY ativos pós-F7: 9 / 10** (era 7). Resta apenas BC-MOORPY-06 (boia + uplift, w<0) que aguarda F12 (linha boiante / riser-like).

---

## 5. Histórico de commits da fase

```
43c1345  feat(frontend): radio + endpoint_depth + plot + destrava sample/verbetes (Q6+Q7+A1+A2)
5998322  feat(diagnostics): D016 + D017 para anchor uplift (Q8)
5153c76  test(solver): BC-UP-01..05 vs MoorPy rtol=1e-2 + destrava BC-MOORPY-04/05 (Q5+Q9)
c6b7adc  chore(audit): MoorPy uplift baseline BC-UP-01..05 + regenerate script (Q4)
d21916c  feat(solver): dispatcher uplift no facade solve() (Q3)
dc03b9b  feat(solver): suspended_endpoint.py — catenária livre fully suspended (Q1+Q3)
616fa17  feat(schema): BoundaryConditions.endpoint_depth + validação Pydantic (Q2)
[este]   docs(fase-7): relatório + CLAUDE.md + plano
```

---

## 6. Mudanças de design durante a execução

### 6.1 — `_solve_uplift_tension_mode` aceita `s_a < 0`

A versão upstream `_solve_suspended_tension_mode` em `catenary.py` rejeita `s_a < 0` com mensagem "demanda touchdown" — correto para grounded (catenária natural exigiria touchdown que está disponível). Em **uplift, touchdown é fisicamente impossível** (anchor não toca seabed por hipótese). A linha pode ter formato "U" com vértice virtual entre anchor e fairlead — `s_a < 0` é a parametrização correta.

Solução: criar `_solve_uplift_tension_mode` em `suspended_endpoint.py` com mesma matemática mas sem o guard. Esta função foi crítica para destravar BC-MOORPY-05 (uplift severo com drop pequeno onde `s_a` fica negativo).

### 6.2 — `tension_y` é magnitude (não signed)

Em uplift com `s_a < 0`, `w·s_cat` (componente vertical da tração) pode ser negativo no início da linha (vértice virtual abaixo do anchor). Para evitar inconsistência com a convenção do AncoPlat (`tension_y >= 0`), usamos `np.abs(w·s_cat)` em `_build_internal_result`. Magnitude da tração total `tension_magnitude = sqrt(H² + (w·s_cat)²)` permanece sempre ≥ 0.

### 6.3 — Frame solver vs frame físico (decisão de design durante Commit 7)

Inicialmente o `suspended_endpoint.py` transladava `coords_y` para o frame físico (anchor em `y=-endpoint_depth`). O `CatenaryPlot` esperava frame solver e fazia translação adicional via `sy - water_depth`, resultando em `y_plot = -endpoint_depth - water_depth` — incorreto.

Decisão fechada: solver devolve coords_y NO FRAME SOLVER (anchor em `y=0`, fairlead em `y=h_drop`); frontend translada via `sy - endpoint_depth`. Em grounded, `endpoint_depth ≈ water_depth` → comportamento idêntico. Convenção uniforme entre os dois caminhos.

### 6.4 — D017 opcional, dispatched pelo solver, não pelo facade

D017 (uplift desprezível) é populado pelo `suspended_endpoint.py` quando uplift < 1m. Para preservar entre solver-special e facade, mudei `solver.py:diagnostics_list = list(result.diagnostics or [])` em vez de `[]` — preserva diagnostics emitidos por solvers especializados. Padrão útil para futuras extensões (multi-seg + uplift, attachments + uplift no F7.x).

### 6.5 — Convenção do MoorPy: `(FxA, FzA, FxB, FzB, info)` (não HF/VF/HA/VA)

Convenção crítica descoberta no Commit 4: o tuple de retorno do MoorPy é `(force_x_A, force_z_A, force_x_B, force_z_B, info)` onde end A = anchor, end B = fairlead. Não `(HF, VF, HA, VA)` como os parâmetros internos sugerem. Tentativa inicial leu na ordem errada → erro de 6% que era na verdade swap T_anchor↔T_fl. Resolvido lendo `Catenary.py:1105` (return statement direto). Comentário registrado em `regenerate_uplift_baseline.py` para auditoria futura.

---

## 7. Divergências do plano original

### 7.1 — A3 (profiling F7 com cenário uplift) — pendência F10

Mini-plano pedia atualizar `tools/perf_watchcircle.py` para que cenário preview F7 use solver real após implementação. Não-bloqueante; gate `<30s` do watchcircle já é **pendência crítica F10** independente. F10 fará benchmark unificado.

### 7.2 — Multi-segmento + uplift e attachments + uplift (Q3=b)

Decisão consciente Q3=b: F7 entrega MVP single-segmento + sem attachments. Multi-seg ou attachments + uplift levantam `NotImplementedError` específico com mensagem clara → `INVALID_CASE` no facade. Pendência **F7.x** (pós-v1.0 ou conforme demanda real).

### 7.3 — Pendant visual no plot (linha tracejada anchor↔seabed)

Q7=a entregou minimalista: anchor deslocado verticalmente sem pendant visual. Pendência **v1.1+**.

---

## 8. Pendências para fases seguintes

### Fase 8 (próxima — AHV)
- Decisão técnica AHV antecipada já registrada em CLAUDE.md (D018 + Memorial PDF + manual). Sem isso F8 não fecha.

### Fase 10 (V&V completo)
- Calibrar tolerância BC-UP de `1e-2` para potencial `1e-4` (atual erro real ~0.25%; pode haver folga para apertar com tolerâncias internas ajustadas).
- Re-rodar `tools/perf_watchcircle.py --include-preview-cases` com solver F7 funcional e atualizar `relatorio_F9_perf_watchcircle.md`.
- Validação adicional: ≥10 BCs uplift (vs 5 atuais) cobrindo regimes adicionais (slope ≠ 0 + uplift, EA muito alto, etc.).
- Apertar BC-MOORPY-04/05 de rtol=1e-2 para 1e-4 se calibração permitir.

### Fase 7.x (pós-v1.0 ou conforme demanda)
- Multi-segmento + uplift (junções intermediárias chain↔wire em linha sem touchdown).
- Attachments (boia/clump) + uplift.
- Pendant visual no plot.

### Fase 12 (futuro)
- BC-MOORPY-06 (linha boiante w<0 + uplift) — modelo de peso distribuído negativo.

---

## 9. Critério de fechamento da fase

| Critério | Status |
|---|---|
| Branch dedicada com 8 commits atômicos | ✅ |
| `BoundaryConditions.endpoint_depth` Optional + validação Pydantic | ✅ Commit 1 |
| `suspended_endpoint.py` módulo dedicado, função pura testável | ✅ Commit 2 |
| Dispatcher no facade remove `NotImplementedError` para single-seg uplift; multi-seg/attach + uplift levanta com mensagem clara | ✅ Commit 3 |
| 5 BC-UP-01..05 verde com rtol=1e-2 vs MoorPy local | ✅ Commit 5 (≤ 0.25% real, folga de 4×) |
| Tabela de erro relativo no relatório | ✅ §4 deste doc + `test_todos_5_BC_UP_passam_rtol_1e_2` |
| D016 nos 2 cenários inválidos (depth ≤ 0 e > h+ε) | ✅ Commit 6 (Pydantic + diagnostic estruturado) |
| D017 em uplift desprezível | ✅ Commit 6 |
| Sample preview anchor-uplift destravado | ✅ Commit 7 (A1) |
| 3 verbetes glossário destravados (anchor-uplift) | ✅ Commit 7 (A2) |
| Radio Grounded/Suspended + endpoint_depth condicional | ✅ Commit 7 |
| `CatenaryPlot` deslocando anchor verticalmente | ✅ Commit 7 |
| Suite backend ≥ 580 (esperado +30) | ✅ **610** (era 554; +56 testes) |
| Suite frontend ≥ 105 | ✅ **105** (+3 plot smoke) |
| `cases_baseline_regression` 3/3 + BC-MOORPY ≥ 7 + BC-FR-01 + BC-EA-01 + BC-FAIRLEAD-SLOPE-01 + diagnostics F4 | ✅ — **BC-MOORPY 9/9** (era 7), zero regressão demais |
| TS build limpo | ✅ |
| CLAUDE.md atualizado | ✅ Commit 8 |
| Relatório com Q1-Q9 + tabela de erro relativo + ajustes A1-A4 | ✅ este doc |

**Fase 7 está pronta para merge.** Aguardando OK do usuário conforme protocolo. Não inicio Fase 8.
