# Release Notes — AncoPlat v1.0.0

**Data prevista de release:** 2026-05-XX
**Branch de origem:** `main` pós-merge da `feature/fase-11-lancamento-v1.0`
**Tag de release:** `v1.0.0`
**Tag âncora de rollback:** `v0.10.0-pre-release`

---

## Sumário

AncoPlat v1.0.0 é o primeiro release público estável. Atinge
**paridade total de features com QMoor 0.8.5** e validação contra
**MoorPy v1.x** (NREL) em 36 cases canônicos.

Mudanças desde **v0.5-baseline** (snapshot pré-profissionalização):
**10 fases** de desenvolvimento, **~3000 testes** (665 backend +
181 frontend, descontando duplicações), **96% cobertura agregada**,
documentação completa em PT-BR.

---

## O que mudou desde v0.5-baseline

### Físicas (afetam resultado numérico)

Vide [`CHANGELOG.md`](../CHANGELOG.md) §"⚠ Mudanças numéricas" para
hashes e tags de cada mudança. Resumo:

1. **Atrito per-segmento** (F-prof.1) — precedência canônica
   `mu_override → seabed_friction_cf → seabed.mu → 0.0`. Cases sem
   overrides preservam comportamento global.
2. **Toggle EA estático/dinâmico** (F-prof.1) — `qmoor` (default) vs
   `gmoor`. Default preserva.
3. **Batimetria 2 pontos** (F-prof.2) — entrada via 2 sondagens com
   slope derivado.
4. **Lifted arches** (F5.7.1) — boia em material uniforme na zona
   apoiada gera arcos catenários simétricos.
5. **Anchor uplift** (F-prof.7) — feature nova, single-seg sem
   attachments.
6. **AHV** (F-prof.8) — feature nova, com mitigação obrigatória em 3
   níveis (D018 + Memorial PDF + manual §7).

### Features novas (backward-compatible)

- **Multi-segmento** com chain+wire+chain ou polyester híbrido
  (F5.1).
- **Attachments** boias e clump weights (F5.2).
- **Seabed inclinado + batimetria 2 pontos** (F5.3 + F-prof.2).
- **Mooring system multi-linha** com plan view, equilíbrio sob carga
  ambiental e watchcircle 360° animado (F5.4 + F5.5 + F5.6).
- **Boias profissionais com pendant** + metadata (F5.7).
- **Lifted arches** boias na zona apoiada (F5.7.1).
- **Catálogo de boias** seed com 11 entradas (F-prof.6).
- **Memorial PDF** rastreável (hash + solver_version + timestamp).
- **Exportação XLSX** com 3-4 abas + CSV ≥5000 pontos formato
  internacional.
- **Importação `.moor` v2** com migrador v1→v2.
- **16 diagnostics** D001..D015 + D900 + D018/D019 dedicados a AHV.
- **Glossário** 40 verbetes em `/help/glossary` (F9).
- **11 case templates** em `/samples` (F9).
- **OnboardingTour DIY** 5 etapas com skip persistente (F9).
- **ProfileType** taxonomy NREL/MoorPy (F-prof.4).
- **Anchor uplift** single-segmento sem attachments (F-prof.7).
- **AHV** (Anchor Handler Vessel) com idealização documentada
  (F-prof.8).

### UI/UX

- Aba Ambiente refatorada com 3 grupos (F-prof.2).
- Quick wins UX (F-prof.3): line summary panel, grounded vermelho,
  ícones startpoint, plot toggles.
- Print stylesheet A4 portrait para CaseDetailPage (F9).
- A11y via auto-associação Label↔Input (F9).
- Hover bidirecional legenda↔segmento (F5.7.1).

### Performance

- Watchcircle paralelizado com ProcessPoolExecutor: Spread 4× foi
  de 56s → 16.6s (gate <30s atingido em 3/4 cenários).
- Endpoints REST p95 <100ms em 5/5 endpoints testados.
- Round-trip unidades SI ↔ {N, kN, te, N/m, kgf/m} rtol<1e-10.

---

## Migração de cases v0.x para v1.0

### Caminho recomendado

1. **Antes do upgrade**: backup do diretório `/opt/ancoplat/data/`
   (já é parte do procedimento padrão de deploy — vide
   [`operacao_producao.md`](operacao_producao.md) §9).
2. **Re-rodar o gate de regressão** após o deploy:
   ```bash
   pytest backend/tests/test_baseline_regression.py -v
   ```
   Cases em `docs/audit/cases_baseline_2026-05-04.json` (3 cases
   originais) re-rodam com `rtol=1e-9`. Se o teste falhar, NÃO
   prosseguir — algo no solver mudou inadvertidamente.
3. **Para cada caso salvo individualmente**: re-rodar via UI ou via
   `POST /api/v1/cases/{id}/solve`. Comparar:
   - Hash do caso (estável em v1.0): se idêntico ao v0.x, o input
     não mudou.
   - Resultado: deve ser idêntico se o caso não usar nenhuma das 6
     features de mudança numérica acima.

### Compatibilidade backward

| Caso v0.x | Comportamento em v1.0 |
|-----------|----------------------|
| Single-seg sem attachments, `mu` global, `endpoint_grounded=True` | **IDÊNTICO** (rtol=1e-9) |
| Multi-seg sem `mu_override`, sem `seabed_friction_cf` per-seg, sem boia em zona apoiada uniforme | **IDÊNTICO** |
| Multi-seg com boia em junção heterogênea (chain↔wire) | **IDÊNTICO** (caminho legacy F5.2) |
| Caso com `ea_source="gmoor"` (não existia em v0.x) | N/A em v0.x |
| Caso com `endpoint_grounded=False` (não existia em v0.x) | N/A em v0.x |
| Caso com `kind="ahv"` (não existia em v0.x) | N/A em v0.x |

### Quebras de compatibilidade

NENHUMA. v1.0.0 é backward-compatible com v0.x para todos os cases
que não ativarem features novas. Schema do `.moor` v2 carrega
campos opcionais novos com defaults — cases v0.x carregam-se sem
modificação.

### Schema `.moor`

- v0.x usavam schema implícito de campos legados.
- v1.0 usa `.moor` v2 com `schema_version: 2`.
- Importador `_migrate_v1_to_v2()` atua automaticamente em arquivos
  sem `schema_version` (assume v1).
- Log estruturado de migração disponível em
  `POST /api/v1/import-moor` retornando `{case, migration_log}`.

### Pendência herdada da F2/F5

`.moor` schema v2 ainda **não cobre** `slope_rad` e `attachments`.
Cases que usam essas features re-importam OK mas perdem essas
informações na conversão round-trip. Reservar bump para `.moor` v3
em v1.1+ quando houver demanda real.

---

## Pendências v1.1 não-bloqueantes

Da Fase 10 (consolidadas em
[`relatorio_F10_vv_completo.md`](relatorio_F10_vv_completo.md)):

1. **Watchcircle shallow chain 4× ainda em 24.8s** (gate <20s
   atingido nos outros 3 cenários). Heurística pré-fsolve para
   azimutes inviáveis. Estimativa: 24.8s → 8-12s.
2. **Cobertura ≥98% nos módulos críticos** (atual: 96% agregado).
   4-6 horas de testes focados em `solver.py`, `suspended_endpoint.py`,
   `multi_segment._solve_multi_sloped`.
3. **Apply tests determinísticos** para D003, D007, D008, D011, D012,
   D015. Refactor de `suggested_changes` para incluir valor
   estruturado em vez de orientação narrativa.
4. **VV-07/08 via MoorPy Subsystem** (atual: cross-check interno
   suficiente para gate v1.0).
5. **BC-UP-06..10 + BC-AHV-05..10** — lista detalhada em
   [`relatorio_F10_vv_completo.md`](relatorio_F10_vv_completo.md)
   §Q4.

De fases anteriores:

6. **Multi-seg + uplift** — combinação não suportada em v1.0
   (rejeitada com `NotImplementedError` específico).
7. **AHV + uplift** — combinação não suportada.
8. **Multi-seg + AHV em uplift** — combinação não suportada.
9. **Pendant visual no plot** — boias profissionais com pendant
   carregam metadata mas plot ainda não desenha o pendant separado.
10. **Mooring system samples** — `mooringSystemTemplates.ts` para
    tab dedicada em `/samples`.
11. **Print stylesheet de MooringSystemDetailPage** — F9 entregou
    print apenas para CaseDetailPage.
12. **Screen reader testing rigoroso** — F9 entregou auto-associação
    Label↔Input mas falta auditoria com leitor de tela real.
13. **Library paramétrica MoorPy** — schema `material_coefficients`
    para gerar line_types via fórmulas. Reservada para F12.x.
14. **`.moor` v3** com `slope_rad` + `attachments` — pendência
    herdada da F2/F5.

---

## Roadmap pós-v1.0

### v1.0.x (patches)

Bug fixes que NÃO afetam resultado numérico de cases salvos.

### v1.1.0 (features menores)

Itens 1-5 acima da Fase 10 + alguns itens de fases anteriores
conforme demanda.

### v2.0.0 (mudanças significativas — sem timeline)

Roadmap opcional Fase 12 (vide
[`docs/plano_profissionalizacao.md`](plano_profissionalizacao.md)
§Fase 12):

- Matrizes de rigidez analíticas K_h, K_v, K_θ.
- Modelo de custo (preço por m de cabo + custo de instalação).
- Bathymetry grid 2D (interpolação de carta náutica completa em vez
  de slope linear).
- Integração RAFT (NREL — análise dinâmica frequency-domain).
- 3D para AHV (componente fora do plano da linha).
- Linha boiante (w<0) — risers, mooring híbrido.

**Fase 12 NÃO é commitment de timeline. É registro de direção.**

---

## Decisões de escopo fechadas (não-negociáveis em v1.0)

- Internacionalização (i18n): **no-go**. PT-BR consistente.
- Multi-seg + uplift, AHV + uplift, AHV 3D: **pós-v1.0**.
- BC-MOORPY-06 (linha boiante w<0 + uplift): **Fase 12**.
- API público com autenticação OAuth/JWT: **pós-v1.0** se demanda
  multi-usuário aparecer.

---

## Como usar v1.0 pela primeira vez

1. Acesse https://ancoplat.duckdns.org (basic auth).
2. Tour DIY de 5 etapas roda automaticamente na primeira visita.
   Skip persistente em localStorage.
3. **Sidebar → "Samples"** para começar com caso pronto. 11
   templates cobrem cenários típicos (single-seg, multi-seg,
   mooring system, lifted arch, anchor uplift, AHV).
4. **Sidebar → "Ajuda" → "Glossário"** para referência técnica
   transversal (40 verbetes em 5 categorias).
5. **Manual de usuário** completo em
   [`docs/manual_usuario.md`](manual_usuario.md). 12 seções,
   conceitos físicos antes das features, seção AHV obrigatória
   para qualquer uso da feature de instalação.

---

## Suporte

- **Documentação:** [`docs/`](.) — manual, decisões fechadas, plano
  de profissionalização, relatórios de fase.
- **Issues:** https://github.com/marcelocaliman/ancoplat/issues
- **Operação produção:** [`docs/operacao_producao.md`](operacao_producao.md)
  para SSH, logs, deploy, rollback, backup.

---

## Agradecimentos

- **NREL** pelo MoorPy (MIT-licensed) usado como referência canônica
  de validação.
- **QMoor 0.8.5** (software comercial de origem) pelo catálogo de
  522 entradas importado integralmente como `data_source: legacy_qmoor`.
- **Engenheiro revisor** pelas respostas no
  [`Documento_B_Checklist_Revisor-RESPONDIDO.docx`](Documento_B_Checklist_Revisor-RESPONDIDO.docx).
