# Relatório — Fase 2: Redesign aba Ambiente + auditoria de validações

**Data de fechamento:** 2026-05-05
**Branch:** `feature/fase-2-ambiente-validacoes`
**Plano de referência:** [`docs/plano_profissionalizacao.md`](plano_profissionalizacao.md), seção "Fase 2".
**Commits:** 7 atômicos.

---

## 1. Sumário executivo

Fase 2 fechada com 7 commits sobre a branch acima. Resolvida a confusão "lâmina d'água sob âncora vs sob fairlead vs prof. fairlead" que motivou a Fase 2 (item 4 da conversa que originou o plano de profissionalização):

- **Aba Ambiente refatorada** com 3 grupos visuais (Geometria / Fairlead / Seabed). Geometria usa novo `BathymetryInputGroup` com 3 inputs primários (prof. seabed sob âncora, prof. seabed sob fairlead, distância horizontal) e slope read-only derivado.
- **`BathymetryPopover` deletado** sem refs órfãs.
- **`startpoint_offset_horz/vert` reservados** como cosméticos (A2.6).
- **Validação `startpoint_depth >= h` relaxada em seabed inclinado** (Q7) — passa a comparar contra `h_at_fairlead = h - tan(slope)·X_estimate`. Caso BC-FAIRLEAD-SLOPE-01 com 3 testes (descendente válido, edge que falharia pré-F2, ascendente excessivo).
- **Auditoria sistemática de 29 raises** em `solver.py` + `multi_segment.py` com classificação a/b/c documentada e justificativa física inline (Ajuste 1).
- **`test_validation_raises.py` com 25 testes** parametrizados cobrindo todos os 13 raises categoria (a) "user-facing" (Q5 = b).
- **Mensagens E4** reescritas: nome do campo + valor recebido + valor esperado + sugestão de causa.

**Suite final:** 365 backend + 32 frontend = **397 testes verdes** + 3 skipados documentados. Zero regressão em `cases_baseline.json` (3/3).

---

## 2. Decisões Q1–Q8 documentadas

| Q | Tema | Decisão | Onde está |
|---|---|---|---|
| **Q1** | Slope: frontend ou backend? | (a) **Frontend** deriva via `BathymetryInputGroup`. Schema backend permanece estável. | `frontend/src/components/common/BathymetryInputGroup.tsx` |
| **Q2** | Offset horizontal: cosmético ou físico? | (a) **Cosmético em v1.0**. Reservado no schema; tooltip explícito "afeta APENAS visualização — não entra no cálculo". | `backend/solver/types.py` (BoundaryConditions) |
| **Q3** | Modo avançado (slope direto)? | (c) **Sim, escondido em `<details>`**. Caso de uso real (inclinômetro/sonar). Default fechado. | `CaseFormPage.tsx` aba Ambiente, grupo Seabed |
| **Q4** | `BathymetryPopover` deletar? | (a) **Sim**. Grep confirmou 0 refs órfãs antes de deletar. | commit 4 |
| **Q5** | Auditoria 93 raises — escopo? | (b) **User-facing** (~25 testes). Comments em todos. Cobertura total = Fase 10. | `test_validation_raises.py` |
| **Q6** | Pre-solve P001/P004 ajustar? | (b) **Adiar para Fase 4**. | pendência |
| **Q7** | `startpoint_depth >= h` relaxar com slope? | (a) **Sim, refletir slope** via `_x_estimate` helper conservador. | `backend/solver/solver.py:_x_estimate` |
| **Q8** | Gate `cases_baseline` obrigatório? | **Sim, indefinidamente**. Princípio transversal #1. | `test_baseline_regression.py` |

### Ajustes do mini-plano

- **Ajuste 1** — Comments em raises devem incluir JUSTIFICATIVA FÍSICA (não só letra a/b/c). ✅ Implementado em todos os 29 raises auditados. Exemplos:
  ```python
  # (a) Fisicamente justificada: catenária requer peso suspenso > 0.
  # Σw·L + Σ F_clump - Σ F_buoy ≤ 0 significa empuxo total >= peso —
  # cabo flutuaria, geometria inverte.
  raise ValueError(...)
  ```

- **Ajuste 2** — Round-trip determinístico do `BathymetryInputGroup`. ✅ Implementado em `frontend/src/test/bathymetry-roundtrip.test.ts` com 7 cases parametrizados de geometrias plausíveis + 9 testes de identidades (clamp, fórmulas explícitas, convenções de sinal, fallback X=500m). Tolerância: rtol=1e-9.

---

## 3. Auditoria de raises — contagem a/b/c

Total auditado: **29 raises** em `solver.py` + `multi_segment.py`.

| Categoria | solver.py | multi_segment.py | Total | Cobertura |
|---|:---:|:---:|:---:|:---:|
| (a) Fisicamente justificada | 5 | 8 | **13** | 24 testes em test_validation_raises.py |
| (b) Defensiva (Pydantic já cobre) | 4 | 11 | **15** | testadas via Pydantic em outros testes |
| (c) Numérica (bracket/fsolve) | 0 | 1 | **1** | coberta indiretamente em test_camada7_robustez |

Distribuição:
- **45%** dos raises são (a) fisicamente justificadas — guards físicos do domínio.
- **52%** são (b) defensivas — duplicam invariantes que Pydantic já enforça via `@field_validator`/`@model_validator`. Mantidas como rede de segurança para uso direto do solver fora da rota API (testes, scripts).
- **3%** são (c) numéricas — limites do método (brentq não-bracketado, fsolve não-convergiu). Pendência: classificar como diagnostics estruturados na Fase 4.

A distribuição é saudável — não há concentração em (c) acidental/excessiva que indicaria problema sistêmico de over-validation.

---

## 4. Métricas atingidas

| Critério | Métrica alvo | Atingido | Evidência |
|---|---|---|---|
| Form aba Ambiente refatorado | 3 campos primários + slope read-only + offset cosmético + modo avançado | ✅ 3 grupos visuais (Geometria / Fairlead / Seabed) | `CaseFormPage.tsx:591-738` |
| `cases_baseline_2026-05-04.json` | rtol=1e-9 em 3/3 | ✅ | `test_baseline_regression.py` |
| BC-FAIRLEAD-SLOPE-01 | converged em descendente, rejeita ascendente excessivo | ✅ 3 testes verdes | `test_mvp_restrictions.py:117-189` |
| Cobertura de raises user-facing | ≥ 25 testes parametrizados | ✅ 25 testes (24 raise/no-raise + 1 sanity) | `test_validation_raises.py` |
| Comments em raises | 100% justificados (a/b/c + razão) | ✅ 29/29 | `solver.py` + `multi_segment.py` |
| Round-trip Bathymetry | rtol=1e-9 em 7 cases | ✅ 16 testes verdes | `bathymetry-roundtrip.test.ts` |
| Suite backend | ≥ 359 verde | ✅ **365 + 3 skipped** | full suite |
| Suite frontend | ≥ 17 + N novos | ✅ **32 verde** | npm test |
| TS build | sem erro | ✅ | npm run build |
| BC-MOORPY 7/7 ativos preservados | rtol≤1e-4 | ✅ | regression |
| BC-FR-01 + BC-EA-01 | preservados | ✅ | regression |
| `BathymetryPopover` deletado | 0 refs órfãs | ✅ | grep confirmado pré-merge |
| Mensagens E4 | nomeiam campo+recebido+esperado | ✅ 6 raises atualizadas | `solver.py:_validate_inputs` |

---

## 5. Histórico de commits da fase

```
be128f5  fix(messages): mensagens E4 nomeando campo, valor recebido, esperado
78d6bb9  test(validation): cobertura unitária dos raises user-facing (Q5)
85511c5  feat(form): aba Ambiente refatorada — batimetria 2-pontos + offset cosmético
0555197  feat(solver): startpoint_depth >= h relaxado em seabed inclinado (Q7)
453b061  feat(types): startpoint_offset_horz/vert reservados (cosmético)
a2c43bb  refactor(solver): docstrings + comments justificados em todos os raises (E4)
[este]   docs(fase-2): relatório + atualização CLAUDE.md
```

---

## 6. Divergências do plano original

### 6.1 — Round-trip clamp em geometrias impossíveis

`deriveBathymetryFromBoundary` clampa `depthFairlead` a 0 quando `h - tan(slope)·X` seria negativo (= seabed acima da superfície, fisicamente impossível). Esse clamp degrada round-trip exato para esses cenários.

**Decisão**: matriz de testes do round-trip evita o regime impossível. Comportamento de clamp documentado em teste explícito (`depthFairlead clamped a 0 quando seria negativo`). Se o usuário apresenta inputs inviáveis, o solver downstream rejeita com mensagem orientada (Q7 / Commit 3).

### 6.2 — `import useState` espurio

Durante o Commit 4, importei `useState` na página `CaseFormPage` sem usá-lo (já estava importado em outra linha). TS build pegou e removi. Lição: rodar `npm run build` antes de commitar mudanças no frontend.

### 6.3 — Pre-solve P001/P004 não tocados

Conforme Q6 = (b), P001 (cabo curto) e P004 (T_fl baixo) não foram revisados nesta fase. Pendência registrada para Fase 4.

---

## 7. Pendências para fases seguintes

- **Fase 4** (Diagnostics maturidade):
  - Revisar P001 (tolerância 5%) e P004 (falsos positivos com poliéster gmoor).
  - Classificar raise (c) numérico de `_solve_suspended_range` (fsolve não convergiu) como diagnostic estruturado.
  - Revisar raise de "bracket de H inválido" — virou comentário explicando que sintoma é caso touchdown não-tratado pelo path fully-suspended.

- **Fase 7** (Anchor uplift):
  - Quando `endpoint_grounded=False` for suportado, remover o NotImplementedError e ajustar test_raise_a5.

- **Fase 10** (V&V completo):
  - Cobertura 100% dos 93 raises totais (incluindo guards internos das outras 6 files do solver).
  - Cobertura agregada `backend/solver/` ≥ 96% (atualmente ~89%).

---

## 8. Critério de fechamento da fase

| Critério | Status |
|---|---|
| Branch dedicada com 7 commits atômicos | ✅ |
| Sem mudanças fora do escopo | ✅ não tocou attachment_resolver, equilibrium, multi_line, grounded_buoys (módulos não mencionados na Fase 2) |
| Suite backend verde | ✅ 365 + 3 skip |
| Suite frontend verde | ✅ 32 |
| TS build | ✅ |
| Form Ambiente refatorado | ✅ 3 grupos + BathymetryInputGroup + modo avançado |
| BathymetryPopover deletado sem órfãos | ✅ |
| Auditoria 29 raises com classificação a/b/c + justificativa física | ✅ Ajuste 1 |
| Round-trip Bathymetry rtol=1e-9 | ✅ Ajuste 2 |
| Q7 implementado (startpoint_depth + slope) | ✅ |
| BC-FAIRLEAD-SLOPE-01 verde | ✅ 3/3 |
| Mensagens E4 hardenizadas | ✅ |
| `cases_baseline_regression` verde | ✅ 3/3 |
| Pendências documentadas | ✅ §7 |

**Fase 2 está pronta para merge.** Aguardando OK do usuário conforme protocolo. Não inicio Fase 3.
