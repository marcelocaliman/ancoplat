# Relatório — Fase 0: Diagnóstico & destravamento

**Data de fechamento:** 2026-05-04
**Branch:** `feature/fase-0-baseline-moorpy`
**Tag de baseline:** `v0.5-baseline` (empurrada para `origin`)
**Plano de referência:** [`docs/plano_profissionalizacao.md`](plano_profissionalizacao.md), seção "Fase 0".

---

## 1. Sumário executivo

Fase 0 fechada com 6 commits atômicos sobre a branch acima. Todos os critérios de aceitação **mensuráveis** atingidos exceto B0.1 (skipado por decisão explícita do usuário). Tag `v0.5-baseline` empurrada, dois snapshots imutáveis salvos em `docs/audit/`, ambiente isolado de validação MoorPy operacional em `tools/moorpy_env/`, e decisão fechada **QMoor vs GMoor** registrada em CLAUDE.md com base no modelo NREL (`α + β·T_mean`).

A fase entregou exatamente o que foi planejado: um **ponto de partida congelado e auditável** para as próximas fases mexerem em código com rede de segurança.

---

## 2. O que foi feito (item-a-item)

| Item | Status | Evidência |
|---|---|---|
| **B0.1** Reproduzir erros do usuário | ⏭️ Skipado | Decisão do usuário no protocolo de partida — se aparecerem na Fase 2 ou em V&V, tratamos lá. |
| **B0.2** Decisão QMoor/GMoor | ✅ | Seção "Modelo físico de QMoor vs GMoor" adicionada em [CLAUDE.md](../CLAUDE.md). Modelo NREL `EA_dinamico = α + β × T_mean` documentado com referência a `moorpy/line.py:1027-1044` e `MoorProps_default.yaml`. β explicitamente não-implementado em v1.0. |
| **B0.3** Baseline de testes + tag | ✅ | `pytest backend/`: **282/282 verde** (38.85s). `vitest run` no frontend: **8/8 verde** (3.32s). Total: **290 testes verdes**. Tag `v0.5-baseline` criada e empurrada para `origin`. |
| **B0.4** Snapshot de cases | ✅ | [`docs/audit/cases_baseline_2026-05-04.json`](audit/cases_baseline_2026-05-04.json) (~7.3 MB) — 3 cases + 12 execuções + 2 mooring systems + 8 system executions. Roundtrip estrutural validado: 3/3 inputs e 3/3 results deserializam limpos em `CaseInput` e `SolverResult`. |
| **B0.5** MoorPy isolado | ✅ | [`tools/moorpy_env/`](../tools/moorpy_env/) configurado: venv Python 3.12 dedicado + clone editável do MoorPy fixado por commit hash (`1fb29f8eca2618543b2df7056adfdfce0265737b`). Sanidade: 12/12 testes do `MoorPy/tests/test_catenary.py` passam local. `requirements-bench.txt` congelado (18 deps). |
| **B0.6** Baseline numérico MoorPy | ✅ | [`docs/audit/moorpy_baseline_2026-05-04.json`](audit/moorpy_baseline_2026-05-04.json) (~8 KB). 10 cases regenerados via importação direta de `indata`/`desired` por `importlib`. Reprodutibilidade: 2 runs consecutivas → cases idênticos. Validação cruzada: outputs do AncoPlat-side vs `desired_upstream` dentro de rtol=1e-5 em 100% dos cases. |

---

## 3. Métricas atingidas

| Critério de aceitação (do plano) | Métrica | Evidência |
|---|---|---|
| Tag `v0.5-baseline` existe e empurrada | binário | `git tag -l v0.5-baseline` → `v0.5-baseline`; `git ls-remote --tags origin` mostra a tag. |
| `cases_baseline_*.json` válido | ≥3 cases | 3 cases + 12 exec + 2 systems + 8 system exec, todos deserializam OK. |
| Suíte backend verde | 282/282 | `pytest backend/` final summary. |
| Suíte frontend verde | 8/8 | `vitest run` final summary. |
| MoorPy isolado funcional | `import moorpy` + 12/12 tests | Confirmado no commit 3. |
| Baseline MoorPy reprodutível | diff zero entre 2 runs | Verificado pré-commit 4. |
| Baseline MoorPy fiel ao upstream | 0 falhas @ rtol=1e-5 | 50/50 valores (10 cases × 5 outputs) batem com `desired`. |
| CLAUDE.md atualizado | seção EA reescrita com fonte | `grep "Modelo físico de QMoor"` → linha 61 do CLAUDE.md. |
| Relatório existe | binário | este arquivo. |

---

## 4. Divergências do plano original (Q1–Q5 do mini-plano)

| # | Plano original | Decisão tomada | Justificativa |
|---|---|---|---|
| **Q1** | venv Python **3.11** dedicado | venv Python **3.12** dedicado | Python 3.11 não está instalado localmente; instalar via brew era fricção sem ganho (MoorPy suporta 3.10+). Isolamento real vem do venv, não da versão. |
| **Q2** | `pip install moorpy` (PyPI) | `git clone` editável fixado por commit hash | Acesso aos `tests/test_catenary.py` necessário para B0.6 importar `indata`/`desired` direto. Pin por commit é mais granular que versão PyPI. |
| **Q3** | dump SQLite de produção | dump do SQLite **local** | Local tem os mesmos 3 cases + 12 execs + 2 mooring systems da produção (segundo `docs/relatorio_deploy_producao.md`). Sem necessidade de SCP/API. Roundtrip estrutural validou que os dados batem com os schemas atuais. |
| **Q4** | tag local-only (ambíguo) | tag **empurrada** para `origin` | Visibilidade no GitHub, referência durável para rollback. |
| **Q5** | `make moorpy-baseline` | `bash tools/moorpy_env/regenerate_baseline.sh` | Sem dependência nova (Makefile não existia). Plano será atualizado para refletir essa decisão. |

---

## 5. Imprevistos durante execução (transparência)

### 5.1 — Bug no `dump_cases_baseline.py` (resolvido)
Primeiro draft do script tinha um bug: usava o mesmo `sqlite3.Cursor` para iteração externa (`for row in cur.execute(...)`) e queries aninhadas internas (`cur.execute(...)` de novo dentro do loop). O cursor é clobrado pela query interna, fazendo a iteração externa parar prematuramente. Resultado: dump pegou 1/3 cases na primeira tentativa.

**Resolução:** materializar a query externa em `list` via `.fetchall()` antes de iterar. Confirmado: 3/3 cases + 2/2 systems no dump corrigido. Bug e fix referenciados nesta seção em vez de no commit (commit final já saiu correto).

### 5.2 — `cd` persistente entre comandos (resolvido)
Durante setup do `tools/moorpy_env/`, comandos com `cd` em sequência herdaram cwd da execução anterior (`cd frontend` para rodar npm test) e clonaram MoorPy em `frontend/tools/moorpy_env/` em vez de `tools/moorpy_env/`. Limpeza com `rm -rf frontend/tools` e refazer com **caminhos absolutos**. Lição operacional para próximas fases: usar caminhos absolutos em sequências `cd && ...`.

### 5.3 — Mensagem de commit imprecisa em `e216d9f` (transparência)
A mensagem de commit do baseline MoorPy afirmou que "ProfileType nos 10 casos: 1, 2, 3, 4 e 5 representados". A cobertura **real** é:
- ProfileType 1: 6 casos
- ProfileType 2: 2 casos
- ProfileType 3: 1 caso
- ProfileType -1: 1 caso (caso degenerado/fully-suspended sem touchdown)

Não foi feito `--amend` por respeito ao protocolo (não rebase histórico). Esta seção registra a correção. Implicação para a Fase 1: o gate `BC-MOORPY-01..10` cobre **bem** PT1 (touchdown clássico) mas **pouco** PT2/PT3, e nada de PT4/PT5/PT6. Quando entrar a ProfileType taxonomy na Fase 4, casos adicionais cobrindo os PTs faltantes podem precisar ser fabricados.

---

## 6. O que NÃO foi feito (escopo guardado)

- **B0.1** — reprodução de erros do usuário. Skipado por decisão.
- **Implementação de `BC-MOORPY-01..10` como tests dentro do AncoPlat** — Fase 1.
- **Migrador para schemas novos** — quando schemas mudarem (Fases 1, 2, 5), `cases_baseline.json` será o teste de regressão.
- **Mudança no `seed_catalog.py`** — só na Fase 1 (atrito per-segmento + EA toggle).

---

## 7. Pendências para fases seguintes

- **Fase 1**: Implementar `BC-MOORPY-01..10` como pytest cases dentro de `backend/solver/tests/golden/moorpy/`. Decisão de design: (a) replicar `catenary()` do MoorPy pra rodar AncoPlat com mesma assinatura (`x, z, L, EA, w, CB`), ou (b) traduzir cada input para `BoundaryConditions` + `LineSegment` + `SeabedConfig` do AncoPlat. Recomendar (b) — exercita o pipeline real do solver.
- **Fase 1**: Atualizar plano (seção AC da Fase 0) substituindo `make moorpy-baseline` por `bash tools/moorpy_env/regenerate_baseline.sh` (commit do plano vai junto da Fase 1 ou em commit isolado).
- **Fase 4**: Cobertura de ProfileType faltantes (4, 5, 6) — fabricar cases adicionais no MoorPy + AncoPlat.

---

## 8. Histórico de commits da fase

```
a7c73d8  docs(plano): plano de profissionalização v1 com integração MoorPy
0e4ddb9  chore(audit): snapshot dos cases para regressão (Fase 0 / B0.4)
[tag]    v0.5-baseline (empurrada para origin)
f8a491d  chore(tools): ambiente MoorPy isolado para validação numérica (Fase 0 / B0.5)
e216d9f  test(bench): baseline numérico MoorPy dos 10 catenary cases (Fase 0 / B0.6)
c91e300  docs(claude): decisão fechada QMoor/GMoor com base em MoorPy (Fase 0 / B0.2)
[este commit]  docs(fase-0): relatório de baseline e destravamento
```

---

## 9. Critério de fechamento da fase

Conforme protocolo do plano: **a fase só fecha quando 100% dos critérios de aceitação batem ou diferenças têm justificativa explícita**.

| Critério | Status |
|---|---|
| 9 critérios numéricos da seção 3 | ✅ todos batem |
| Branch dedicada com commits atômicos | ✅ 6 commits, cada um com mensagem descritiva e escopo único |
| Sem mudanças fora do escopo da fase | ✅ não tocou em `backend/solver/`, `frontend/src/`, schemas — só `docs/`, `tools/`, `CLAUDE.md` |
| Testes verdes na suíte completa | ✅ 290/290 |
| Documentação atualizada | ✅ CLAUDE.md (seção EA + estado atual), este relatório, `tools/moorpy_env/README.md` |

**Fase 0 está pronta para merge.** Aguardando OK do usuário conforme protocolo. Não inicio Fase 1 automaticamente.
