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
