# Decisões fechadas — AncoPlat v1.0

**Documento canônico para auditoria científica externa.**

Este documento consolida as 13 decisões físicas, numéricas e
arquiteturais não-triviais tomadas durante o desenvolvimento do
AncoPlat (fases F0–F10), cada uma com justificativa técnica, fonte de
referência canônica e link para o relatório de fase onde foi
formalizada.

> Audiência: outro engenheiro/revisor científico avaliando o solver
> sem ter participado das discussões. Este NÃO é o briefing
> operacional para Claude (esse é [`CLAUDE.md`](../CLAUDE.md)) — é o
> registro permanente que sobrevive ao histórico do repositório.

---

## #1 — EA estático (QMoor) vs EA dinâmico (GMoor)

**Fase:** F-prof.0 (auditoria pré-profissionalização).

**Decisão:** o solver usa `EA_estatico = EA_MBL × MBL` (default,
campo `qmoor_ea` do catálogo) como rigidez axial. O usuário pode
trocar para `EA_dinamico = EAd × MBL` (campo `gmoor_ea`) caso a
análise demande rigidez de curto prazo (após relaxamento elástico,
antes de creep). Modelo dinâmico completo
`EA(T) = α + β·T_mean` tem `β` reservado como pendência v1.1+ — em
v1.0, β=0 implícito (modelo dinâmico simplificado).

**Justificativa:** a premissa "não há base documental" registrada na
origem foi resolvida por inspeção do
[MoorPy](https://github.com/NREL/MoorPy) (NREL, peer-reviewed em ASME
2025). `moorpy/line.py:1027-1044` e
`moorpy/library/MoorProps_default.yaml` formalizam a separação
estático/dinâmico. Polyester exibe razão `gmoor/qmoor` de 10–22×;
wires EIPS ~1.45×; correntes ~0.88×.

**Referência canônica:** MoorPy `moorpy/line.py:1027-1044`,
`moorpy/library/MoorProps_default.yaml`.

**Link:** [`relatorio_F1_correcoes_fisicas.md`](relatorio_F1_correcoes_fisicas.md)
e [`CLAUDE.md` §"Modelo físico de QMoor vs GMoor"](../CLAUDE.md).

---

## #2 — Atrito de seabed per-segmento (precedência canônica)

**Fase:** F-prof.1 (correções físicas críticas).

**Decisão:** o coeficiente de atrito efetivo de cada segmento é
resolvido pelo helper `_resolve_mu_per_seg()` em
[`backend/solver/solver.py`](../backend/solver/solver.py) seguindo
precedência canônica:
```
segment.mu_override → segment.seabed_friction_cf → seabed.mu → 0.0
```

**Sem feature-flag**: defaults `None` em `mu_override` e
`seabed_friction_cf` preservam comportamento legado naturalmente
(cai no `seabed.mu` global). Cases v0.x salvos antes da F-prof.1
re-rodam com mesmo resultado dentro de `rtol=1e-9`.

**Justificativa:** materiais heterogêneos (chain + wire) em mesma
linha têm coeficientes muito diferentes (chain studless μ≈0.6-1.0,
wire EIPS μ≈0.6, polyester μ≈1.0). Atrito global único era
aproximação grosseira. Validação: BC-FR-01 (capstan manual) confirma
`ΔT = μ·w·L_grounded` (Coulomb axial) dentro de ±2%.

**Referência canônica:** Coulomb friction model + catálogo legacy
QMoor.

**Link:** [`relatorio_F1_correcoes_fisicas.md`](relatorio_F1_correcoes_fisicas.md)
e [`CLAUDE.md` §"Atrito de seabed per-segmento"](../CLAUDE.md).

---

## #3 — Catenária na forma geral (`s_a ≥ 0`)

**Fase:** F1b (implementação do solver).

**Decisão:** o solver implementa a forma geral da catenária
parametrizada por `s_a ≥ 0` (arc length do vértice virtual ao
anchor), cobrindo tanto V_anchor=0 (touchdown iminente) quanto
V_anchor > 0 (fully suspended típico). Posteriormente estendido em
F7 para aceitar `s_a < 0` (vértice em "U" — uplift severo).

**Justificativa:** a Seção 3.3.1 do Documento A v2.2 apresentava
equações assumindo âncora no vértice (V_anchor=0). É caso particular.
BC-01 (T_fl=785 kN, MoorPy benchmark) exige V_anchor > 0 — linha
quase taut, anchor pull-up acentuado. Forma geral é necessária para
cobrir o domínio.

**Referência canônica:** MoorPy `Catenary.catenary` upstream + nossa
extensão para uplift severo
([`backend/solver/suspended_endpoint.py`](../backend/solver/suspended_endpoint.py)
F7).

**Link:** [`relatorio_F1b.md`](relatorio_F1b.md),
[`relatorio_F7_anchor_uplift.md`](relatorio_F7_anchor_uplift.md).

---

## #4 — Loop elástico via `scipy.optimize.brentq`

**Fase:** F1b.

**Decisão:** a iteração elástica que ajusta `L_eff = L·(1+T̄/EA)` é
resolvida por `brentq` sobre `F(L_eff) = L_eff − L·(1+T̄/EA) = 0`
com bracket explícito em limites físicos. **Não** ponto-fixo,
**não** fallback de bisseção manual.

**Justificativa:** a iteração ingênua de ponto-fixo
`L_{n+1} = L·(1 + T̄(L_n)/EA)` diverge por oscilação em casos muito
taut (L_stretched próximo de √(X²+h²)), notadamente BC-05. `brentq`
internamente é Brent-Dekker (híbrido com fallback de bisseção
nativo) — robusto em todos os 45 testes da F1b. Parâmetro
`max_bisection_iter` (mencionado no Documento A v2.2) foi removido
como redundante.

**Referência canônica:** SciPy
[`scipy.optimize.brentq`](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.brentq.html)
+ Brent (1973) "Algorithms for Minimization Without Derivatives".

**Link:** [`relatorio_F1b.md`](relatorio_F1b.md) e
[`backend/solver/elastic.py`](../backend/solver/elastic.py).

---

## #5 — ProfileType taxonomy NREL/MoorPy

**Fase:** F-prof.4 (diagnostics maturidade).

**Decisão:** AncoPlat adota o vocabulário **ProfileType** do
MoorPy/NREL (`Catenary.py:147-163`) para classificar regimes
catenários. Enum com 10 valores forward-compat: `PT_0..PT_8 + PT_U`.
Alguns valores são reservados para fases futuras (PT_4 boiante = F12,
PT_5 U-shape = F7+).

**Justificativa:** vocabulário comum com a referência (MoorPy)
permite cross-validação direta de cases. Validação na F4: 6/7 match
perfeito + 1 divergência Cat-3 documentada (BC-MOORPY-08 hardest taut
PT_-1, fallback do MoorPy sem equivalente canônico). Princípio
transversal: divergências são registradas e categorizadas (Cat-1 bug
/ Cat-2 modelo / Cat-3 numérica), nunca forçadas a match cosmético.

**Referência canônica:** MoorPy `Catenary.py:147-163` (NREL,
MIT-licensed).

**Link:** [`relatorio_F4_diagnostics.md`](relatorio_F4_diagnostics.md)
e [`backend/solver/profile_type.py`](../backend/solver/profile_type.py).

---

## #6 — Confidence levels em `SolverDiagnostic`

**Fase:** F-prof.4 (Q7).

**Decisão:** cada `SolverDiagnostic` carrega um campo
`confidence: high | medium | low`:
- **high** — violação determinística (matemática ou física).
  Diagnóstico SEMPRE correto quando dispara.
- **medium** — heurística calibrada empiricamente. Pode ter falso
  positivo em casos extremos legítimos.
- **low** — pattern detection sem base teórica forte.
  RESERVADO — exige justificativa explícita no docstring.

**Justificativa:** sem o campo, todos os diagnostics tinham peso
implícito igual. Calibração empírica do D013 (μ=0 com catálogo,
limiar 0.3) é diferente em natureza da validação determinística do
D001 (boia próxima da âncora). Engenheiros consumindo a UI/Memorial
PDF precisam discriminar.

**Referência canônica:** docstring de `ConfidenceLevel` em
[`backend/solver/diagnostics.py`](../backend/solver/diagnostics.py).

**Link:** [`relatorio_F4_diagnostics.md`](relatorio_F4_diagnostics.md).

---

## #7 — Grounded pontilhado vermelho (divergência consciente do QMoor)

**Fase:** F-prof.3 (quick wins UX).

**Decisão:** AncoPlat exibe a porção apoiada (grounded) da linha
como **linha pontilhada vermelha** (`dash: 'dot'`, cor ≈ `#DC2626`).
QMoor 0.8.5 usa cinza pontilhado.

**Justificativa:** três motivos técnicos:
1. Vermelho destaca melhor a porção apoiada do que cinza,
   especialmente em plots com tema claro/escuro.
2. Princípio transversal #4 do plano de profissionalização —
   "MoorPy/QMoor são referência de validação, não target de paridade
   total" — então cinza seria nivelamento por baixo sem ganho técnico.
3. Engenheiros vindos do QMoor reconhecem o padrão "sólido =
   suspended, pontilhado = grounded" pela TEXTURA, não pela cor —
   afetação semântica é preservada.

**Referência canônica:** decisão consciente registrada no plano §274
e formalizada em F3.

**Link:** [`relatorio_F3_quick_wins.md`](relatorio_F3_quick_wins.md)
§3.

---

## #8 — Batimetria 2 pontos (slope derivado read-only)

**Fase:** F-prof.2 (redesign aba Ambiente).

**Decisão:** a aba Ambiente do frontend recebe **batimetria por dois
pontos** (`startpoint_depth` no fairlead + `h` na âncora) e o solver
deriva `slope_rad` automaticamente. Modo "slope direto" é avançado
(escondido por default). `BathymetryPopover` da F1 foi removido.

**Justificativa:** engenheiro recebe carta náutica com profundidade
em pontos discretos — workflow natural. Forçar inferência de slope
em graus era ergonomia ruim. Round-trip
`BathymetryInputGroup ↔ slope_rad ↔ BathymetryInputGroup` valida em
`rtol=1e-9` (sem perda de precisão).

**Referência canônica:** ergonomia do workflow offshore
(carta náutica → 2 sondagens → slope).

**Link:** [`relatorio_F2_ambiente_validacoes.md`](relatorio_F2_ambiente_validacoes.md).

---

## #9 — AHV idealização estática (D018 + Memorial + manual)

**Fase:** F-prof.8 (AHV).

**Decisão:** AHV (Anchor Handler Vessel) modelado como força lateral
estática num ponto da linha **é idealização modelada**, não
representação fiel da operação real (rebocador dinâmico, cabo
oscila, hidrodinâmica). Mitigação obrigatória em **3 níveis**:
1. **D018** (severity warning, confidence medium) ao ativar AHV.
   Sempre dispara — sem opção de esconder.
2. **Memorial PDF** com seção "AHV — Domínio de aplicação" obrigatória
   quando AHV está presente no caso.
3. **Manual de usuário** com seção dedicada (cobre 6 pontos:
   domínio, idealização vs real, quando usar, quando NÃO usar,
   D018/D019, exemplo numérico).

**Justificativa:** AHV é instalação dinâmica real. Análise estática
é útil para estimativa preliminar de carga em junção mas pode
mascarar snap loads + dinâmica do rebocador. Sem a mitigação em 3
níveis, F8 não fecha — engenheiro pode usar a feature acreditando
que substitui análise dinâmica de instalação.

**Referência canônica:** plano de profissionalização §F8 + decisão
fechada antecipada (registrada em CLAUDE.md antes da F8 começar).

**Link:** [`relatorio_F8_ahv.md`](relatorio_F8_ahv.md),
[`CLAUDE.md` §"Decisão fechada — Fase 8 antecipada"](../CLAUDE.md).

---

## #10 — Identidade matemática V_hemi vs V_conic (Excel R5/R7)

**Fase:** F-prof.6 (catálogo de boias).

**Decisão:** as fórmulas de volume `V_hemispherical(r, L)` e
`V_semi_conical(r, L)` em
[`backend/api/services/buoyancy.py`](../backend/api/services/buoyancy.py)
**coincidem matematicamente** quando h_cap = r (regime canônico do
Excel `Buoy_Calculation_Imperial_English.xlsx` Formula Guide R5/R7),
porque 2 hemisférios com raio r removem (2/3)·π·r³ do cilindro reto,
e 2 cones com altura D/4 e raio r removem o mesmo (2/3)·π·r³.

**Justificativa:** identidade é consequência da especificação do
Excel — não defeito de implementação. Bug que troque hemi↔conic NÃO
seria detectado no regime canônico h_cap = r. **Anti-identity test**
adicionado em F10/Commit 5: com h_cap ≠ r (h_cap=0.3, r=1.5), as
fórmulas DEVEM divergir mensuravelmente (>1e-3 m³). Garante
detectabilidade do bug em qualquer regime não-canônico.

**Referência canônica:** Excel
`docs/Cópia de Buoy_Calculation_Imperial_English.xlsx` Formula Guide
R4-R7.

**Link:** [`relatorio_F6_buoys.md`](relatorio_F6_buoys.md) §6 +
[`backend/solver/tests/test_diagnostics_apply_full.py`](../backend/solver/tests/test_diagnostics_apply_full.py).

---

## #11 — ProcessPoolExecutor para watchcircle (não Thread)

**Fase:** F-prof.10 / Commit 1.

**Decisão:** `compute_watchcircle()` paraleliza os N azimutes via
`concurrent.futures.ProcessPoolExecutor`. **Não** ThreadPool.

**Justificativa:** medição empírica falsificou a hipótese inicial de
que SciPy/numpy liberam o GIL em chamadas BLAS suficientes para
ThreadPool dar speedup. O hot loop é Python puro CPU-bound (brentq
externo + iteração de catenária + outer fsolve), não BLAS-pesado.
ThreadPool ADICIONA overhead (Spread 4× foi de 55.74s → 70.08s,
+25%). ProcessPoolExecutor bypassa o GIL via processos
independentes, com trade-off de ~1-2s de startup do pool por chamada
(spawn + reimport), amortizado em N tasks de segundos cada.
Resultado: Spread 4× foi de 55.74s → 16.60s (3.36× speedup).

**Referência canônica:** GIL semantics em CPython +
`concurrent.futures` standard library docs.

**Link:** [`relatorio_F10_C1_perf_watchcircle.md`](relatorio_F10_C1_perf_watchcircle.md).

---

## #12 — Convenção MoorPy `Catenary.catenary` retorna `(FxA, FzA, FxB, FzB, info)`

**Fase:** F-prof.7 (anchor uplift).

**Decisão:** ao integrar resultados do MoorPy nos baselines V&V,
respeitar a convenção da função `Catenary.catenary` upstream:
**anchor end PRIMEIRO** (FxA, FzA), fairlead end DEPOIS (FxB, FzB),
seguido por dict `info`. **NÃO** HF/VF/HA/VA como a signature da
função poderia sugerir.

**Justificativa:** descoberta crítica durante a F7 — leitura inicial
errada do contrato produziu swap T_anchor ↔ T_fl com erro de ~6% em
BC-UP-01..05. A convenção é respeitada no código upstream
(`moorpy/Catenary.py`) mas a signature mistura nomenclaturas; cada
integração V&V deve seguir o contrato real, não o sugerido.

**Referência canônica:** MoorPy `Catenary.catenary` source code
(commit `1fb29f8e` capturado no baseline da F0).

**Link:** [`relatorio_F7_anchor_uplift.md`](relatorio_F7_anchor_uplift.md)
§"Convenção MoorPy descoberta".

---

## #13 — H per-segmento no solver (mudança de invariante para AHV)

**Fase:** F-prof.8 (AHV).

**Decisão:** o solver multi-segmento aceita componente **horizontal**
de força em junção AHV, alterando a invariante histórica "H constante
ao longo da linha" (válida para boias e clumps que aplicam apenas
salto em V).

**Justificativa:** AHV aplica força lateral pontual no plano da
linha; modelagem requer salto em H na junção (além do salto em V já
suportado por buoy/clump). Antes da F8, `H_local` era constante ao
longo da linha (decorria da catenária 2D estática sem cargas
horizontais externas). Pós-F8, o solver multi-segmento integra
junção a junção tratando ambos os componentes: nova função
`_signed_force_2d` retorna tupla `(H_jump, V_jump)`;
`_integrate_segments` agora propaga `H_local` per-segmento;
`_solve_suspended_tension` ajusta `H_fairlead = H_anchor +
sum_H_jump` no residual. Função legacy `_signed_force` preservada
(retorna 0 em AHV) para retro-compatibilidade.

Esta é uma decisão arquitetural não-trivial. Cases sem AHV produzem
o mesmo resultado pré e pós-F8 (regressão `cases_baseline.json`
re-roda em `rtol=1e-9`). Cases com AHV produzem resultado novo —
não comparável a v0.x onde a feature não existia.

**Referência canônica:** F8 commit `18da690` (`feat(solver): força
horizontal em junção AHV + auto-disparo D018/D019`).

**Link:** [`relatorio_F8_ahv.md`](relatorio_F8_ahv.md) §descobertas
técnicas.

---

## Mapa fase → decisões

| Fase     | Decisões fechadas              |
|----------|--------------------------------|
| F1b      | #3 (forma geral), #4 (brentq)  |
| F-prof.0 | #1 (QMoor/GMoor)               |
| F-prof.1 | #2 (atrito per-seg)            |
| F-prof.2 | #8 (batimetria 2 pontos)       |
| F-prof.3 | #7 (grounded vermelho)         |
| F-prof.4 | #5 (ProfileType), #6 (confidence) |
| F-prof.6 | #10 (V_hemi/V_conic)           |
| F-prof.7 | #3 ext, #12 (convenção MoorPy) |
| F-prof.8 | #9 (AHV idealização), #13 (H per-seg) |
| F-prof.10| #11 (ProcessPool watchcircle)  |
| Sprint 1 | #14 (Vessel case-level metadata) |
| Sprint 2 | #15 (AHV install via mode Tension), #16 (heurística bollard pull) |
| Sprint 3 | #17 (modelagem AHV Tier C exige reference numbers) |

---

## #14 — `Vessel` é metadado de CASE, não AttachmentKind

**Tomada em:** Sprint 1 (v1.1.0, 2026-05-06).

QMoor JSON tem `vessels[]` como top-level, semanticamente o
**hull flutuante** ao qual a linha está conectada via fairlead.
Distinto de `LineAttachment.kind="ahv"` (Fase 8) que modela carga
pontual APLICADA ao longo da linha.

**Decisão:** criar `Vessel` model em `backend/solver/types.py` e
expor como `CaseInput.vessel: Optional[Vessel]` (case-level
metadata). NÃO criar `AttachmentKind="vessel"` (que confundiria
com AHV pontual e não mapearia direto à estrutura QMoor).

Solver não consome `Vessel` — é metadado puro. Plot desenha
casco rectangular com LOA × draft quando preenchido.

**Referência canônica:** Sprint 1 / Commit 3 `e957398`
(`feat(schema): adiciona Vessel + CaseInput.vessel`).

**Link:** [`relatorio_sprint1_qmoor_import.md`](relatorio_sprint1_qmoor_import.md) §1.

---

## #15 — Cenário AHV de instalação resolve via mode Tension forçado

**Tomada em:** Sprint 2 (v1.1.x, 2026-05-06).

**Contexto físico:**

Cenários AHV de instalação (Backing Down / Hookup / Load Transfer)
são fases TEMPORÁRIAS onde um Anchor Handler Vessel está na
superfície segurando a linha. Estrutura no plano vertical 2D:

```
 [AHV] superfície (y = +deck_level)
  |
  | Work Wire (último segmento)
  |
  o--- connection point
   \\
    \\  Mooring line restante
     v Anchor (X = horzDistance, y = -h)
```

**Problema observado:** QMoor 0.8.0 exporta esses cases às vezes em
`inputParam: "Range"` com `horzDistance > L_min = √(X² + h²)`.
L_total não-esticada insuficiente — solução matemática não existe.
fsolve diverge.

**Análise:** os 4 cases AHV que convergiam pré-Sprint 2 estavam em
`inputParam: "Tension"` com `fairleadTension` definido. Inferência
empírica: QMoor real sempre dirige cenários AHV por **bollard pull**
(força do cabo de trabalho), não por X target. `horzDistance` no JSON
Range é informativo (X resultante de execução prévia).

**Decisão:**

Schema novo `AHVInstall` em `backend/solver/types.py` com 4 campos:
`bollard_pull` (req), `deck_level_above_swl`, `stern_angle_deg`,
`target_horz_distance` (informativo). Anexado a
`BoundaryConditions.ahv_install: Optional[AHVInstall]`.

Parser QMoor 0.8.0 detecta cenário AHV por DOIS sinais:
1. `boundary.startpointType="AHV"` explícito.
2. Nome do mooringLine contém "Hookup", "Backing Down",
   "Load Transfer" ou "Install".

Quando detectado, parser **força `mode=Tension`** com
`input_value = bollard_pull`, preserva `horzDistance` em
`ahv_install.target_horz_distance` (NÃO consumido pelo solver).
Diagnostic D021 (info) emitido no migration log.

**Solver core INALTERADO** — caminho Tension já validado em F1+.

**Diferença vs `LineAttachment.kind="ahv"` (Fase 8):**
- F8: AHV como carga pontual aplicada NUM PONTO da linha.
- Sprint 2: AHV como "fairlead virtual" durante instalação
  (substitui o rig fairlead pelo convés do AHV na superfície).
- Coexistem — podem aparecer juntos em casos complexos.

**Resultado:** 16/16 KAR006 cases convergem em produção
(era 11/16 pós-Sprint 1).

**Referência canônica:** Sprint 2 / Commit 24 `0fd4205` +
Commit 24.1 `2746f9f`.

**Link:** [`relatorio_sprint2_ahv_install.md`](relatorio_sprint2_ahv_install.md).

---

## #16 — Heurística adaptativa de bollard pull

**Tomada em:** Sprint 2 (v1.1.x, 2026-05-06).

Quando JSON QMoor 0.8.0 marca cenário AHV mas omite
`solution.fairleadTension`, o parser precisa inferir um bollard
pull para popular `ahv_install`. Decisão:

```
bollard_pull = max(50 te, 1.5 × w_max × h)
```

Onde:
- `w_max` = peso submerso por unidade do segmento mais pesado (N/m).
- `h` = profundidade da âncora (m).
- 50 te = 490.3 kN (piso conservador).

**Justificativa:**

Para Hookup ML3 (KAR006): w_max = 1477 N/m (Rig Chain), h = 311 m
→ 1.5·1477·311 ≈ 689 kN ≈ 70 te. Operação AHV real tipicamente
usa 50-200 te, então 70 te é razoável.

Heurística garante T_fl alto suficiente para levantar o segmento
mais pesado do anchor (evita regime "fully grounded" onde fsolve
trava numericamente — testado: 30 te bate em invalid_case;
50 te já converge para ML3).

User pode editar via aba "AHV Install" do CaseFormPage se valor
heurístico não for o desejado para o cenário operacional real.

**Referência canônica:** Sprint 2 / Commit 24 (mesmo commit que #15).

**Link:** [`relatorio_sprint2_ahv_install.md`](relatorio_sprint2_ahv_install.md) §3.

---

## #17 — Modelagem AHV Tier C exige QMoor reference numbers

**Tomada em:** Sprint 3 (v1.1.x, 2026-05-06).

**Contexto:** Sprint 2 entregou suporte AHV via **mode Tension
forçado** (decisão #15) — robusto numericamente, simplificado
fisicamente. 16/16 KAR006 cases convergem.

Pendência identificada: implementar **modelagem física Tier C**
com Work Wire elástico tratado separadamente do main mooring
line (catenária dual / sistema acoplado).

**Decisão:** **Adiada para v1.2.0+**, contingente em ground truth.

**Razão:**

Implementar Tier C **sem QMoor reference numbers** seria:

1. Tomar decisões de modelagem (Work Wire em série vs paralelo;
   anchor uplift; deck level efetivo; junção AHV-line; matriz de
   compliance) baseadas em literatura genérica.
2. Entregar números fisicamente plausíveis mas não-validados
   contra software comercial.
3. Risco de divergência sutil vs QMoor que só apareceria em
   produção, depois de muito investimento.

**Alinhamento com decisão #15** (Sprint 2): solver core inalterado
até ter dados de validação.

**Princípio transversal:** "MoorPy/QMoor são referência de validação,
não target de paridade total" — válido em ambas as direções:
- Não nivelar por baixo (não copiar limitações).
- Não inventar matemática nova sem dado para validar.

**Quando reabrir:** user passa **3-5 cases AHV install** com:
- Input completo (CaseInput JSON ou .moor).
- Output esperado do QMoor (T_fl, T_anchor, X_anchor, geometria
  da linha, posição do AHV).
- Tolerância aceitável (default sugerido: rtol=1e-2 = 1%).

Mini-plano com 8-12 commits será apresentado nessa altura.

**Referência canônica:** Sprint 3 / Commit 32.

**Link:** [`relatorio_sprint3_v1_1_x.md`](relatorio_sprint3_v1_1_x.md)
§decisões.

**SUPERSEDIDA pela Decisão #18 (Sprint 4).** Mantida no histórico como
documentação do raciocínio inicial, mas a Sprint 4 substitui esta
escolha por validação direta contra MoorPy Subsystem (open-source
NREL) em vez de exigir QMoor reference data.

---

## Decisão #18 — Tier C físico AHV validado contra MoorPy Subsystem (Sprint 4)

**Decisão:** Implementar Tier C físico AHV (Work Wire elástico real
acoplado à linha de ancoragem via ponto de pega) validando contra
**MoorPy Subsystem** ao invés de exigir QMoor reference numbers.

**Razão (corrige a Decisão #17):**

A Decisão #17 foi conservadora demais. O AncoPlat já tem MoorPy
integrado como referência canônica de validação desde F1b/F-prof.0
(`tools/moorpy_env/venv/`):

- F1b: 9 BC-MOORPY validados rtol < 1e-2.
- F-prof.0: F-prof.1 baseline com 7 BC-MOORPY ativos.
- F7: 5 BC-UP validados rtol < 1e-2 contra `moorpy.Catenary.catenary`.
- VV-01..05: validação cruzada em F10.

Para AHV especificamente, MoorPy oferece `Subsystem.makeGeneric()`
que modela naturalmente sistemas multi-trecho heterogêneo com
endpoints livres (anchor + AHV deck). Isso é EXATAMENTE o caso AHV
Tier C.

**Vantagens vs QMoor:**

1. **Reproduzível por auditoria externa**: outro engenheiro pode
   instalar MoorPy via `pip install moorpy` e re-rodar os benchmarks.
   QMoor é proprietário/comercial, não-reproduzível.
2. **Peer-reviewed**: MoorPy é open-source NREL com publicação ASME
   2025. Para um memorial de auditoria científica isso é mais
   defensável do que paridade com legado.
3. **Já validado em-house**: 21 BCs já validam contra MoorPy. Adicionar
   Tier C nesse pipeline reusa toda a infra existente.

**Implementação (Sprint 4 / Commits 33-41):**

10 cenários BC-AHV-MOORPY-01..10 (`docs/audit/moorpy_ahv_baseline_*.json`)
com gerador `tools/moorpy_env/regenerate_ahv_baseline.py`. Solver
Tier C em `backend/solver/ahv_work_wire.py` resolve catenárias
acopladas via brentq sobre Z_p (continuidade horizontal H_moor = H_ww
no ponto de pega).

**Resultado:**

- 6/6 cenários canônicos (operação real de instalação) → fallback
  Sprint 2 automático com D024 (regime físico onde mooring fica
  deitado).
- 4 xfails informativos: 2 uplift+touchdown (pendência F7.x), 2
  deepwater taut com divergência ~20% em H (pendência F-prof.X
  para refatorar elastic.py).

**Princípio transversal aplicado:**

"MoorPy é referência de validação científica externa." Quando o
modelo AncoPlat diverge, **registramos a divergência como pendência
explícita** com path de saída técnico (qual módulo refatorar, qual
abordagem matemática), em vez de aceitar paridade superficial ou
inventar matemática nova sem revisão.

**Decisões implementadas como consequência:**

- D018 (sempre dispara em AHV) ganhou parâmetro `tier_c_active` com
  mensagem específica citando os limites: Work Wire elástico
  modelado, **SEM** snap loads, **SEM** movimento dinâmico AHV,
  **SEM** hidrodinâmica do casco.
- D022 (warning, high) — bollard pull ≥ 90% MBL Work Wire (DNV-OS-E301).
- D024 (info, high) — Tier C reduzido a Sprint 2 (transparência).

**Referência canônica:** Sprint 4 / Commits 33-41.

**Link:** [`relatorio_sprint4_ahv_tier_c.md`](relatorio_sprint4_ahv_tier_c.md).


---

## Decisão #19 — Tier D AHV Operacional Mid-Line (Sprint 5)

**Decisão:** Estender `LineAttachment` (kind="ahv") com campos opcionais `ahv_work_wire` (WorkWireSpec) + `ahv_deck_x` para ativar **Tier D operacional**: linha de ancoragem instalada continua íntegra entre plataforma e anchor; um AHV puxa lateralmente via Work Wire conectado num ponto intermediário. Default `None` preserva F8 puro (carga pontual).

**Razão:** cenário identificado a partir de screenshot QMoor real mostrando "Anchor Handler Vessels" tab com Bollard Pull + Connection Position + Work Line. É o 4º cenário AHV (após Sprint 2 instalação, Sprint 4 Tier C endpoint, Fase 8 carga pontual) — comum em operações reais de manutenção/análise de tensão.

**Implementação:** solver pre-processor 2-pass em `backend/solver/ahv_operational.py` com refinamento iterativo. Pass 1 resolve linha SEM ww (F8 puro); pass 2 substitui (bollard, heading) pela resultante calculada do Work Wire elástico. Convergência quando |ΔX_pega| + |ΔZ_pega| < 0.5m em até 5 iterações outer.

Fallback automático para F8 puro com **D025** quando catenária ww inviável OU iteração não converge.

**Validação:** 6 BC-AHV-OP-01..06 contra MoorPy `System.solveEquilibrium`. Marcados como xfail informativos por divergência conceitual: MoorPy com pega FREE; AncoPlat com pega FIXA via position_s_from_anchor. Validação fina é F-prof.X.

**Decisões implementadas:**
- D025 (info, high) — Tier D reduziu para F8 (transparente).
- D026 (warning, medium) — Work Wire com ângulo vertical < 10°.
- D018 atualizado com `tier_d_active=True` citando snap loads + motion AHV + hidrodinâmica + fadiga + oscilação como NÃO modelados.

**Referência canônica:** Sprint 5 / Commits 42-49.

**Link:** [`relatorio_sprint5_ahv_operational.md`](relatorio_sprint5_ahv_operational.md).
