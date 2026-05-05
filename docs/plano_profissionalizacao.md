# AncoPlat — Plano de Profissionalização

> **Objetivo final:** levar o AncoPlat de "MVP funcional em produção" a **ferramenta profissional de engenharia de mooring**, correta fisicamente, ergonômica para uso por engenheiros offshore, validada contra referências canônicas e robusta a entradas adversas.
>
> **Documento gerado em:** 2026-05-04, baseado em três insumos:
> 1. Auditoria comparativa AncoPlat × QMoor (software comercial proprietário, prints fornecidos pelo usuário) realizada na mesma sessão.
> 2. Inspeção técnica de [MoorPy](https://github.com/NREL/MoorPy) (NREL, open-source, peer-reviewed em ASME 2025 — referência canônica de mooring quasi-estático em Python). Código-fonte lido em `moorpy/Catenary.py`, `moorpy/line.py`, `moorpy/system.py`, `moorpy/library/MoorProps_default.yaml`, `tests/test_catenary.py`.
> 3. Conteúdo de [CLAUDE.md](../CLAUDE.md), `docs/relatorio_F*.md` e código do repositório AncoPlat.
>
> **MoorPy** é adotado neste plano como **referência técnica secundária** para validação numérica e fonte documental de modelos físicos. É open-source, citável (DOI 10.11578/dc.20210726.1), usado em produção pela [RAFT](https://github.com/WISDEM/RAFT) (frequency-domain floating system simulator, NREL/WISDEM), e cobre o mesmo domínio do AncoPlat. Em vários pontos resolve incertezas que o software comercial proprietário deixava em aberto — notavelmente o significado físico de QMoor vs GMoor (modelo `EA_dynamic = EAd + EAd_Lm × T_mean`, ver Fase 1).
>
> **Status atual:** F0–F5.7 + F5.7.1 fechadas, 281 testes verdes, em produção em https://ancoplat.duckdns.org. Cobertura de paridade com QMoor ≈ 58%; vantagens próprias relevantes (F5.5/F5.6/F5.7.1, diagnostics estruturados, multi-system compare). Áreas onde o AncoPlat está atrás do MoorPy: modelo de EA dinâmico documentado, biblioteca paramétrica de materiais, ProfileType taxonomy explícita, matrizes de rigidez analíticas, modelo de custo. Áreas onde o AncoPlat está à frente do MoorPy: UI moderna, equilíbrio de plataforma sob carga ambiental (F5.5), watchcircle 360° animado (F5.6), lifted arches (F5.7.1), diagnostics estruturados, sistema de unidades comutável, importação .moor legacy.

---

## 1. Resumo executivo

O plano se organiza em **12 fases** (0 a 11), sequenciadas por: (i) bloqueios → (ii) correções físicas críticas → (iii) UX que fecha gaps com referência profissional → (iv) features de escopo expandido → (v) V&V → (vi) lançamento 1.0. Estimativa total: **~12–18 semanas-engenheiro** se executado por uma única pessoa, com pontos de paralelização possíveis a partir da Fase 3. Fases 0–4 são bloqueantes para um lançamento "1.0 RC"; fases 5–11 podem ser priorizadas por valor relativo. **Tudo que mexe no solver passa por gate de V&V física antes de mergear**, e qualquer mudança que afete resultado numérico é registrada em changelog público para reprodutibilidade científica.

**Integração do MoorPy como referência técnica.** Após a inspeção do código aberto do MoorPy (NREL), o plano incorpora explicitamente:
- **10 golden cases de catenária** extraídos de `moorpy/tests/test_catenary.py` viram regression tests obrigatórios do AncoPlat (Fase 1 e Fase 10).
- **Modelo físico documentado de EA dinâmico** (`EA_dynamic = EAd + EAd_Lm × T_mean`) substitui a premissa em aberto QMoor/GMoor, com base documental em `MoorProps_default.yaml` (Fase 1).
- **ProfileType taxonomy** (9+ casos catenários enumerados) entra como estrutura dos diagnostics e cobertura de testes (Fases 4 e 10).
- **Biblioteca paramétrica de materiais** (`mass_d2`, `MBL_d²`, `EA_MBL`, etc.) é avaliada como complemento ao catálogo fixo de 522 entradas (Fase 6 expandida).
- **Modelo de custo** parametrizado por material entra como Fase futura opcional (não MVP).
- **Bathymetry grid 2D** (`seabedMod=2` no MoorPy) entra como direção futura, registrada para v1.x.

---

## 2. Tabela-síntese de fases

| Fase | Tema | Esforço | Itens-chave | Bloqueio |
|---|---|:---:|---|:---:|
| **0** | Diagnóstico & destravamento | **S** (2–3 d) | reproduzir erros do usuário, instalar MoorPy local, baseline de testes, snapshot de cases | ✅ |
| **1** | Correções físicas críticas | **M** (5–7 d) | B3 atrito per-segmento, A1.4+B4 toggle EA com modelo MoorPy `α + β·T_m`, golden cases MoorPy | ✅ |
| **2** | Redesign aba Ambiente + auditoria de validações | **M** (4–5 d) | A2.2/A2.3 batimetria primária, A2.6, revisão de validators, mensagens E4 | ✅ |
| **3** | Quick wins UX | **S** (2–3 d) | A1.5, D6, D7, A2.5, D9 | ❌ |
| **4** | Diagnostics maturidade + ProfileType taxonomy | **M** (4–5 d) | D001–D011 com repro, pre-solve coverage, surface_violations UI, ProfileType enum | ❌ |
| **5** | Reports, memorial e exportação | **M** (4–6 d) | memorial PDF, .moor v2, CSV/Excel, reprodutibilidade | ❌ |
| **6** | Catálogo de boias + library paramétrica opcional | **M** (4–6 d) | A5.2, modelo de dados + picker, fórmulas paramétricas MoorPy como fallback | ❌ |
| **7** | Anchor uplift | **L** (8–12 d) | A2.7–A2.9, novo path do solver, V&V dedicado vs MoorPy | ❌ |
| **8** | AHV (decisão + implementação) | **L** se go (10–14 d) | A4, attachment com componente horizontal | ❌ |
| **9** | UI polish & onboarding | **M** (4–6 d) | help, glossário, samples, performance, a11y básico | ❌ |
| **10** | V&V completo (gate de release) | **L** (10–12 d) | golden cases, robustez, performance, V&V vs MoorPy em ≥10 casos canônicos | ✅ p/ 1.0 |
| **11** | Documentação & lançamento 1.0 | **M** (3–5 d) | CLAUDE, manual, changelog, release notes | ✅ p/ 1.0 |
| **12** *(futura, pós-1.0)* | Features avançadas inspiradas em MoorPy | **XL** | matrizes de rigidez analíticas, modelo de custo, bathymetry grid 2D | ❌ |

**Legenda esforço:** S = 1–3 dias-engenheiro, M = 3–6 dias, L = 7–14 dias, XL = >14 dias.

---

## Fase 0 — Diagnóstico & destravamento

### Tema
Antes de qualquer fase técnica, destravar bloqueios pendentes e confirmar premissas que afetam o resto do plano.

### Itens
- **B0.1** — Reproduzir os "muitos erros" mencionados pelo usuário (item 4 da conversa anterior).
- **B0.2** — Confirmar premissa física: QMoor EA vs GMoor EA. **Resolvido por MoorPy**: o modelo físico é `EA_dynamic = EAd + EAd_Lm × T_mean` (linear no carregamento médio, ver `moorpy/line.py:1027-1044` e `MoorProps_default.yaml`). Decisão a tomar: adotar modelo completo (α + β·T_m) ou simplificar para toggle binário com EA_d como valor de referência fixo.
- **B0.3** — Baseline de testes: confirmar 281/281 verde no `main` atual; criar tag `v0.5-baseline` para regressão futura.
- **B0.4** — Inventariar cases salvos em produção (3 cases + 12 execuções + 2 mooring systems segundo o relatório de deploy) para garantir migração sem perda nas próximas fases.
- **B0.5** *(novo)* — **Instalar MoorPy localmente em ambiente isolado** (`pip install moorpy` em venv dedicado `tools/moorpy_env/`). Pin de versão exato em `requirements-bench.txt`. Não é dependência de runtime, é dependência de validação.
- **B0.6** *(novo)* — **Reproduzir os 10 golden cases do `tests/test_catenary.py` do MoorPy** localmente para confirmar que o ambiente está funcional. Salvar saída em `docs/audit/moorpy_baseline_2026-05-04.json`.

### Pré-requisitos
Nenhum.

### Como destravar cada bloqueio
- **B0.1**: pedir ao usuário 1–2 prints de erro (mensagem + parâmetros). Para cada um: classificar causa-raiz em uma das categorias: (a) validação backend excessivamente restritiva, (b) pré-solve diagnostic falso-positivo, (c) bug numérico no solver, (d) input ambíguo na UI causando configuração inválida. Documentar cada um em issue interna.
- **B0.2**: **resposta com base no MoorPy** — adotar como decisão fechada que `gmoor_ea` representa o termo `EAd` (dynamic stiffness offset) do modelo NREL. Se `EAd_Lm` não estiver disponível no catálogo, β = 0 (modelo simplificado constante). Documentar em CLAUDE.md citando `MoorProps_default.yaml` como fonte. Tooltip da UI passa a explicar: "EA dinâmico (α): rigidez de curto-prazo após relaxamento; aplicável em análise de tensão dinâmica". Manter QMoor (estático, EA_MBL) como default.
- **B0.3**: rodar `pytest backend/solver/tests/ -v` e `cd frontend && npm test` localmente; tag `v0.5-baseline` no git apenas se ambos verdes.
- **B0.4**: dump SQLite de produção, snapshot em `docs/audit/cases_baseline_2026-05-04.json` para teste de migração.
- **B0.5**: criar `tools/moorpy_env/` com venv Python 3.11 dedicado; `pip install moorpy==<latest> numpy matplotlib pyyaml scipy`; congelar em `requirements-bench.txt`. Não toca o ambiente principal do AncoPlat.
- **B0.6**: rodar `pytest tools/moorpy_env/MoorPy/tests/test_catenary.py -v`; capturar 10 outputs (fAH, fAV, fBH, fBV, LBot, ProfileType) em JSON estruturado.

### Critérios de aceitação
- Issue tracker com 1+ erro reproduzível classificado por causa-raiz.
- `git tag v0.5-baseline` criada e empurrada.
- `cases_baseline.json` salvo e validado por re-import.
- Decisão registrada em CLAUDE.md: QMoor permanece default (EA_MBL); GMoor passa a ter base documental (EAd via MoorPy/NREL); semântica documentada com referência ao paper ASME 2025.
- `moorpy_baseline_2026-05-04.json` salvo com 10 outputs de referência; reprodutível via `bash tools/moorpy_env/regenerate_baseline.sh` (decisão Q5 da Fase 0 — shell script em vez de Makefile, aplicada na Fase 1).

### Riscos
- Usuário pode não conseguir reproduzir os erros → mitigação: instrumentar logs de erro detalhados em produção (já há `api.log`; verificar conteúdo).
- Cases salvos podem ter campos legados incompatíveis com schemas atuais → mitigação: testar import antes de mexer em qualquer schema.
- MoorPy pode ter mudança breaking entre versões → mitigação: pin exato em `requirements-bench.txt`, congelar baseline JSON.

### Esforço
**S** (2–3 dias). +0.5 dia para B0.5 e B0.6 (instalação MoorPy + baseline).

---

## Fase 1 — Correções físicas críticas

### Tema
Eliminar as duas divergências físicas críticas identificadas na auditoria. Após esta fase, casos com linhas mistas (chain + wire) e poliéster podem produzir resultados materialmente diferentes — gate de V&V obrigatório.

### Itens
- **B3** — Atrito de seabed per-segmento (hoje global)
- **A1.4 + B4** — Toggle EA QMoor/GMoor por segmento (hoje sempre QMoor implícito)

### Pré-requisitos
- Fase 0 concluída (baseline de testes, snapshot de cases).
- Decisão sobre default GMoor confirmada (manter QMoor por padrão).

### Mudanças no schema/types
- [backend/solver/types.py](../backend/solver/types.py) — `LineSegment`:
  - Novo campo `mu_override: Optional[float] = None` — quando informado, sobrescreve `seabed.mu` para este segmento.
  - Novo campo `ea_source: Literal["qmoor", "gmoor"] = "qmoor"` — qual coluna do catálogo foi aplicada para popular `EA`.
  - Novo campo opcional `ea_dynamic_beta: Optional[float] = None` — coeficiente β do modelo MoorPy (`EAd_Lm`); quando presente e `ea_source="gmoor"`, ativa modelo linear `EA = α + β × T_mean`. Quando `None`, modelo simplificado constante (β=0).
- [backend/api/schemas/cases.py](../backend/api/schemas/cases.py) — campo `ea_source` opcional no `CaseInput.boundary` ou per segmento (decidir granularidade — recomendado per segmento).
- [frontend/src/lib/caseSchema.ts](../frontend/src/lib/caseSchema.ts) — espelhar Zod.
- Migração: cases salvos sem esses campos → defaults `mu_override=None`, `ea_source="qmoor"`, `ea_dynamic_beta=None` (idempotente).

### Modelo físico de EA (decisão fechada com base no MoorPy)
Adotamos o modelo de `moorpy/line.py:1027-1044` e `MoorProps_default.yaml`:

```
EA_estatico  = EA_MBL × MBL                    [QMoor — default]
EA_dinamico  = EAd × MBL + EAd_Lm × T_mean    [GMoor — opcional]
            = α + β × T_mean
```

Onde:
- `EA_MBL` é o coeficiente quasi-estático por MBL (existe para todos materiais no catálogo NREL).
- `EAd` (= α por MBL) é o coeficiente dinâmico de offset (rigidez de curto prazo).
- `EAd_Lm` (= β por MBL) é o coeficiente dinâmico linear na carga média (slope da rigidez vs tensão).

**Implementação V1 (MVP da Fase 1):** suportar α (constante) por segmento. β fica como campo opcional para Fase 2 ou posterior, não bloqueante.

**Implementação V2 (Fase 4 ou 10):** quando β presente, solver itera: estima `T_mean` → calcula `EA(T_mean)` → solve catenária → atualiza `T_mean` → repete até convergência.

**Tooltip canônico (UI):** "EA estático (QMoor): rigidez quasi-estática (carga lentamente aplicada). EA dinâmico (GMoor): rigidez de curto prazo após relaxamento, aplicável em análise de tensão dinâmica. Modelo NREL/MoorPy."

### Mudanças no solver/backend
- [backend/solver/multi_segment.py](../backend/solver/multi_segment.py) — aceitar `mu_per_seg: Optional[Sequence[float]] = None`; quando presente, usar valor por segmento no cálculo de atrito grounded; quando ausente, manter behavior atual (μ global). Linhas afetadas: ~493, ~533, ~607.
- [backend/solver/solver.py](../backend/solver/solver.py) — facade `solve()` constrói `mu_per_seg` resolvendo precedência: `segment.mu_override` → `segment.line_type.seabed_friction_cf` (do catálogo) → `seabed.mu` global → 0.0.
- [backend/api/services/](../backend/api/services/) — pipeline de seed/conversão respeita `ea_source` ao popular `segment.EA` do catálogo.

### Mudanças na UI/frontend
- [frontend/src/components/common/SegmentEditor.tsx](../frontend/src/components/common/SegmentEditor.tsx) — adicionar:
  - Toggle radio "EA: QMoor / GMoor" (default QMoor); recálculo do EA via `applyLineTypeToSegment` ao trocar.
  - Campo opcional "Atrito (μ) — sobrescrever catálogo" com placeholder mostrando o valor do catálogo se houver.
- [frontend/src/components/common/LineTypePicker.tsx](../frontend/src/components/common/LineTypePicker.tsx) — exibir ambos `qmoor_ea` e `gmoor_ea` lado-a-lado quando ambos existirem; razão `gmoor/qmoor` como dica visual.
- [frontend/src/pages/CaseDetailPage.tsx](../frontend/src/pages/CaseDetailPage.tsx) — exibir per segmento `μ_eff` e `EA source` no card de "Resultados".

### Mudanças em testes
- Testes solver: novos `BC-FR-01` (linha mista chain/wire com μ por catálogo) e `BC-EA-01` (poliéster com gmoor_ea explícito) — comparar contra cálculo manual e/ou MoorPy.
- **Novo: `BC-MOORPY-01..10`** — os 10 inputs/outputs do `tests/test_catenary.py` do MoorPy viram regression tests no AncoPlat. Tolerância: rtol=1e-4 em (T_anchor_h, T_anchor_v, T_fairlead_h, T_fairlead_v, L_grounded). Cada caso registrado em `backend/solver/tests/golden/moorpy/case_NN.json`. Ver Fase 10.3 para a tabela completa.
- Regressão: re-rodar BC-01..09 com `mu_override=None` e `ea_source="qmoor"` — deve manter resultados bit-a-bit dentro de tolerância de ponto flutuante.
- Frontend: teste de unidade do `applyLineTypeToSegment` com `ea_source="gmoor"`.

### Critérios de aceitação
- Para BC-FR-01 (linha mista R4Studless μ=0.6 + IWRC μ=0.3 + R4Studless μ=1.0): ΔT (atrito) computado dentro de **±2%** do cálculo manual.
- Para BC-EA-01 (poliéster gmoor_ea ≈ 12× qmoor_ea): elongation mudou na razão esperada; geometria muda em proporção verificável; alerta_level pode mudar de `ok` para `yellow` em casos taut — registrar.
- **BC-MOORPY-01..10** todos passam com `rtol=1e-4` (input/output extraídos de `moorpy/tests/test_catenary.py`).
- Cases existentes em `cases_baseline.json` re-rodam e produzem **mesmo resultado** (defaults preservam comportamento).
- 100% dos testes anteriores continuam verdes; cobertura ≥ 96% no `backend/solver/`.

### Riscos
- **R1.1 — Cases salvos podem assumir μ global** que estava conscientemente "errado" mas calibrado contra observação. Mitigação: feature-flag `use_per_segment_friction` por execução; default `False` para cases pré-fase, `True` para novos.
- **R1.2 — Catálogo `seabed_friction_cf` tem anomalia conhecida em R5Studless (μ=0.6) registrada em CLAUDE.md.** Mitigação: documento explica, validador alerta com warning quando aplicar valor anômalo, mas não bloqueia.
- **R1.3 — Significado de gmoor_ea agora documentado via MoorPy** (modelo `α + β × T_mean`). Risco residual: catálogo legacy do AncoPlat pode não ter `EAd_Lm`; nesse caso tratar como β=0 e marcar com warning estruturado.

### Esforço
**M** (5–7 dias). +1 dia em relação à versão original para incluir geração e validação dos `BC-MOORPY-01..10`.

### Validação física específica
- Comparar BC-FR-01 contra cálculo manual de capstan equation por trecho.
- Comparar BC-EA-01 contra solução analítica (catenária inextensível) no limite EA→∞ e contra catenária com EA gmoor variando dentro do ratio observado.
- **BC-MOORPY-01..10**: rodar mesmos inputs no AncoPlat e no MoorPy local (ambiente da Fase 0), comparar tabela de outputs lado-a-lado, registrar em `docs/relatorio_F6_1_moorpy_validation.md`.
- Documentar resultados em `docs/relatorio_F6_1_correcoes_fisicas.md`.

---

## Fase 2 — Redesign aba Ambiente + auditoria de validações

### Tema
Resolver a confusão "lâmina d'água sob âncora vs sob fairlead vs prof. fairlead" que motivou esta conversa, transformando batimetria nos dois pontos em input primário; revisar todas as validações da UI e backend para eliminar restrições injustificadas (responde ao "ponto 4" da conversa).

### Itens
- **A2.2 / A2.3** — `depth_at_anchor`, `depth_at_fairlead` e `horizontal_distance` como inputs primários; slope derivado.
- **A2.6** — offset horizontal do startpoint.
- **E4** — auditoria de mensagens de erro/warning.
- **Auditoria de validações** — varredura completa de `raise ValueError` no solver, `min/max` no Zod e no Pydantic, restrições do pre-solve diagnostics; classificar cada uma como (a) fisicamente justificada, (b) defensiva mas relaxável, (c) acidental/excessiva.

### Pré-requisitos
- Fase 0 (erros reproduzidos do usuário ajudam a ranquear quais validações relaxar).

### Mudanças no schema/types
- [backend/solver/types.py](../backend/solver/types.py) — `BoundaryConditions`:
  - **Manter** `h` como derivado interno (= `depth_at_anchor − startpoint_depth`), mas a entrada canônica passa a ser `depth_at_anchor`.
  - Mudar docstring que hoje diz "h = distância anchor→fairlead" — está inconsistente com o uso real (= water_depth absoluto). Documentar como `water_depth_at_anchor`.
- `SeabedConfig.slope_rad` continua existindo, mas a UI deixa de aceitar input direto (modo "avançado" opcional).
- Possível novo wrapper `BathymetryInput` (depth_anchor, depth_fairlead, horizontal_distance) que gera `BoundaryConditions.h` + `SeabedConfig.slope_rad` derivados — alternativamente, manter campos planos e calcular no frontend.

### Mudanças no solver/backend
- Mínimas. A maior parte é UI. Mas:
  - Revisar [backend/solver/solver.py:75](../backend/solver/solver.py#L75) — relaxar mensagem de erro "h ≤ 0" para incluir contexto (`depth_at_anchor`, não `h` sozinho).
  - Revisar [backend/solver/solver.py:93](../backend/solver/solver.py#L93) — validação `startpoint_depth >= h` deve incluir `slope` no cálculo (em seabed inclinado, `h` no fairlead é diferente).
  - Auditoria **completa** de `raise ValueError` em `solver.py`, `multi_segment.py`, `seabed_sloped.py`, `attachment_resolver.py`, `equilibrium.py`, `grounded_buoys.py`. Para cada um: justificativa em comment, downgrade para warning quando aplicável.

### Mudanças na UI/frontend
- [frontend/src/pages/CaseFormPage.tsx](../frontend/src/pages/CaseFormPage.tsx) — refatorar aba "Ambiente":
  ```
  Geometria:
    Profundidade do seabed sob a âncora    [m]
    Profundidade do seabed sob o fairlead  [m]
    Distância horizontal âncora → fairlead [m]
       → Slope derivado: X.XX° (read-only, calculado em tempo real)

  Fairlead:
    Profundidade do fairlead abaixo da água [m]   (default 0)
    Offset horizontal do fairlead           [m]   (default 0)
    Tipo (cosmético): Semi-Sub | AHV | Barge | None

  Seabed:
    Coeficiente de atrito μ (default catálogo)
    [Modo avançado] Slope direto em graus
  ```
- [frontend/src/components/common/BathymetryPopover.tsx](../frontend/src/components/common/BathymetryPopover.tsx) — desativar (vira modo avançado dentro do form).
- [frontend/src/lib/preSolveDiagnostics.ts](../frontend/src/lib/preSolveDiagnostics.ts) — revisar P001 (cabo curto) tolerância 5% pode ser apertada demais; P004 (T_fl baixo) pode disparar inadequadamente em casos de poliéster com gmoor_ea.
- Novos componentes: `BathymetryInputGroup` (3 campos com slope read-only ao lado).

### Mudanças em testes
- Frontend: testes de derivação de slope a partir das três entradas.
- Backend: testes de migração — input antigo (`h`, `slope_rad`) e novo (3 campos) produzem mesmo `BoundaryConditions` interno.
- Integração: cases salvos pré-fase abrem corretamente com novo form (campos populam-se via derivação reversa).

### Critérios de aceitação
- Form da aba Ambiente exibe **3 campos primários** + slope derivado read-only.
- Toggle "modo avançado" expõe slope direto + offset; default fechado.
- Pelo menos 1 erro relatado pelo usuário na Fase 0 deixa de ocorrer (verificar no caso original).
- 100% dos `raise ValueError` no solver têm comment justificando ou foram relaxados; cada um tem **um teste de unidade** que dispara o erro.
- Cases salvos pré-fase abrem sem erro e o solve produz resultado idêntico.

### Riscos
- **R2.1 — Quebrar cases existentes** que assumem semântica antiga de `h`. Mitigação: testes de regressão sobre `cases_baseline.json`.
- **R2.2 — Confusão durante a transição** entre engenheiros que já usam o app. Mitigação: tooltip explicativo + entrada antiga ainda aceita via "modo avançado".
- **R2.3 — Validações que hoje protegem o solver de inputs que crashariam** se forem relaxadas demais. Mitigação: cada relaxamento gera um warning via diagnostic estruturado em vez de bloquear.

### Esforço
**M** (4–5 dias).

### Validação física específica
- Caso BC-SLP-01 (seabed inclinado 5°, batimetria nos dois pontos com Δprof = X·tan(5°)) — slope derivado bate com o input original em <1e-6 rad.
- Caso BC-FAIRLEAD-01 (`startpoint_depth=30m`) — comportamento idêntico ao input antigo `h=270, startpoint_depth=30`.

---

## Fase 3 — Quick wins UX

### Tema
Lista de melhorias triviais altamente visíveis que fecham gaps cosméticos com o QMoor sem mexer em física.

### Itens
- **A1.5** — Painel agregado na aba "Linha" (n. segmentos, L_total, peso seco, peso molhado).
- **D6** — Grounded como linha pontilhada (alinha com QMoor).
- **D7** — Ícones de startpoint conforme tipo (Semi-Sub/AHV/Barge).
- **A2.5** — Dropdown Startpoint Type (cosmético, sem efeito físico).
- **D9** — Toggle equal-scale, labels/legend visíveis no plot.

### Pré-requisitos
- Fase 2 (Startpoint Type entrou no schema).

### Mudanças no schema/types
- `BoundaryConditions.startpoint_type: Literal["semisub", "ahv", "barge", "none"] = "semisub"` — apenas cosmético; nunca usado no solver.

### Mudanças no solver/backend
Nenhuma.

### Mudanças na UI/frontend
- [frontend/src/components/common/LineSummaryPanel.tsx](../frontend/src/components/common/LineSummaryPanel.tsx) (novo) — soma agregada exibida no topo da aba Linha.
- [frontend/src/components/common/CatenaryPlot.tsx:650](../frontend/src/components/common/CatenaryPlot.tsx#L650) — mudar `dash: 'solid'` para `'dot'` no overlay grounded; manter cor vermelha (decisão consciente, mais visível que o cinza pontilhado do QMoor — registrar em CLAUDE.md).
- [frontend/src/components/common/CatenaryPlot.tsx:73-79](../frontend/src/components/common/CatenaryPlot.tsx#L73-L79) — substituir `fairleadSvg` fixo por seletor baseado em `startpoint_type`. Adicionar SVGs `ahvSvg`, `bargeSvg`, `noneSvg`.
- [frontend/src/components/common/CatenaryPlot.tsx](../frontend/src/components/common/CatenaryPlot.tsx) — expor toggles `equalAspect`, `showLabels`, `showLegend`, `showImages` como controles visíveis no canto do plot (botões pequenos).

### Mudanças em testes
- Snapshot tests do plot com cada `startpoint_type`.
- Teste do `LineSummaryPanel` com 1, 3, 10 segmentos.

### Critérios de aceitação
- Aba Linha exibe painel com agregados que somam corretamente para `cases_baseline.json` (validação programática).
- Grounded aparece pontilhado em todos os plots; suspended sólido.
- Trocar `startpoint_type` muda só o ícone — solver não chamado.
- Toggle equal-scale exibe plot em proporção 1:1 quando ativo; auto-scale quando inativo.

### Riscos
- Baixíssimos. Tudo cosmético.

### Esforço
**S** (2–3 dias).

---

## Fase 4 — Diagnostics maturidade + ProfileType taxonomy

### Tema
Cada diagnostic estruturado (D001–D011 + pre-solve) precisa ter teste mínimo reproduzível, sugestão "Aplicar" funcional e mensagem clara. Esta é a vantagem principal do AncoPlat sobre o QMoor — amadurecer. Adicionalmente, adotar a **ProfileType taxonomy** do MoorPy (`Catenary.py:147-163`) para classificar regimes catenários explicitamente, melhorando diagnostics e cobertura de testes.

### Itens
- Auditoria completa dos diagnostics existentes (pre-solve P001–P004 e backend D004/D006/D008/D009/D010/D011).
- Teste mínimo reproduzível para cada um (caso simples que dispara, caso simples que não dispara).
- Sugestão "Aplicar" testada end-to-end (botão muda form, novo solve passa).
- Surface violations (F5.7.3) com UI de alerta dedicada.
- Cobertura de novos diagnostics potenciais identificados na Fase 0 (erros do usuário viram diagnostics estruturados em vez de exception).
- **Novo: ProfileType enum** — classificar cada solve em um dos casos enumerados pelo MoorPy:
  - `PT_0`: linha inteira no seabed
  - `PT_1`: nenhuma porção no seabed (catenária livre)
  - `PT_2`: porção no seabed, tensão na âncora não-zero (com atrito)
  - `PT_3`: porção no seabed, tensão na âncora = zero (sem atrito ou μ saturado)
  - `PT_4`: linha negativamente flutuante com seabed
  - `PT_5`: linha em U totalmente slack
  - `PT_6`: linha completamente vertical
  - `PT_7`: porção no seabed, seabed inclinado (caso F5.3 do AncoPlat)
  - `PT_8`: linha apoiada no seabed inclinado
  - `PT_U`: ambos extremos fora do seabed, contato com seabed, não slack (com slope)

### Pré-requisitos
- Fase 0 (erros reproduzidos viram base para novos diagnostics).
- Fase 2 (validators relaxados — vários se transformam em warnings/diagnostics).

### Mudanças no schema/types
- Possível extensão de `SolverDiagnostic` em [backend/solver/diagnostics.py](../backend/solver/diagnostics.py) com campo `confidence: "high" | "medium" | "low"` para diferenciar erro determinístico de heurística.
- **Novo: `ProfileType` enum** em `backend/solver/types.py`. Resultado do solve passa a incluir `profile_type: ProfileType` para introspecção.

### Mudanças no solver/backend
- Auditar `diagnostics.py` para garantir cobertura de cenários frequentes:
  - **D012** (novo, candidato) — Slope > 30° detectado, alerta de baixa precisão.
  - **D013** (novo, candidato) — μ_global = 0 mas catálogo sugere μ ≥ 0.3.
  - **D014** (novo, candidato) — `gmoor_ea` selecionado mas sem `EAd_Lm` no catálogo; warning explicativo.
  - **D015** (novo, candidato) — ProfileType detectado é raro (PT_5 slack U-shape, PT_6 vertical) com nota de cuidado.
- Implementar classificador `classify_profile_type(result) -> ProfileType` em `backend/solver/profile_type.py` (novo arquivo). Lógica espelha decisões do MoorPy `Catenary.py:191-450`.

### Mudanças na UI/frontend
- [frontend/src/components/common/SolverDiagnosticsCard.tsx](../frontend/src/components/common/SolverDiagnosticsCard.tsx) — verificar que cada diagnostic renderiza, severity correta, botão "Aplicar" funciona.
- Card dedicado para `surface_violations` (lista de boias acima da água com `height_above_surface_m`).
- Pre-solve diagnostics integrados no badge "Antes de resolver" antes do botão Solve.

### Mudanças em testes
- Para cada diagnostic D001–D014 e P001–P004:
  - **Test repro** — input mínimo que dispara o diagnostic.
  - **Test no-repro** — input mínimo similar que NÃO dispara (margem).
  - **Test apply** — aplicar `suggested_change` produz solve `converged`.
- Total esperado: ~45 novos testes (3 por diagnostic × ~15 diagnostics).

### Critérios de aceitação
- 100% dos diagnostics têm teste repro + no-repro + apply.
- Cobertura de [backend/solver/diagnostics.py](../backend/solver/diagnostics.py) ≥ 95%.
- Pelo menos 1 erro do usuário (Fase 0) virou diagnostic estruturado em vez de exception.
- Surface violations aparece como card próprio quando >0 boias violam.

### Riscos
- **R4.1 — Sugestões de "Aplicar" podem estar matematicamente erradas.** Mitigação: cada teste apply valida que o novo solve converge.

### Esforço
**M** (3–4 dias).

---

## Fase 5 — Reports, memorial e exportação

### Tema
Memorial de cálculo profissional para entrega ao cliente; exportação CSV/Excel para análise externa; `.moor` v2 com todos os campos novos das fases 1–2.

### Itens
- Memorial de cálculo PDF: capa + premissas + segmentos + boundary + resultados + plot + diagnostics (rastreabilidade total).
- Exportação CSV (geometria do cabo) e Excel (caso completo + resultados).
- `.moor` v2 com `ea_source`, `mu_override`, `startpoint_type`, batimetria nos dois pontos.
- Reprodutibilidade: cada PDF/Memorial inclui `solver_version`, hash do caso, data.

### Pré-requisitos
- Fases 1, 2 (campos novos consolidados).

### Mudanças no schema/types
- `.moor` schema versionado: `version: int = 2`.
- Migrador que aceita `version: 1` e popula defaults nos campos novos.

### Mudanças no solver/backend
- [backend/api/services/moor_service.py](../backend/api/services/moor_service.py) — versionamento do export/import.
- [backend/api/services/pdf_service.py] — extender PDF com seção "Memorial técnico" (cálculo passo-a-passo opcional).
- Novo endpoint `GET /cases/{id}/export/csv` (geometria) e `/export/xlsx` (caso completo).

### Mudanças na UI/frontend
- [frontend/src/pages/ImportExportPage.tsx](../frontend/src/pages/ImportExportPage.tsx) — botões Export CSV / Export Excel.
- Botão "Memorial" no detalhe do caso (mais detalhado que o PDF atual).

### Mudanças em testes
- Round-trip `.moor` v1 → import → export v2 → import (idempotência).
- Teste de import de `cases_baseline.json` com schema v1.
- PDF golden snapshot (mudanças no layout precisam de aprovação explícita).

### Critérios de aceitação
- Importar `.moor` v1 produz caso idêntico (mesmo solve result) ao caso original em `cases_baseline.json`.
- Memorial PDF inclui `solver_version` e hash do caso.
- CSV exporta geometria (x, y, T_x, T_y, T_mag) com ≥ 5000 pontos.
- Excel inclui aba "Caso", aba "Resultados", aba "Geometria".

### Riscos
- **R5.1 — Mudança no PDF quebra layout.** Mitigação: snapshot test com tolerância visual.
- **R5.2 — Cases legacy `.moor` v1 com bugs não-óbvios.** Mitigação: warning explícito em vez de erro silencioso.

### Esforço
**M** (4–6 dias).

---

## Fase 6 — Catálogo de boias (A5.2) + library paramétrica de cabos opcional

### Tema
Adicionar catálogo de boias semelhante ao catálogo de cabos atual. Tipos canônicos com dimensões, peso no ar e empuxo total/líquido pré-calculados. **Adicionalmente:** avaliar e (opcionalmente) implementar **library paramétrica de cabos** inspirada no MoorPy, permitindo derivar propriedades a partir de fórmulas (`mass_d2 × d²`, `MBL_d² × d²`, etc.) quando o engenheiro quer dimensionamento preliminar sem entrada manual completa.

### Itens
- Modelo de dados `Buoy` no SQLite (legacy_id opcional, name, type, end_type, dimensões, weight_in_air, total_buoyancy).
- Importação inicial do catálogo de boias (se houver fonte) ou seed mínima com 5–10 modelos típicos.
- Picker no frontend integrado ao `AttachmentsEditor`.
- Cálculo automatizado de `submerged_force` a partir de dimensões + peso (com validação contra `Cópia de Buoy_Calculation_Imperial_English.xlsx`).
- *(Opcional, decisão go/no-go em Fase 0 ou início da Fase 6)* — **Library paramétrica MoorPy**: importar coeficientes do `MoorProps_default.yaml` (8 materiais base: chain studless/studlink R3/R4/R5, polyester, nylon, hmpe, wire 6-strand, wire spiral) e oferecer modo "calculadora" que computa propriedades a partir de diâmetro + material. Complementa (não substitui) o catálogo legacy_qmoor de 522 entradas.

### Pré-requisitos
- Fase 5 (export/import estabilizado).

### Mudanças no schema/types
- Nova tabela `buoys` em SQLite + Pydantic `BuoyCatalogEntry`.
- Possível extensão de `LineAttachment` com campo `buoy_catalog_id: Optional[int]` para rastreabilidade.
- *(Opcional)* Nova tabela `material_coefficients` com schema espelhando `MoorProps_default.yaml`. Endpoint `POST /line-types/from-parametric` que aceita `{material, diameter}` e retorna `LineSegment` populado.

### Mudanças no solver/backend
- Endpoint `GET /buoys` com paginação.
- Endpoint `POST /buoys` para entradas custom (espelhando padrão de `line_types`).
- *(Opcional)* Módulo `backend/api/services/parametric_lines.py` com fórmulas do MoorPy (mass, MBL, EA, density via density). Validação de domínio (`MBL_dmin`/`MBL_dmax`).

### Mudanças na UI/frontend
- `BuoyPicker` componente.
- Página `/catalog/buoys` espelhando `/catalog`.
- *(Opcional)* No `LineTypePicker`, aba secundária "Calculadora paramétrica (MoorPy)" — usuário escolhe material + diâmetro, vê propriedades derivadas, opção de salvar como entrada custom.

### Mudanças em testes
- Testes de fórmula de empuxo (cilindro com end_type elliptical/flat/hemispherical/semi_conical) contra Excel de referência.
- Testes de seed/import.
- *(Opcional)* Round-trip parametric: gerar `LineSegment` do paramétrico → solver → resultado bate com solver usando entrada equivalente do catálogo legacy.

### Critérios de aceitação
- Catálogo seed com ≥ 5 boias canônicas.
- `submerged_force` calculado a partir de dimensões + peso bate com Excel dentro de **±1%**.
- Picker integrado no `AttachmentsEditor`.
- *(Opcional)* Calculadora paramétrica produz EA, MBL, peso linear dentro de **±5%** do catálogo legacy para os 5 materiais mais comuns no diâmetro mediano da base.

### Riscos
- **R6.1 — Fonte do catálogo de boias inexistente** (CLAUDE.md menciona Excel mas pode ser limitado). Mitigação: começar com seed mínima de modelos genéricos.
- **R6.2 — Library paramétrica pode confundir engenheiros** que esperam só catálogo. Mitigação: tab separada e clara; tooltip explica origem (NREL/MoorPy).

### Esforço
**M** (3–5 dias) sem library paramétrica; **M+ (5–7 dias)** com library paramétrica.

---

## Fase 7 — Anchor uplift (A2.7–A2.9)

### Tema
Habilitar âncoras elevadas do seabed (suspended endpoint). Mudança física grande, requer novo dispatch no solver.

### Itens
- A2.7 — Radio Grounded/Suspended na UI.
- A2.8 — Campo Depth do endpoint quando Suspended.
- A2.9 — Suporte real no solver.

### Pré-requisitos
- Fases 1, 2, 4 estáveis.
- V&V parcial (Fase 10) feita pelo menos para casos grounded.

### Mudanças no schema/types
- `BoundaryConditions.endpoint_grounded` aceita `False`.
- `BoundaryConditions.endpoint_depth: Optional[float]` quando suspended.

### Mudanças no solver/backend
- Novo módulo `backend/solver/suspended_endpoint.py` ou extensão de `solver.py`.
- Path do solver para anchor não-grounded:
  - Sem touchdown na âncora.
  - Catenária livre nas duas pontas.
  - Validação: tração na âncora ≠ 0.
- [backend/solver/solver.py:85-89](../backend/solver/solver.py#L85-L89) — remover `NotImplementedError`.

### Mudanças na UI/frontend
- Radio Grounded/Suspended na aba Ambiente.
- Campo Depth do endpoint condicional.
- Plot atualizado para mostrar anchor flutuando.

### Mudanças em testes
- BC-UP-01 a BC-UP-05 — casos canônicos de anchor uplift validados contra MoorPy.
- Regressão: cases grounded continuam idênticos.

### Critérios de aceitação
- BC-UP-01 (anchor 50m acima do seabed em 300m d'água) converge em <0.1s e bate com MoorPy dentro de **±1%** em força e geometria.
- Cases grounded: 0 regressão.

### Riscos
- **R7.1 — Solver pode não convergir em casos taut com anchor elevado** (sem touchdown para "ancorar" a solução). Mitigação: chute inicial específico para uplifted; usar diagnostics para falhas.
- **R7.2 — Edge cases físicos** (anchor "voando" acima da água em casos absurdos). Mitigação: validação de domínio + diagnostic dedicado.

### Esforço
**L** (8–12 dias).

### Validação física específica
- Caso BC-UP-01 vs MoorPy: <1% erro em T_fl, T_anchor, X.
- Caso BC-UP-02 (uplift severo, anchor a 100m do fundo): convergência sem warnings.

---

## Fase 8 — AHV (A4) — decisão go/no-go + execução

### Tema
**Decisão estratégica**: implementar Anchor Handler Vessels (carga lateral em ponto intermediário da linha) ou marcar como N/A definitivo?

### Análise
- **Caso de uso real**: simulação de instalação de mooring (rebocadores puxando cabo durante deployment). Pouco comum em análise operacional.
- **Custo**: novo tipo de attachment com componente horizontal; afeta solver multi-segmento; UI categoria nova.
- **Já temos**: `EnvironmentalLoad` no nível de sistema (F5.5) que cobre carga ambiental global. AHV é diferente — força num ponto da linha.

### Recomendação inicial
**No-go** para v1.0; revisitar em v1.1 se houver demanda. Justificativa: AncoPlat é ferramenta de **análise operacional estática**, não de instalação. AHV expande escopo significativamente sem retorno proporcional.

### Se go (caso o usuário decida)
- Novo tipo `LineAttachment.kind = "external_force"` com componentes (Fx_local, Fz_local) em arc length específico.
- Solver multi-segmento aceita força lateral aplicada (mudança de jump no nó).
- UI categoria External Forces / AHV completa (heading, stern angle, bollard pull, deck level, work line).
- V&V dedicado: comparar com MoorPy quando possível (MoorPy não suporta nativamente, então validação contra cálculo manual).

### Esforço se go
**L** (10–14 dias).

### Decisão a tomar antes de começar
Perguntar ao usuário: o caso de uso "AHV durante instalação" está no escopo profissional pretendido para o AncoPlat?

---

## Fase 9 — UI polish & onboarding

### Tema
Polir UX para uso por engenheiros que não conhecem o app; adicionar onboarding e samples; performance check.

### Itens
- Tour/tutorial inicial ("primeiro caso em 5 minutos").
- Página "Samples" com 5–8 cases canônicos pré-carregados (catenária pura, com touchdown, multi-segmento, com boia, com clump, com lifted arch, com slope, com platform equilibrium).
- Glossário de termos técnicos.
- Performance: profiling de watchcircle 360°; otimizar se >5s por varredura.
- Internacionalização: app está em PT-BR; adicionar EN seria valioso para uso internacional (fase posterior, opcional).
- Acessibilidade básica: keyboard nav, ARIA labels nos forms.
- Print stylesheet: Memorial e detalhe do caso imprimíveis.

### Pré-requisitos
- Fases 1–4 fechadas (forma estável da UI).

### Mudanças no schema/types
Nenhuma.

### Mudanças na UI/frontend
- Componente `OnboardingTour` (lib `react-joyride` ou similar).
- Página `/help/glossary`.
- Templates já existem em [frontend/src/lib/caseTemplates.ts](../frontend/src/lib/caseTemplates.ts) — expandir para 8+ samples cobrindo features F5.x.
- CSS print media queries.
- (Opcional) i18n com `react-i18next`.

### Mudanças em testes
- Smoke test do tour não bloqueia uso.
- Lighthouse score ≥ 85 em accessibility, performance.

### Critérios de aceitação
- Tour completo em <2 min para usuário novo.
- 8 samples disponíveis e funcionando.
- Memorial imprime em A4 sem corte.
- Watchcircle 36 azimuths roda em <30s em hardware típico.

### Riscos
- **R9.1 — Tour atrapalha usuário avançado.** Mitigação: skip persistente em localStorage.

### Esforço
**M** (4–6 dias).

---

## Fase 10 — V&V completo (gate de release)

### Tema
Esta é a fase final antes do lançamento 1.0. Validação física e de software exaustiva. Nenhuma versão "1.0" sai sem esta fase passar.

### 10.1 — Testes unitários (cobertura mínima por módulo)

| Módulo | Cobertura mínima |
|---|---|
| `backend/solver/catenary.py` | ≥ 98% |
| `backend/solver/elastic.py` | ≥ 98% |
| `backend/solver/multi_segment.py` | ≥ 96% |
| `backend/solver/seabed_sloped.py` | ≥ 95% |
| `backend/solver/grounded_buoys.py` | ≥ 95% |
| `backend/solver/equilibrium.py` (F5.5) | ≥ 95% |
| `backend/solver/multi_line.py` (F5.6) | ≥ 95% |
| `backend/solver/attachment_resolver.py` | ≥ 98% |
| `backend/solver/diagnostics.py` | ≥ 95% |
| `frontend/src/lib/units.ts` | ≥ 98% |
| `frontend/src/lib/caseSchema.ts` | ≥ 95% |
| `frontend/src/lib/preSolveDiagnostics.ts` | ≥ 95% |

### 10.2 — Testes de regressão (golden cases)

Conjunto frozen `golden/` em `backend/solver/tests/golden/` com:
- BC-01 a BC-09 originais.
- BC-FR-01 (Fase 1 — atrito per-segmento).
- BC-EA-01 (Fase 1 — gmoor_ea).
- **BC-MOORPY-01..10** (Fase 1 — golden cases extraídos de `moorpy/tests/test_catenary.py`).
- BC-SLP-01 (Fase 2 — batimetria 2 pontos).
- BC-AT-GB-01..15 (F5.7.1 lifted arches já existem).
- BC-UP-01..05 (Fase 7 — uplift, se implementada).

Cada golden inclui: `input.json`, `expected_output.json`, `tolerances.json`. Toda PR que mexe em solver roda contra golden e bloqueia merge se desviar além da tolerância sem justificativa explícita.

### 10.3 — Casos de validação física (vs referência externa)

Validação física **primária** contra MoorPy (open-source, peer-reviewed). Tabela detalhada:

| Caso | Setup | Referência | Tolerância | Onde validar |
|---|---|---|---|---|
| **VV-01** Linha mono-segmento, seabed plano, sem touchdown | XF=400, ZF=200, L=500, EA=7.5e12, W=800 | MoorPy `test_catenary.py[0]` | rtol=1e-4 em (HF,VF,LBot) | Backend test |
| **VV-02** Linha mono-segmento com touchdown, μ>0 | XF=400, ZF=200, L=500, EA=7.5e12, W=800, CB=5 | MoorPy `test_catenary.py[0]` | rtol=1e-4 | Backend test |
| **VV-03** Linha taut (limite quase-rígido) | XF=246, ZF=263, L=360, EA=700e6, W=3.08 | MoorPy `test_catenary.py[7]` (hardest case) | rtol=1e-3 (caso difícil) | Backend test |
| **VV-04** Linha vertical | XF=0, ZF=200, L=210, EA=1e9, W=500 | Cálculo analítico + MoorPy `ProfileType=6` | rtol=1e-5 | Backend test |
| **VV-05** Linha em U slack (PT_5) | duas pontas elevadas, slack | MoorPy `test_catenary_symmetricU` | rtol=1e-4 | Backend test |
| **VV-06** Seabed inclinado (slope mirror test) | α=10°, dz=60·tan(10°) | MoorPy `test_sloped_mirror` | rtol=1e-4 | Backend test |
| **VV-07** Linha multi-segmento (3 trechos), seabed plano | chain+wire+chain, μ varia | MoorPy via `Subsystem` ou cálculo manual | rtol=1e-3 | Backend test |
| **VV-08** Linha multi-segmento, seabed inclinado | mesma + α=5° | MoorPy via `Subsystem` | rtol=1e-3 | Backend test |
| **VV-09** Linha com boia intermediária | catenária + buoy a 60% do span | MoorPy não suporta nativamente — comparar contra caso publicado [DNV ou ABS reference] | rtol=3e-2 | Backend test |
| **VV-10** Linha com clump weight | catenária + clump a 70% | Cálculo manual (descontinuidade de tensão vertical) | rtol=2e-2 | Backend test |
| **VV-11** Lifted arches (F5.7.1) | série de boias formando arco | Solução analítica para arco simétrico + caso publicado se existir | rtol=3e-2 | Backend test |
| **VV-12** Equilíbrio de plataforma (F5.5) | FPSO com 8 linhas spread, carga lateral | MoorPy `solveEquilibrium` (validação cruzada) | erro <5% no offset | Backend test |
| **VV-13** Watchcircle (F5.6) | spread simétrico 360° | Simetria geométrica + MoorPy se possível | <1% de erro | Backend test |
| **VV-14** Anchor uplift (Fase 7) | endpoint suspended | MoorPy `ProfileType=1` com end A elevado | rtol=2e-2 | Backend test (se Fase 7 fechada) |

**Procedimento de validação MoorPy** (para casos VV-01..08, VV-12..14):

1. Rodar caso no AncoPlat → salvar output em `backend/solver/tests/golden/vv/case_NN_ancoplat.json`.
2. Rodar mesmo caso no MoorPy (ambiente da Fase 0 `tools/moorpy_env/`) → salvar em `case_NN_moorpy.json`.
3. Diff structural com tolerância → relatório em `docs/relatorio_VV_v1.md`.
4. Para cada caso onde divergência excede tolerância: documentar análise de causa (diferença de modelo? bug? aproximação?) e decidir se aceitável.

Para casos VV-09, VV-10, VV-11 (que MoorPy não cobre nativamente): validação contra solução analítica simplificada e/ou caso publicado em literatura técnica (DNV, ABS, OMAE, ISOPE).

### 10.4 — Testes de robustez (entradas adversas)

- Slope = ±45° (limite).
- EA = 1e3 (muito flexível) e EA = 1e10 (rígido).
- Segmento length = 0.1m (curtíssimo).
- Atrito μ = 0 e μ = 5 (extremos).
- Touchdown exatamente na fronteira de segmento.
- Linha com 10 segmentos e 20 attachments simultâneos.
- T_fl = 0.001 × MBL (quase frouxa) e T_fl = 0.99 × MBL (quase rompida).
- Caso degenerado: fairlead exatamente sobre a âncora (X→0).

### 10.5 — Testes de UI

- Renderização sem warnings em React DevTools.
- Live preview com debounce 600ms — sem travas no UI durante typing.
- Hover bidirecional legenda↔segmento (já implementado, regressão).
- Importação `.moor` legacy (v1) e v2.
- Sistema de unidades comutável: round-trip metric→SI→metric com diff zero.
- Plot responsive em resoluções 1080p, 1440p, 4K.

### 10.6 — Testes de diagnostics

- Para cada D001–D014 e P001–P004: caso mínimo dispara, sugestão "Aplicar" produz solve `converged`.

### 10.7 — Validação de unidades

- Round-trip metric↔SI sem perda de precisão (diff < 1e-10 em todos os campos).
- Pint conversions auditadas.

### 10.8 — Validação de performance

- Solve single-segment: <10ms.
- Solve multi-segment 5 trechos: <50ms.
- Solve com 5 attachments: <100ms.
- Watchcircle 36 pontos: <20s em laptop típico.
- Equilíbrio de plataforma com 8 linhas: <2s.
- API endpoints `/cases`, `/line-types`: p95 <100ms.

### Critérios de aceitação para Fase 10
- Cobertura agregada ≥ 90%.
- 0 regressões no conjunto golden.
- 100% dos casos de validação física dentro de tolerância OU justificativa documentada por divergência.
- Todos os testes de robustez passam OU produzem diagnostic estruturado em vez de exception.
- Performance dentro dos targets em hardware de referência (M2 8GB).
- Documento `docs/relatorio_VV_v1.md` consolidando resultados.

### Esforço
**L** (8–10 dias).

---

## Fase 11 — Documentação & lançamento 1.0

### Tema
Pacote final de release. Nada de código novo (a menos que V&V revele bugs).

### Itens
- **CLAUDE.md atualizado**:
  - Status final F0 a F11.
  - Novas decisões fechadas das fases 1–7.
  - Convenções consolidadas (batimetria 2 pontos, EA per-segmento, etc.).
- **Manual de usuário** ([docs/manual_usuario.md](../docs/manual_usuario.md) já existe — expandir):
  - Walkthrough completo.
  - Glossário.
  - Convenções de sinal e unidades.
  - FAQ baseada em erros do usuário (Fase 0).
- **Documentação técnica**:
  - `docs/Documento_A_v3_0.docx` ou changelog consolidado a partir de `Documento_A_v2_3_changelog.md`.
  - `docs/decisoes_fechadas.md` — sumário de decisões físicas/numéricas.
- **Changelog público**:
  - `CHANGELOG.md` na raiz.
  - Mudanças que afetam resultado numérico explicitamente marcadas.
- **Release notes 1.0**:
  - O que mudou.
  - Migração de cases v0.x para v1.0.
  - Compatibilidade backward.
- **Tag git** `v1.0.0` + GitHub release.
- **Smoke test em produção** após deploy.

### Critérios de aceitação
- CLAUDE.md atualizado e revisado.
- Manual cobre 100% dos campos da UI.
- Changelog tem entrada para cada PR que afetou resultado numérico desde `v0.5-baseline`.
- Tag `v1.0.0` empurrada.
- Produção rodando v1.0.0 sem erros há ≥ 48h após deploy.

### Esforço
**M** (3–5 dias).

---

## Fase 12 *(futura, pós-1.0)* — Features avançadas inspiradas em MoorPy

### Tema
Pós-lançamento 1.0, considerar adoção de capacidades técnicas do MoorPy que ampliam o escopo do AncoPlat de "análise estática operacional" para "análise quasi-estática completa de sistema flutuante". **Decisão go/no-go por feature após v1.0 em produção, com base em demanda observada.**

### Itens candidatos

#### 12.1 — Matrizes de rigidez analíticas (semi-analytic Jacobians)
**O que é**: substituir cálculo de rigidez por diferenças finitas pela formulação analítica do MoorPy (`Catenary.py:223-225`, retorna `stiffnessA`, `stiffnessB`, `stiffnessBA` 2D, e `getSystemStiffnessA` retorna 3D para sistema acoplado). Permite linearização em torno de equilíbrio sem custo de re-solve.

**Onde aplicar**:
- F5.5 (equilíbrio de plataforma) — speed-up de 10–100× em sistemas multi-linha.
- Análise modal e linearização para frequência (cabe em RAFT-like análise dinâmica).
- Watchcircle (F5.6) com gradiente analítico em vez de varredura.

**Esforço**: **L** (8–12 dias). Tradução de `Catenary.py` Jacobianos para o solver AncoPlat; testes contra diferença finita.

**Valor**: alto se app evoluir para multi-linha sistemática; médio se uso fica em análise de linha individual.

#### 12.2 — Modelo de custo paramétrico
**O que é**: `getCost()` no nível de Line, Point, System usando coeficientes do `MoorProps_default.yaml` (`cost_d`, `cost_d2`, `cost_mass`, `cost_EA`, `cost_MBL`) — paper ASME 2025 (Davies, Baca, Hall).

**Onde aplicar**:
- Análise de viabilidade econômica em fase de projeto preliminar.
- Otimização de dimensionamento (menor custo para atender restrições).

**Esforço**: **M** (5–7 dias). Schema + endpoint + UI + V&V contra exemplos do paper.

**Valor**: diferencial competitivo médio; maior em consultoria de projeto, menor em análise operacional pura.

#### 12.3 — Bathymetry grid 2D (`seabedMod=2`)
**O que é**: representar fundo do mar como grade 2D (não-uniforme, não-plana). MoorPy lê arquivo MoorDyn-style (`tests/bathymetry200m_sample.txt`).

**Onde aplicar**:
- Sites com batimetria complexa (offshore real).
- Análise de touchdown em fundo irregular.

**Esforço**: **L** (10–15 dias). Mudança fundamental no solver para suportar `getDepthFromBathymetry(x,y)`. Mudança no plot 2D para mostrar fundo real.

**Valor**: alto para uso profissional avançado; pouco relevante em projeto preliminar com batimetria simplificada.

**Nota**: até v1.x, manter modelo `seabedMod=1` (plano inclinado uniforme — F5.3 atual do AncoPlat) que já cobre 90% dos casos.

#### 12.4 — Modos dinâmicos e RAFT-coupling
**O que é**: integração com [RAFT](https://github.com/WISDEM/RAFT) (frequency-domain floating system simulator) — AncoPlat fornece quasi-estático, RAFT acopla com dinâmica de plataforma.

**Esforço**: **XL** (>15 dias). Decisão estratégica.

**Valor**: posiciona AncoPlat como peça de cadeia de simulação maior; abre caminho para clientes que precisam análise dinâmica.

### Critérios de decisão
Cada subitem 12.x ativado independentemente, com base em:
- Demanda explícita de usuário em produção (≥3 pedidos).
- Disponibilidade de horas de engenharia.
- Existência de caso publicado para V&V.

### Esforço total se tudo go
**XL+** (>40 dias-engenheuiro), distribuídos em sprints pós-1.0.

---

## 3. Riscos transversais e mitigações

### R-T1 — Migração de cases salvos
**Risco**: cases criados em v0.x podem ficar incompatíveis com schema v1.0.
**Mitigação**: cada fase com mudança de schema inclui migrador idempotente; `cases_baseline.json` testado em CI a cada PR.

### R-T2 — Drift do solver entre versões
**Risco**: mudanças em F1/F7 alteram resultado numérico de cases existentes silenciosamente.
**Mitigação**: golden cases bloqueiam merge; `solver_version` registrado em cada execução; banner "Stale solver" no UI quando case foi resolvido com versão antiga.

### R-T3 — Premissas em aberto QMoor/GMoor
**Risco**: significado físico de gmoor_ea segue incerto; usuários podem aplicar erradamente.
**Mitigação**: tooltip explícito + warning em diagnostic + documentação dedicada em CLAUDE.md.

### R-T4 — Dependência de MoorPy para validação
**Risco**: MoorPy pode mudar comportamento e quebrar baselines.
**Mitigação**: pin de versão exato em `requirements-dev.txt`; reproduzir baseline localmente quando atualizar MoorPy.

### R-T5 — Performance degradada em features compostas
**Risco**: watchcircle com 36 azimuths × 8 linhas × multi-segment pode passar de 30s.
**Mitigação**: profiling em Fase 9; cache de baseline; paralelização opcional via threads.

### R-T6 — Solo de produção único, sem staging
**Risco**: bug em produção sem ambiente de pré-prod.
**Mitigação**: para v1.0, considerar staging (`staging.ancoplat.duckdns.org`) com mesmo droplet ou um menor.

### R-T7 — Catálogo de tipos de linha imutável
**Risco**: 522 entradas legacy_qmoor têm dados imperiais convertidos; erros de conversão silenciosos.
**Mitigação**: revisar conversões na Fase 0 ou 10; testes de round-trip imperial↔SI no `seed_catalog.py`.

### R-T8 — Decisões físicas não-documentadas
**Risco**: implementações fazem escolhas implícitas que não estão em CLAUDE.md.
**Mitigação**: cada PR que afeta solver atualiza seção "Decisões fechadas" no CLAUDE.md.

---

## 4. Checklist final — "App pronto para engenheiro profissional usar"

### Estado de progresso por fase (atualizado a cada fase fechada)

- ✅ **Fase 0** — fechada em 2026-05-04. Tag `v0.5-baseline`, snapshots `docs/audit/cases_baseline_2026-05-04.json` e `docs/audit/moorpy_baseline_2026-05-04.json`, ambiente MoorPy isolado em `tools/moorpy_env/`, decisão fechada QMoor/GMoor (modelo NREL `α + β·T_mean`) registrada em CLAUDE.md. 290 testes verdes (282 backend + 8 frontend). Ver [`relatorio_F0_baseline.md`](relatorio_F0_baseline.md).
- ✅ **Fase 1** — fechada em 2026-05-04. Atrito per-segmento (B3) via helper `_resolve_mu_per_seg`; toggle `ea_source` qmoor/gmoor por segmento (A1.4+B4); gate `BC-MOORPY-01..10` (7 ativos + 3 skipados); BC-FR-01 (capstan manual ±2%) e BC-EA-01 (ratio gmoor/qmoor ~12×); frontend com Select EA source + μ override + card "Atrito & EA". 334 backend + 17 frontend verdes. Regressão `cases_baseline` 3/3. Decisão consciente: sem feature-flag (defaults idempotentes). Ver [`relatorio_F1_correcoes_fisicas.md`](relatorio_F1_correcoes_fisicas.md).
- ✅ **Fase 2** — fechada em 2026-05-05. Aba Ambiente refatorada (3 grupos + `BathymetryInputGroup` com slope derivado + modo avançado); `BathymetryPopover` deletado; offset cosmético `startpoint_offset_horz/vert` reservado; validação `startpoint_depth ≥ h` relaxada com slope (Q7) via `_x_estimate`; BC-FAIRLEAD-SLOPE-01 (3 testes); auditoria 29 raises em solver.py + multi_segment.py com classificação a/b/c (13a + 15b + 1c); 25 testes user-facing parametrizados em `test_validation_raises.py`; mensagens E4 hardenizadas. 365 backend + 32 frontend verdes. Round-trip Bathymetry em rtol=1e-9. Regressão baseline 3/3. Ver [`relatorio_F2_ambiente_validacoes.md`](relatorio_F2_ambiente_validacoes.md).
- ✅ **Fase 3** — fechada em 2026-05-05. Quick wins UX: `LineSummaryPanel` com 4 agregados na aba Linha (A1.5); grounded pontilhado vermelho (D6 — decisão consciente, divergência do QMoor cinza, registrada em CLAUDE.md); `boundary.startpoint_type` enum cosmético + Select no grupo Fairlead + ícones SVG novos AHV/Barge/None via dispatcher `getStartpointSvg()` (A2.5+D7); 4 toggles compactos no plot (D9): equal-aspect / labels / legend / images. 372 backend + 41 frontend verdes. Solver intacto. Regressão baseline 3/3. Ver [`relatorio_F3_quick_wins.md`](relatorio_F3_quick_wins.md).
- ✅ **Fase 4** — fechada em 2026-05-05. Diagnostics maturidade + ProfileType taxonomy: `ProfileType` enum (10 valores forward-compat) + `classify_profile_type()` puro em módulo dedicado; validação vs MoorPy 6/7 match + 1 divergência Cat-3 documentada; 4 diagnostics novos (D012 slope alto + D013 μ=0 com catálogo limiar 0.3 empírico + D014 gmoor sem β + D015 PT raro); cobertura `diagnostics.py` em **100%**; `confidence` field (high/medium/low) com critério documentado; `SurfaceViolationsCard` UI dedicada. 438 backend + 57 frontend verdes. Apply tests: 3 garantidos + 3 best-effort + 9 deferred para Fase 10. Ver [`relatorio_F4_diagnostics.md`](relatorio_F4_diagnostics.md).
- ✅ **Fase 5** — fechada em 2026-05-05. Reports, memorial e exportação: `case_input_hash()` SHA-256 canonicalizado (sort_keys + separators, exclui name/description) com 16 testes de canonicalização + estabilidade (Ajuste 1); `.moor` v2 schema versionado + migrador v1→v2 com **log estruturado** `{field, old, new, reason}` exposto via `/import/moor` retornando `{case, migration_log}` (Ajuste 2); `build_memorial_pdf()` com rastreabilidade total (hash[:16] + solver_version + timestamp em footer de cada página) + ProfileType + diagnostics estruturados (severity colorida + confidence) — content checks via PyPDF; CSV de geometria ≥ 5000 pontos international format (`,` separator, `.` decimal) com comentários de metadata; Excel `.xlsx` com 3 abas mínimas (Caso/Resultados/Geometria) + Diagnostics opcional consistente com Memorial PDF; UI com 3 botões em CaseDetail e ImportExportPage; 4 endpoints REST novos (`memorial-pdf`, `csv`, `xlsx`, `import/moor` v2). 499 backend + 4 skipped + 57 frontend verdes. Pendência herdada de F2: `.moor` schema sem `slope_rad`/`attachments` — round-trip dos baseline cases skipa quando aplicável. Ver [`relatorio_F5_reports.md`](relatorio_F5_reports.md).
- ⬜ Fases 6–11 — pendentes

### 4.1 — Correção física
- [ ] Atrito de seabed per-segmento (Fase 1)
- [ ] Toggle EA QMoor/GMoor por segmento com modelo MoorPy `α + β·T_m` documentado (Fase 1)
- [ ] Batimetria 2 pontos como input primário (Fase 2)
- [ ] ProfileType enum exposto no resultado do solve (Fase 4)
- [ ] Anchor uplift (Fase 7) — se em escopo
- [ ] AHV (Fase 8) — se em escopo
- [ ] Todas as `raise ValueError` no solver têm justificativa em comment (Fase 2)
- [ ] V&V vs MoorPy passa em ≥ 10 casos canônicos (BC-MOORPY-01..10) (Fase 1 e 10)
- [ ] V&V vs MoorPy passa em ≥ 14 casos da tabela 10.3 (Fase 10)
- [ ] V&V vs cálculo manual passa em ≥ 5 casos analíticos (Fase 10)

### 4.2 — UX e ergonomia
- [ ] Aba Ambiente sem campos redundantes (Fase 2)
- [ ] Painel agregado na aba Linha (Fase 3)
- [ ] Grounded pontilhado no plot (Fase 3)
- [ ] Toggle equal-scale + labels/legend visível (Fase 3)
- [ ] Ícones de startpoint conforme tipo (Fase 3)
- [ ] Tooltips em todos os campos (Fase 9)
- [ ] Tour de onboarding (Fase 9)
- [ ] 8+ samples canônicos (Fase 9)

### 4.3 — Robustez
- [ ] 100% dos diagnostics têm test repro + apply (Fase 4)
- [ ] Pre-solve cobre ≥ 5 cenários frequentes de erro (Fase 4)
- [ ] Surface violations renderiza UI dedicada (Fase 4)
- [ ] Cobertura ≥ 90% em todos os módulos (Fase 10)
- [ ] Cases extremos (slope ±45°, EA 1e3..1e10, μ 0..5) não crasham (Fase 10)

### 4.4 — Reprodutibilidade
- [ ] Cada execução salva tem `solver_version` (✅ já existe)
- [ ] Banner "Stale solver" funcional (✅ já existe)
- [x] Memorial PDF inclui hash do caso (Fase 5)
- [ ] Changelog público com mudanças que afetam resultado numérico (Fase 11)
- [ ] Cases salvos em v0.x abrem em v1.0 (Fase 11)

### 4.5 — Exportação e integração
- [x] PDF profissional (✅ existe; ampliado na Fase 5 com Memorial técnico)
- [x] Memorial técnico (Fase 5)
- [x] Export CSV (geometria) e Excel (caso completo) (Fase 5)
- [x] `.moor` v2 com round-trip estável (Fase 5) — limitação herdada: schema sem slope_rad/attachments, pendente em Fase 5.x ou 12

### 4.6 — Catálogos
- [ ] Cabos: 522 entradas legacy_qmoor (✅)
- [ ] Cabos: library paramétrica MoorPy disponível em modo "calculadora" (Fase 6, opcional)
- [ ] Boias: ≥ 5 entradas seed (Fase 6)
- [ ] Usuário pode adicionar entradas custom (✅ cabos; Fase 6 boias)

### 4.7 — Documentação
- [ ] CLAUDE.md atualizado (Fase 11)
- [ ] Manual de usuário cobre 100% da UI (Fase 11)
- [ ] Glossário (Fase 9)
- [ ] Decisões fechadas documentadas (Fase 11)
- [ ] Convenções de sinal/unidade (Fase 11)
- [ ] Changelog público (Fase 11)

### 4.8 — Operação
- [ ] Backups diários funcionando (✅)
- [ ] Healthcheck a cada 5 min (✅)
- [ ] SSL renovação automática (✅)
- [ ] Manual operacional ([operacao_producao.md](../docs/operacao_producao.md)) atualizado (Fase 11)
- [ ] Plano de rollback testado (Fase 11)

### 4.9 — Performance
- [ ] Solve typical < 100ms (Fase 10)
- [ ] Watchcircle 36 azimuths < 30s (Fase 10)
- [ ] Live preview sem trava (Fase 10)
- [ ] API p95 < 100ms (Fase 10)

### 4.10 — Lançamento
- [ ] Tag v1.0.0 (Fase 11)
- [ ] GitHub release com notas (Fase 11)
- [ ] Deploy em produção sem erros (Fase 11)
- [ ] 48h de uptime pós-deploy (Fase 11)

---

## 5. Princípios transversais

1. **Não quebrar cases existentes** — toda mudança física é feature-flag ou tem migrador idempotente. Testes de regressão sobre `cases_baseline.json` em todo PR.
2. **Decisões fechadas em CLAUDE.md são respeitadas** — default QMoor (EA estático), submerged_force líquido, brentq sem fallback bisection, fairlead/anchor convenções de sinal. Revisitar uma decisão fechada exige seção dedicada no PR explicando por quê.
3. **Vantagens do AncoPlat são preservadas** — F5.5, F5.6, F5.7.1, diagnostics estruturados, multi-system compare, sistema de unidades comutável, importação .moor legacy. **Nada disso é nivelado por baixo para "alinhar com QMoor" ou MoorPy.**
4. **MoorPy é referência de validação, não target de paridade total.** Adotamos modelos físicos documentados (EA dinâmico α+β·T_m, ProfileType taxonomy) e usamos como benchmark numérico (golden cases). Não copiamos features que não fazem sentido no escopo do AncoPlat (ex: integração com simulador dinâmico, output via matplotlib).
5. **Cada fase entrega independente** — fim de fase = PR mergeado, deploy em produção possível, valor incremental para o usuário.
6. **Critérios de aceitação são métricos** — sem "está bom"; só números (cobertura ≥ X%, erro ≤ Y%, latência < Z ms).
7. **Validação física precede merge no solver** — qualquer PR que toca `backend/solver/` passa por gate de golden cases + V&V dedicada da fase. **A partir da Fase 1, BC-MOORPY-01..10 entram nesse gate.**
8. **Mudanças que afetam resultado numérico aparecem em changelog público** — princípio de reprodutibilidade científica.
9. **Conversa com usuário antes de fases especulativas** — Fase 8 (AHV) depende de decisão go/no-go explícita; Fase 7 (uplift) depende de demanda confirmada; Fase 12 (features avançadas) só após v1.0 em produção e demanda observada.

---

## 6. Resumo: o que falta para "profissional completo"

- **3 correções físicas** (atrito per-segmento, EA toggle com modelo MoorPy `α + β·T_m`, batimetria 2 pontos).
- **5 quick wins UX** (agregado, grounded dotted, ícones, equal-scale, startpoint type).
- **1 fase de robustez + ProfileType taxonomy** (diagnostics maturidade + classificação MoorPy de regimes catenários).
- **1 fase de exportação** (memorial, CSV, .moor v2).
- **1 fase de catálogo + library paramétrica opcional** (boias + fórmulas MoorPy de materiais).
- **1 ou 2 fases de feature** (uplift definitivo; AHV se go).
- **1 fase de polish** (onboarding, performance, a11y).
- **1 fase de V&V** com **14 casos canônicos validados contra MoorPy** + cálculo manual + casos publicados.
- **1 fase de doc** (lançamento 1.0).
- **+1 fase futura pós-1.0** com features avançadas opcionais (Jacobianos analíticos, modelo de custo, bathymetry 2D, integração RAFT).

Total núcleo: **12 fases**, ~13–20 semanas-engenheiro (incluindo aumento de Fase 1 e Fase 10 para integrar MoorPy), todas com critérios de aceitação mensuráveis e gates de qualidade explícitos. Fase 12 é roadmap, não MVP.

**Diferencial após este plano**: AncoPlat passa a ter **3 referências externas validadas** (cálculo manual analítico, MoorPy/NREL open-source, casos publicados em literatura técnica), o que é cobertura de V&V acima da média de ferramentas comerciais do setor (que tipicamente validam só contra si mesmas ou contra um único software de referência).

---

*Plano gerado em 2026-05-04 e atualizado na mesma data com integração MoorPy. Revisar trimestralmente ou ao fim de cada fase.*
