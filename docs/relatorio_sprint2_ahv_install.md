# Sprint 2 — AHV Install scenarios (v1.1.x)

> Branch: `feature/ahv-install-ui` (depois merged em `main`)
> Commits: 23, 24, 24.1, 25, 26, 27, 28, 29
> Status: 16/16 KAR006 cases convergem em produção

## Contexto

Após Sprint 1 (import QMoor 0.8.0 v1.1.0), usuário tentou importar
o JSON real do projeto KAR006 (Karoon Energy / Maersk Developer /
Bauna Field). Resultado: **5 de 16 cases falhavam** com diagnostic
`solver_invalid_case` + mensagem "fsolve não convergiu para
multi-segmento + slope".

Os 5 cases falhos eram **cenários AHV de instalação**:
- Backing Down — ML1/2/5/6/7/8
- Hookup — ML3
- Load Transfer — ML3, ML4, ML1/2/5/6/7/8

## Diagnóstico

Análise comparativa dos 9 cenários AHV (4 que convergiam vs 5 que
falhavam) revelou padrão claro:

| Subgrupo | Mode | L vs L_min(X,h) | Status |
|---|---|---|---|
| `inputParam="Tension"` (sem X target) | TENSION | — | ✅ converge |
| `inputParam="Range"` com L > L_min | RANGE | ratio ≥ 1.0 | ✅ converge |
| `inputParam="Range"` com L < L_min | RANGE | ratio < 1.0 | ❌ falha |

**Causa raiz:** o JSON QMoor exporta cenários AHV de instalação às
vezes em mode Range com horzDistance que excede a corda mínima da
linha (catenária 2D estática não fecha). QMoor real internamente
usa modo dirigido por bollard pull (força aplicada pelo cabo de
trabalho), não por X target — `horzDistance` nesses casos é
informativo (X resultante de execução prévia), não constraint
do solver.

## Estratégia

**Opção C.2 — Suporte AHV completo** (escolhida pelo usuário):
schema rico para cenário AHV de instalação + UI editável + plot
adaptado. Implementação preserva solver core (zero risco de
regressão dos gates F1-F11 + Sprint 1).

## Decisões fechadas

### 1. AHV install é METADADO de boundary

Novo modelo `AHVInstall` em `backend/solver/types.py` com 4 campos:
`bollard_pull` (req), `deck_level_above_swl`, `stern_angle_deg`,
`target_horz_distance`. Anexado a `BoundaryConditions.ahv_install`
opcional.

**Solver não usa diretamente** — quando AHV install está set,
parser força mode Tension com `input_value = bollard_pull`. Caminho
de cálculo continua o mesmo (mode Tension validado em F1+).

### 2. Detecção AHV via 2 sinais

Parser QMoor 0.8.0 detecta cenário AHV por:
- **Explícito**: `boundary.startpointType="AHV"` no JSON.
- **Inferido**: nome do mooringLine contém "Hookup", "Backing Down",
  "Load Transfer" ou "Install".

Quando qualquer sinal dispara → mode forçado Tension + ahv_install
populado + diagnostic D021 emitido.

### 3. Heurística de bollard pull

Quando `solution.fairleadTension` ausente no JSON:
`bollard_pull = max(50 te, 1.5 × w_max × h)`

Para Hookup ML3 (w_max=1477 N/m, h=311m):
- 1.5 × 1477 × 311 ≈ 689 kN ≈ 70 te
- max(50 te=490 kN, 689 kN) = 689 kN ✓

Garantia: T_fl alto suficiente pra levantar o segmento mais pesado
do anchor (evita "fully grounded" onde fsolve trava numericamente).

### 4. Diferença vs `LineAttachment.kind="ahv"` (Fase 8)

| Característica | `kind="ahv"` (F8) | `AHVInstall` (Sprint 2) |
|---|---|---|
| Posição na linha | Junção pontual (intermediário) | Startpoint (substitui rig fairlead) |
| Função | Carga horizontal aplicada | "Fairlead virtual" temporário |
| Cenário | AHV puxando lateralmente | AHV segurando linha durante install |
| Coexistência | Sim — podem aparecer juntos | Sim — independentes |

## Resultados

### Antes
- 11/16 KAR006 cases convergiam em produção.
- 5 cases AHV falhavam com `solver_invalid_case`.

### Depois
- **16/16 KAR006 cases convergem em produção.**
- Importação QMoor 0.8.0 passa por:
  1. Detecção automática de cenário AHV (startpointType ou nome).
  2. Parser força mode Tension + popula ahv_install.
  3. Diagnostic D021 informa o user da conversão (visível no log de
     migração da UI).
  4. Plot mostra linha vertical informativa em `target_horz_distance`.
  5. ImportedModelCard exibe bloco "AHV Install" com bollard pull,
     target X, etc.
  6. User pode editar via aba dedicada "AHV Install" no CaseFormPage.

### 16 cases KAR006 em produção

| Categoria | Cases | Status |
|---|---:|---:|
| Operational Profiles | 4 | ✅ |
| Preset Profiles | 3 | ✅ |
| Backing Down Profiles | 3 | ✅ |
| Hookup Profiles | 3 | ✅ |
| Load Transfer Profiles | 3 | ✅ |
| **Total** | **16** | **100%** |

## Sequência de commits

| # | Hash | Descrição |
|---|---|---|
| 23 | `997dd6f` | Schema `AHVInstall` + `BoundaryConditions.ahv_install` |
| 24 | `0fd4205` | Parser força Tension quando startpointType=AHV |
| 24.1 | `2746f9f` | Parser detecta AHV também via nome do mooringLine |
| 25 | `1e0419d` | BC-AHV-INSTALL-01..05 + 4 negativos + heurística (9 testes) |
| 26 | `29e551e` | AHVInstallEditor componente + Zod schema |
| 27 | `67341b1` | Aba "AHV Install" no CaseFormPage |
| 28 | `13e7dcb` | Plot + ImportedModelCard adaptam visual |
| 29 | (este) | Docs (relatório, CLAUDE.md, decisões) |

## Gates atendidos

- ✅ `cases_baseline_regression` 3/3 (rtol=1e-9)
- ✅ BC-MOORPY 7/7 ativos
- ✅ BC-FR-01 + BC-EA-01 + BC-FAIRLEAD-SLOPE-01
- ✅ BC-SLACK-01 (Commit 21)
- ✅ BC-AHV-INSTALL-01..05 (novos)
- ✅ Backend full: 863 passed, 6 skipped, 6 xfailed (era 854, +9)
- ✅ Frontend: 196 passed (era 192, +4 ahv-install-editor)
- ✅ Build frontend: ~1.5s
- ✅ p95 solve <100ms (gate F10) preservado — caminho Tension
  é o mesmo já validado.

## Pendências reservadas (não-bloqueantes para v1.1.x)

1. **Iteração automática "Aplicar via Sensitivity"** — botão no
   AHVInstallEditor que itera bollard_pull até X≈target. Atualmente
   user faz iteração manual via aba Análise / Sensitivity Panel.
2. **Modelagem física AHV completa** (Tier C) — Work Wire elástico
   separado, anchor não-grounded, validação numérica vs QMoor real.
   Reservado para fase futura quando houver demanda.
3. **`openapi.ts` regen** — tipos `AHVInstall` ainda inline em
   componentes via cast `as unknown`. Regenerar quando o ciclo de
   codegen for re-rodado.

## Arquivos novos

- `backend/solver/tests/test_ahv_install_schema.py` — 13 testes
- `backend/api/tests/test_ahv_install_scenarios.py` — 9 testes
- `frontend/src/components/common/AHVInstallEditor.tsx`
- `frontend/src/test/ahv-install-editor.test.tsx` — 4 smokes
- `docs/relatorio_sprint2_ahv_install.md` (este)

## Arquivos modificados

- `backend/solver/types.py` — `AHVInstall` + `BoundaryConditions.ahv_install`
- `backend/api/services/moor_qmoor_v0_8.py` — parser detecta AHV
- `frontend/src/lib/caseSchema.ts` — Zod schema
- `frontend/src/pages/CaseFormPage.tsx` — aba AHV Install
- `frontend/src/components/common/ImportedModelCard.tsx` — bloco AHV
- `frontend/src/components/common/CatenaryPlot.tsx` — linha target X
- `frontend/src/pages/CaseDetailPage.tsx` — wire ahv_install
