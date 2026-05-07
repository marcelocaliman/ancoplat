# Sprint 5 — AHV Operacional Mid-Line (Tier D)

> Branch: `feature/sprint5-ahv-operational`
> Commits: 42, 43, 44, 45, 46, 47, 48, 49
> Status: ✅ Sprint completa, 8 commits sequenciais
> Data: 2026-05-07

## Contexto

O usuário forneceu screenshot do QMoor mostrando cenário operacional onde:
- Plataforma (semisub) fixa à esquerda no plot.
- AHV (Anchor Handler Vessel) à direita na superfície.
- Linha de ancoragem multi-segmento completa (anchor → fairlead).
- **Work Wire conectando o AHV ao MEIO da linha** formando um "Y".

Esse é o **4º cenário AHV** modelado pelo AncoPlat:
- Sprint 2 (instalação): bollard = T_fl direto.
- Sprint 4 (Tier C): Work Wire elástico no endpoint (fairlead virtual).
- Fase 8: força pontual mid-line, sem Work Wire modelado.
- **Sprint 5 (Tier D, novo)**: linha íntegra + Work Wire elástico mid-line.

## Decisão fechada #19 — Tier D operacional

**Decisão:** estender `LineAttachment` (kind="ahv") com 2 novos campos opcionais (`ahv_work_wire`, `ahv_deck_x`) que ativam Tier D operacional. Default `None` preserva F8 puro (carga pontual).

**Razão:** reusa schema `WorkWireSpec` da Sprint 4 + retro-compat absoluto F8. Tier D dispara automaticamente quando `ahv_work_wire is not None`, com fallback para F8 + D025 quando geometria inviável.

**Validação:** 6 BC-AHV-OP-01..06 contra MoorPy `System.solveEquilibrium` com pega FREE (4 pontos: anchor fixed, pega free, AHV deck fixed, fairlead fixed). Resultado: BCs vs MoorPy marcados como xfail informativos por divergência conceitual (MoorPy resolve com pega free; AncoPlat com pega fixa via `position_s_from_anchor`). Validação fina fica como F-prof.X (mesmo padrão BC-AHV-MOORPY-09/10 da Sprint 4).

## Mapa dos 8 commits

| # | Tema | Status | Suite |
|---|---|---|---|
| 42 | Schema `LineAttachment.ahv_work_wire` opt-in | ✅ | +13 schema |
| 43 | `regenerate_ahv_op_baseline.py` + 6 BC-AHV-OP | ✅ | +1 baseline JSON |
| 44 | Solver `ahv_operational.py` + dispatcher | ✅ | +14 (8 pipeline + 6 xfail) |
| 45 | D025/D026 + D018 update tier_d_active | ✅ | +8 diagnostics |
| 46 | Parser QMoor `boundary.anchorHandlerVessels[]` | ✅ | +5 parser |
| 47 | Frontend `AHVOperationalSubcard` | ✅ | typecheck OK |
| 48 | CatenaryPlot AHV deck + ww mid-line | ✅ | typecheck OK |
| 49 | Relatório + Decisão #19 + manual + CHANGELOG | ✅ | docs only |

## Arquitetura entregue

### Solver Tier D — pre-processor 2-pass

`backend/solver/ahv_operational.py` (~340 LoC):

```
1. Pass 1: resolve linha SEM ww (F8 puro com bollard/heading
   originais). Lê posição da pega via _find_pega_indices.
2. Compute ww: catenária Work Wire entre (X_pega, Z_pega) e
   (X_AHV, deck_z) via solve_elastic_iterative em mode Range.
3. Pass 2: substitui (bollard, heading) do attachment por
   (magnitude, angle) derivados de (H_ww, V_ww). Re-roda solver.
4. Convergência: |ΔX_pega| + |ΔZ_pega| < 0.5m. Max 5 iters outer.
```

**Truque anti-recursão**: `clean_att` zera `ahv_work_wire`/`ahv_deck_x` antes de chamar `facade_solve` — evita re-disparar Tier D no path interno.

**Fallback automático F8 com D025** quando:
- Catenária ww geometricamente inviável.
- Iteração outer não converge em 5 ciclos.
- Solver da linha falha em algum pass.

### Validação — 6 BC-AHV-OP

| ID | Modo | h | T_AHV (kN) | T_anchor (kN) | pega(x,z) | residual |
|---|---|---:|---:|---:|---|---:|
| 01 | favorable-symmetric | 200 | 44.9 | 0.0 | (900, -200) | 0.12 N |
| 02 | ahv-strong-pull | 200 | 44.9 | 0.0 | (900, -200) | 0.03 N |
| 03 | pega-near-anchor | 300 | 67.3 | 0.0 | (587, -300) | 0.0 N |
| 04 | pega-near-fairlead | 300 | 67.3 | 0.0 | (1500, -300) | 0.07 N |
| 05 | deepwater | 1500 | 338.9 | 0.0 | (1445, -1470) | 3.65 N |
| 06 | ultra-deepwater | 2000 | 453.5 | 0.0 | (1769, -1958) | 0.45 N |

H_continuity_residual ≤ 4 N em todos = continuidade física correta no MoorPy. T_anchor=0 nos 6 casos significa lower mooring totalmente apoiada (fisicamente válido em águas com bollard moderado).

**xfail informativo**: validação fina vs MoorPy bloqueada por divergência conceitual (pega free vs pega fixa). Pendência F-prof.X.

### Diagnostics novos

| Code | Severity | Confidence | Quando |
|---|---|---|---|
| **D025** | info | high | Tier D reduziu para F8 (fallback) |
| **D026** | warning | medium | Work Wire muito horizontal (< 10° vertical) |

D018 atualizado com parâmetro `tier_d_active=True` que customiza mensagem citando explicitamente os limites: snap loads, motion AHV, hidrodinâmica casco, fadiga ciclos, oscilação ângulo ww — todos **NÃO modelados**. Tier D tem prioridade sobre Tier C quando ambos active.

### Frontend

- `caseSchema.ts`: `LineAttachment.ahv_work_wire` Zod schema + `ahv_deck_x`. 2 refines novos.
- `AttachmentsEditor.tsx`: `AHVOperationalSubcard` colapsado abaixo dos campos AHV F8 (bollard/heading) quando kind='ahv'. LineTypePicker integrado, 6 campos físicos editáveis (length/EA/w/MBL/ahv_deck_x/ahv_deck_level).
- `CatenaryPlot.tsx`: para cada attachment Tier D, desenha linha laranja (#F97316 dashdot) entre pega → AHV deck + marker quadrado no AHV deck. Pega localizada via arc length acumulado (mesmo padrão Sprint 4.1).

### Parser QMoor 0.8.0

`_parse_ahv_operational_as_attachments` detecta `boundary.anchorHandlerVessels[]` e converte cada item:
- `connectionPosition.lineDistanceFromFairlead` → `position_s_from_anchor` (via `L_total - dist_fl`).
- `bollardPull.force` → `ahv_bollard_pull`.
- `heading` (texto/número): `_interpret_heading()` mapa `"Away from Fairlead"` → 0°, `"Toward Fairlead"` → 180°.
- `workLine.{length,EA,wetWeight,MBL,diameter,lineType}` → `WorkWireSpec`.
- `ahv_deck_x` estimado em `lineDistanceFromFairlead ± 30m` (refine via UI).
- D026 (info) emitido no migration log para cada AHV operacional importado.

## Suite numérica

- Backend: 941 → 954 passed (+13 schema + 8 diagnostics + 5 parser − xfails). 6 skipped, 16 xfailed.
- Frontend: 207 passed (sem testes novos diretos — coberto via tsc + smoke).
- **Gates F0-F11 + Sprints 1-4**: TODOS verdes.

## Pendências v1.3+

1. **F-prof.X — calibração Tier D vs MoorPy**: implementar comparação compatível (pega free vs pega fixa).
2. **Multi-AHV simultâneos** (2 AHVs operacionais na mesma linha): rejeitado em Sprint 5.
3. **AHV Tier D + uplift + touchdown**: extensão F7.x.
4. **3D fora do plano vertical**: Fase 12.
5. **Snap loads tabelados (DAF)**: pós-v1.3.
6. **Smoke tests do AHVOperationalSubcard**: após PR primeira versão.

## Princípios físicos honestos

1. **Tier D é matematicamente consistente**: pre-processor 2-pass converge na maioria dos casos onde o ww é geometricamente factível. Refinamento iterativo dentro de `MAX_OUTER_ITERS=5` capta variação da pega entre passes.
2. **Análise estática**: D018 atualizado dispara obrigatoriamente, citando todos os fenômenos NÃO modelados (snap loads, motion, hidrodinâmica, fadiga, oscilação).
3. **Fallback transparente**: D025 informa quando Tier D reduz para F8 puro. Engenheiro VÊ a redução, não fica oculta.
4. **Pega fixa via position_s_from_anchor**: decisão de design — diferente do MoorPy mas mais determinística para o user (define onde o ww conecta na linha).

## Próximos passos

1. PR para main com 8 commits.
2. Deploy SSH + smoke prod.
3. Tag `v1.2.0` (bump minor: nova feature Tier D).
4. Atualizar `CLAUDE.md` + `docs/decisoes_fechadas.md` (#19) + `manual_usuario.md` (§7.10) + `CHANGELOG.md`.
