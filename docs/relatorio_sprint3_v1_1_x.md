# Sprint 3 — Pendências v1.1.x

> Branch: `feature/v1-1-x-pending`
> Commits: 30, 31, 32
> Status: 2 de 3 pendências entregues; #2 adiada com justificativa

## Contexto

Após Sprint 2 (AHV install scenarios), 3 pendências v1.1.x ficaram
documentadas no relatório:
1. Iteração automática "Aplicar via Sensitivity" no `AHVInstallEditor`.
2. Modelagem física AHV completa (Work Wire elástico separado).
3. Regen `openapi.ts` + cleanup de casts inline.

User decidiu implementar **as opções mais completas e robustas**.

## Decisões fechadas

### Pendências entregues vs adiada

| # | Pendência | Status | Razão |
|---|---|---|---|
| 1 | Iteração automática | ✅ Sprint 3 / Commit 30 | Alta valor, baixo risco |
| 2 | Modelagem física Tier C | ⏸ Adiada para v1.2.0+ | **Sem QMoor reference numbers para validar** |
| 3 | Regen openapi.ts + cleanup | ✅ Sprint 3 / Commit 31 | Refactor, valor de qualidade interna |

### #17 — Modelagem AHV Tier C exige reference numbers

**Decisão:** não implementar modelagem física AHV completa (Work Wire
elástico separado, anchor não-grounded em catenária dual) **sem
ground truth empírico** (QMoor real ou outro software validado).

**Razão:**

A Sprint 2 entregou suporte AHV via mode Tension forçado — solução
**robusta numericamente** mas **simplificada fisicamente**. Os 16/16
KAR006 cases convergem; números são plausíveis; não temos dado para
afirmar correção fina.

Implementar Tier C sem reference seria:
- Tomar decisões de modelagem (Work Wire em série vs paralelo;
  anchor uplift; deck level efetivo) baseadas em literatura genérica.
- Entregar números fisicamente plausíveis mas não-validados.
- Risco de divergência sutil vs QMoor que só apareceria muito depois.

**Alinhamento com decisão fechada #15** (Sprint 2): solver core
inalterado até ter dados de validação. Princípio transversal:
"MoorPy/QMoor são referência de validação, não target de paridade
total" — válido em ambas as direções (não nivelar por baixo nem
inventar matemática nova sem dado).

**Quando reabrir:** user passa 3-5 cases AHV install com:
- Input (CaseInput JSON)
- Output esperado do QMoor (T_fl, T_anchor, X, geometria)
- Tolerância aceitável

Mini-plano será apresentado nessa altura com 8-12 commits estimados.

## Pendência #1 — Iteração automática

### Algoritmo

Bissection client-side com bracket adaptativo, dirigida por
`iterateBollardPullForTargetX`:

```
Etapa 1: encontrar bracket [lo, hi] tal que x(lo) < target < x(hi).
  Inicial: [bollard/4, bollard×4]
  Adaptativo: até 5 expansões (dobra) se não envolver target.

Etapa 2: bissection.
  Max 12 iterações.
  Tolerância: |x_result - target| < 0.5 m.
  Cada avaliação chama /solve/preview (~50ms).
  Total: ~500ms-1s.
```

### Convenção física

X cresce monotonicamente com bollard_pull (mais força → linha
mais esticada → maior X horizontal). Bissection assume isso:
- x(b_lo) < target → precisa aumentar bollard
- x(b_hi) > target → precisa diminuir bollard

### UI inline progress

`IterationProgress` sub-componente do `AHVInstallEditor` mostra:
- Header com badge de status (Loader2 / CheckCircle2 / XCircle)
- Tabela compacta: # | bollard (te) | X (m) | erro (m) | status
- Highlight da melhor linha (verde, font medium)
- Footer com resumo final (converged / não-converged + razão)

### Stop reasons

| reason | Significado |
|---|---|
| `tolerance_met` | Convergiu (\|err\| < tol). Bollard final aplicado. |
| `max_iters` | 12 iter atingidas, melhor encontrado retornado. |
| `bracket_invalid` | Não conseguiu envolver target após 5 expansões. |
| `all_invalid` | Todas avaliações falharam (geometria inviável). |

### Edge cases

- **Heurística inicial muito longe**: bracket adaptativo expande até 5×.
  Casos típicos KAR006 convergem em 2-3 iterações de expansão.
- **Solver retorna invalid_case**: passo é registrado com `xResult=null`,
  bissection encolhe `hi=mid` para evitar repetir falha.
- **Monotonicidade X(bollard)**: assumida; em geometrias muito slack
  pode não valer (boia muda regime). Caso patológico raro.

## Pendência #3 — Regen `openapi.ts`

### Comando

```bash
# Backend local (port 8765 livre)
uvicorn backend.api.main:app --host 127.0.0.1 --port 8765 &
sleep 3
npx openapi-typescript \
  http://127.0.0.1:8765/api/v1/openapi.json \
  -o frontend/src/types/openapi.ts
pkill -f "uvicorn.*8765"
```

### Tipos reconhecidos

`AHVInstall`, `Vessel`, `CurrentProfile`, `CurrentLayer`,
`PendantSegment`, `BoundaryConditions.ahv_install`,
`CaseInput.{vessel, current_profile, metadata}`,
`LineAttachment.pendant_segments`.

### Cleanup

CaseDetailPage: 4 casts `as unknown as {...}` removidos (acesso
direto agora). Tipos display (`VesselDisplay`, `CurrentProfileDisplay`)
deletados do import (não usados após cleanup).

### Mismatch corrigido

`pendant_segments[].category`:
- Antes: `z.string()` (Zod). Backend gerava
  `Literal["Wire" | "StuddedChain" | "StudlessChain" | "Polyester"]`.
- Após: `z.enum(['Wire', 'StuddedChain', 'StudlessChain', 'Polyester'])`.
- Era mismatch silencioso pré-regen (nenhum tipo enxergava o
  constraint completo).

### Casts mantidos (justificados)

9 casts `as unknown as` em outros arquivos foram mantidos. Razão:
referenciam campos NÃO presentes no openapi.ts gerado:
- `result.diagnostics`, `result.segment_boundaries` — campos internos
  do SolverResult não expostos no schema.
- `boundary.startpoint_type` cast para Literal — narrow type usage,
  não acesso a campo unknown.

## Sequência de commits

| # | Hash | Descrição |
|---|---|---|
| 30 | `5903c2f` | Iteração automática + UI inline progress + 4 smoke tests |
| 31 | `b639750` | Regen openapi.ts + cleanup 4 casts CaseDetailPage |
| 32 | (este) | Docs CLAUDE.md + relatório + decisão #17 (adiamento Tier C) |

## Gates atendidos

- ✅ `cases_baseline_regression` 3/3 (rtol=1e-9)
- ✅ BC-MOORPY 7/7 ativos
- ✅ BC-AHV-INSTALL-01..05 (Sprint 2) preservados
- ✅ Backend full: 863 passed (sem mudança backend nesta sprint)
- ✅ Frontend: **200 passed** (era 196, +4 ahv-iteration smokes)
- ✅ Build frontend: ~1.7s
- ✅ p95 solve <100ms preservado

## Como usar a iteração automática

1. Importe um case AHV (Hookup/Backing Down/Load Transfer) ou
   adicione AHV Install manualmente em qualquer case via aba
   "AHV Install" do CaseFormPage.
2. Verifique que `target_horz_distance` está populado.
3. Clique no botão **"Aplicar via Sensitivity"** no card de target.
4. Tabela de progresso mostra cada iteração; melhor linha em verde.
5. Quando converge, bollard_pull final é aplicado automaticamente
   ao form. Toast confirma com bollard final + X resultante + erro.
6. Salve o case (botão Salvar do form) para persistir.

## Pendências v1.2.0+

1. **Modelagem física AHV Tier C** (#2 adiada — ver decisão #17).
   Aguarda QMoor reference data.
2. **Performance da iteração** (opcional): se p95 ficar > 1s,
   considerar Web Worker para off-main-thread bissection.
3. **Botão "Aplicar via Sensitivity" também no SensitivityPanel**
   para non-AHV scenarios (encontrar T_fl que dá X target em mode
   Range arbitrário). Pendência identificada durante implementação;
   não-bloqueante.

## Arquivos novos

- `frontend/src/lib/ahvIteration.ts` — helper de bissection
- `frontend/src/test/ahv-iteration.test.ts` — 4 smoke tests
- `docs/relatorio_sprint3_v1_1_x.md` (este)

## Arquivos modificados

- `frontend/src/components/common/AHVInstallEditor.tsx` — UI inline progress
- `frontend/src/pages/CaseFormPage.tsx` — passa getValues
- `frontend/src/types/openapi.ts` — regen completo
- `frontend/src/lib/caseSchema.ts` — pendant_segments.category enum
- `frontend/src/pages/CaseDetailPage.tsx` — cleanup 4 casts
- `CLAUDE.md` — entry Sprint 3 + #17
