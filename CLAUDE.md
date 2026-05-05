# AncoPlat — Briefing para Claude Code

> **Convenção de nomes:**
> - **AncoPlat** — este app, em desenvolvimento. (Antes chamado "QMoor Web"; renomeado em 2026 por questão de marca/registro.)
> - **QMoor 0.8.5** / **QMoor original** / **QMoor legacy** — software comercial de origem do qual o catálogo veio e contra o qual validamos numericamente. NÃO confundir com o app que estamos construindo.
> - Identificadores de dados que mantêm o nome "qmoor" (`qmoor_ea`, `qmoor_database_inventory.xlsx`, `data_source: legacy_qmoor`) são referências ao software legado e ficam como rastreabilidade — não devem ser renomeados.

## Contexto

Este é um projeto de aplicação web pessoal para análise estática de linhas de ancoragem offshore. Detalhes completos em `docs/Documento_A_Especificacao_Tecnica_v2_2.docx`.

## Regras importantes

1. **Antes de qualquer tarefa significativa**, consulte `docs/Documento_A_Especificacao_Tecnica_v2_2.docx`. Esse é o briefing técnico definitivo.
2. **Não questione decisões marcadas como "Decisão fechada"** (caixas verdes no documento) sem motivo técnico claro.
3. **Stack:** Python 3.12 (backend), React + Vite + TypeScript (frontend), SQLite (banco), FastAPI (API).
4. **Solver:** catenária elástica com seabed, baseado em SciPy. Validação contra MoorPy (open-source).
5. **Catálogo de materiais:** importado integralmente de `docs/QMoor_database_inventory.xlsx` (522 entradas, 16 tipos).
6. **Unidades internas:** sempre SI (metros, Newtons, kg). Conversões só nas bordas (input/output).
7. **Comunicação:** o usuário não usa terminal. Sempre execute comandos por ele e mostre resultados visualmente.

## Estado atual

- ✅ F0 — Setup do ambiente (concluído)
- ✅ F1a — Importação do catálogo QMoor (legacy) para SQLite (concluída, 522 entradas)
- ✅ F1b — Implementação do solver (concluída, 45 testes, 96% cobertura, BC-01..09 validados contra MoorPy)
- ✅ F2 — API FastAPI (concluída; ver `docs/relatorio_F2.md`)
- ✅ F3 — Frontend React (concluída; ver `docs/relatorio_F3.md`)
- ✅ F4 — Calibração com MoorPy (concluída; ver `docs/relatorio_F4.md`)
- ✅ F5.1 — Multi-segmento (concluída)
- ✅ F5.2 — Attachments (boias e clumps)
- ✅ F5.3 — Seabed inclinado + batimetria (concluída)
- ✅ F5.4 — Sistema multi-linha (mooring system) — encerrada. Schema + solver dispatcher + frontend completo (lista/detail/form/plan view) + PDF report + comparação multi-sistema. Ver `docs/relatorio_F5_4.md`.
- ✅ F5.5 — Equilíbrio de plataforma sob carga ambiental — encerrada. Solver `solve_platform_equilibrium` (fsolve outer + per-line Range), endpoints REST, painel UI com plan view deslocado e setas de offset/carga. **Motor estático fechado em termos físicos.** Ver `docs/relatorio_F5_5.md`.
- ✅ F5.6 — Watchcircle (envelope de offset sob carga rotacionada). `compute_watchcircle` reusa baseline; estratégia de chute robusta no fsolve (4 candidatos + descarte de soluções não-físicas). Frontend com card de varredura + animação play/pause/scrub varrendo 360°.
- ✅ F5.7 — Boias profissionais com pendant + metadata (tipo, end_type, dimensões da boia, modelo do cabo do pendant). UI com painel "Detalhes" colapsável; PDF report estendido com tabela de attachment_details.
- ✅ **F-prof.0** — Baseline pré-profissionalização: tag `v0.5-baseline`, snapshot dos cases em `docs/audit/cases_baseline_2026-05-04.json` (3 cases + 12 execs + 2 mooring systems), ambiente isolado de validação MoorPy em `tools/moorpy_env/`, baseline numérico dos 10 catenary cases do MoorPy em `docs/audit/moorpy_baseline_2026-05-04.json` (entrada do gate `BC-MOORPY-01..10` na Fase 1). 282 backend + 8 frontend testes verdes. Decisão fechada QMoor/GMoor com base no modelo NREL (ver seção "Modelo físico de QMoor vs GMoor"). Ver `docs/relatorio_F0_baseline.md`.
- ✅ **F-prof.1** — Correções físicas críticas: atrito per-segmento (B3) com helper `_resolve_mu_per_seg` (precedência `mu_override → seabed_friction_cf → seabed.mu → 0`); toggle `ea_source` per-segmento (A1.4+B4); gate `BC-MOORPY-01..10` (7 ativos passando rtol=1e-4 ou justificado, 3 skipados nominalmente até Fase 7/12); BC-FR-01 (capstan manual) e BC-EA-01 (ratio gmoor/qmoor). Frontend ganhou Select "EA source" + Input "μ override" no SegmentEditor + card "Atrito & EA por segmento" no detail. Suite: 334 backend + 17 frontend verdes. Regressão `cases_baseline.json`: 3/3 cases preservam resultado (rtol=1e-9). Ver `docs/relatorio_F1_correcoes_fisicas.md`.
- ✅ **F-prof.2** — Redesign aba Ambiente + auditoria de validações: aba Ambiente refatorada com 3 grupos (Geometria/Fairlead/Seabed) e novo `BathymetryInputGroup` (entrada por batimetria 2-pontos, slope derivado read-only, modo avançado escondido para slope direto); `BathymetryPopover` deletado; `startpoint_offset_horz/vert` reservados como cosméticos (A2.6); validação `startpoint_depth >= h` relaxada para seabed inclinado via helper `_x_estimate` (Q7) com BC-FAIRLEAD-SLOPE-01; auditoria sistemática de 29 raises em solver.py + multi_segment.py com classificação a/b/c documentada (13 a + 15 b + 1 c) e justificativa física inline; `test_validation_raises.py` com 25 testes parametrizados; mensagens E4 hardenizadas (campo + recebido + esperado). Suite: 365 backend + 32 frontend verdes. Round-trip `BathymetryInputGroup` em rtol=1e-9. Regressão baseline 3/3. Ver `docs/relatorio_F2_ambiente_validacoes.md`.
- ✅ **F-prof.3** — Quick wins UX: 5 melhorias visuais que fecham gaps cosméticos com QMoor sem mexer em física. (A1.5) `LineSummaryPanel` com 4 agregados (n. segs, L_total, peso seco, peso molhado) no topo da aba Linha; (D6) trecho grounded pontilhado vermelho — **decisão consciente, divergência do cinza QMoor** (ver seção "Decisão fechada: grounded vermelho" abaixo); (D7) ícones do startpoint conforme `boundary.startpoint_type` (semisub default + AHV + Barge + none) via dispatcher `getStartpointSvg()`; (A2.5) Select "Tipo de plataforma" no grupo Fairlead da aba Ambiente; (D9) 4 toggles compactos no canto superior do plot (equal-aspect / labels / legend / images). Suite: 372 backend + 41 frontend verdes. Solver intacto, regressão `cases_baseline` 3/3. Ver `docs/relatorio_F3_quick_wins.md`.
- ✅ **F-prof.4** — Diagnostics maturidade + ProfileType taxonomy: `ProfileType` enum (10 valores PT_0..PT_8 + PT_U) espelhando MoorPy/Catenary.py:147-163 + classifier puro `classify_profile_type()` em módulo dedicado; validação cruzada vs MoorPy nos 7 BC-MOORPY ativos = 6 match perfeito + 1 divergência Cat-3 (BC-MOORPY-08 hardest taut, fallback PT_-1 do MoorPy sem equivalente no vocabulário canônico); 4 diagnostics novos (D012 slope alto / D013 μ=0 com catálogo / D014 gmoor sem β / D015 PT raro); cobertura **100% de `diagnostics.py`**; campo `confidence` (high/medium/low) no `SolverDiagnostic` com critério explícito documentado; `SurfaceViolationsCard` UI dedicada. Suite: 438 backend + 57 frontend verdes. Apply tests: 3 garantidos + 3 best-effort + 9 deferred para Fase 10. Ver `docs/relatorio_F4_diagnostics.md`.
- ✅ **F-prof.5** — Reports, memorial e exportação: `case_input_hash()` SHA-256 canonicalizado em `backend/api/services/case_hash.py` (sort_keys + separators sem whitespace, exclui `name`/`description`) com 16 testes de canonicalização e estabilidade (Ajuste 1 do mini-plano); `.moor` v2 schema versionado + migrador `_migrate_v1_to_v2()` com **log estruturado** `{field, old, new, reason}` exposto via `/import/moor` retornando `{case, migration_log}` (Ajuste 2); `build_memorial_pdf()` com rastreabilidade total (hash[:16] + solver_version + timestamp em footer de cada página) + ProfileType + diagnostics estruturados (severity colorida + confidence) — content checks via PyPDF; CSV de geometria ≥ 5000 pontos international format (`,` separator, `.` decimal) com comentários de metadata; Excel `.xlsx` com 3 abas mínimas (Caso/Resultados/Geometria) + Diagnostics opcional consistente com Memorial PDF; UI com 3 botões em CaseDetail e ImportExportPage; 4 endpoints REST novos (`/cases/{id}/export/memorial-pdf`, `/csv`, `/xlsx`, `/import/moor` v2). Suite: 499 backend + 4 skipped + 57 frontend verdes. Pendência herdada de F2: `.moor` schema sem `slope_rad`/`attachments` — round-trip dos baseline cases skipa quando aplicável. Ver `docs/relatorio_F5_reports.md`.
- ✅ **F-prof.6** — Catálogo de boias: tabela `buoys` no SQLite + `BuoyRecord` SQLAlchemy + Pydantic schemas (`BuoyCreate/Update/Output`) com 4 end_types fechados (`flat | hemispherical | elliptical | semi_conical`); `compute_submerged_force()` em `backend/api/services/buoyancy.py` ancorado nas fórmulas do Excel "Formula Guide" R4-R7 (cita sheet+row no docstring) com **23 testes** (8 ±1% volume + 8 ±1% empuxo cobrindo 4 end_types × 2 dimensões + 7 sanity); seed canônico de **11 boias** (1× `excel_buoy_calc_v1` da R7 do Excel + 10× `generic_offshore` cobrindo dimensões típicas D 1.0-3.0 m / L 2.0-4.5 m) com `data_source` documentado por entrada (Q2 ajustado pelo usuário); 5 endpoints REST `/buoys` (GET list paginado + filtros end_type/buoy_type/search, GET id, POST user_input, PUT/DELETE com 403 para seed canônico) espelhando padrão `line_types`; `LineAttachment.buoy_catalog_id: Optional[int]` rastreável **NÃO autoritativo em runtime** (solver ignora — verificado por teste); `BuoyPicker` (popover de busca debounced) integrado ao `AttachmentsEditor` com modo "do catálogo / manual": override em qualquer dos 6 campos físicos zera `buoy_catalog_id` automaticamente (Q7); badges visuais "do catálogo" (azul) vs "modo manual" (laranja, AlertTriangle); tab "Boias" em `/catalog` com URL deep-linking via `?tab=buoys` (Q6). **Library paramétrica MoorPy reservada para F12.x** (Q1=no-go consciente — catálogo legacy de 522 entradas cobre uso prático). Suite: 554 backend + 4 skipped + 66 frontend verdes (+55 testes backend, +9 testes frontend). Identidade matemática registrada: `V_hemispherical(r,L) = V_semi_conical(r,L)` por especificação do Excel — bug troca hemi↔conic não detectável pelo gate ±1%, documentado no docstring. Ver `docs/relatorio_F6_buoys.md`.
- ✅ **F-prof.9** — UI polish & onboarding: 5 case templates novos em [`frontend/src/lib/caseTemplates.ts`](frontend/src/lib/caseTemplates.ts) (clump-weight, lifted-arch, sloped-seabed + 2 preview marcados com `requirePhase`: anchor-uplift F7 e ahv-pull F8) — total 11 samples; nova rota `/samples` com grid visual + filtro busca + toggle preview; `frontend/src/lib/glossary.ts` com **40 verbetes canônicos** em 5 categorias (incluindo verbetes preview F7/F8: anchor-uplift, suspended endpoint, AHV, bollard pull); rota `/help/glossary` com busca + cross-references; **OnboardingTour DIY** (sem dependência nova — princípio "polish ≠ rewrite") com 5 etapas + skip persistente em localStorage (`ancoplat:onboarding-completed`) + reset programático em `/settings`; sidebar ganha entries "Samples" e "Ajuda"; a11y via auto-associação Label↔Input nos helpers `InlineLabeled` (SegmentEditor) e `InlineField` (CaseFormPage) usando `useId` + `cloneElement` — cobre 4 forms principais sem refactor amplo; `aria-required`/`aria-invalid`/`aria-describedby` injetados automaticamente; `StaleSolverBanner` ganha `role="status"` + `aria-live="polite"`; print stylesheet `@media print` em `index.css` com A4 portrait + `@page` 15mm/12mm de margens, ativado via classe `print-area` no wrapper de CaseDetailPage; pendência F6 fechada com 6 testes E2E do popover BuoyPicker via `@testing-library/user-event`; `tools/perf_watchcircle.py` profila 4 cenários functional + 2 preview F7/F8 (flag `--include-preview-cases`) com targets <30s gate / <5s aspirational. **DESCOBERTA CRÍTICA**: 2/4 cenários functional violam gate <30s (Spread 4×: 56s, Shallow chain 4×: 86s) — pendência crítica registrada para F10 com 4 estratégias candidatas (paralelização ThreadPoolExecutor, caching agressivo, redução de tolerâncias, vectorização). i18n NO-GO consciente para v1.0. Suite: 554 backend + 4 skipped + 102 frontend verdes (+36 testes frontend, zero regressão backend). Ver `docs/relatorio_F9_ui_polish.md` e `docs/relatorio_F9_perf_watchcircle.md`.
- ✅ **F-prof.8** — AHV (Anchor Handler Vessel): paridade total com QMoor alcançada. `LineAttachment.kind="ahv"` aplica carga estática horizontal num ponto da linha durante operação de instalação. **Idealização modelada explícita** documentada em 3 níveis (D018 + Memorial PDF + manual F11). Schema com 4 campos (`ahv_bollard_pull` + `ahv_heading_deg` em referencial eixo X global anti-horário + 2 metadados opcionais); validação Pydantic cruzada (required quando `kind="ahv"`). Solver multi-segmento estendido em [`backend/solver/multi_segment.py`](backend/solver/multi_segment.py): nova função `_signed_force_2d` retorna tupla `(H_jump, V_jump)`; `_integrate_segments` agora trata H per-segmento (era constante ao longo da linha) — H_local cresce/decresce a cada junção AHV; `_solve_suspended_tension` ajusta para H_fairlead = H_anchor + sum_H_jump no residual e bracket. `_signed_force` legado preservado (retorna 0 em AHV) para retro-compat. **D018** (warning, medium) sempre dispara em AHV — sem opção de esconder, decisão Q6 não-negociável; **D019** (warning, high, Ajuste 1) alerta quando heading resulta em projeção <30% no plano vertical da linha (engenheiro digita bollard alto + heading perpendicular → vê resultado idêntico ao caso sem AHV; D019 evita confusão). 4 BC-AHV-01..04 vs cálculo manual com **erro 0.0000%** (catenária paramétrica é exata; sem incerteza de modelo elástico como em F7). Memorial PDF inclui seção "AHV — Domínio de aplicação" com 3 parágrafos cobrindo descrição da idealização + uso válido + delimitação de escopo; 5 strings-chave verificadas via PyPDF (`idealização`, `não substitui`, `análise dinâmica`, `snap loads`, `Anchor Handler Vessel`). AHV + uplift bloqueado com mensagem clara (extensão natural F7); AHV + boia/clump em multi-seg suportado (Q5). Frontend: `AttachmentsEditor` ganha "AHV (Fase 8)" no Select kind; campos Bollard pull (UnitInput) + Heading (Input com tooltip de referencial) substituem campos buoy/clump quando kind=ahv; sample `ahv-pull` destravado (BC-AHV-01 carregado funcionalmente); 2 verbetes glossário (`ahv`, `bollard-pull`) destravados — definição de AHV cita D018 + Memorial PDF + manual F11. Pendência v1.1+: ícone dedicado AHV em junção com seta heading (atualmente usa ícone startpoint AHV de F3/D7); pitch da força AHV (Fz não-zero); 3D fora do plano (F12). Suite: 666 backend + 2 skipped + 119 frontend verdes (+32 backend testes ativos, +14 frontend; zero regressão F1-F7+F9). **Status pós-F8: AncoPlat alcança paridade total de features com QMoor**. Próxima: F10 V&V completo. Ver `docs/relatorio_F8_ahv.md`.
- ✅ **F-prof.7** — Anchor uplift (suspended endpoint): bloqueio físico mais antigo do MVP v1 finalmente removido. Solver hoje rejeitava `endpoint_grounded=False` com `NotImplementedError` desde a Fase 1; agora habilita catenária livre PT_1 (fully suspended, MoorPy taxonomy) para single-segmento sem attachments. `BoundaryConditions.endpoint_depth: Optional[float]` em `backend/solver/types.py` com `@model_validator` que falha rápido (Pydantic) em 4 cenários inválidos (depth ausente quando suspended, ≤0, >h+ε); novo módulo `backend/solver/suspended_endpoint.py` (~320 linhas) com `solve_suspended_endpoint()` + função interna `_solve_uplift_tension_mode` que aceita `s_a < 0` (vértice virtual entre anchor e fairlead em "U" — diferente da versão upstream que rejeita; crítico para destravar BC-MOORPY-05); dispatcher no facade `solve()` delega para suspended_endpoint quando endpoint_grounded=False, single-seg, sem attachments — multi-seg+uplift e attachments+uplift levantam `NotImplementedError` específico → INVALID_CASE com mensagem clara (Q3=b reserva F7.x); `tools/moorpy_env/regenerate_uplift_baseline.py` + `docs/audit/moorpy_uplift_baseline_2026-05-05.json` (5 BC-UP); **5 BC-UP-01..05 verde com erro real ≤ 0.25%** (gate Q5 era 1%, folga de 4×); **2 BC-MOORPY destravados** (04 e 05 que estavam skipados desde Fase 1) — 9 BC-MOORPY ativos pós-F7 (era 7); D016 (high, error) "anchor uplift fora de domínio" + D017 (medium, warning) "uplift desprezível < 1m" sugerindo `endpoint_grounded=True` para regime numericamente mais robusto; frontend com radio Grounded/Suspended na aba Ambiente, input condicional `endpoint_depth`, `CatenaryPlot.anchorY = -endpoint_depth` (translação no plot via endpoint_depth — uniforme com grounded onde endpoint_depth ≈ water_depth), sample `anchor-uplift` destravado (era preview F9 → carrega BC-UP-01 funcional), verbete glossário `anchor-uplift` destravado. **Convenção MoorPy descoberta**: `Catenary.catenary` retorna `(FxA, FzA, FxB, FzB, info)` — anchor end PRIMEIRO, fairlead DEPOIS (não HF/VF/HA/VA como signature sugere); leitura inicial errada produziu swap T_anchor↔T_fl com erro de 6%. F7 é feature completa sem ressalva (≠ F8 que carrega "AHV idealização estática"). Suite: 610 backend + 2 skipped + 105 frontend verdes (+56 backend, +3 frontend; zero regressão F1-F6+F9). Pendências F10: re-rodar `perf_watchcircle.py` com cenários uplift reais; calibrar BC-UP de rtol=1e-2 para 1e-4 se possível. Pendência F7.x: multi-seg + uplift, attachments + uplift, pendant visual. Ver `docs/relatorio_F7_anchor_uplift.md`.

### Decisão fechada — ProfileType taxonomy (Fase 4 / Q1)

O AncoPlat adota o vocabulário **ProfileType** do MoorPy/NREL (`Catenary.py:147-163`) para classificar regimes catenários. Enum forward-compat com 10 valores (`PT_0..PT_8 + PT_U`) — alguns reservados para fases futuras (PT_4 boiante = Fase 12, PT_5 U-shape = Fase 7+). Classificador puro em `backend/solver/profile_type.py` com tolerâncias calibradas. Mesmo padrão das outras decisões fechadas: vocabulário comum com a referência (MoorPy) sem nivelamento por baixo — divergências são registradas e categorizadas (Categoria 1 bug / 2 modelo / 3 numérica), nunca forçadas a match cosmético.

### Critério `confidence` no SolverDiagnostic (Fase 4 / Q7)

Cada `SolverDiagnostic` tem um campo `confidence: high | medium | low` documentando o tipo de violação:

- **high** — violação determinística (matemática ou física). Diagnóstico SEMPRE correto quando dispara. Default de retro-compat. Exemplos: D001..D011 originais, D012, D014, D015.
- **medium** — heurística calibrada empiricamente. Pode ter falso positivo em casos extremos legítimos. Exemplos: D013 (limiar 0.3 calibrado contra catálogo), P004, D008.
- **low** — pattern detection sem base teórica forte. RESERVADO — ainda nenhum diagnóstico nesta categoria. Exigirá justificativa explícita no docstring quando aparecer.

Critério permanente — registrado no docstring de `ConfidenceLevel` em `diagnostics.py`.

### Decisão fechada — Grounded pontilhado vermelho (Fase 3 / D6)

O AncoPlat exibe a porção apoiada (grounded) da linha como **linha pontilhada vermelha** (`dash: 'dot'`, cor ≈ `#DC2626`). O QMoor 0.8.5 usa **cinza pontilhado**. Adotamos vermelho como decisão consciente porque (1) destaca melhor a porção apoiada do que cinza, especialmente em plots com tema claro/escuro; (2) princípio transversal #4 do plano de profissionalização — "MoorPy/QMoor são referência de validação, não target de paridade total" — então cinza seria nivelamento por baixo sem ganho técnico; (3) engenheiros novos vindos do QMoor reconhecem o padrão "sólido = suspended, pontilhado = grounded" pela textura, não pela cor.

Plano §274 documenta. Ver também `docs/relatorio_F3_quick_wins.md` §3.
- ✅ F5.7.1 — Boias na zona apoiada com força de elevação (lifted arches). Modelo físico: `s_arch = F_b / w_local` (equilíbrio vertical na boia, simétrico em material uniforme). Cada metade do arco é catenária com vértice em cada touchdown e kink na boia. Solver detecta automaticamente boias com posição em `[0, L_g_total]` em material uniforme e substitui o walk linear flat por integração com arches via `backend/solver/grounded_buoys.py`. Boias em junção heterogênea (chain↔wire) seguem o caminho legacy F5.2 (junction force jump). Suite: 281 testes (266 baseline + 15 BC-AT-GB-*) verde. Frontend rederiva `onGround` ponto-a-ponto comparando `y` ao seabed line — corrige o critério antigo `x ≤ td` que não distingue arches no grounded. Hover bidirecional na legenda↔segmento implementado na mesma fase (legenda do CatenaryPlot interativa).
- ✅ **Fase 10 — V&V completo (gate de release v1.0)** — fechada em 2026-05-05. 11 commits atômicos + 1 fix. Catálogo **VV-01..14** unificado em `backend/solver/tests/test_vv_v1.py` (5 vs MoorPy + 1 slope mirror + 2 multi-segmento + 6 cálculo manual) com erro real medido por caso serializado em `docs/audit/vv_v1_errors.json`. **Watchcircle paralelizado com ProcessPoolExecutor** (ThreadPool descartado por GIL-bound) — Spread 4× foi de 56s → 16.6s, 3/4 cenários atingem gate <20s; shallow chain 4× em 24.8s aceito como pendência v1.1 conforme spec Q1. **Gate p95 <100ms** validado em 5 endpoints REST. Round-trip unidades SI ↔ {N, kN, te, N/m, kgf/m} em 59 testes rtol<1e-10. Robustez: 8 casos extremos (R1..R8) sem crashar. Apply tests cobrem 100% dos 16 diagnostic codes (5 garantidos + 6 xfail informativos com Q5-style reason + 5 misc). Identidade V_hemi vs V_conic com anti-identity test para h_cap≠r. Cobertura 96% agregado (críticos ≥98% NÃO atingido — backlog v1.1 documentado honestamente em `relatorio_F10_C6_coverage.md`). Suite: 665 backend + 5 skipped + 6 xfailed + 181 frontend verdes. Pendências v1.1: BC-UP-06..10 + BC-AHV-05..10 (lista detalhada no relatório), VV-07/08 via MoorPy Subsystem, watchcircle shallow chain heurística pré-fsolve. Ver [`relatorio_F10_vv_completo.md`](docs/relatorio_F10_vv_completo.md) e [`relatorio_VV_v1.md`](docs/relatorio_VV_v1.md).
- ✅ **Fase 11 — Documentação & lançamento v1.0** — fechada em 2026-05-05. 9 commits atômicos de documentação + tooling + tag pre-release. Entregas: (i) `docs/decisoes_fechadas.md` consolidado com **13 decisões** físicas/numéricas/arquiteturais (cada uma com fase de origem + justificativa + referência canônica + link); (ii) `docs/manual_usuario.md` rewrite estruturado em **12 seções** cobrindo F5-F10, com seção AHV obrigatória (§7, 6 pontos: domínio, idealização vs real, quando usar, quando NÃO usar, D018/D019, exemplo numérico) — fecha gate F8 retroativamente (D018+Memorial+manual); (iii) `CHANGELOG.md` formato Keep a Changelog 1.1.0 com seção destacada **⚠ Mudanças numéricas** citando commit hash + tag de origem para cada uma (7 mudanças catalogadas); (iv) `docs/release_notes_v1.0.md` com matriz de compatibilidade backward + 14 pendências v1.1 + roadmap v1.0.x→v1.1.0→v2.0.0; (v) `tools/smoke_prod.sh` com `set -euo pipefail` (falha fechado per Q9) + 7 asserções via curl+jq cobrindo health/catálogo/solve/memorial PDF/.moor round-trip/watchcircle; (vi) `docs/rollback_v1.0.md` com 3 níveis (código <5min / DB <10min / catastrófico ~30min) + critério explícito de escalação entre níveis (Q8); (vii) atualizações CLAUDE.md + plano. **Tag v0.10.0-pre-release** criada como âncora de rollback; **tag v1.0.0** criada apenas após smoke prod + 48h uptime validado (gate de release). **Princípios anti-erro reforçados**: zero feature nova, tag = exact commit pós-validação, smoke prod é gate, 48h uptime é tempo real não-negociável. Suite preserved: 665 backend + 5 skipped + 6 xfailed + 181 frontend verdes (zero mudança em código, apenas docs + tooling). Ver [`relatorio_F11_lancamento.md`](docs/relatorio_F11_lancamento.md).

### Documentação de referência (ordem de leitura recomendada)

**Para Claude (briefing operacional):**
1. **Este arquivo** (CLAUDE.md) — briefing + decisões fechadas (formato denso, status fases).
2. [`docs/plano_profissionalizacao.md`](docs/plano_profissionalizacao.md) — plano canônico das fases F0-F12.

**Para humano (auditoria + uso):**
3. [`docs/decisoes_fechadas.md`](docs/decisoes_fechadas.md) — **documento canônico para auditoria científica externa** com 13 decisões físicas/numéricas/arquiteturais. Outro engenheiro/revisor/peer review deve começar aqui.
4. [`docs/manual_usuario.md`](docs/manual_usuario.md) — manual completo v1.0 em 12 seções (PT-BR, termos técnicos em inglês quando padrão internacional).
5. [`docs/release_notes_v1.0.md`](docs/release_notes_v1.0.md) — release notes v1.0.0 com migração v0.x→v1.0 + roadmap.
6. [`CHANGELOG.md`](CHANGELOG.md) — Keep a Changelog 1.1.0 com seção ⚠ Mudanças numéricas (hash + tag).

**Spec técnica + revisor:**
7. [`docs/Documento_A_Especificacao_Tecnica_v2_2.docx`](docs/Documento_A_Especificacao_Tecnica_v2_2.docx) — especificação técnica canônica do domínio.
8. [`docs/Documento_B_Checklist_Revisor-RESPONDIDO.docx`](docs/Documento_B_Checklist_Revisor-RESPONDIDO.docx) — respostas do engenheiro revisor.

**Operações:**
9. [`docs/operacao_producao.md`](docs/operacao_producao.md) — SSH, logs, deploy, backup, SSL, firewall.
10. [`docs/rollback_v1.0.md`](docs/rollback_v1.0.md) — plano de rollback do release v1.0.0 (3 níveis + critério de escalação).

Em caso de conflito entre docs: o **Documento A v2.2** é canônico para domínio; este CLAUDE.md registra qualquer override com justificativa (ver seções "Decisões de projeto"); `docs/decisoes_fechadas.md` é a versão consolidada para auditoria externa.

## Decisões de projeto — Fase 1a (catálogo)

Tomadas após inspeção de `docs/QMoor_database_inventory.xlsx` (522 entradas, 16 tipos, 100% imperial, 100% `data_source=legacy_qmoor`). Substituem qualquer ambiguidade da Seção 4.2 do Documento A.

### Rigidez axial EA
- Schema preserva ambas as colunas `qmoor_ea` e `gmoor_ea` (nomes do xlsx mantidos).
- **Default do solver: `qmoor_ea`** — preserva comportamento do QMoor 0.8.5 original, que é o baseline de validação do projeto.
- Cada caso pode sobrescrever via campo `ea_source: "qmoor" | "gmoor"` (default `"qmoor"`).
- Motivação: poliéster exibe razão `gmoor_ea/qmoor_ea` de 10–22×; wires EIPS ~1,45×; correntes ~0,88×.

### Modelo físico de QMoor vs GMoor (decisão fechada — Fase 0 / B0.2)

A premissa "não há base documental para escolher `gmoor_ea`" registrada na origem foi resolvida por inspeção do [MoorPy](https://github.com/NREL/MoorPy) (NREL, open-source, peer-reviewed em ASME 2025) durante a Fase 0 do plano de profissionalização. O modelo físico canônico é (`moorpy/line.py:1027-1044` e `moorpy/library/MoorProps_default.yaml`):

```
EA_estatico   = EA_MBL × MBL                    [QMoor — default]
EA_dinamico   = EAd  × MBL  +  EAd_Lm × T_mean  [GMoor — opcional]
              = α     +     β     × T_mean
```

Semântica:
- **QMoor** (`qmoor_ea`) ≡ `EA_estatico` (`EA_MBL × MBL`). Rigidez quasi-estática, válida para análise de carga lentamente aplicada. **Default permanente do AncoPlat.**
- **GMoor** (`gmoor_ea`) ≡ termo `α` (`EAd × MBL`) do modelo dinâmico. Rigidez dinâmica de offset — corresponde ao comportamento de curto prazo (após relaxamento elástico, antes de creep). Aplicável quando o caso requer análise de tensão dinâmica.

#### β (`EAd_Lm`) NÃO implementado em v1.0

`β` modela rigidez dinâmica linear no carregamento médio (slope da rigidez vs tensão). É a parte que torna o modelo verdadeiramente linear em `T_mean`. **Não está implementado na v1.0 — campo opcional reservado, valor padrão 0** (modelo dinâmico simplificado para `α` constante, equivalente a usar `gmoor_ea` direto). Reavaliar em Fase 4 ou pós-1.0 conforme demanda. Quando implementado, exigirá iteração externa: estima `T_mean` → calcula `EA(T_mean)` → solve catenária → atualiza `T_mean` → repete até convergência.

#### Tooltip canônico (UI)
"EA estático (QMoor): rigidez quasi-estática (carga lentamente aplicada). EA dinâmico (GMoor): rigidez de curto prazo após relaxamento, aplicável em análise de tensão dinâmica. Modelo NREL/MoorPy."

### Atrito de seabed per-segmento (decisão fechada — Fase 1 / B3)

Implementado na Fase 1 do plano de profissionalização. Helper centralizado `_resolve_mu_per_seg` no `backend/solver/solver.py` resolve o coeficiente efetivo de cada segmento aplicando precedência canônica:

```
1. segment.mu_override         — override explícito do usuário
2. segment.seabed_friction_cf  — valor do catálogo (line_type)
3. seabed.mu                   — valor global do caso
4. 0.0                         — fallback final
```

Decisão consciente — **NÃO há feature-flag `use_per_segment_friction`** (originalmente prevista em R1.1 do plano). Defaults `None` em `mu_override` e `seabed_friction_cf` preservam comportamento legado naturalmente: quando ambos são `None`, solver cai no `seabed.mu` global, equivalente a antes da Fase 1. Cases salvos em produção (`docs/audit/cases_baseline_2026-05-04.json`) re-rodam com mesmo resultado dentro de `rtol=1e-9` — verificado por `test_baseline_regression.py` que entra como gate em todo PR que toque `backend/solver/`.

Validação física: `BC-FR-01` em `test_friction_per_seg.py` confirma `ΔT = μ · w · L_grounded` (Coulomb axial) dentro de ±2% do cálculo manual em regime onde `T_anchor > 0`.

### Atrito de seabed — anomalia R5Studless
- `seabed_friction_cf` é uniforme dentro de cada categoria exceto em `StudlessChain`:
  - R4Studless (63 entradas): μ = 1,0
  - R5Studless (41 entradas): μ = 0,6
- **Valores do catálogo preservados sem alteração.** Princípio: não modificar dado legado silenciosamente.
- Anomalia registrada aqui como pendência para validação com o engenheiro revisor.
- Hierarquia de precedência em runtime: solo informado pelo usuário > catálogo da linha (Seção 4.4 do Documento A).

### Primary key e rastreabilidade
- `id INTEGER PRIMARY KEY AUTOINCREMENT` (gerado pelo SQLite).
- **Extensão do schema**: adicionar coluna `legacy_id INTEGER` preservando o id original do xlsx (1–522). Permite auditoria contra o catálogo QMoor e evita colisões quando o usuário adicionar entradas próprias. Entradas criadas pelo usuário têm `legacy_id = NULL`.

### Conversão de unidades na seed
- Todas as 522 entradas estão em imperial — conversão para SI acontece no momento da importação (via Pint).
- `seabed_friction_cf` é adimensional — não converte.
- Armazenamento final: 100% SI (m, N, kg, Pa). `base_unit_system` da entrada reflete unidade **de origem**, não de armazenamento.

### Limpeza do xlsx
- Colunas fantasma do Excel (índices 17–26 sem cabeçalho) são descartadas.
- `comments`, `manufacturer`, `serial_number` estão 100% NULL no catálogo legado; importadas como NULL.

## Decisões de projeto — Fase 1b (solver)

Tomadas durante F1b para resolver situações onde a Seção 3 do Documento A v2.2 era ambígua ou insuficiente. **Todas validadas por benchmarks contra MoorPy** (9/9 BCs dentro das tolerâncias).

### Catenária na forma geral (âncora pode ter V_anchor > 0)
A Seção 3.3.1 do Documento A apresenta equações assumindo âncora no vértice (V_anchor=0). Isso é um caso particular. O BC-01 (T_fl=785 kN) exige V_anchor > 0 — linha quase taut, anchor pull-up acentuado. O solver implementa a **forma geral** parametrizada por `s_a ≥ 0` (arc length do vértice virtual ao anchor), cobrindo tanto V_anchor=0 (touchdown iminente) quanto V_anchor > 0 (fully suspended típico). Ver docstring de [backend/solver/catenary.py](backend/solver/catenary.py).

### Loop elástico via brentq (não ponto-fixo)
A iteração ingênua `L_{n+1} = L·(1 + T̄(L_n)/EA)` **diverge por oscilação** em casos de linha muito taut (L_stretched próximo de √(X²+h²)), notadamente BC-05. Substituído por `scipy.optimize.brentq` sobre `F(L_eff) = L_eff − L·(1+T̄/EA) = 0`, com bracket explícito em limites físicos. Robusto em todos os 45 testes. Ver [backend/solver/elastic.py](backend/solver/elastic.py).

### BCs redefinidos (liberdade da Seção 6.2)
A Seção 6.2 do Documento A listava BC-02/07/08/09 com "entradas a definir". Além disso, **BC-04 e BC-05 com os parâmetros do Documento A são fully suspended, não touchdown** (T_fl_crit ≈ 426 kN < T_fl=1471 kN → sem grounded segment). Rótulo "com touchdown" do BC-04/05 é incorreto. Para ter touchdown real, BC-02/08/09 foram redefinidos com h=300, L=700, T_fl=150 kN, wire rope 3" (T_fl_crit ≈ 194 kN → touchdown garantido). BC-07 com h=100, L=2000, T_fl=30 kN para grande grounded. Documentação detalhada em [docs/relatorio_F1b.md](docs/relatorio_F1b.md) e docstrings dos testes.

### Fallback de bisseção NÃO implementado (divergência vs Documento A)
A Seção 3.5.1 do Documento A menciona "Fallback: bisseção pura se Brent não convergir em 50 iterações" e `SolverConfig.max_bisection_iter=200`. O código usa **apenas brentq** (que internamente já é um método híbrido Brent-Dekker com fallback de bisseção nativo). Como brentq nunca falhou em nenhum dos 45 testes, o fallback manual seria redundante. `max_bisection_iter` foi removido do schema.

### Documento A — changelog v2.3 consolidado
As correções das decisões acima estão consolidadas em [`docs/Documento_A_v2_3_changelog.md`](docs/Documento_A_v2_3_changelog.md) para eventual geração de um novo `.docx`. Até que isso aconteça, o changelog + este CLAUDE.md são as fontes autoritativas das divergências em relação ao v2.2.

## Decisões de projeto — Fase 2 (API e persistência)

Estabelecidas durante a auditoria estratégica pré-F2. Detalhes em [docs/plano_F2_api.md](docs/plano_F2_api.md).

### Autenticação: zero
Aplicação local (localhost). Firewall do macOS protege. Nada de tokens, cookies, basic auth. Se o projeto virar multiusuário, revisitar.

### Formato `.moor` = JSON próprio do AncoPlat
O `.moor` original do QMoor 0.8.5 estava em binário proprietário (`.pyd` do módulo `cppmoor`). Impossível replicar. `.moor` exportado daqui é JSON com schema compatível com a Seção 5.2 do MVP v2 PDF.

### Persistência de execuções
Cada chamada de solve persiste um `execution_record` com timestamp. **Mantém-se as últimas 10 execuções por caso**; mais antigas são truncadas.

### Âncora sempre no seabed (v1)
MVP v1 **rejeita** `endpointGrounded=false` com INVALID_CASE + mensagem. Casos com anchor elevado ficam para v2+.

### Critérios de utilização: 4 perfis disponíveis desde v1
Conforme Seção 5 do Documento A: `MVP_Preliminary` (default, 0.60 MBL), `API_RP_2SK` (intacto 0.60 / danificado 0.80), `DNV` (placeholder; formal só em v3+ com análise dinâmica), `UserDefined`. `SolverResult` retorna `alert_level: ok | yellow | red | broken`.

## Sequência v1.0 do plano de profissionalização

**Decisão fechada (2026-05-05):** AncoPlat v1.0 tem **paridade total de features com QMoor**. Sequência de fechamento:

```
F9 (UI polish, M 4–6 dias)
 → F7 (Anchor uplift, L 8–12 dias)
 → F8 (AHV, L 8–12 dias)
 → F10 (V&V completo, L 10–12 dias)
 → F11 (lançamento 1.0, M 3–5 dias)
```

Total restante: **~40–55 dias-engenheiro**. Mini-planos detalhados das próximas fases ficam em [`docs/proximas_fases/`](docs/proximas_fases/).

Pós-v1.0: Fase 12 (features avançadas opcionais — library paramétrica MoorPy, modelo de custo, batimetria 2D, integração RAFT). F12 não entra em v1.0.

### Decisão fechada — Fase 8 antecipada (AHV idealização estática)

AHV (Anchor Handler Vessel) modelado como força lateral estática num ponto da linha **é idealização modelada**, não representação fiel da operação real (rebocador dinâmico, cabo oscila, hidrodinâmica). Mitigação **obrigatória** registrada antes de F8 começar — sem isso F8 não fecha:

1. **Diagnostic D018** (severity warning, confidence medium) ao ativar AHV no caso. Mensagem: "Análise estática de AHV é idealização — não substitui análise dinâmica de instalação."
2. **Memorial PDF** com parágrafo dedicado ao domínio de aplicação quando AHV está presente.
3. **Manual de usuário** (Fase 11) com seção sobre quando recomendar análise dinâmica externa.

Plano §F8 será expandido com esses 3 itens como AC obrigatórios quando F8 iniciar. Princípio transversal: features que envolvem idealização explícita carregam ressalva permanente, não opcional.

## Pendências F1–F6 → Fases futuras

Itens identificados durante as fases F1–F6 que não entraram no escopo da fase original e foram empurrados para fases posteriores.

### Para Fase 9 (UI polish)
- **Testes E2E do popover BuoyPicker** (F6) — smokes atuais em `frontend/src/test/buoy-picker-smoke.test.tsx` cobrem render + fallback id + callbacks, mas não exercitam o popover Radix (portal + lista clicável). Esperar `@testing-library/user-event` flow completo: abrir popover → digitar busca → selecionar boia → confirmar `onPick` chamado com payload correto.

### Para Fase 10 (V&V completo)
- **Identidade matemática `V_hemi = V_conic`** (F6) — caso onde fórmulas de hemispherical e semi_conical produzem volumes idênticos pela especificação do Excel `Formula Guide` R5/R7. Bug que troque hemi↔conic não é detectável pelo gate ±1% atual de `test_buoy_buoyancy.py`. Adicionar 1 caso na F10 com **dimensão tampa ≠ raio** (ex.: tampa hemisférica com altura customizada h ≠ D/2) onde as duas fórmulas produziriam resultados distintos, garantindo que estão de fato implementadas separadamente. Documentado em `docs/relatorio_F6_buoys.md` §6.
- **Boias com `manufacturer`** (F6) — catálogo seed atual de 11 boias (1× excel_buoy_calc_v1 + 10× generic_offshore) não inclui modelos comerciais reais. F10 ou pós-v1.0 pode adicionar entradas com `data_source="manufacturer_<X>"` (Crosby, Trelleborg, etc.) quando houver documentação de campo.

### Para Fase 7 (Anchor uplift, próxima após F9)
- Mini-plano detalhado em [`docs/proximas_fases/F7_anchor_uplift_miniplano.md`](docs/proximas_fases/F7_anchor_uplift_miniplano.md). 8 commits propostos, BC-UP-01..05 vs MoorPy, D016/D017 dedicados.

### Para v1.1+ (pós-v1.0)
- **Library paramétrica MoorPy** (origem F6 / Q1) — schema `material_coefficients` espelhando `MoorProps_default.yaml` + endpoint `POST /line-types/from-parametric` + tab "Calculadora paramétrica" no `LineTypePicker`. Reservada para **Fase 12.x**. Catálogo legacy de 522 entradas cobre uso prático em v1.0.
- **`.moor` schema com `slope_rad` + `attachments`** (origem F2 / F5) — `.moor` v2 atual não cobre esses campos. Round-trip dos baseline cases skipa quando aplicável. Reservar bump v3 para fase pós-v1.0 quando houver redemanda real.
- **Mooring system samples** (origem F9) — `mooringSystemTemplates.ts` + tab dedicada em /samples. Pendência v1.1+.
- **Print stylesheet de MooringSystemDetailPage** (origem F9) — F9 entrega print apenas para CaseDetailPage. MS detail v1.1+.

## Convenções de código

- Backend: type hints obrigatórios, docstrings em funções públicas
- Testes com pytest, casos de benchmark numerados BC-01 a BC-10
- Commits em português, padrão Conventional Commits (feat:, fix:, chore:, docs:, test:)
- Manter assinatura "Co-Authored-By: Claude Opus 4.7" nos commits

## Documentação técnica

- `docs/Documento_A_Especificacao_Tecnica_v2_2.docx` — briefing principal
- `docs/Documento_B_Checklist_Revisor-RESPONDIDO.docx` — respostas técnicas do engenheiro revisor
- `docs/QMoor_database_inventory.xlsx` — catálogo de materiais (fonte de dados)
- `docs/Documentacao_MVP_Versao_2_QMoor.pdf` — documentação original do escopo
- `docs/Cópia de Buoy_Calculation_Imperial_English.xlsx` — fórmulas de boia (uso futuro v2.1)
