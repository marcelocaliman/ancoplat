# Mini-plano ativo — Fase 7 Anchor Uplift (v1.0)

> **Status:** **ativo** desde 2026-05-05 (revertido escopo de v1.1 para v1.0 — paridade total com QMoor).
> **Sequência v1.0:** F9 (UI polish) → **F7 (Anchor uplift)** → F8 (AHV) → F10 (V&V) → F11 (lançamento).
> **Conteúdo abaixo** reflete análise feita no contexto pós-Fase 6 do plano de profissionalização (cases_baseline 3/3, 554 backend + 4 skipped + 66 frontend verde).
> **Antes de retomar:** atualizar Q1–Q9 + cases BC-UP conforme estado do código pós-F9. Em particular, samples preview `anchor-uplift` criados em F9 ([`frontend/src/lib/caseTemplates.ts`](../../frontend/src/lib/caseTemplates.ts)) já trazem payload pronto para os cases canônicos — evita retrabalho de input.

> **Histórico:** Mini-plano originalmente proposto pós-F6 (mesmo dia); arquivado para v1.1 por decisão de escopo enxuto (~30 min depois); reativado para v1.0 (~30 min depois) pela decisão de paridade total. Sem mudança no conteúdo técnico.

---

## Mini-plano da Fase 7 — Anchor uplift (suspended endpoint)

### Objetivo
Habilitar âncoras elevadas do seabed. Hoje [solver.py:159-163](../backend/solver/solver.py#L159-L163) rejeita `endpoint_grounded=False` com `NotImplementedError` — Fase 7 remove essa barreira e implementa o solver de catenária livre nas duas pontas (sem touchdown). Validação contra MoorPy obrigatória (5 casos canônicos BC-UP-01..05).

### Branch e commits propostos
- Branch: `feature/fase-7-anchor-uplift`
- 8 commits atômicos:
  1. **`feat(schema): BoundaryConditions.endpoint_depth + validação`** — campo `Optional[float]`, validação `0 < endpoint_depth ≤ h`. Round-trip dos cases existentes preservado.
  2. **`feat(solver): suspended_endpoint.py — catenária livre`** — novo módulo dedicado (espelha `multi_segment.py`, `grounded_buoys.py`). Catenária parametrizada com vértice em qualquer ponto, sem touchdown. Function pura testável.
  3. **`feat(solver): dispatcher uplift no facade solve()`** — remove `NotImplementedError`. Quando `endpoint_grounded=False`, chama `suspended_endpoint.solve_suspended()`. Multi-segmento + attachments funcionam (ou ficam ressalvados explicitamente para fase futura — decisão Q3 abaixo).
  4. **`chore(audit): MoorPy uplift baseline (5 cases) + regenerate script`** — `tools/moorpy_env/regenerate_uplift_baseline.py` + `docs/audit/moorpy_uplift_baseline_2026-05-DD.json`. 5 casos cobrindo uplift moderado/severo/quase-grounded.
  5. **`test(solver): BC-UP-01..05 verde com rtol=1e-2 vs MoorPy`** — `test_uplift_moorpy.py` parametrizado.
  6. **`feat(diagnostics): D016 + D017 para anchor uplift inválido`** — D016 (high) anchor abaixo do seabed ou acima da superfície; D017 (medium) "uplift desprezível" quando endpoint_depth ≈ h.
  7. **`feat(frontend): radio Grounded/Suspended + endpoint_depth + plot atualizado`** — radio na aba Ambiente, input condicional `endpoint_depth`, `CatenaryPlot` desloca anchor verticalmente. Schema Zod + tipos.
  8. **`docs(fase-7): relatório + CLAUDE.md + plano`**.

### Decisões abertas (Q1–Q9)

**Q1 — Modelo físico do uplift.**
- (a) **Catenária livre nas duas pontas** (sem touchdown na âncora). MoorPy faz isso. PT_1 (fully suspended) já cobre. **Sugiro (a).**
- (b) Catenária com mass-spring na âncora (futurístico, fora do estático).

**Q2 — Schema do endpoint elevado.**
- (a) `endpoint_depth: Optional[float]` em `BoundaryConditions`. Required quando `endpoint_grounded=False`; ignorado/None quando grounded.
- (b) Sempre obrigatório, com sentinel `endpoint_depth=h` significando grounded.
- **Sugiro (a)** — preserva semântica atual de `endpoint_grounded` como flag primária.

**Q3 — Multi-segmento + attachments com uplift: agora ou ressalva?**
- (a) **Suportar tudo** — multi-segmento, attachments, uplift na primeira fase. Maior escopo, mais testes.
- (b) **MVP de uplift = single-segment, sem attachments**. Multi-seg + attachments + uplift fica para F7.x. Path mais conservador.
- **Sugiro (b)**: já é uma fase L (8-12 dias). MVP de uplift cobre 80% dos casos práticos (anchor pile elevado por flutuabilidade tipicamente é wire reto). Multi-seg + uplift exige cuidado adicional com touchdown intermediários e fica naturalmente para F7.x. Ressalva via `NotImplementedError` específica + diagnostic.

**Q4 — Casos canônicos BC-UP.**
Sugestão de 5 cenários (rodados via MoorPy local em `tools/moorpy_env/`):

| ID | Cenário | h (m) | endpoint_depth (m) | uplift | Notas |
|---|---|---|---|---|---|
| BC-UP-01 | Moderado | 300 | 250 | 50 m | Caso "padrão" do plano |
| BC-UP-02 | Severo | 300 | 200 | 100 m | Anchor longe do seabed |
| BC-UP-03 | Quase grounded | 300 | 295 | 5 m | Continuidade vs caso grounded |
| BC-UP-04 | Anchor próximo à surface | 250 | 50 | 200 m | Anchor a 50 m da superfície (extremo) |
| BC-UP-05 | Taut + uplift | 300 | 200 | 100 m | EA grande, T_fl alto |

**Q5 — Tolerância vs MoorPy.**
- (a) **rtol=1e-2** em (T_fl, T_anchor, X) — alinhado com critério do plano (±1%).
- (b) rtol=1e-4 (mesmo dos BC-MOORPY-01..06 ativos).
- **Sugiro (a)** — uplift é caso novo, esperar maior variabilidade numérica que grounded. Apertar para 1e-4 só após confirmar que faz sentido.

**Q6 — UI: Radio Grounded/Suspended.**
- (a) **Radio button explícito** com 2 opções: "Âncora cravada (grounded)" / "Âncora elevada (suspended)".
- (b) Toggle/Switch.
- **Sugiro (a)**: radio é mais explícito que switch para 2 estados com semântica distinta.

**Q7 — Plot: como mostrar anchor elevado.**
- (a) **Manter ícone atual do anchor**, só deslocar verticalmente para `y = -endpoint_depth`. Linha do seabed continua aparecendo logo abaixo.
- (b) Adicionar pendant visual entre anchor e seabed (mostra o offset físico).
- **Sugiro (a)**: minimalista. Pendant visual fica para F9.

**Q8 — Diagnostic dedicado.**
- **D016** (high, error) — `anchor_uplift_invalid`: dispara quando `endpoint_depth ≤ 0` (anchor acima da superfície) ou `endpoint_depth > h + tolerance` (anchor abaixo do seabed). Pré-validação antes de solver.
- **D017** (medium) — `anchor_uplift_negligible`: dispara quando `0 < (h − endpoint_depth) < 1.0 m`. Sugere usar `endpoint_grounded=True` que é mais robusto numericamente.
- **Sugiro: D016 obrigatório, D017 opcional.** D016 é gate de validação; D017 é dica de UX.

**Q9 — Critério de fechamento da fase.**
- BC-UP-01..05 todos verde com rtol=1e-2 vs MoorPy.
- **Cases grounded: 0 regressão** — BC-MOORPY 7/7 ativos + `cases_baseline_regression` 3/3 + BC-FR-01 + BC-EA-01 + BC-FAIRLEAD-SLOPE-01 + diagnostics tudo intacto.
- Multi-seg + uplift retorna `NotImplementedError` específico com diagnostic dedicado (D018 opcional ou só raise informativo).
- D016 dispara nos 2 cenários inválidos (≤0 e >h) com testes.
- Suite ≥ 580 backend (esperado +30 testes), ≥ 75 frontend (esperado +9 testes do radio + plot).
- TS build limpo.
- CLAUDE.md + relatório `docs/relatorio_F7_anchor_uplift.md`.

### Riscos identificados
- **R7.1** — Solver pode não convergir em casos taut com anchor elevado (sem touchdown). Mitigação: chute inicial específico baseado em catenária analítica (V/H = (z_b−z_a)/X).
- **R7.2** — Edge cases físicos (anchor "voando" acima da água, ou abaixo do seabed). Mitigação: D016 + validação de domínio explícita antes do brentq.
- **R7.3** — Esforço L (8–12 dias) maior que F6. Mitigação: Q3=b reduz escopo para single-segment + sem attachments.

### Pendências fora do escopo F7
- **F7.x** — multi-segmento + uplift (junções intermediárias entre material chain↔wire em linha sem touchdown).
- **F7.x** — attachments + uplift (boia/clump em linha sem touchdown).
- **F9** — pendant visual no plot mostrando offset físico anchor↔seabed.
- **F10** — V&V completo: ≥10 BC-UP em vez de 5.
