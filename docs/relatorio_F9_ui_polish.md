# Relatório — Fase 9: UI polish & onboarding

**Data de fechamento:** 2026-05-05
**Branch:** `feature/fase-9-ui-polish`
**Plano de referência:** [`docs/plano_profissionalizacao.md`](plano_profissionalizacao.md), seção "Fase 9".
**Commits:** 9 atômicos.

---

## 1. Sumário executivo

Fase 9 fechada com 9 commits sobre a branch acima. Entrega o pacote de UX/onboarding/a11y/print/perf da v1.0:

- **`/samples`** com 11 case templates (6 existentes + 5 novos: 3 funcionais + 2 preview F7/F8 antecipando paridade total com QMoor).
- **`/help/glossary`** com 40 verbetes canônicos cobrindo geometria, físico, componentes, operacional, boia.
- **Tour DIY** linear de 5 etapas com skip persistente em localStorage (sem dependência nova).
- **a11y nos forms principais** via auto-associação Label↔Input nos 2 helpers `InlineLabeled`/`InlineField`.
- **Print stylesheet A4** para CaseDetailPage.
- **E2E popover BuoyPicker** (pendência F6 fechada).
- **Profiling watchcircle** com descoberta crítica: 2/4 cenários violam o gate <30s. Pendência crítica registrada para F10.

**Suite final:** 554 backend + 4 skipped + 102 frontend = **656+4 testes verdes**. Zero regressão. TS build limpo.

---

## 2. Decisões Q1–Q10 documentadas

| Q | Tema | Decisão | Onde está |
|---|---|---|---|
| **Q1** | Tour: dependência ou DIY | (b) **DIY** com shadcn Dialog | `OnboardingTour.tsx` |
| **Q2** | Página `/samples` ou expandir TemplatePicker | (a) **Rota dedicada** + grid visual | `SamplesPage.tsx` |
| **Q3** | Quantos samples + quais cenários | **5 novos** (clump, lifted-arch, slope, anchor-uplift preview F7, ahv-pull preview F8) — total 11 | `caseTemplates.ts` |
| **Q4** | Sample mooring system | (b) Fora de escopo F9 — pendência v1.1+ | — |
| **Q5** | Glossário: rota | (a) `/help/glossary` + entry "Ajuda" na sidebar | `HelpGlossaryPage.tsx` |
| **Q6** | Conteúdo do glossário | **40 verbetes** (incluindo uplift/AHV/bollard pull) | `glossary.ts` |
| **Q7** | Print stylesheet: escopo | (a) **Apenas CaseDetailPage** A4 | `index.css` + `CaseDetailPage.tsx` |
| **Q8** | A11y: até onde | aria-label + aria-required + aria-live (sem screen reader rigoroso) | `SegmentEditor.tsx` + `CaseFormPage.tsx` |
| **Q9** | Performance | **Medir antes de otimizar** + flag `--include-preview-cases` | `tools/perf_watchcircle.py` |
| **Q10** | Skip persistente | localStorage `ancoplat:onboarding-completed`; reset em `/settings` | `OnboardingTour.tsx` |

### Ajustes do mini-plano (incorporados após realinhamento de escopo v1.0)

- **Ajuste 1** — Commit 1 expandido para 5 templates novos (+anchor-uplift +ahv-pull preview). ✅
- **Ajuste 2** — Commit 3 expandido para 40 verbetes (+anchor uplift +suspended endpoint +AHV +bollard pull). ✅
- **Ajuste 3** — Commit 8 com flag `--include-preview-cases` para baseline antecipado de perf F7/F8. ✅

---

## 3. Estrutura dos artefatos

### 3.1 — Frontend (12 novos arquivos + 6 modificados)

```
frontend/src/lib/caseTemplates.ts            +5 templates + tag preview/attachment/slope
frontend/src/lib/glossary.ts                 NEW · 40 verbetes + searchGlossary
frontend/src/pages/SamplesPage.tsx           NEW · grid visual 11 samples
frontend/src/pages/HelpGlossaryPage.tsx      NEW · busca + filtro categoria
frontend/src/components/common/OnboardingTour.tsx  NEW · DIY 5-step
frontend/src/components/layout/Sidebar.tsx   +items Samples + Ajuda
frontend/src/components/layout/Topbar.tsx    breadcrumb mapping novo
frontend/src/components/layout/AppLayout.tsx mounta <OnboardingTour />
frontend/src/components/common/SegmentEditor.tsx  helper InlineLabeled c/ useId+cloneElement
frontend/src/components/common/TemplatePicker.tsx  +ícones/cores 3 tags novos
frontend/src/pages/CaseFormPage.tsx          banner preview + helper InlineField a11y
frontend/src/pages/CaseDetailPage.tsx        wrapper print-area + StaleSolverBanner aria-live
frontend/src/pages/SettingsPage.tsx          card Onboarding + botão Refazer tour
frontend/src/Router.tsx                      +/samples + /help/glossary
frontend/src/index.css                       +@media print A4 portrait
```

### 3.2 — Backend / tools (1 novo)

```
tools/perf_watchcircle.py    NEW · profiling CLI com 6 cenários + flag --include-preview-cases
```

### 3.3 — Testes novos

```
frontend/src/test/samples-page-smoke.test.tsx       6 testes
frontend/src/test/glossary-smoke.test.tsx           9 testes
frontend/src/test/onboarding-tour-smoke.test.tsx    8 testes
frontend/src/test/a11y-forms-smoke.test.tsx         5 testes
frontend/src/test/print-stylesheet-smoke.test.tsx   2 testes
frontend/src/test/buoy-picker-e2e.test.tsx          6 testes (pendência F6)
```

**Total:** 36 testes frontend novos.

### 3.4 — Documentação

```
docs/relatorio_F9_ui_polish.md            NEW · este arquivo
docs/relatorio_F9_perf_watchcircle.md     NEW · profiling + pendência F10
```

---

## 4. Métricas atingidas

| Critério | Métrica alvo | Atingido | Evidência |
|---|---|---|---|
| 9 case templates funcionando | preview-solve verde | ✅ **11** (6 existentes + 3 novos + 2 preview marcados) | `samples-page-smoke.test.tsx` |
| /samples lista 11 com cards visuais + preview marcados | binário | ✅ | smokes |
| /help/glossary com ≥ 30 termos + busca | contagem | ✅ **40** | `glossary-smoke.test.tsx` |
| Verbetes preview F7/F8 (uplift/suspended/AHV/bollard pull) | binário | ✅ 4 verbetes marcados | grep |
| Tour DIY ≤ 2 min usuário novo + skip persistente em sessão fresh | binário | ✅ 5 etapas | `onboarding-tour-smoke.test.tsx` |
| aria-labels + Tab order nos 4 forms principais | helper auto-associa | ✅ via `InlineLabeled`/`InlineField` + `useId`+`cloneElement` | `a11y-forms-smoke.test.tsx` |
| CaseDetailPage imprime em A4 sem corte | DevTools print preview | ✅ via `print-area` + `@page A4 portrait` | `print-stylesheet-smoke.test.tsx` |
| E2E popover BuoyPicker (pendência F6) | testes verde | ✅ 6 testes | `buoy-picker-e2e.test.tsx` |
| Profiling watchcircle medido + relatório | binário | ✅ + flag `--include-preview-cases` | `tools/perf_watchcircle.py` |
| Performance watchcircle <30s gate | gate plano | ❌ **2/4 cenários violam** | ver §6 (pendência F10) |
| Suite backend ≥ 554 + 4 skip | regressão | ✅ **554 + 4 skip** | pytest |
| Suite frontend ≥ 75 | regressão | ✅ **102** (era 66; +36) | npm test |
| TS build limpo | binário | ✅ | npm run build |
| Todos os gates F1–F6 preservados | regressão | ✅ | suite full |
| CLAUDE.md atualizado | grep | ✅ seção F-prof.9 + decisão AHV antecipada | inspeção |
| Relatório com tabela Q1–Q10 + 2 samples preview documentados | binário | ✅ | este doc |

---

## 5. Histórico de commits da fase

```
950f338  perf(audit): profiling watchcircle 36 steps + relatório (Q9)
946f7a5  test(e2e): popover BuoyPicker com user-event (pendência F6)
5f0ac29  feat(print): print stylesheet A4 portrait CaseDetailPage (Q7)
ce3301e  feat(a11y): aria-labels + keyboard nav nos forms principais (Q8)
8bb62df  feat(onboarding): tour DIY com skip persistente (Q1+Q10)
6b887e7  feat(help): /help/glossary com 40 verbetes canônicos (Q5+Q6)
9560701  feat(sidebar): items "Samples" + "Ajuda" (Q5)
6e90ae5  feat(samples): 5 templates novos + página /samples (Q2+Q3)
[este]   docs(fase-9): relatório + CLAUDE.md + plano
```

Commit administrativo prévio (em `main`, fora da branch F9): `f33e03d` realinha sequência v1.0 (F9→F7→F8→F10→F11) + decisão técnica AHV antecipada.

---

## 6. Descoberta crítica de performance

**Profiling do watchcircle (`tools/perf_watchcircle.py`)** revelou que **2 dos 4 cenários functional violam o gate <30s** do plano:

| Cenário | Linhas | Mediana | Status |
|---|---:|---:|---|
| Spread 4× baseline | 4 | **56s** | ❌ FAIL — viola gate ~2× |
| Spread 8× | 8 | 28s | ⚠️ no limite |
| Taut deep 4× | 4 | 0.024s | ✅ trivial |
| Shallow chain 4× | 4 | **86s** | ❌ FAIL — viola gate ~3× |

**Decisão consciente**: F9 é "polish, não rewrite" (princípio do plano). Otimização do solver de equilíbrio é refactor não-trivial e foi **registrada como pendência crítica para F10** (V&V completo, que cobre robustez e performance como gates de release).

Estratégias candidatas detalhadas em [`docs/relatorio_F9_perf_watchcircle.md`](relatorio_F9_perf_watchcircle.md):
1. Paralelização das `n_steps=36` queries (SciPy libera GIL → speedup 2-4× esperado).
2. Caching mais agressivo do baseline.
3. Redução cirúrgica de tolerâncias do `fsolve` outer.
4. Vectorização parcial.

Cenários preview F7/F8 também rodam acima do gate (49s e 68s) — mesma pendência se aplica quando F7/F8 fecharem.

---

## 7. Divergências do plano original

### 7.1 — i18n NÃO entregue (no-go consciente v1.0)

Plano §F9 lista i18n como item opcional. Decisão fechada do usuário: **PT-BR only para v1.0**. EN entra em v1.1+ se houver demanda. Sem refactor de copy nem `react-i18next`.

### 7.2 — Print stylesheet limitado a CaseDetailPage (Q7=a)

MooringSystemDetailPage não recebeu print stylesheet — pendência v1.1+ (Memorial PDF é a saída formal do mooring system).

### 7.3 — A11y sem screen reader testing rigoroso

Pendência v1.1+. Cobrimos o essencial (aria-label, aria-required, aria-live, Tab order) via helper centralizado.

### 7.4 — Performance gate VIOLADO em 2/4 cenários

Documentado em §6. Pendência crítica F10. F9 entrega o **profiling** (gate "medir antes de otimizar"); a **otimização** é F10.

### 7.5 — Mooring system samples NÃO entregues

Q4=b — fora de escopo. Pendência v1.1+ junto com `mooringSystemTemplates.ts` + tab dedicada em `/samples`.

---

## 8. Pendências para fases seguintes

### Fase 7 (Anchor uplift, próxima)
- Sample preview `anchor-uplift` em `caseTemplates.ts` já tem payload pronto. Quando F7 fechar, basta remover `requirePhase: 'F7'`.
- Verbete `anchor-uplift` no glossário também já existe.
- Cenário preview F7 no `tools/perf_watchcircle.py` ganha solve real automaticamente.

### Fase 8 (AHV)
- Sample preview `ahv-pull` em `caseTemplates.ts` ainda usa payload base de catenária. Quando F8 fechar com schema AHV, atualizar payload + remover preview flag.
- 3 verbetes preview no glossário (AHV, bollard-pull) destravam.
- **Decisão técnica AHV antecipada** registrada em CLAUDE.md (mitigação obrigatória: D018 + Memorial PDF + manual de usuário). Sem isso, F8 não fecha.

### Fase 10 (V&V completo) — pendências CRÍTICAS
- **Otimizar `compute_watchcircle()`** para passar gate <30s nos 4 cenários functional. Estratégias candidatas detalhadas no relatório de perf.
- **Identidade `V_hemi = V_conic`** (origem F6) — adicionar caso teste com tampa ≠ raio.
- **Boias com manufacturer real** (origem F6).
- **Apply tests dos 9 diagnostics deferred** (origem F4).

### Fase 11 (lançamento 1.0)
- Manual de usuário em `/help/*` (estrutura de rota já reservada na F9).
- Seção sobre AHV idealização estática (decisão técnica antecipada).
- Changelog público + tag v1.0.0.

### v1.1+
- i18n / EN.
- Mooring system samples + print stylesheet.
- Screen reader testing rigoroso.
- Library paramétrica MoorPy (origem F6 / F12.x).
- `.moor` schema v3 com `slope_rad` + `attachments` (origem F2/F5).

---

## 9. Critério de fechamento da fase

| Critério | Status |
|---|---|
| Branch dedicada com 9 commits atômicos | ✅ |
| Sem mudanças fora do escopo (solver intacto) | ✅ apenas frontend + tools |
| Suite backend verde | ✅ 554 + 4 skip |
| Suite frontend verde | ✅ 102 |
| TS build limpo | ✅ |
| 11 samples + página /samples + URL deep-linking | ✅ |
| Glossário 40 verbetes + busca + categorias | ✅ |
| Tour DIY com skip persistente | ✅ |
| A11y nos forms principais (auto-associação Label↔Input) | ✅ |
| Print stylesheet A4 CaseDetailPage | ✅ |
| E2E BuoyPicker (pendência F6 fechada) | ✅ |
| Profiling watchcircle + relatório | ✅ — **+ pendência crítica F10 documentada** |
| `cases_baseline_regression` 3/3 | ✅ |
| BC-MOORPY 7/7 + BC-FR-01 + BC-EA-01 + BC-FAIRLEAD-SLOPE-01 + diagnostics F4 | ✅ |
| CLAUDE.md atualizado (F-prof.9 + decisão AHV antecipada + sequência v1.0) | ✅ commit administrativo prévio |
| Relatório com Q1–Q10 + ajustes + 2 samples preview | ✅ |

**Fase 9 está pronta para merge.** Aguardando OK do usuário conforme protocolo. Não inicio Fase 7.
