# Manual do Usuário — AncoPlat v1.0

> Versão do app: **1.0.0** · Última atualização: 2026-05-05
> URL pública: **https://ancoplat.duckdns.org**

---

## Sumário

1. [O que é o AncoPlat](#1-o-que-é-o-ancoplat)
2. [Conceitos físicos essenciais](#2-conceitos-físicos-essenciais)
3. [Walkthrough — caso simples (single-segmento)](#3-walkthrough--caso-simples-single-segmento)
4. [Walkthrough — multi-segmento e attachments](#4-walkthrough--multi-segmento-e-attachments)
5. [Walkthrough — sistema de mooring (multi-linha)](#5-walkthrough--sistema-de-mooring-multi-linha)
6. [Anchor uplift (linha suspensa)](#6-anchor-uplift-linha-suspensa)
7. [AHV (Anchor Handler Vessel)](#7-ahv-anchor-handler-vessel)
8. [Diagnostics — quando aparecem e como agir](#8-diagnostics--quando-aparecem-e-como-agir)
9. [Importar / exportar](#9-importar--exportar)
10. [Glossário](#10-glossário)
11. [FAQ](#11-faq)
12. [Disclaimer técnico](#12-disclaimer-técnico)

---

## 1. O que é o AncoPlat

AncoPlat é um aplicativo web de **análise estática de linhas de
ancoragem offshore**. Você descreve um cabo (geometria, propriedades
do material, critério de utilização) e o app resolve a equação da
**catenária elástica com contato no seabed e atrito de Coulomb**,
devolvendo:

- Tração no fairlead e na âncora.
- Distribuição de tensões ao longo da linha (T_max, T_min).
- Geometria resolvida (touchdown, comprimento apoiado, elongação).
- Ângulos críticos (anchor uplift, fairlead).
- Classificação operacional (`ok | yellow | red | broken`) por
  critério selecionado.
- Memorial PDF, exportação CSV/XLSX, importação `.moor` v2.

### Validação

A v1.0 carrega **36 cases canônicos** validados:
- **9 BC-MOORPY** ativos (catenária pura) vs MoorPy v1.x rtol≤1e-4.
- **5 BC-UP** (anchor uplift) vs MoorPy rtol≤1e-2.
- **4 BC-AHV** (Anchor Handler Vessel) vs cálculo manual rtol=1e-2
  (catenária paramétrica, erro 0.0000%).
- **7 BC-AT-GB** (lifted arches) com geometria analítica
  s_arch=F_b/w confirmada.
- **14 VV-01..14** (gate v1.0) com erro real medido em
  [`docs/audit/vv_v1_errors.json`](audit/vv_v1_errors.json).

### Limites de uso (escopo v1.0)

- Análise **estática** — sem dinâmica, snap loads ou viscosidade.
- 2D no plano vertical da linha — sem 3D.
- AHV = idealização estática (vide §7).
- Sem multi-seg + uplift, sem AHV + uplift, sem linha boiante (w<0).

Roda inteiramente no servidor de produção; cases ficam em SQLite. UI
em PT-BR, termos técnicos em inglês quando padrão internacional
(catenary, fairlead, bollard pull).

---

## 2. Conceitos físicos essenciais

### Catenária elástica com seabed

A linha pendurada entre âncora e fairlead toma a forma de uma
**catenária**. Uma fração pode estar **apoiada** no fundo (grounded)
quando o peso supera a tensão horizontal — o ponto onde a linha
descola do solo é o **touchdown point** (TD). Atrito de Coulomb
(coeficiente `μ`) age na zona apoiada, transferindo tensão da âncora
para a parte suspensa.

### Modos de solução

- **Tension** — você informa a tração desejada no fairlead `T_fl`.
  Solver encontra a distância horizontal X que resulta nessa tensão.
- **Range** — você informa a distância `X` entre âncora e fairlead.
  Solver encontra `T_fl` correspondente.

### Sistema de unidades

Internamente sempre **SI** (metros, Newtons, kg). Conversões são
apenas nas bordas (input/output de UI, exports). O usuário pode
visualizar resultados em SI ou métrico (te, kgf/m). Conversão
round-trip preserva precisão dentro de `rtol < 1e-10` (gate F10).

### EA estático (QMoor) vs EA dinâmico (GMoor)

Cada material do catálogo carrega dois valores de rigidez axial:
- **EA estático** (default, `qmoor_ea`) — rigidez quasi-estática,
  válida para análise de carga lentamente aplicada.
- **EA dinâmico** (`gmoor_ea`) — rigidez de curto prazo após
  relaxamento elástico. Aplicável quando a análise demanda tensão
  dinâmica.

Toggle por segmento via campo `ea_source: "qmoor" | "gmoor"`.
Detalhes em [decisões fechadas §1](decisoes_fechadas.md#1).

### ProfileType (taxonomia NREL/MoorPy)

Cada solução é classificada em uma das categorias:
- **PT_1** — fully suspended (linha não toca seabed).
- **PT_2** — touchdown sem atrito (μ=0).
- **PT_3** — touchdown com atrito (μ>0).
- **PT_-1** — ill-conditioned (catenária degenerada, ex.: hardest
  taut).
- Outros (PT_4 boiante, PT_5 U-shape, PT_6 vertical) reservados
  para v1.1+.

Vide [decisões fechadas §5](decisoes_fechadas.md#5).

### Convenção de sinal

- Eixo X: horizontal, positivo do anchor para o fairlead.
- Eixo Y: vertical, positivo apontando para CIMA.
- Tensões reportadas em **magnitude positiva**.
- `endpoint_grounded=True` (default): âncora apoiada no seabed.
- `endpoint_grounded=False`: âncora elevada (anchor uplift, vide §6).

---

## 3. Walkthrough — caso simples (single-segmento)

### 3.1. Abrir o formulário

Caminhos equivalentes:
- Sidebar → **"Casos"** → botão **"Novo caso"**.
- Atalho `g c` (vai para Casos) e clicar em "Novo".
- Atalho `g s` para abrir templates samples e duplicar caso pronto.

### 3.2. Metadados

- **Nome do caso** (obrigatório). Ex.: `BC-01 catenária suspensa`.
- **Critério de utilização** (default `MVP_Preliminary`):
  - `MVP_Preliminary` — yellow 0.50, red 0.60, broken 1.00 (T/MBL).
  - `API_RP_2SK` — perfil oficial intacto/danificado (0.60/0.80).
  - `DNV` — placeholder; análise dinâmica formal só em v3+.
  - `UserDefined` — você define os limites yellow/red/broken.
- **Notas** (opcional, collapsible).

### 3.3. Definir o segmento de linha

No card **Segmento de linha**:

1. Clique no seletor de catálogo no topo. Pesquise (ex.: `IWRCEIPS`,
   `R4Studless`, `DiamondBlue`). Ao escolher, os campos abaixo são
   preenchidos automaticamente em SI a partir do catálogo legacy
   (522 entradas).
2. Você pode editar manualmente:
   - **Comprimento `L`** (m).
   - **Peso linear `w`** (N/m, peso submerso).
   - **Rigidez axial `EA`** (N).
   - **MBL** (Minimum Breaking Load, N).
3. Toggles avançados:
   - **EA source** — `qmoor` (default) ou `gmoor`.
   - **μ override** — sobrescreve atrito do catálogo só neste
     segmento.

### 3.4. Aba Ambiente

- **Geometria** — modo "batimetria 2 pontos" (default):
  - Profundidade no fairlead `startpoint_depth` (sondagem 1).
  - Profundidade na âncora `h` (sondagem 2).
  - Slope é **derivado** read-only.
  Modo avançado libera `slope_rad` direto.
- **Fairlead** — tipo de plataforma (semisub default, AHV, Barge,
  none) que determina o ícone do startpoint no plot.
- **Seabed** — `mu` global (default catálogo do segmento se houver).

### 3.5. Aba Linha → Modo + input

- **Modo Tension**: campo `T_fl` (default) — força no fairlead.
- **Modo Range**: campo `X` — distância horizontal âncora→fairlead.

### 3.6. Resolver

Clique **"Resolver"**. Aparecem 3 abas de resultado:
- **Plot** — geometria 2D com touchdown marcado, grounded em
  pontilhado vermelho, suspended em sólido azul.
- **Resultados** — cards com T_fl, T_anchor, T_max, ângulos,
  alert_level.
- **Diagnostics** — vide §8.

---

## 4. Walkthrough — multi-segmento e attachments

### 4.1. Adicionar segmentos

No card **Segmento de linha**, clique **"+ Adicionar segmento"**.
Cada segmento herda config do catálogo independentemente — config
típica: chain (heavy) + wire/polyester (light) + chain (heavy)
para FPSO.

O atrito é **per-segmento** com precedência canônica:
```
mu_override → seabed_friction_cf (catálogo) → seabed.mu (global) → 0
```
Vide [decisões fechadas §2](decisoes_fechadas.md#2).

### 4.2. Attachments (boias e clump weights)

Em cada junção entre segmentos OU posição arbitrária ao longo da
linha, você pode adicionar:

- **Boia** (`kind=buoy`) — empurra a linha PARA CIMA. Campo
  `submerged_force` em N (≥0).
- **Clump weight** (`kind=clump_weight`) — puxa a linha PARA BAIXO.
  Mesmo campo.

Posicionamento (mutuamente exclusivo):
- `position_index` (legacy F5.2): índice da junção pré-existente.
  0 = entre seg 0 e seg 1.
- `position_s_from_anchor` (recomendado): arc length desde a âncora
  (m). Solver divide o segmento contendo essa posição em
  sub-segmentos automaticamente.

### 4.3. Boias profissionais (do catálogo)

Tab **"Boias"** em `/catalog` (deep-link `?tab=buoys`) lista 11
boias seed:
- 1× `excel_buoy_calc_v1` (R7 do Excel `Buoy_Calculation_*.xlsx`).
- 10× `generic_offshore` cobrindo dimensões D 1.0–3.0 m / L 2.0–4.5 m.

`BuoyPicker` em `AttachmentsEditor` permite buscar e aplicar boia do
catálogo. Override em qualquer dos 6 campos físicos zera
`buoy_catalog_id` automaticamente (badge muda de azul "do catálogo"
para laranja "modo manual"). Override deliberado preserva
rastreabilidade — solver ignora `buoy_catalog_id` em runtime
(verificado por teste).

### 4.4. Lifted arches (boia na zona apoiada)

Quando uma boia está em material UNIFORME e na zona grounded
(posição em `[0, L_grounded_total]`), o solver detecta automaticamente
e substitui o walk linear flat por **arcos catenários simétricos**
em torno da boia. Geometria: `s_arch = F_b / w_local`.

Boias em junção heterogênea (chain↔wire) seguem o caminho legacy
(force jump na junção). Detecção é automática em
[`backend/solver/grounded_buoys.py`](../backend/solver/grounded_buoys.py).

---

## 5. Walkthrough — sistema de mooring (multi-linha)

### 5.1. Criar um sistema

**Sidebar → "Mooring systems" → "Novo sistema"**.

Schema:
- **Plataforma**: raio (m), tipo de plataforma.
- **N linhas** com fairlead em coordenadas polares:
  - `fairlead_azimuth_deg` (graus, eixo X global anti-horário).
  - `fairlead_radius` (m, do centro).
  - Cada linha carrega um caso completo (segmentos, boundary,
    seabed) — pode reusar de um caso já criado.

### 5.2. Plan view

Aba **Plan view** mostra layout 2D do sistema (top-down): plataforma
no centro, linhas radiais, âncoras como pontos.

### 5.3. Equilíbrio sob carga ambiental

Aba **Equilíbrio**:
- Informe carga horizontal externa `F_env` em (Fx, Fy) N.
- Solver `solve_platform_equilibrium` itera offset (Δx, Δy) tal que
  Σ F_lines(Δ) + F_env = 0.
- Resultado: deslocamento da plataforma + resultado individual de
  cada linha sob o novo arranjo.

### 5.4. Watchcircle (envelope 360°)

Aba **Watchcircle**:
- Magnitude de carga fixa, varre 360° em N passos (default 36).
- Plot mostra envelope de offsets + animação play/pause/scrub.
- Performance: paralelizado via `ProcessPoolExecutor`. Spread 4×
  resolve em ~17s (gate <30s); shallow chain 4× pode levar ~25s
  (pendência v1.1 de heurística pré-fsolve).
- Vide [decisões fechadas §11](decisoes_fechadas.md#11).

---

## 6. Anchor uplift (linha suspensa)

### 6.1. Quando usar

A maioria dos cases assume `endpoint_grounded=True` (âncora
apoiada). Mas em águas profundas ou com tensão alta, a âncora pode
ficar **elevada acima do seabed** — a linha não toca o solo na
extremidade da âncora. Isso é **anchor uplift** (PT_1 em
ProfileType).

Tipicamente requerido em:
- Águas profundas (>500 m) com pré-tensão alta.
- Pile/suction caisson anchors (toleram tração vertical).
- Análise de cenários de tempestade onde linha levanta âncora.

### 6.2. Como ativar

Aba **Ambiente** → grupo **Geometria**:
- Radio: **Grounded** (default) ou **Suspended**.
- Selecionar **Suspended** habilita o campo `endpoint_depth` (m,
  profundidade onde a âncora está fisicamente).

Validações (Pydantic):
- `endpoint_depth` é obrigatório quando `endpoint_grounded=False`.
- `endpoint_depth` deve ser positivo e ≤ `h + ε`.

### 6.3. Limitações em v1.0

A v1.0 suporta uplift apenas em:
- **Single-segmento** (multi-seg + uplift bloqueado com
  `NotImplementedError` específico → INVALID_CASE).
- **Sem attachments** (uplift + boia/clump bloqueado).
- **Sem AHV** (uplift + AHV bloqueado).

Combinações pendentes documentadas em
[`docs/proximas_fases/F7_anchor_uplift_miniplano.md`](proximas_fases/F7_anchor_uplift_miniplano.md)
para v1.1+.

### 6.4. Diagnostics dedicados

- **D016** (high, error) — anchor uplift fora de domínio.
- **D017** (medium, warning) — uplift desprezível (<1 m), sugere
  voltar a `endpoint_grounded=True` para regime numericamente mais
  robusto.

---

## 7. AHV (Anchor Handler Vessel)

> **Esta seção é leitura obrigatória antes de usar a feature AHV.**

### 7.1. Domínio de aplicação

A feature **AHV (Anchor Handler Vessel)** modela uma carga estática
horizontal aplicada num ponto da linha de ancoragem durante operação
de **instalação de âncora**. O caso de uso típico é o cálculo
preliminar da tensão na linha quando um rebocador (anchor handler)
está engatado ao cabo aplicando bollard pull para posicionar a
âncora.

A feature é **especializada para análise de instalação** — não
substitui as análises rotineiras de operação (catenária pura sem
AHV) nem deve ser usada para certificação de operação dinâmica
(snap loads, ondas, vento variável).

### 7.2. Idealização modelada vs operação real

> **Esta é a parte mais importante desta seção. Leia com atenção.**

A modelagem do AncoPlat é uma **idealização estática** da operação
real:

| Aspecto físico | Realidade na operação | Modelo AncoPlat v1.0 |
|----------------|-----------------------|----------------------|
| Posição do rebocador | Dinâmica (oscila com ondas) | Fixa, ponto único na linha |
| Direção do bollard pull | Varia com posicionamento dinâmico | Constante, ângulo `heading` informado |
| Magnitude da força | Oscila com ondas + vento | Constante, valor `bollard_pull` informado |
| Acoplamento hidrodinâmico | Cabo/rebocador interagem com fluxo | Não modelado |
| Snap loads | Ocorrem em rebocador desalinhado | Não capturados |
| Pitch da força (Fz≠0) | Existe quando rebocador puxa pra cima | Não modelado em v1.0 |
| 3D (componente fora do plano) | Existe na operação real | Reduzido a 2D no plano da linha |

A consequência prática é: o resultado do AncoPlat é uma estimativa
**média conservadora** da carga em junção sob aquela combinação de
bollard pull + heading, válida para dimensionamento preliminar mas
**não substitui análise dinâmica de instalação** com modelo de
ondas, posicionamento do rebocador e dinâmica do cabo.

### 7.3. Quando usar

Use a feature AHV quando:
- Estimar carga em junção durante operação de instalação para
  dimensionamento preliminar de pendant.
- Avaliar sensibilidade da tensão na linha à magnitude e direção do
  bollard pull (varredura paramétrica).
- Documentar premissas estáticas em memorial técnico para revisão
  por engenheiro responsável.
- Comparar layouts de instalação alternativos (rota de aproximação
  do rebocador, ângulo de engate) em primeira ordem.

### 7.4. Quando NÃO usar

> **Quando NÃO usar tem peso igual ao "quando usar". Não é footnote.**

NÃO use a feature AHV para:

- **Certificação operacional** de instalação. AncoPlat não substitui
  software dedicado de análise dinâmica (OrcaFlex, Aqwa, Sesam,
  etc.). Use AncoPlat para preliminary scoping; certificação requer
  análise dinâmica auditada.
- **Análise de snap loads**. Cargas de impacto durante desalinhamento
  do rebocador NÃO são capturadas pela idealização estática.
  Subestima carga máxima em cenários adversos.
- **Operação em ondas significativas** (Hs > ~1.5 m) sem cross-check
  dinâmico. A idealização estática perde aderência à realidade
  conforme aumenta a oscilação do rebocador.
- **Decisão de bollard pull máximo aplicável**. O número de bollard
  pull que você informa é input, não output. AncoPlat reporta o que
  acontece NA LINHA dado o bollard, não diz qual bollard é seguro
  aplicar — isso depende do AHV físico, do cabo de engate, do
  conector e da equipe de operação.
- **Substituto de análise de fadiga**. Carga estática única não dá
  ciclos.

### 7.5. Diagnostics dedicados (D018 e D019)

A v1.0 carrega 2 diagnostics que disparam automaticamente em cases
com AHV:

#### D018 — AHV idealização estática

- **Severity:** warning
- **Confidence:** medium
- **Quando dispara:** **sempre que `kind="ahv"` está presente em
  qualquer junção do caso**. Não há opção de esconder.
- **Mensagem:** "Análise estática de AHV é idealização — não
  substitui análise dinâmica de instalação."
- **O que fazer:** ler esta seção do manual e o bloco "AHV — Domínio
  de aplicação" no Memorial PDF gerado para o caso. Confirmar que o
  uso pretendido se enquadra em §7.3.

D018 é registrado no Memorial PDF em seção dedicada,
explicitamente, **com o texto canônico desta idealização**. Esta
mitigação em 3 níveis (D018 + Memorial + manual) é decisão fechada
da Fase 8 e **não é opcional**: vide
[decisões fechadas §9](decisoes_fechadas.md#9).

#### D019 — Heading com projeção <30%

- **Severity:** warning
- **Confidence:** high
- **Quando dispara:** quando o `ahv_heading_deg` resulta em projeção
  inferior a 30% no plano vertical da linha. Exemplo: linha alinhada
  com eixo X (azimute 0°) + AHV com heading=85° → projeção horizontal
  da força AHV no plano da linha é cos(85°)=0.087, ou seja, ~9%.
- **Por que importa:** se o engenheiro digita um bollard pull alto
  (1+ MN) e um heading quase perpendicular ao plano da linha,
  o resultado da análise pode ficar quase idêntico ao caso SEM AHV
  (porque a força projetada é desprezível). D019 alerta para o
  usuário verificar se o heading está correto OU se o caso deveria
  ser modelado em 3D (limitação v1.0 — vide §7.2).
- **O que fazer:** revisar `ahv_heading_deg`. Em referencial: 0° = eixo
  X global, anti-horário. Se a linha é radial num spread mooring,
  use o azimute do fairlead como heading do AHV alinhado.

### 7.6. Exemplo numérico — BC-AHV-01 (lateral pura)

Caso canônico do gate v1.0:

- **Geometria:** 2 segmentos chain studless de 200 m cada, h=200 m,
  `T_fl=2 MN`.
- **AHV:** junção 0 (entre seg 0 e seg 1), `bollard_pull=1 MN`,
  `heading=0°` (alinhado com eixo X global, mesma direção da
  catenária).

Resultado:
- **H_jump na junção 0:** -1 MN (AHV puxa contra a tensão da linha
  na direção da âncora).
- **H_anchor:** ≈ H_fairlead − 1 MN (queda de 1 MN passando pela
  junção AHV).
- **V_jump:** 0 (AHV horizontal puro).
- **Erro vs cálculo manual:** 0.0000% (catenária paramétrica é
  exata; sem incerteza de modelo elástico como em F7).

Reproduza este caso clicando em **Sidebar → "Samples" → "AHV pull
durante instalação"**.

### 7.7. Onde encontrar mais detalhes

- **Memorial PDF do caso** — seção "AHV — Domínio de aplicação"
  obrigatória quando AHV está presente. Texto canônico verificado
  via 5 strings-chave em PyPDF (vide
  [`backend/api/tests/test_memorial_pdf_ahv.py`](../backend/api/tests/test_memorial_pdf_ahv.py)).
- **Relatório técnico:**
  [`relatorio_F8_ahv.md`](relatorio_F8_ahv.md) — desenvolvimento
  completo da feature, BC-AHV-01..04, descobertas técnicas (H
  per-segmento).
- **Especificação técnica:**
  [`Documento_A_Especificacao_Tecnica_v2_2.docx`](Documento_A_Especificacao_Tecnica_v2_2.docx)
  — domínio offshore canônico.

---

## 8. Diagnostics — quando aparecem e como agir

A v1.0 implementa **16 diagnostics** (D001..D015 + D900) cobrindo
violações geométricas, físicas e numéricas. Cada um carrega:
- **Severity**: `info | warning | error`.
- **Confidence**: `high | medium | low` (vide
  [decisões fechadas §6](decisoes_fechadas.md#6)).
- **Cause**: explicação em PT-BR.
- **Suggestion**: ação recomendada.
- **Suggested changes**: quando aplicável, lista de mudanças
  estruturadas que o usuário pode aplicar.
- **Affected fields**: lista dos campos no schema.

### Tabela rápida

| Code | Significado | Confidence | Apply automatizável |
|------|-------------|:----------:|:-------------------:|
| D001 | Boia próxima da âncora | high | ✓ (mover) |
| D002 | Boia próxima do fairlead | high | ✓ (mover) |
| D003 | Arco overflow do grounded | high | narrativo |
| D004 | Boia acima da superfície | high | ✓ (reduzir empuxo) |
| D005 | Empuxo > peso da linha | high | ✓ (reduzir empuxo) |
| D006 | Cabo curto demais (< chord) | high | ✓ (aumentar L) |
| D007 | T_fl < T_critico horizontal | high | narrativo |
| D008 | Margem ao taut próxima do limite | high | informativo |
| D009 | Anchor uplift > 5° | high | ✓ (aumentar L) |
| D010 | Alta utilização T/MBL | high | ✓ (aumentar MBL) |
| D011 | Cabo abaixo do seabed | high | narrativo |
| D012 | Slope > 30° | high | informativo |
| D013 | μ=0 com catálogo populado | medium | ✓ (setar μ) |
| D014 | gmoor sem β | high | ✓ (voltar qmoor) |
| D015 | ProfileType raro (PT_4/5/-1) | medium | informativo |
| D018 | AHV idealização estática | medium | sempre dispara |
| D019 | AHV heading projeta <30% | high | informativo |
| D900 | Não-convergência genérica | high | narrativo |

### UI

Card **"Diagnostics"** na aba de resultados:
- Lista colapsada por severity (errors > warnings > info).
- Cada item mostra severity badge + confidence badge + cause +
  suggestion.
- Botão "Aplicar sugestão" quando `suggested_changes` é estruturado.

### Memorial PDF

Cada execução do solver gera Memorial PDF rastreável (hash[:16] +
solver_version + timestamp em footer). Diagnostics aparecem em
seção dedicada com severity colorida + confidence indicado.

---

## 9. Importar / exportar

### 9.1. Formato `.moor` v2

JSON próprio do AncoPlat (compatível com Seção 5.2 do MVP v2 PDF).
Schema versionado em `_v2`. Migrador automático `_migrate_v1_to_v2()`
com **log estruturado** `{field, old, new, reason}` exposto via
`POST /api/v1/import-moor` retornando `{case, migration_log}`.

> O `.moor` original do QMoor 0.8.5 era binário proprietário (`.pyd`
> do módulo `cppmoor`) — impossível replicar. Este formato é nosso.

Caminho UI: aba **"Importar/Exportar"** → "Importar" → arrastar
`.moor` ou clicar para selecionar.

### 9.2. Memorial PDF

Geração: botão **"Memorial PDF"** em CaseDetailPage. Conteúdo:
- Cabeçalho com nome do caso, hash, solver_version, timestamp.
- Geometria do caso (segmentos, boundary, seabed).
- Resultado (tensões, ângulos, alert_level, ProfileType).
- Diagnostics estruturados.
- Tabela de attachment_details (boias profissionais com pendant).
- **Seção AHV — Domínio de aplicação** quando `kind="ahv"` está
  presente (vide §7).
- Footer rastreável em cada página.

### 9.3. CSV de geometria

Botão **"Exportar CSV"**. Conteúdo:
- Header com metadata como comentários (`#`).
- ≥ 5000 pontos (s, x, y, T, V, H, on_ground).
- Formato internacional: `,` separator, `.` decimal.

### 9.4. XLSX

Botão **"Exportar XLSX"**. Abas:
- **Caso** — input geometry + boundary + seabed.
- **Resultados** — tensões, ângulos, alert_level.
- **Geometria** — pontos s, x, y, T, V, H.
- **Diagnostics** (opcional, aparece se houver diagnostics).

### 9.5. Importação batch

Aba **"Importar/Exportar"** → "Exportar em lote" exporta múltiplos
casos selecionados por checkbox.

---

## 10. Glossário

Acessível em **Sidebar → "Ajuda" → "Glossário"** (rota
`/help/glossary`). 40 verbetes canônicos em 5 categorias:
- **geometria** — catenária, touchdown, fairlead, anchor.
- **físico** — atrito, EA, MBL, T_fl, T_anchor.
- **componentes** — segmento, attachment, line_type.
- **operacional** — alert_level, critério, AHV, bollard pull.
- **boia** — submerged_force, end_type, pendant.

Busca textual filtra por termo + definição. Filtros por categoria.

---

## 11. FAQ

**Q: Onde ficam meus casos salvos?**
SQLite local em produção `/opt/ancoplat/data/cases.db`. Backup
automático diário (vide
[`operacao_producao.md`](operacao_producao.md) §9). Cases não saem
do servidor.

**Q: Posso usar o solver fora da UI (programaticamente)?**
Sim. API REST documentada em `/api/v1/docs` (FastAPI auto-docs).
Endpoints principais: `POST /api/v1/cases`, `POST /api/v1/cases/{id}/solve`,
`GET /api/v1/cases/{id}/export/memorial-pdf`.

**Q: O que faço se o solver não convergir?**
Verifique os diagnostics retornados — geralmente apontam o problema
exato (cabo curto, EA inválido, geometria infactível). Se status =
`ill_conditioned`, o solver convergiu para uma solução numericamente
delicada (típico de casos hardest taut) — resultado utilizável com
ressalva.

**Q: Cases salvos em v0.x produzem o mesmo resultado em v1.0?**
Sim, **se** não tocarem nas features novas (atrito per-segmento,
ea_source=gmoor, lifted arches em material uniforme, etc.). Lista
exata em [`CHANGELOG.md`](../CHANGELOG.md) §"⚠ Mudanças numéricas".
Regressão `cases_baseline.json` re-roda em rtol=1e-9 a cada PR.

**Q: AHV substitui análise dinâmica de instalação?**
**Não.** Vide §7. AHV é idealização estática útil para estimativa
preliminar de carga em junção. Snap loads e dinâmica do rebocador
NÃO são modelados.

**Q: Como reportar bug?**
Abra issue em https://github.com/marcelocaliman/ancoplat/issues com:
- Versão do app (footer da UI).
- Hash do caso (gerado em cada solve).
- Descrição do que esperava vs o que aconteceu.
- Memorial PDF se possível (anonimiza dados sensíveis).

---

## 12. Disclaimer técnico

### Validação

AncoPlat v1.0 é validado contra **MoorPy** (NREL, MIT-licensed) em
9 cases ativos do `tests/test_catenary.py` (BC-MOORPY) + 5 cases de
anchor uplift (BC-UP) + 4 BC-AHV vs cálculo manual + 7 BC-AT-GB
analítico + 14 VV-01..14 (gate v1.0). Erro real medido em
[`docs/audit/vv_v1_errors.json`](audit/vv_v1_errors.json).

### Limitações de modelagem

1. **Estática 2D** — sem dinâmica, snap loads, viscosidade ou 3D.
2. **AHV é idealização** — vide §7.
3. **Linha boiante (w<0)** não suportada — reservado para v1.2+.
4. **Multi-seg + uplift, AHV + uplift, boia + uplift** bloqueados
   em v1.0 — combinações para v1.1+.
5. **Modelo dinâmico EA(T) com β** — `β=0` implícito em v1.0;
   modelo completo `EA(T)=α+β·T_mean` reservado para v1.1+.

### Reprodutibilidade científica

- Cada caso gera hash SHA-256 canonicalizado em `case_input_hash()`
  (sort_keys + separators sem whitespace, exclui `name`/`description`).
- Memorial PDF carrega hash[:16] + solver_version + timestamp em
  cada página.
- Mudanças numéricas entre versões marcadas em
  [`CHANGELOG.md`](../CHANGELOG.md) §"⚠ Mudanças numéricas".
- Decisões físicas/numéricas/arquiteturais consolidadas em
  [`docs/decisoes_fechadas.md`](decisoes_fechadas.md).

### Responsabilidade

AncoPlat é ferramenta de análise técnica. Resultados são
estimativas baseadas em modelos físicos com tolerâncias documentadas
— **não substituem** análise certificada por profissional habilitado
(engenheiro offshore, certificação DNV/ABS/etc.) para projetos
operacionais. O usuário é responsável pela aplicação dos resultados.

### Licenças

- AncoPlat: pessoal/research (verificar com autor).
- Integração com MoorPy: MoorPy é MIT-licensed (NREL).
- Catálogo de materiais: importado de QMoor 0.8.5 legacy (522
  entradas, rastreabilidade preservada via `legacy_id`).

---

*Manual gerado para v1.0.0. Para versões anteriores, consulte o git
log e CHANGELOG.md.*
