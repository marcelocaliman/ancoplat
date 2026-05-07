# Sprint 7 — v1.3+ pendências (Multi-AHV + uplift xfail + Snap loads)

> Branch: `feature/sprint7-multi-ahv-snap-loads`
> Commits: 59, 60, 61+62+63, 64, 65
> Status: ✅ Sprint completa, 7 commits sequenciais
> Data: 2026-05-07

## Contexto

Pendências v1.3+ herdadas das Sprints 4-5:
1. Multi-AHV simultâneos (Tier D)
2. AHV Tier D + uplift + touchdown
3. Snap loads tabelados
4. ~~3D fora do plano~~ — confirmado fora desta sprint (F12 inteira)

## Decisão fechada #21

**Decisão:** Multi-AHV implementado via loop interno do solver Tier D.
Tier D + uplift documentado como **F7.x.y** (pendência v1.5+) com
xfail strict=True para que o test vire pass automaticamente quando
implementado. Snap loads via DAF tabelado (DNV-RP-H103 §5.5)
opcional aplicado ao SolverResult com D028 transparente.

## Mapa dos 7 commits

| # | Tema | Resultado |
|---|---|---|
| 59 | Multi-AHV Tier D simultâneos | Solver aceita N attachments com ahv_work_wire |
| 60 | AHV Tier D + uplift xfail F7.x.y | xfail strict + mensagem de erro melhor |
| 61+62+63 | Snap loads (schema + solver + D028) | DAF aplicado, D028 dispara |
| 64 | UI EnvCard "Snap loads (DAF)" | dropdown DNV + override |
| 65 | Docs + decisão #21 + CHANGELOG | final |

## Arquitetura entregue

### Multi-AHV Tier D (Commit 59)

`backend/solver/ahv_operational.py`:
- `tier_d_indices: list[int]` (era único int).
- Loop sobre cada AHV em CADA outer iteration:
  1. Localiza pega via arc length cumulado.
  2. `_compute_ww_force_at_pega` para cada um independente.
  3. Substitui `(bollard, heading)` no attachment correspondente.
- Convergência: `max(|ΔX|+|ΔZ|) < tol` em TODOS os pegas.
- Helper `_attach_ww_metadata_multi` consolida msg + diagnostics.

### AHV Tier D + uplift (Commit 60)

Não implementado nesta sprint — exige extensão F7.x.y de
`solve_suspended_endpoint` para aceitar force injection F8 mid-line.
Documentado:
- Mensagem de erro do facade `solve()` cita "Tier D" + "F7.x.y" + "v1.5+".
- 2 testes xfail informativos em `test_ahv_tier_d_uplift_xfail.py`:
  - `test_tier_d_com_uplift_converge_v1_5_plus` (xfail strict): vira PASS quando F7.x.y existir.
  - `test_tier_d_com_uplift_rejeita_com_mensagem_clara_em_v1_4` (atual): valida rejeição explícita.

### Snap loads via DAF (Commits 61+62+63)

Schema novo `BoundaryConditions.snap_load_daf: Optional[float]` (range 1.0-5.0).

Solver hook ao final do facade `solve()`:
```python
if daf is not None and daf > 1.0:
    T_fairlead *= daf
    T_anchor *= daf
    tension_magnitude/x/y *= daf
    utilization recalculada
    alert_level reclassificado
    D028 disparado
```

D028 (warning, medium) com regime classificado:
- DAF ≤ 1.5: "calma (Hs < 1m)"
- DAF ≤ 2.0: "média (Hs 1-2m)"
- DAF ≤ 3.0: "severa (Hs > 2m)"
- DAF > 3.0: "extremo"

### UI (Commit 64)

EnvCard "Snap loads (DAF)" na aba Ambiente do `CaseFormPage`:
- Dropdown 5 presets DNV-RP-H103.
- Input numérico para override custom (1.0-5.0).
- Helper text explicando envelope de pico vs análise dinâmica real.

## Suite

- Backend: 972 → 989 passed (+17 testes snap_loads). 6 skipped, 17 xfailed (+1 Tier D uplift).
- Frontend: 207 passed (estabilidade preservada).
- Zero regressão F0-F11 + Sprints 1-6.

## Pendências v1.5+

1. **F7.x.y — Tier D + uplift + touchdown**: extensão `suspended_endpoint`
   para aceitar attachments mid-line.
2. **Snap loads dinâmicos REAIS** (não DAF estático): integração com
   solver dinâmico externo ou módulo próprio.
3. **3D fora do plano vertical**: F12 inteira separada — refatoração
   completa do solver de 2D para 3D.
4. **Multi-vessel por caso**: 2+ plataformas + linhas compartilhadas.

## Princípios físicos honestos

1. **DAF ≠ dinâmica real.** D028 cita explicitamente que resultado é
   "envelope de pico ESTIMADO" e que validação certificável requer
   software dinâmico (Orcaflex/SIMA/RAFT).
2. **Multi-AHV usa pre-processor 2-pass** — convergência depende da
   geometria; em casos extremos (AHVs muito próximos com forças
   conflitantes) pode cair no fallback F8 com D025.
3. **Tier D + uplift bloqueado é honesto** — em vez de fingir
   funcionalidade que produziria resultados não-validados, rejeita
   com path claro de implementação futura.

## Próximos passos

1. PR para main com 7 commits.
2. Deploy SSH + smoke prod.
3. Tag `v1.4.0` (bump minor: multi-AHV + snap loads).
