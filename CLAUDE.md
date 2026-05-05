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

### Documentação de referência (ordem de leitura recomendada)

1. **Este arquivo** (CLAUDE.md) — briefing + decisões fechadas.
2. [`docs/Documento_A_Especificacao_Tecnica_v2_2.docx`](docs/Documento_A_Especificacao_Tecnica_v2_2.docx) — especificação técnica canônica do domínio.
3. [`docs/plano_F2_api.md`](docs/plano_F2_api.md) — desenho da API (schemas SQL, request/response, erros).
4. [`docs/relatorio_F1b.md`](docs/relatorio_F1b.md) — estado e validações do solver.
5. [`docs/auditoria_estrategica_pre_F2.md`](docs/auditoria_estrategica_pre_F2.md) — auditoria pré-F2 (contexto de decisões tomadas).
6. [`docs/Documento_B_Checklist_Revisor-RESPONDIDO.docx`](docs/Documento_B_Checklist_Revisor-RESPONDIDO.docx) — respostas do engenheiro revisor.

Em caso de conflito entre docs: o **Documento A v2.2** é canônico para domínio; este CLAUDE.md registra qualquer override com justificativa (ver seções "Decisões de projeto").

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
