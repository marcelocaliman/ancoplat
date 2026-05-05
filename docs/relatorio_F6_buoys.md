# Relatório — Fase 6: Catálogo de boias

**Data de fechamento:** 2026-05-05
**Branch:** `feature/fase-6-buoy-catalog`
**Plano de referência:** [`docs/plano_profissionalizacao.md`](plano_profissionalizacao.md), seção "Fase 6".
**Commits:** 7 atômicos.

---

## 1. Sumário executivo

Fase 6 fechada com 7 commits sobre a branch acima. Engenheiro agora pode escolher boias do catálogo no `AttachmentsEditor` em vez de digitar `submerged_force` à mão — com rastreabilidade ao catálogo (`buoy_catalog_id`) e indicador visual quando o engenheiro override valores do catálogo.

- **Modelo `BuoyRecord`** + tabela `buoys` no SQLite + Pydantic schema (`BuoyCreate/Update/Output`).
- **`compute_submerged_force()`** ancorado no Excel "Formula Guide" R4-R7. 8 testes parametrizados (4 end_types × 2 dimensões) ±1%.
- **Seed canônico**: 11 entradas com `data_source` documentado (1× `excel_buoy_calc_v1` + 10× `generic_offshore`).
- **Endpoints REST**: `GET/POST/PUT/DELETE /buoys` espelhando `line_types`. Paginação + busca + filtros end_type/buoy_type. Imutabilidade do seed.
- **`LineAttachment.buoy_catalog_id`**: campo opcional rastreável (não-autoritativo em runtime — solver ignora).
- **`BuoyPicker`** integrado ao `AttachmentsEditor` com modo "do catálogo / manual" + override automático (Q7).
- **Tab "Boias" em `/catalog`** com URL deep-linking (`?tab=buoys`).
- **`docs/relatorio_F6_buoys.md`** + entrada F-prof.6 no CLAUDE.md.

**Suite final:** 554 backend + 4 skipped + 66 frontend = **620 testes verdes**. Library paramétrica MoorPy (Q1=no-go) reservada para F12.

---

## 2. Decisões Q1–Q9 documentadas

| Q | Tema | Decisão | Onde está |
|---|---|---|---|
| **Q1** | Library paramétrica MoorPy | (a) **No-go** — reservado para F12. | Pendência registrada |
| **Q2** | Fonte do seed | (c) Excel + genéricos, ≥10 entradas, `data_source` por entrada | `backend/data/seed_buoys.py` |
| **Q3** | End_type enum | 4 valores fechados (flat / hemispherical / elliptical / semi_conical) | `buoyancy.py` |
| **Q4** | `buoy_catalog_id` em LineAttachment | (a) Opcional, sem bump de schema, docstring "não-autoritativo" | `solver/types.py:LineAttachment` |
| **Q5** | Validação ±1% | (a) Hard-coded com sheet+row no docstring | `test_buoy_buoyancy.py` |
| **Q6** | UI tabs | (b) Tabs Cabos/Boias dentro de `/catalog` + URL deep-linking | `CatalogPage.tsx` + `BuoysTab.tsx` |
| **Q7** | Modo manual | (b) Override destrava + `buoy_catalog_id=null` automático + indicador ⚠ | `AttachmentsEditor.tsx` |
| **Q8** | Estrutura de testes | 3 arquivos como propostos | `test_buoy_buoyancy/seed/catalog.py` |
| **Q9** | Critério de fechamento | ≥10 boias (ajustado pelo usuário) + 8 testes de empuxo | seção 4 abaixo |

### Ajuste único do usuário

- **Commit 2 — testes de fórmula com 2 dimensões por end_type**: ✅ implementado. 8 testes parametrizados (`flat-D1.0-L4.0`, `flat-D2.0-L3.0`, `hemispherical-D1.5-L2.5`, `hemispherical-D3.0-L4.0`, `elliptical-D2.0-L3.0`, `elliptical-D2.5-L3.5`, `semi_conical-D2.0-L2.5`, `semi_conical-D3.0-L4.0`) cada um citando "Formula Guide R4/R5/R6/R7" no docstring + dimensão. Total **23 testes** em `test_buoy_buoyancy.py` (8 ±1% volume + 8 ±1% submerged_force + 7 sanity).

---

## 3. Estrutura dos artefatos

### 3.1 — Backend

```
backend/api/db/models.py             +BuoyRecord
backend/api/schemas/buoys.py         BuoyBase/Create/Update/Output (4 end_types fechados)
backend/api/services/buoyancy.py     compute_volume + compute_submerged_force
backend/api/services/buoy_service.py CRUD + IMMUTABLE_SOURCES
backend/api/routers/buoys.py         GET/POST/PUT/DELETE /buoys
backend/api/main.py                  registra router
backend/data/seed_buoys.py           11 entradas + idempotência
```

### 3.2 — Solver

```
backend/solver/types.py              +LineAttachment.buoy_catalog_id
```

### 3.3 — Frontend

```
frontend/src/api/types.ts            +BuoyOutput/Create/Update + Paginated_BuoyOutput_
frontend/src/api/endpoints.ts        +listBuoys/getBuoy/createBuoy/updateBuoy/deleteBuoy
frontend/src/lib/caseSchema.ts       +buoy_catalog_id (z.number().int().min(1).nullable())
frontend/src/components/common/BuoyPicker.tsx           novo
frontend/src/components/common/AttachmentsEditor.tsx    BuoyPicker + override + badge ⚠
frontend/src/pages/CatalogPage.tsx                      Tabs Cabos/Boias + deep-linking
frontend/src/pages/BuoysTab.tsx                         tabela + dialog (CRUD user_input)
```

### 3.4 — Testes

```
backend/api/tests/test_buoy_buoyancy.py    23 testes (8 ±1% + 8 + 7 sanity)
backend/api/tests/test_buoy_seed.py        8 testes (≥10 entradas, idempotência, etc)
backend/api/tests/test_buoy_catalog.py     17 testes (CRUD + filtros + 403 imutável)
backend/api/tests/conftest.py              +seeded_buoys fixture
backend/solver/tests/test_buoy_catalog_id.py  7 testes (round-trip + solver-ignora)
frontend/src/test/buoy-picker-smoke.test.tsx     4 smoke (placeholder, fallback id, callbacks)
frontend/src/test/catalog-tabs-smoke.test.tsx    5 smoke (deep-linking, fallback)
```

**Backend novo: 55 testes** (23 + 8 + 17 + 7). Frontend novo: **9 smokes**.

---

## 4. Métricas atingidas

| Critério | Métrica alvo | Atingido | Evidência |
|---|---|---|---|
| ≥ 10 boias no seed (Q9 ajustado) | contagem | ✅ **11** | `test_seed_tem_ao_menos_10_entradas` |
| `data_source` documentado por entrada (Q2) | string ≠ user_input | ✅ | `test_cada_entrada_tem_data_source_documentado` |
| 4 end_types representados | enum | ✅ | `test_seed_cobre_4_end_types` |
| Excel Formula Guide R4-R7 citado em cada teste de empuxo | docstring | ✅ 8/8 | `test_buoy_buoyancy.py` (parametrize.id contém dimensão) |
| ±1% para volume e empuxo (Q9 ajustado para 2 dimensões) | rel_err ≤ 1% | ✅ 8 + 8 | `test_volume_within_1pct_of_excel_formula` + `test_submerged_force_consistente_com_buoyancy_minus_weight` |
| 5 endpoints REST espelhando line_types | smoke | ✅ | `test_buoy_catalog.py` (17 testes) |
| Imutabilidade seed → 403 PUT/DELETE | binário | ✅ | `test_update_buoy_seed_403` + `test_delete_buoy_seed_403` |
| `LineAttachment.buoy_catalog_id` opcional + round-trip | binário | ✅ 7 testes | `test_buoy_catalog_id.py` |
| Solver ignora `buoy_catalog_id` em runtime | binário | ✅ | `test_solver_ignora_buoy_catalog_id` |
| BuoyPicker integrado com override → null | binário | ✅ | `clearCatalogLink()` em 6 campos físicos |
| Indicador visual "⚠ modo manual" | binário | ✅ | badge AlertTriangle |
| Tab "Boias" em /catalog | binário | ✅ | `BuoysTab` + `Tabs` em CatalogPage |
| URL deep-linking `?tab=buoys` | binário | ✅ 5 smokes | `catalog-tabs-smoke.test.tsx` |
| Suite backend ≥ 499 verde | regressão | ✅ **554 + 4 skipped** | pytest |
| Suite frontend ≥ 57 verde | regressão | ✅ **66** | npm test |
| TS build sem erro | binário | ✅ | npm run build |
| Todos os gates F1–F5 preservados | regressão | ✅ | suite full |
| CLAUDE.md atualizado | grep | ✅ | seção F-prof.6 |
| Relatório com tabela Q1–Q9 + Excel ref | binário | ✅ | este doc |

---

## 5. Histórico de commits da fase

```
96f1484  feat(frontend): tab Boias em /catalog com URL deep-linking (Q6)
2fdfeb2  feat(frontend): BuoyPicker + integração AttachmentsEditor (Q1+Q7)
9174b97  feat(schema): LineAttachment.buoy_catalog_id opcional rastreável (Q4)
5bf4742  feat(api): endpoints REST /buoys (Q1)
680e3d9  feat(catalog): seed de boias canônicas com data_source documentado (Q2)
a246914  feat(catalog): modelo Buoy + schema Pydantic + função de empuxo (Q3+Q5)
[este]   docs(fase-6): relatório + CLAUDE.md + plano
```

---

## 6. Identidade matemática registrada

**`V_hemispherical(r, L) = V_semi_conical(r, L)`** quando ambos seguem as fórmulas do Excel Formula Guide R5/R7.

Demonstração:
- Hemi: 2 hemisférios com raio `r` ocupam comprimento `D=2r` mas adicionam volume `(4/3)·π·r³`. Diferença líquida vs cilindro reto = `(4/3)·π·r³ − 2π·r³ = −(2/3)·π·r³`.
- Conic: 2 cones com altura `D/4` e base `r` ocupam comprimento `D/2` mas adicionam `(1/6)·π·r²·D = (1/3)·π·r³`. Diferença líquida vs cilindro reto = `(1/3)·π·r³ − π·r³ = −(2/3)·π·r³`.

→ Ambos retiram `(2/3)·π·r³` do cilindro reto. Resultado idêntico.

**Implicação para os 8 testes**: bug que troque hemi↔conic NÃO é detectável pelo gate ±1%. Documentado no docstring do módulo de testes — não é defeito do teste, é propriedade do Excel. Os outros pares (flat ↔ hemi, flat ↔ ellip, ellip ↔ conic) discriminam.

---

## 7. Divergências do plano original

### 7.1 — Library paramétrica MoorPy NÃO entregue (Q1=a)

Decisão consciente do usuário. Motivos:
- Catálogo legacy de 522 entradas cobre uso prático.
- F6 já tem 6 commits substanciais — empilhar library viraria fase de 5–7 dias com dois temas paralelos.
- Não é bloqueante para v1.0.

**Reservada para F12.x** (Features avançadas pós-1.0). Schema `material_coefficients` + `POST /line-types/from-parametric` + tab "Calculadora paramétrica" no `LineTypePicker` continuam mapeados no plano §365.

### 7.2 — Pré-existente exposto pela regeneração de OpenAPI

A regeneração do `openapi.ts` (necessária para incluir os novos schemas de boia) expôs **inconsistência pré-existente** em `MooringSystemFormPage.EMPTY_LINE`:

- `ea_source` agora é required no LineSegment (consequência da Fase 1 — antes era optional).
- `startpoint_offset_horz/vert/startpoint_type` agora required em BoundaryConditions (Fase 2/3).

`EMPTY_LINE` não tinha esses campos → TypeScript bloqueava o build. **Não é regressão da F6** — bug latente desde Fase 3, escondido porque ninguém regenerava `openapi.ts`. Corrigido junto com o Commit 5 (5 linhas).

### 7.3 — Sem teste E2E do popover do BuoyPicker

Smokes do BuoyPicker (4 testes) cobrem render + fallback + callbacks. **Não exercitam o popover Radix** (portal + lista clicável). Tradeoff consciente: testar popover requer `@testing-library/user-event` + portais → overhead alto para baixo valor numa fase de feature work.

**Pendência**: testes E2E de seleção real entram na Fase 9 (UI polish) ou Fase 10 (V&V completo).

---

## 8. Pendências para fases seguintes

- **F12.x** — Library paramétrica MoorPy. Schema `material_coefficients` + endpoint `POST /line-types/from-parametric` + tab "Calculadora paramétrica" no `LineTypePicker`. ~3-5 dias de trabalho.
- **Fase 9 (UI polish)** — testes E2E de download/picker; smoke completo do popover do BuoyPicker.
- **Fase 10 (V&V)** — boias com manufacturer (catálogo de fabricantes reais como Crosby, Trelleborg).
- **Pós-1.0** — boia esférica (não cilíndrica) e formato toroidal (boias de superfície ancoradas).

---

## 9. Critério de fechamento da fase

| Critério | Status |
|---|---|
| Branch dedicada com 7 commits atômicos | ✅ |
| Sem mudanças fora do escopo (solver intacto exceto +1 campo opcional não-autoritativo) | ✅ |
| Suite backend verde | ✅ 554 + 4 skip |
| Suite frontend verde | ✅ 66 |
| TS build limpo | ✅ |
| 5 endpoints novos `/buoys` | ✅ |
| Seed ≥10 boias com `data_source` por entrada | ✅ 11 entradas |
| 8 testes ±1% citando Excel Formula Guide R4-R7 | ✅ |
| `LineAttachment.buoy_catalog_id` opcional | ✅ |
| Solver ignora `buoy_catalog_id` em runtime | ✅ teste explícito |
| BuoyPicker integrado + override automático + indicador ⚠ | ✅ |
| Tab "Boias" em /catalog + URL deep-linking | ✅ |
| `cases_baseline_regression` 3/3 verde | ✅ |
| BC-MOORPY 7/7 + BC-FR-01 + BC-EA-01 + BC-FAIRLEAD-SLOPE-01 + diagnostics | ✅ |
| CLAUDE.md atualizado | ✅ |
| Relatório com Q1–Q9 + Excel ref | ✅ |

**Fase 6 está pronta para merge.** Aguardando OK do usuário conforme protocolo. Não inicio Fase 7.
