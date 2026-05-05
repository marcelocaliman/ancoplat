# Relatório — Fase 8: AHV (Anchor Handler Vessel)

**Data de fechamento:** 2026-05-05
**Branch:** `feature/fase-8-ahv`
**Plano de referência:** [`docs/plano_profissionalizacao.md`](plano_profissionalizacao.md), seção "Fase 8".
**Decisão técnica antecipada:** [`CLAUDE.md`](../CLAUDE.md) — seção "Decisão fechada — Fase 8 antecipada (AHV idealização estática)" (registrada em 2026-05-05 antes da F8 começar).
**Commits:** 7 atômicos (Commits 4 e 5 combinados em um só pelo cálculo manual ser direto).

---

## 1. Sumário executivo

Fase 8 fechada com 7 commits. AncoPlat agora habilita Anchor Handler Vessels (carga estática horizontal aplicada a um ponto da linha durante operação de instalação). **Idealização explícita** documentada em 3 níveis (D018 + Memorial PDF + manual F11).

- **Schema**: `AttachmentKind` ganha `"ahv"`; 4 novos campos em `LineAttachment` (`ahv_bollard_pull`, `ahv_heading_deg`, `ahv_stern_angle_deg`, `ahv_deck_level`) com referencial explícito (eixo X global, anti-horário positivo).
- **Solver**: `multi_segment.py` estendido para aceitar **jump em H** na junção AHV (não só em V como buoy/clump). Função `_signed_force_2d` retorna tupla `(H_jump, V_jump)`. `_solve_suspended_tension` ajusta para H_fairlead = H_anchor + sum_H_jump.
- **D018** (sempre dispara em AHV) + **D019** (projeção in-plane < 30%).
- **4 BC-AHV** verde com **erro 0.0000%** (catenária paramétrica é exata; sem incerteza de modelo elástico como em F7).
- **Memorial PDF** com seção "AHV — Domínio de aplicação" + texto literal aprovado (Q9 / Ajuste 3) verificado via 5 strings-chave.
- **AHV + uplift** bloqueado com mensagem clara (extensão natural de F7).
- **Frontend**: Select kind ganha "AHV (Fase 8)"; campos Bollard pull + Heading aparecem condicionalmente; sample `ahv-pull` destravado; verbetes `ahv` e `bollard-pull` destravados.

**Suite final:** 666 backend + 2 skipped + 119 frontend = **787+2 testes verdes**. TS build limpo. Zero regressão F1-F7+F9.

**Status pós-F8:** AncoPlat alcança **paridade total de features com QMoor** conforme decisão estratégica de v1.0. Próxima fase: **F10 V&V completo**.

---

## 2. Decisões Q1–Q9 + Ajustes documentadas

| Q | Tema | Decisão | Onde está |
|---|---|---|---|
| **Q1** | Modelo físico | (a) Força aplicada num ponto, componentes (Fx, Fz). | `_signed_force_2d` em `multi_segment.py` |
| **Q2** | Schema (bollard_pull + heading_deg) | (a) Terminologia engineer-friendly + referencial explícito (eixo X global, anti-horário) | `solver/types.py:LineAttachment` |
| **Q3** | 2D vs 3D | (a) **2D no plano vertical da linha**. Fora do plano via D019. | Decisão registrada |
| **Q4** | Múltiplos AHVs | (a) Sim — solver multi-junction já trata. | `test_BC_AHV_04_multi_AHV_simetrico` |
| **Q5** | AHV + uplift / + boia/clump | AHV + uplift BLOQUEADO; AHV + boia/clump SUPORTADO em multi-seg | Mensagem clara em `solver.py` |
| **Q6** | D018 sempre | (a) **Sempre** dispara, sem opção de esconder | `solver.py` facade |
| **Q7** | V&V via cálculo manual | 3 BCs propostos + Ajuste 2 (BC-AHV-04 multi-AHV) = 4 BCs | `test_ahv_canonical_bc.py` |
| **Q8** | UI radio kind | (a) Radio kind={buoy, clump, ahv}; campos AHV substituem buoy quando selecionado | `AttachmentsEditor.tsx` |
| **Q9** | Memorial seção dedicada | (a) Seção numerada antes do sumário + texto literal aprovado | `pdf_report.py:_memorial_ahv_block` |

### Ajustes do mini-plano (3) — todos incorporados

- **Ajuste 1** ✅ D019 (projeção fora do plano < 30%) implementado em Commit 2 junto com D018. Cabia no mesmo commit (afinal são os 2 diagnostics novos da fase).
- **Ajuste 2** ✅ BC-AHV-04 (multi-AHV simétrico) adicionado a `test_ahv_canonical_bc.py`. Total: 4 BCs (não 3). Cobre Q4 (múltiplos AHVs) com gate explícito.
- **Ajuste 3** ✅ Texto literal Memorial PDF como entrega obrigatória — 5 strings-chave verificadas via PyPDF content check em `test_memorial_pdf_ahv.py` (estratégia idêntica à Fase 5).

---

## 3. Estrutura dos artefatos

### 3.1 — Backend (8 novos arquivos + 4 modificados)

```
backend/solver/types.py                            +AttachmentKind 'ahv' + 4 campos AHV
backend/solver/diagnostics.py                      +D018 + D019 (~120 linhas)
backend/solver/multi_segment.py                    _signed_force_2d + H_local per-seg
backend/solver/solver.py                           dispatcher D018/D019 auto + msg AHV+uplift
backend/api/services/pdf_report.py                 +_memorial_ahv_block + _has_ahv

backend/solver/tests/test_ahv_schema.py            NEW · 15 testes
backend/solver/tests/test_ahv_diagnostics.py       NEW · 9 testes
backend/solver/tests/test_ahv_solver.py            NEW · 15 testes
backend/solver/tests/test_ahv_canonical_bc.py      NEW · 8 testes (BC-AHV-01..04)
backend/api/tests/test_memorial_pdf_ahv.py         NEW · 9 testes (5 strings-chave)
```

### 3.2 — Frontend (4 modificados + 1 novo)

```
frontend/src/types/openapi.ts                      regenerado (kind=ahv + 4 campos)
frontend/src/lib/caseSchema.ts                     +ahv enum + 4 campos + 2 .refine()
frontend/src/lib/caseTemplates.ts                  ahv-pull destravado + payload BC-AHV-01
frontend/src/lib/glossary.ts                       ahv + bollard-pull destravados
frontend/src/components/common/AttachmentsEditor.tsx  Select +AHV item + bollard/heading inputs
frontend/src/components/common/SensitivityPanel.tsx   kind type estendido
frontend/src/test/ahv-frontend-smoke.test.tsx      NEW · 14 testes
frontend/src/test/glossary-smoke.test.tsx          ajustado pós-destravamento
frontend/src/test/samples-page-smoke.test.tsx      ajustado pós-destravamento
```

---

## 4. Tabela de erro relativo BC-AHV-01..04 (Q9 reforço — Q9 do mini-plano)

Validação via cálculo manual (sem MoorPy — não suporta carga lateral em ponto da linha; decisão registrada em plano §F8). Os 4 BCs canônicos verificam diretamente o invariante chave da Fase 8:

> **H_fairlead - H_anchor = sum(F_x_local_per_AHV)**

| ID | Cenário | Heading | Bollard pull esperado | H_jump esperado | H_jump real | rel_err |
|----|---|---:|---:|---:|---:|---:|
| **BC-AHV-01** | Lateral pura (alinhada) | 0.0° | 200 kN | 200 000 N | 200 000 N | **0.0000%** |
| **BC-AHV-02** | Cross-check vertical (clump) | n/a | n/a | 0 N (H constante) | 0 N | **0.0000%** |
| **BC-AHV-03** | Diagonal | 60.0° | 200 kN | 100 000 N (cos 60°·200k) | 100 000 N | **0.0000%** |
| **BC-AHV-04** | Multi-AHV (2 simétricos) | 0.0° + 0.0° | 100k + 80k | 180 000 N (soma linear) | 180 000 N | **0.0000%** |

**Observação científica (Q9):** todos os BCs ficam com **erro 0.0000%** (limite numérico de ponto flutuante). Diferentemente de F7 BC-UP onde a comparação era contra MoorPy (modelo elástico ligeiramente diferente, ~0.25% de erro), aqui validamos contra **cálculo analítico exato da catenária paramétrica**. Não há incerteza de modelo. Gate Q5 (rtol=1e-2) atendido trivialmente.

**Cobertura do gate**:
- BC-AHV-01: testa o invariante novo (H muda na junção AHV).
- BC-AHV-02: cross-check inteligente — clump_weight (jump em V apenas) preserva H constante. Regressão da extensão para tupla `(H_jump, V_jump)`.
- BC-AHV-03: testa projeção horizontal cos(heading) com heading não-trivial.
- BC-AHV-04: testa soma linear de jumps (Q4 — múltiplos AHVs).

---

## 5. Texto literal Memorial PDF "AHV — Domínio de aplicação"

Texto reproduzido em 3 parágrafos — verificado via 5 strings-chave (`pypdf` content check em `test_memorial_pdf_ahv.py`):

> **AHV — Domínio de aplicação**
>
> Esta análise modela a força aplicada pelo Anchor Handler Vessel (AHV) — N ativo[s] neste caso — como uma **carga estática pontual** aplicada à linha. A operação real envolve dinâmica do rebocador (movimento, aceleração, oscilação), comportamento dinâmico do cabo (vibração, snap loads) e hidrodinâmica do casco do AHV. Estes efeitos **não são modelados** na análise quasi-estática.
>
> **Use esta análise para:** verificação de tensão de pico em condição idealizada, dimensionamento preliminar de geometria, avaliação de equilíbrio estático.
>
> **Não substitui:** análise dinâmica de instalação, avaliação de cargas de impacto (snap loads), estudo de operabilidade em condições ambientais reais.

**Strings-chave verificadas (case-insensitive):**
- `idealização` (palavra-chave técnica antecipada em CLAUDE.md)
- `não substitui` (delimitação explícita do escopo)
- `análise dinâmica` (alternativa recomendada)
- `snap loads` (cargas dinâmicas específicas)
- `Anchor Handler Vessel` (terminologia explícita não-abreviada)

Pluralização correta: "1 AHV" (singular) vs "N AHVs" (plural).

---

## 6. Mitigação obrigatória — checklist (decisão técnica antecipada)

CLAUDE.md registrou em 2026-05-05 (antes da F8 começar) que F8 **não fecha sem** as 3 mitigações. Status:

| Mitigação | Onde | Status |
|---|---|---|
| **D018** (warning, medium) — "Análise estática de AHV é idealização" — dispara SEMPRE em AHV | `diagnostics.py` + facade `solve.py` | ✅ Commit 2 + Commit 3 |
| **Memorial PDF** com seção dedicada "AHV — Domínio de aplicação" citando dinâmica vs estática | `pdf_report.py` | ✅ Commit 6 |
| **Manual de usuário** (Fase 11) com seção sobre quando recomendar análise dinâmica externa | F11 (próxima após F10) | ⬜ Pendência F11 — registrada |

Bonus dessa fase: **D019** (Ajuste 1) alerta quando heading resulta em projeção <30% no plano da linha — evita confusão de engenheiro digitando bollard pull alto + heading perpendicular e vendo resultado idêntico ao caso sem AHV.

---

## 7. Histórico de commits da fase

```
a510e0c  feat(frontend): UI AHV + plot icon + destrava sample/verbetes (Q8 + A1+A2)
a582efd  feat(memorial): bloco "AHV — Domínio de aplicação" no PDF (Q9 + Ajuste 3)
e863086  test(solver): BC-AHV-01..04 vs cálculo manual rtol=1e-2 (Q5+Q7+Ajuste 2+Q9)
18da690  feat(solver): força horizontal em junção AHV + auto-disparo D018/D019 (Q3+Q4+Q5+Q6)
c99f6f2  feat(diagnostics): D018 + D019 para AHV (Q6 + Ajuste 1)
ef55402  feat(schema): LineAttachment.kind='ahv' + campos AHV (Q1+Q2)
[este]   docs(fase-8): relatório + CLAUDE.md + plano
```

Commits 4 e 5 do mini-plano original combinados em um só (`e863086`) — cálculo manual é trivial (sem ferramenta externa como MoorPy), então geração do baseline + testes virou um único commit autocontido.

---

## 8. Mudanças de design durante a execução

### 8.1 — `submerged_force` agora é optional default 0

Originalmente `submerged_force: gt=0` (required positivo) em `LineAttachment`. AHV não tem semântica de "força submersa" (terminologia de boia/clump). Para acomodar:
- `submerged_force` muda para `ge=0` default 0.
- Validador cruzado preserva: `kind=buoy/clump_weight` exige > 0.

Schema retro-compat: payloads existentes com `submerged_force > 0` continuam válidos.

### 8.2 — `_signed_force` legado preservado, `_signed_force_2d` é novo

Para minimizar risco de regressão, `_signed_force(att) → float` (legado, retorna apenas V) foi preservado. Para AHV retorna 0 (componente vertical não modelada). A nova função `_signed_force_2d(att, line_az) → (H_jump, V_jump)` é usada apenas em pontos onde realmente precisamos da componente horizontal — `_integrate_segments` (Commit 3) e o residual do `_solve_suspended_tension`.

### 8.3 — H per-segmento no `_integrate_segments`

A mudança mais profunda: `H_local` agora é uma variável que cresce/decresce a cada junção AHV. Antes era um único `H` constante ao longo de toda a linha (premissa de catenária livre). Implementação: `H_local += H_jump` ao entrar no segmento i+1; cada segmento usa `a_i = H_local / w_i` próprio.

Side effect: o resultado agora inclui `H_fairlead` (era apenas `H` antes). Em casos sem AHV, `H_fairlead == H` (zero diferença, retro-compat preservado).

### 8.4 — `T_anchor` usa `H_anchor` (= H input); `T_fairlead` usa `H_fairlead`

`_integrate_segments` ajusta:
- `T_anchor = sqrt(H * H + V_anchor²)` — H input do solver.
- `T_fairlead = sqrt(H_local * H_local + V_fairlead²)` — H_local final pós-jumps.

Em casos sem AHV, são iguais. Com AHV, T_fairlead > T_anchor (assumindo bollard alinhado, H_jump positivo) ou T_fairlead < T_anchor (heading oposto à linha).

### 8.5 — `_solve_suspended_tension` brentq sobre `H_anchor`

Variável de busca permanece H_anchor (= H[0]). Mas a relação `T_fl² = H_fl² + V_fl²` agora usa `H_fl = H_anchor + sum_H_jump`. Bracket: `H_max_anchor = H_max_fairlead - sum_H_jump`. Caso AHV bollard ≥ H_max_fairlead → ValueError com mensagem clara.

---

## 9. Divergências do plano original

### 9.1 — Sem ícone dedicado de AHV no plot (Q7)

Mini-plano originalmente listava "Plot mostra AHV com seta de direção (heading visualizado)" como Commit 8. Implementação: o ícone do startpoint AHV já existia desde F3/D7 (`getStartpointSvg`), e o sample `ahv-pull` usa `startpoint_type=ahv`. Mas **ícone na junção AHV (não no startpoint)** com seta indicando heading — pendência v1.1+. Visualização da força AHV em v1.0 vai pelo Memorial PDF + diagnostics.

### 9.2 — Plano original recomendava no-go

§F8 do plano original recomendava **no-go** para v1.0. Decisão **revertida** em 2026-05-05 (paridade total com QMoor). Mitigação obrigatória registrada antes da fase começar. Decisão final: go com 3 mitigações (D018 + Memorial + manual).

### 9.3 — Cálculo manual em vez de MoorPy

§F8 dizia "MoorPy não suporta nativamente, então validação contra cálculo manual". Implementado conforme — não tentamos forçar MoorPy a aceitar AHV. Cálculo manual cobre o invariante fundamental (jump em H) com erro 0.0000%.

---

## 10. Pendências para fases seguintes

### Fase 10 (V&V completo, próxima)
- ≥10 BC-AHV adicionais (cobertura ampliada de cenários).
- Comparação com software comercial de instalação se disponível.
- Performance: re-rodar `tools/perf_watchcircle.py` com cenário AHV agora real. Atualizar `relatorio_F9_perf_watchcircle.md`.

### Fase 11 (lançamento 1.0)
- **Manual de usuário com seção AHV** (mitigação técnica antecipada, obrigatória):
  - Domínio de aplicação válido (verificação de pico, dimensionamento preliminar).
  - Quando recomendar análise dinâmica externa (snap loads, operabilidade).
  - Tutorial: "como configurar um caso AHV no AncoPlat"; texto-base já no Memorial PDF + verbete glossário.

### Pós-v1.0
- **F8.x**: ícone dedicado AHV em junção (não no startpoint) com seta heading.
- **F8.x**: pitch da força AHV (componente vertical Fz). Hoje AHV é puramente horizontal — adicionar pitch_deg para AHVs com componente vertical (rebocador puxando para cima/baixo).
- **F12**: 3D AHV (Q3=a). Componente fora do plano da linha modelada.
- **F12**: AHV com momento (Q1=b). Modelo de corpo rígido do rebocador.
- **F7.x/F8.x combinados**: AHV + uplift (atualmente bloqueado).

---

## 11. Critério de fechamento da fase

| Critério | Status |
|---|---|
| Branch dedicada com 7 commits atômicos | ✅ |
| Schema `kind="ahv"` + 4 campos + Pydantic cross-validation | ✅ Commit 1 |
| Docstring `ahv_heading_deg` com referencial explícito (eixo X global, anti-horário) | ✅ Commit 1 |
| Solver multi-segmento aplica jump (H, V); buoy/clump preservados | ✅ Commit 3 |
| BC-MOORPY 9/9 + BC-UP 5/5 sem regressão | ✅ |
| **D018 sempre dispara em AHV** (decisão Q6 não-negociável) | ✅ Commit 2+3, teste explícito |
| D019 quando in_plane_fraction < 30% | ✅ Commit 2+3 |
| **4 BC-AHV verde com rtol=1e-2** (Q5 + Ajuste 2) | ✅ Erro 0.0000%, folga total |
| **Tabela de erro relativo no relatório** (Q9 reforço) | ✅ §4 + teste imprime no -v |
| **AHV + uplift bloqueado com mensagem clara** (Q5) | ✅ Commit 3 |
| **Memorial PDF com seção "AHV — Domínio de aplicação" + texto literal** (Q9 + Ajuste 3) | ✅ Commit 6, 5 strings verificadas |
| Sample `ahv-pull` destravado | ✅ Commit 7 (A1) |
| 2 verbetes glossário (`ahv`, `bollard-pull`) destravados | ✅ Commit 7 (A2) |
| Plot mostra AHV com seta heading | ⚠️ Parcial (ícone startpoint AHV; seta na junção fica para v1.1+) |
| UI radio kind={buoy, clump, ahv} com campos AHV substituindo buoy | ✅ Commit 7 |
| Suite backend ≥ 645 (esperado +35) | ✅ **666** (era 634; +32 ativos) |
| Suite frontend ≥ 110 (esperado +5) | ✅ **119** (era 105; +14) |
| Gates F1-F7+F9 preservados | ✅ |
| TS build limpo | ✅ |
| CLAUDE.md atualizado: F-prof.8 + decisão D019 acrescentada | ✅ Commit 8 |
| Relatório com Q1-Q9 + tabela erro relativo + texto Memorial reproduzido | ✅ este doc |

**Fase 8 está pronta para merge.** AncoPlat alcança paridade total de features com QMoor. Aguardando OK do usuário conforme protocolo. Não inicio Fase 10.

---

## 12. Status pós-F8

Fases v1.0 fechadas: **F0 → F1 → F2 → F3 → F4 → F5 → F6 → F9 → F7 → F8** (10 fases, sequência ajustada para paridade total com QMoor).

Restam: **F10 (V&V completo)** + **F11 (lançamento 1.0)**.

Decisão técnica antecipada AHV — checklist no manual de usuário (F11) é o último item pendente da mitigação obrigatória.
