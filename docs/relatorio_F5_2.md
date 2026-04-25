# Relatório F5.2 — Boias e clump weights (massas distribuídas)

> Branch: `main` · Data: 25 de abril de 2026

## Sumário executivo

F5.2 estende o solver multi-segmento com elementos pontuais (boias e
clump weights) posicionados nas **junções entre segmentos**. Boias
adicionam empuxo (V diminui); clumps adicionam peso (V aumenta). A
geometria continua C0 mas tem quebra de tangente (kink) nas junções
com attachment. Validação por invariantes físicas: V_fl − V_anchor =
Σ w·L_eff + Σ F_attachments dentro de 1 %. 6 BC-AT cobrem boia única,
clump, múltiplas boias, caso degenerado (empuxo > peso → INVALID), e
não-regressão. Backend 174/174 verde, frontend build limpo.

## Modificações no solver

| Arquivo | Mudança |
|---|---|
| `backend/solver/types.py` | Novo `LineAttachment(kind, submerged_force, position_index, name)`; `AttachmentKind = Literal["clump_weight", "buoy"]`. |
| `backend/solver/multi_segment.py` | `_integrate_segments` aceita `attachments` e aplica salto em `V_local` nas junções (V += signed_force(att)). `_solve_suspended_tension` e `_range` propagam para o cálculo de `sum_total = sum_wL + Σ F_signed`. Bracket de brentq usa `sum_total`. |
| `backend/solver/solver.py` | `solve()` recebe `attachments=()` opcional; despacha para `solve_multi_segment` quando `n_segments > 1` ou `attachments != []`. Rejeita attachments em single-segmento com mensagem orientadora. |
| `backend/solver/__init__.py` | `SOLVER_VERSION = "1.3.0"`. |

### Decisões físicas tomadas autonomamente

1. **Attachments só em junções entre segmentos**. Para colocar uma boia
   no meio de uma linha "homogênea", o usuário cria 2 segmentos
   idênticos com a boia entre eles. Decisão simplifica drasticamente a
   integração e mantém a estrutura existente intocada.
2. **Convenção de sinais**: `clump_weight → V += force`,
   `buoy → V −= force`. `submerged_force` é sempre magnitude positiva.
3. **Detecção de geometria invertida**: se Σ F_signed faz V_anchor < 0
   ou Σ_total ≤ 0, o solver retorna INVALID_CASE com mensagem clara
   ("empuxo excede peso suspenso").
4. **Continuidade**: posição (x, y) é contínua na junção; ângulo da
   tangente faz quebra. Coords entre `seg_i_end` e `seg_{i+1}_start`
   coincidem (mesmo ponto físico).

## Modificações na API

| Arquivo | Mudança |
|---|---|
| `backend/api/schemas/cases.py` | `CaseInput.attachments: list[LineAttachment]` (default `[]`, max 20). |
| `backend/api/services/execution_service.py` | `solver_solve(..., attachments=case_input.attachments)`. |
| `backend/api/routers/solve.py` | `/solve/preview` propaga attachments do body. |

## Modificações no frontend

| Arquivo | Mudança |
|---|---|
| `frontend/src/components/common/AttachmentsEditor.tsx` (novo) | Editor collapsible que aparece quando há ≥ 2 segmentos. Cada attachment vira uma linha com seletor de tipo (boia/clump), `UnitInput` para força submersa e índice da junção. Default: boia 50 kN na primeira junção livre. |
| `frontend/src/components/common/CatenaryPlot.tsx` | Nova prop `attachments?: LineAttachment[]`. Renderiza marcadores nas junções (círculo azul para boia, quadrado laranja para clump) com hover mostrando nome + força. |
| `frontend/src/lib/caseSchema.ts` | `lineAttachmentSchema` Zod + `attachments: array().max(20)` em `caseInputSchema`. `EMPTY_CASE.attachments = []`. |
| `frontend/src/pages/CaseFormPage.tsx` | `useFieldArray` para `attachments`; passa `attachments` no `previewKey` e no `PlotArea`. |
| `frontend/src/pages/CaseDetailPage.tsx` | `<CatenaryPlot attachments={caseInput.attachments} />`. |
| `frontend/src/api/types.ts` | `LineAttachment` e `AttachmentKind` exportados do OpenAPI. |
| `frontend/src/types/openapi.ts` | regenerado. |

## Benchmarks BC-AT contra invariantes físicas

| BC | Configuração | Resultado |
|---|---|---|
| BC-AT-01 | 2 segs Wire idênticos + 1 boia 50 kN no meio | converged, V_fl−V_an = Σw·L_eff − 50 kN ±0,5 % |
| BC-AT-02 | 2 segs Wire + 1 clump 30 kN no meio | converged, V_fl−V_an = Σw·L_eff + 30 kN ±0,5 % |
| BC-AT-03 | 3 segs com 2 boias alternadas (S-curve) | converged, equilíbrio com 2 attachments |
| BC-AT-04 | Boia 200 kN > peso total 160 kN | INVALID_CASE com mensagem "empuxo excede peso suspenso" |
| BC-AT-05 | `attachments=[]` vs sem o parâmetro | match exato (caminho single-segmento intocado) |
| BC-AT-06 | Attachment com 1 segmento | INVALID_CASE com mensagem "junções precisam ≥ 2 segmentos" |

### Validação contra MoorPy

MoorPy `Subsystem.makeGeneric` aceita `connectors` (dict opcional) que
representa pontos pesados/com flutuação entre seções, mas a parametrização
exata do empuxo via `m`/`d_vol` é diferente da nossa (em MoorPy, peso
submerso é calculado a partir de massa e volume; aqui passamos `w`
direto). Para ganhar tempo, optei por validar pelas **invariantes físicas
fundamentais** (H constante, equilíbrio vertical estendido) em vez de
calibrar a parametrização MoorPy. Caso queira validação cruzada exata,
roadmap F6 pode adicionar essa harmonização (estimativa: ~2 dias).

## E2E

```
POST /api/v1/solve/preview com 2 segmentos + 1 boia (50 kN):
  status     : converged
  T_fl       : 1500 kN (input)
  T_anchor   : 1442,2 kN
  X          : 809,4 m
  iters      : 2
  boundaries : [0, 49, 98]
```

Comparado a sem attachment (T_anchor = 1420 kN), a boia mudou a
geometria mensurávelmente. Frontend renderiza um círculo azul com
hover "Boia M (50,0 kN)" no ponto da junção.

## Não-regressão

- 168 testes do final da F5.1 → **174 testes verde** (+6 BC-AT).
- BC-01..09 originais contra MoorPy: tolerâncias mantidas.
- BC-MS-01..05 da F5.1: continuam passando.
- `test_BC_AT_05_sem_attachments_match_sem_parametro` garante que o
  caminho single-segmento (caso F1b) é idêntico com ou sem o parâmetro
  `attachments`.

## Performance

| Caso | Tempo (warm) |
|---|---|
| BC-AT-01 (2 segs + 1 boia) | ~5 ms |
| BC-AT-03 (3 segs + 2 boias) | ~8 ms |

Sem regressão. Attachments são triviais no integrador (só somam à V
local entre segmentos), então o custo é dominado pelas iterações
elásticas como na F5.1.

## Pendências e atenção

1. **Validação cruzada com MoorPy** ficou em invariantes físicas em vez
   de comparação numérica direta — exige harmonização de parametrização
   (massa+volume vs peso submerso direto). Roadmap.
2. **Attachments em multi-segmento com touchdown**: como a F5.1, o
   touchdown em multi não é suportado. Combinar attachments com
   touchdown também não.
3. **Posição livre dentro de um segmento**: F5.2 só permite attachment
   nas junções. Para colocar no meio, o usuário divide o segmento — é
   pedagógico mas exige uma linha de UX.

## Roadmap interno F5.3

- Seabed inclinado: contato unilateral com superfície de inclinação θ.
  Generalização do touchdown para superfície não-horizontal.
- Provavelmente toca `seabed.py` mais que `multi_segment.py`. Pode
  resolver simultaneamente o "touchdown em multi-segmento" pendente da
  F5.1.
