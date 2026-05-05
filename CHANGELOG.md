# Changelog

Todas as mudanças notáveis do AncoPlat estão documentadas neste
arquivo.

O formato segue [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/),
e o projeto adere a [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html).

> **Princípio de reprodutibilidade científica:** mudanças que afetam
> resultado numérico de cases salvos aparecem em seção destacada com
> ⚠ e citam **commit hash + tag de origem**. Engenheiro reproduzindo
> case pode bisseccionar entre versões com rastreabilidade completa.

---

## [Unreleased]

Pendências v1.1 não-bloqueantes (vide
[`docs/release_notes_v1.0.md`](docs/release_notes_v1.0.md) §Roadmap):

- Watchcircle shallow chain 4× — heurística pré-fsolve.
- Cobertura ≥98% módulos críticos.
- Apply tests determinísticos para D003/D007/D008/D011/D012/D015.
- VV-07/08 via MoorPy Subsystem (atual: cross-check interno).
- BC-UP-06..10 + BC-AHV-05..10 (lista detalhada em
  [`docs/relatorio_F10_vv_completo.md`](docs/relatorio_F10_vv_completo.md)).

---

## [1.0.0] — 2026-05-XX

Primeiro release público estável. Paridade total com QMoor 0.8.5
alcançada e validada contra MoorPy v1.x (NREL).

### ⚠ Mudanças numéricas (afetam resultado de cases salvos)

> Cases salvos em v0.x produzem resultado **idêntico** em v1.0 dentro
> de `rtol=1e-9` (gate `cases_baseline_regression.py`) **se** não
> ativarem nenhuma das features abaixo. Ativá-las produz resultado
> novo — investigar antes de comparar.

- **Atrito per-segmento via precedência canônica**
  (`mu_override → seabed_friction_cf → seabed.mu → 0.0`).
  - Origem: F-prof.1, commit `e83c6b5`, tag `v0.6-fase1`.
  - Cases sem `mu_override` e sem `seabed_friction_cf` per-seg
    preservam comportamento global anterior (gate baseline_regression).
  - Cases que ativarem qualquer um dos overrides produzem resultado
    diferente — investigar.
  - Validação: BC-FR-01 (capstan manual) ±2%.

- **Toggle EA estático (qmoor) vs dinâmico (gmoor)**
  (campo `LineSegment.ea_source: "qmoor" | "gmoor"`, default `qmoor`).
  - Origem: F-prof.1, commit `4ea2a47` (schema) +
    `76176c0` (UI toggle), tag `v0.6-fase1`.
  - Default `qmoor` preserva comportamento anterior (rigidez
    quasi-estática `EA_MBL × MBL`).
  - Trocar para `gmoor` em segmento de poliéster pode alterar
    resultado em 10-22× na rigidez axial.
  - Validação: BC-EA-01 (ratio gmoor/qmoor por categoria).

- **Batimetria 2 pontos com slope derivado**
  (input `startpoint_depth + h` na aba Ambiente).
  - Origem: F-prof.2, commit `85511c5`.
  - Cases que usam o modo "slope direto" (avançado, escondido por
    default) preservam comportamento anterior.
  - Cases construídos via UI nova (modo "batimetria 2 pontos")
    derivam `slope_rad` automaticamente — round-trip preserva
    `rtol=1e-9`.

- **Lifted arches (boias na zona apoiada de material uniforme)**.
  - Origem: F5.7.1, commit `a271ca8`.
  - Cases SEM boia na zona apoiada preservam comportamento anterior.
  - Cases com boia em material UNIFORME e em
    `position_s_from_anchor` ∈ `[0, L_grounded_total]` agora geram
    arcos catenários simétricos com `s_arch = F_b/w` em vez de walk
    linear flat. Resultado é fisicamente correto e diverge do
    comportamento legado.
  - Boias em junção heterogênea (chain↔wire) preservam caminho
    legacy F5.2 (force jump na junção).

- **ProfileType taxonomy NREL/MoorPy**
  (campo `SolverResult.profile_type` enum).
  - Origem: F-prof.4, commit `613727b`.
  - Resultado numérico das tensões/forças é IDÊNTICO ao anterior;
    mudança é apenas de classificação/labeling.
  - Mas: cases salvos em v0.x não tinham `profile_type` no schema.
    Re-rodar gera o campo novo no resultado.

- **Anchor uplift (single-segmento sem attachments)**
  (`endpoint_grounded=False` + `endpoint_depth`).
  - Origem: F-prof.7, commits `dc03b9b` (solver core) +
    `d21916c` (dispatcher facade).
  - Feature **NOVA** em v1.0 — cases v0.x não podiam ter
    `endpoint_grounded=False` (era rejeitado com
    `NotImplementedError`).
  - 2 cases (BC-MOORPY-04, BC-MOORPY-05) que estavam skipados na
    suite desde F1 agora estão ativos com rtol=1e-2 vs MoorPy.
  - Validação: BC-UP-01..05 vs MoorPy uplift baseline com erro real
    ≤ 0.25%.

- **AHV (Anchor Handler Vessel) — H per-segmento no solver**.
  - Origem: F-prof.8, commit `18da690`.
  - Feature **NOVA** em v1.0 — cases v0.x não podiam ter
    `kind="ahv"` em attachment.
  - Mudança arquitetural: solver multi-segmento agora trata
    componente H per-segmento (era invariante constante). Cases SEM
    AHV preservam mesmo resultado pré e pós-F8 (regressão
    `cases_baseline.json` rtol=1e-9). Cases COM AHV são novos.
  - Mitigação obrigatória D018 + Memorial PDF + manual de usuário §7
    (vide [`docs/decisoes_fechadas.md`](docs/decisoes_fechadas.md#9)).
  - Validação: BC-AHV-01..04 vs cálculo manual rtol=1e-2 (erro
    real **0.0000%**).

### Adicionado

- Manual de usuário rewrite estruturado em 12 seções
  ([`docs/manual_usuario.md`](docs/manual_usuario.md)).
- Documento canônico de decisões fechadas
  ([`docs/decisoes_fechadas.md`](docs/decisoes_fechadas.md)) com 13
  decisões físicas/numéricas/arquiteturais.
- Catálogo de boias profissionais (11 entradas seed) com tab
  dedicada em `/catalog?tab=buoys` (F-prof.6).
- Glossário canônico com 40 verbetes em rota `/help/glossary` (F9).
- 11 case templates em rota `/samples` (6 existentes + 5 novos
  F9: clump-weight, lifted-arch, sloped-seabed, anchor-uplift,
  ahv-pull) com filtro de busca.
- OnboardingTour DIY de 5 etapas com skip persistente em
  localStorage (F9).
- Mooring system (multi-linha) com plan view + equilíbrio sob carga
  ambiental + watchcircle 360° animado (F5.4 + F5.5 + F5.6).
- Comparação multi-sistema na lista de mooring systems (F5.4).
- Memorial PDF rastreável (hash SHA-256 + solver_version + timestamp
  em footer de cada página) com diagnostics estruturados e seção AHV
  obrigatória (F-prof.5).
- Exportação XLSX com 3-4 abas (Caso/Resultados/Geometria/Diagnostics).
- Exportação CSV de geometria ≥5000 pontos formato internacional.
- Importação `.moor` v2 com migrador v1→v2 e log estruturado.
- Print stylesheet A4 portrait para CaseDetailPage (F9).
- 16 diagnostics codes (D001..D015 + D900) com confidence levels +
  D018 (AHV idealização) + D019 (heading <30%).
- 36 BCs canônicos validados: 9 BC-MOORPY ativos + 5 BC-UP + 4
  BC-AHV + 7 BC-AT-GB + 14 VV-01..14.
- Performance gates: watchcircle <30s (paralelizado ProcessPool),
  endpoints REST p95 <100ms, round-trip unidades rtol<1e-10.

### Modificado

- Renomeação do app: **AncoPlat** (antes "QMoor Web", renomeado em
  2026 por questão de marca).
  - Commit: [`d7cdfb9`](commit/d7cdfb9).
  - Identificadores de dados que mantêm "qmoor" (`qmoor_ea`,
    `qmoor_database_inventory.xlsx`, `data_source: legacy_qmoor`)
    são referências ao software legado e ficam como rastreabilidade.
- Solver multi-segmento: integra junção a junção propagando
  H_local + V_local per-segmento (mudança arquitetural F-prof.8).
- Aba Ambiente refatorada com 3 grupos (Geometria/Fairlead/Seabed)
  e novo modo "batimetria 2 pontos" como default (F-prof.2).
- ProfileType passa a ser campo do `SolverResult` (espelha MoorPy).
- Diagnostics ganham campo `confidence: high | medium | low`
  (F-prof.4 / Q7).

### Corrigido

- Loop elástico convergia para tensão errada em near-taut quando
  iterado por ponto-fixo. Corrigido em F1b com `scipy.optimize.brentq`
  + bracket explícito.
  - Commit: F1b implementação inicial.
- ThreadPoolExecutor no watchcircle adicionava overhead em vez de
  speedup (solver é Python puro CPU-bound, não BLAS-pesado).
  Corrigido em F10/Commit 1 com ProcessPoolExecutor.
  - Commit: [`dd22d83`](commit/dd22d83).
- Convenção MoorPy `Catenary.catenary` retorna anchor PRIMEIRO
  (FxA, FzA, FxB, FzB, info), não HF/VF/HA/VA. Leitura inicial
  errada produzia swap T_anchor↔T_fl com erro ~6%.
  - Detalhes em [`docs/decisoes_fechadas.md`](docs/decisoes_fechadas.md#12).

### Segurança

- Autenticação básica HTTP em produção (vide
  [`docs/operacao_producao.md`](docs/operacao_producao.md) §7).
- Rate limit slowapi 100 req/min por IP (vide
  [`backend/api/main.py`](backend/api/main.py)).
- HTTPS via Let's Encrypt + nginx + auto-renew certbot.timer.
- SQLite com backup automático diário (vide
  [`docs/operacao_producao.md`](docs/operacao_producao.md) §9).
- Firewall UFW restritivo (vide
  [`docs/operacao_producao.md`](docs/operacao_producao.md) §10).

### Validação

- 665 testes backend + 5 skipped + 6 xfailed
- 181 testes frontend
- Cobertura agregada 96% (gap honesto vs meta 98% críticos
  documentado em
  [`docs/relatorio_F10_C6_coverage.md`](docs/relatorio_F10_C6_coverage.md)).
- Erros reais medidos por VV case em
  [`docs/audit/vv_v1_errors.json`](docs/audit/vv_v1_errors.json).

---

## Versões pré-release (tags v0.X)

Estes tags marcam o estado do código ao final de cada fase do plano
de profissionalização. Não são releases públicos — são âncoras de
desenvolvimento. Detalhes individuais nos relatórios em `docs/`.

- **v0.5-baseline** (2026-04-XX) — F-prof.0, snapshot pré-correções
  físicas.
- **v0.6-fase1** (2026-04-XX) — F-prof.1: atrito per-segmento +
  ea_source toggle.
- **v0.7-fase2** (2026-04-XX) — F-prof.2: batimetria 2 pontos +
  auditoria de validações.
- **v0.8-fase3** (2026-05-XX) — F-prof.3: quick wins UX (line
  summary, grounded vermelho, ícones startpoint, etc.).
- **v0.9-fase4** (2026-05-XX) — F-prof.4: diagnostics maturidade +
  ProfileType + confidence levels.
- **v0.10.0-pre-release** (a criar antes do deploy v1.0.0) — âncora
  de rollback do release v1.0.0.

---

## Convenção de versionamento

- **MAJOR** (`X.0.0`) — quebras de compatibilidade ou mudanças
  numéricas significativas que invalidam cases salvos.
- **MINOR** (`1.X.0`) — features novas backward-compatible. Cases
  v1.X re-rodam idênticos em v1.(X+1).
- **PATCH** (`1.0.X`) — bug fixes que NÃO afetam resultado numérico
  de cases salvos. Cases v1.0.0 produzem resultado idêntico em
  v1.0.X.

Mudanças numéricas que afetam cases salvos (mesmo que pequenas)
SEMPRE bumpam pelo menos MINOR e SEMPRE aparecem na seção
"⚠ Mudanças numéricas" deste arquivo com hash + tag.
