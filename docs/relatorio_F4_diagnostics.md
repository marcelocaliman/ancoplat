# Relatório — Fase 4: Diagnostics maturidade + ProfileType taxonomy

**Data de fechamento:** 2026-05-05
**Branch:** `feature/fase-4-diagnostics-profiletype`
**Plano de referência:** [`docs/plano_profissionalizacao.md`](plano_profissionalizacao.md), seção "Fase 4".
**Commits:** 7 atômicos.

---

## 1. Sumário executivo

Fase 4 fechada com 7 commits sobre a branch acima. Entrega o amadurecimento dos diagnostics estruturados (vantagem do AncoPlat sobre QMoor) + adoção da **ProfileType taxonomy** do MoorPy/NREL como vocabulário canônico para classificação de regimes catenários.

Entregas:
- **ProfileType enum** com 10 valores (PT_0..PT_8 + PT_U) — vocabulário forward-compat espelhando `MoorPy/Catenary.py:147-163`.
- **Classificador puro** `classify_profile_type()` em módulo dedicado `backend/solver/profile_type.py`.
- **Validação cruzada com MoorPy**: 6/7 BC-MOORPY ativos com match perfeito, 1 divergência aceita (Categoria 3 — edge case numérico em BC-MOORPY-08).
- **`confidence` field** no `SolverDiagnostic` com critério explícito (high / medium / low).
- **Cobertura dos 15 diagnostics existentes** (D001–D011 + P001–P004) com structural + integration + apply tests.
- **4 diagnostics novos**: D012 (slope alto), D013 (μ=0 com catálogo), D014 (gmoor sem β), D015 (PT raro).
- **`SurfaceViolationsCard`** UI dedicada com lista detalhada das boias acima da água.

**Suite final:** 438 backend + 57 frontend = **495 testes verdes** + 3 skipados. Cobertura `diagnostics.py`: **100%** (target ≥ 95% ✅).

---

## 2. Decisões Q1–Q9 documentadas

| Q | Tema | Decisão | Onde está |
|---|---|---|---|
| **Q1** | ProfileType — todos ou só atingíveis? | (a) Todos 10 (vocabulário forward-compat) | `backend/solver/types.py` ProfileType enum |
| **Q2** | Localização do classifier | (a) Módulo novo `backend/solver/profile_type.py` | função pura |
| **Q3** | Implementar todos D012/D013/D014/D015? | (a) Todos os 4 | `backend/solver/diagnostics.py` |
| **Q4** | Refactor SolverDiagnosticsCard? | (a) Não — só smoke + functional | `diagnostics-card-smoke.test.tsx` |
| **Q5** | Test "apply" — escopo | (b) Best-effort com TODO | contagem em §5 |
| **Q6** | SurfaceViolationsCard | (a) Card dedicado | `SurfaceViolationsCard.tsx` |
| **Q7** | Campo `confidence` | (a) Adicionar com critério documentado | docstring `ConfidenceLevel` |
| **Q8** | AC "1 erro do usuário" | (a) Relaxar — B0.1 skipado permanentemente | pendência registrada |
| **Q9** | Cobertura diagnostics.py ≥ 95% | viável, atingiu **100%** | `pytest --cov` |

### Ajustes do mini-plano

- **Ajuste 1** — Tabela de divergências classifier vs MoorPy. ✅ Implementado em `test_profile_type_moorpy.py` `ACCEPTED_DIVERGENCES` dict + sanity test que enforça nomenclatura de Categoria 1/2/3 nos motivos.
- **Ajuste 2** — D013 limiar 0.3 documentado em comment com tabela empírica:
  - Polyester: 1.0
  - StuddedChain: 1.0
  - StudlessChain: 0.6 (R5) ou 1.0 (R4)
  - Wire: 0.6
  - Mínimo absoluto: 0.6 → limiar 0.3 captura todas com folga.

---

## 3. Tabela de divergências classifier vs MoorPy

Validação cruzada nos 7 BC-MOORPY ativos (sem uplift, sem buoyant):

| Case | AncoPlat PT | MoorPy PT | Match | Categoria |
|---|---|---|:---:|---|
| BC-MOORPY-01 (CB=5, μ saturado) | PT_3 | PT_3 | ✅ | — |
| BC-MOORPY-02 (CB=0 touchdown) | PT_2 | PT_2 | ✅ | — |
| BC-MOORPY-03 (CB=0.1 touchdown) | PT_2 | PT_2 | ✅ | — |
| BC-MOORPY-07 (near-taut suspended) | PT_1 | PT_1 | ✅ | — |
| **BC-MOORPY-08** (hardest taut, L=chord) | **PT_1** | **PT_-1** | ❌ | **Categoria 3** |
| BC-MOORPY-09 (near-taut suspended) | PT_1 | PT_1 | ✅ | — |
| BC-MOORPY-10 (hard starting point) | PT_1 | PT_1 | ✅ | — |

**Categoria 3 — BC-MOORPY-08 (edge case numérico):**

MoorPy ativa fallback `PT_-1` (aproximação para taut quando algoritmo normal falha). AncoPlat resolve via brentq+elastic com `status=ill_conditioned` (geometria ainda válida) e classifica `PT_1` (fully suspended). Ambas as escolhas são defensáveis — `PT_-1` do MoorPy não tem equivalente físico claro no vocabulário canônico (é uma flag de "approximation used").

Nenhuma divergência Categoria 1 (bug) ou 2 (modelo) detectada. Cobertura: PT_1 (4×), PT_2 (2×), PT_3 (1×). PT_4/5/6 não cobertos (deferido para casos específicos da Fase 7+).

---

## 4. Critério de `confidence` (Q7) — documentado

Registrado no docstring de `ConfidenceLevel` em `backend/solver/diagnostics.py`:

- **high** — violação determinística de premissa física ou matemática. Sem ambiguidade — o diagnóstico SEMPRE é correto quando dispara.
  - Exemplos: D012 (slope > 30°), D014 (gmoor sem β), todos os D001–D011 existentes.

- **medium** — heurística calibrada com base empírica. Pode ter falso positivo em casos extremos legítimos, mas captura >90% dos cenários problemáticos típicos.
  - Exemplos: P004 (T_fl baixo, regra de thumb), D008 (safety margin), **D013** (μ=0 com catálogo, limiar 0.3 calibrado).

- **low** — pattern detection sem base teórica forte. **RESERVADO** — ainda nenhum diagnóstico nesta categoria. Quando aparecer, exigirá justificativa explícita no docstring do builder.

Default `high` para retro-compat. D013 e P004 são os únicos `medium` no momento.

---

## 5. Cobertura dos 15 diagnostics — apply garantido vs best-effort (Q5)

| Diagnostic | Structural | Integration | Apply | Status apply |
|---|:---:|:---:|:---:|---|
| D001 buoy_near_anchor | ✅ | ❌ (path complexo) | ❌ | TODO Fase 10 |
| D002 buoy_near_fairlead | ✅ | ❌ | ❌ | TODO Fase 10 |
| D003 arch_overflows | ✅ | ❌ | ❌ | TODO Fase 10 |
| D004 buoy_above_surface | ✅ | ❌ (heurístico) | ❌ | TODO Fase 10 |
| **D005 buoyancy_exceeds_weight** | ✅ | ✅ repro+no-repro | ✅ | **garantido** |
| **D006 cable_too_short** | ✅ | ✅ repro | ✅ | **best-effort** |
| D007 tfl_below_critical | ✅ | ❌ (caminho específico) | ❌ | TODO Fase 10 |
| D008 safety_margin | ✅ | ✅ best-effort | ❌ | TODO Fase 10 |
| D009 anchor_uplift_high | ✅ | ❌ (precisa V_anchor alto) | ❌ | TODO Fase 10 |
| D010 high_utilization | ✅ | ✅ best-effort | ❌ | TODO Fase 10 |
| D011 cable_below_seabed | ✅ | ❌ (precisa clump) | ❌ | TODO Fase 10 |
| **P001 cable_too_short (front)** | ✅ | ✅ | ✅ | **garantido** |
| **P002 buoyancy (front)** | ✅ | ✅ | ✅ | **garantido** |
| P003 attachment_out_of_range | ✅ | ✅ | ❌ | best-effort (sem suggested) |
| P004 tfl_too_low (heurístico) | ✅ | ✅ | ❌ | best-effort (calibração) |

**Contagem (Q5 conforme refinamento):**
- Apply garantido: **3 de 15** (D005, P001, P002).
- Apply best-effort com TODO: **3 de 15** (D006, P003, P004).
- Sem apply test (structural-only): **9 de 15**. Deferido para Fase 10 V&V.

---

## 6. Diagnostics novos da Fase 4

### D012 — Slope alto (`> 30°`)
- Severity: warning, confidence: high
- Limiar 30° é fronteira determinística; rampas mais íngremes são raras em batimetria offshore real.
- Disparo testado com slope=-35° descendente (35° ascendente bate na validação Q7 da F2).

### D013 — μ global = 0 mas catálogo do segmento tem cf ≥ 0.3
- Severity: warning, confidence: medium
- **Limiar 0.3 com justificativa empírica** (Ajuste 2):
  - Catálogo do AncoPlat tem mínimos por categoria: Polyester 1.0, StuddedChain 1.0, StudlessChain 0.6 (R5) / 1.0 (R4), Wire 0.6.
  - Mínimo absoluto observado: 0.6 → limiar 0.3 captura todos com 50% de folga.
  - Caso o catálogo ganhe entradas com cf entre 0.1–0.3, ajustar para 0.2.
- Não dispara quando segmento tem `mu_override` (usuário sabe o que faz).
- Sugestão: aplicar `seabed.mu = catalog_cf` (suggested_change ativo).

### D014 — `ea_source='gmoor'` sem `ea_dynamic_beta`
- Severity: info, confidence: high
- Pendência da Fase 1 fechada — torna explícito que modelo dinâmico simplificado (β=0) está sendo aplicado.
- Aceitação implícita do comportamento NREL para análise quasi-estática.

### D015 — ProfileType raro (PT_4, PT_5, PT_6)
- Severity: warning, confidence: high
- Cada PT tem descrição customizada no dict `descriptions`:
  - PT_5: linha em U slack (raro em offshore).
  - PT_6: vertical (X≈0, caso degenerado).
  - PT_4: boiante com seabed (RESERVADO p/ Fase 12 — w<0).

---

## 7. Métricas atingidas

| Critério | Métrica alvo | Atingido | Evidência |
|---|---|---|---|
| ProfileType enum + classifier | 10 PTs, 6/7 match com MoorPy | ✅ | `test_profile_type_moorpy.py` |
| Classifier vs BC-MOORPY 7/7 ativos | match ou divergência categoria 3 documentada | ✅ 6 match + 1 cat-3 | `ACCEPTED_DIVERGENCES` |
| 100% diagnostics têm test repro + (no-repro + apply best-effort) | 15 × structural + subset com integration/apply | ✅ 31 testes em 1 arquivo | `test_diagnostics_coverage.py` |
| Cobertura `diagnostics.py` ≥ 95% | métrica pytest-cov | ✅ **100%** | suite full |
| `surface_violations` card dedicado | renderiza com violações | ✅ 4 testes | `diagnostics-card-smoke.test.tsx` |
| 4 diagnostics novos D012–D015 | builders + integração + testes | ✅ | 11 testes novos |
| Suite backend ≥ 372 verde | zero regressão | ✅ **438 + 3 skip** | pytest |
| Suite frontend ≥ 41 + N novos | zero regressão | ✅ **57** (41 → 57) | npm test |
| TS build sem erro | binário | ✅ | npm run build |
| `cases_baseline_regression` 3/3 verde | gate Princípio #1 | ✅ | regression |
| BC-MOORPY 7/7 + BC-FR-01 + BC-EA-01 + BC-FAIRLEAD-SLOPE-01 preservados | F1+F2 gates | ✅ | regression |
| CLAUDE.md atualizado com ProfileType + confidence | grep | ✅ | inspeção |
| Relatório com tabela Q1–Q9 + divergências classifier | binário | ✅ | este doc |

---

## 8. Histórico de commits da fase

```
1cb797d  feat(ui): SurfaceViolationsCard + smoke (Q6)
613727b  feat(diagnostics): D012 + D013 + D014 + D015 + integração + testes
29247ba  test(diagnostics): cobertura D001..D011 + P001..P004 (Q5)
8616ec6  test(profile_type): integração classifier vs BC-MOORPY 7/7 (Q2 + Ajuste 1)
7b7c368  feat(solver): classify_profile_type() + integração (Q2)
8ecf477  feat(types): ProfileType enum + confidence field (Q1+Q7)
[este]   docs(fase-4): relatório + CLAUDE.md + plano
```

---

## 9. Pendências para fases seguintes

- **Fase 10** (V&V completo):
  - Apply tests para 9 diagnostics restantes (D001-D004, D007, D008, D009, D010, D011) que requerem path solver complexo.
  - Cobertura ProfileType nos casos PT_4/5/6 (fabricar cases dedicados — atualmente PT_4 é fora MVP v1, PT_5/6 são degenerados).
  - Investigar correção do solver de Range em near-taut (pendência herdada da Fase 1) — D015 atual ajuda detectar mas não resolve.

- **Fase 7** (Anchor uplift):
  - Quando uplift for suportado, `endpoint_grounded=False` poderá disparar PT_4 ou casos novos. Reativar ACCEPTED_DIVERGENCES checks com BC-MOORPY-04, 05.

- **Fase 12** (pós-1.0):
  - Implementar β (`ea_dynamic_beta`) com iteração externa de tensão. D014 será desativado quando β estiver implementado.
  - PT_4 (linhas boiantes w<0) — reativar BC-MOORPY-06.

- **B0.1 (erros do usuário)** — pendência permanente. Skipado em F0; se aparecer caso concreto, vira diagnostic novo em PR isolado (não em fase específica).

---

## 10. Critério de fechamento da fase

| Critério | Status |
|---|---|
| Branch dedicada com 7 commits atômicos | ✅ |
| Sem mudanças fora do escopo (sem refactor de UI) | ✅ Q4 = a |
| Suite backend verde | ✅ 438 + 3 skip |
| Suite frontend verde | ✅ 57 |
| TS build | ✅ |
| Cobertura `diagnostics.py` 100% | ✅ |
| ProfileType enum + classifier funcionais | ✅ |
| BC-MOORPY 7/7 com classificação documentada | ✅ |
| Tabela apply garantido vs best-effort no relatório | ✅ §5 |
| Critério `confidence` documentado | ✅ docstring + §4 |
| D013 limiar com tabela empírica | ✅ §6 + comment do builder |
| `cases_baseline_regression` 3/3 verde | ✅ |
| CLAUDE.md atualizado | ✅ |
| Relatório com Q1–Q9 + divergências | ✅ |

**Fase 4 está pronta para merge.** Aguardando OK do usuário conforme protocolo. Não inicio Fase 5.
