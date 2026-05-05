# Relatório F10 / Commit 6 — Cobertura de testes

**Branch:** `feature/fase-10-vv-completo`
**Data:** 2026-05-05
**Comando:** `pytest backend/ --cov=backend.solver --cov=backend.api`

## Resumo

**Cobertura total: 96% (10 167 statements, 423 missed)**

Per Q6 do mini-plano F10 ("métrica honesta — não force vanity"), este
relatório documenta o estado real **após Fase 10 commits 1-5** com
classificação por módulo, metas alcançadas e gap aberto.

## Cobertura por módulo (críticos do solver)

| Módulo                  | Stmts | Miss | Cov  | Meta v1.0 | Status |
|-------------------------|------:|-----:|-----:|:---------:|:-------|
| `__init__.py`           |     2 |    0 | 100% | ≥98%      | ✅      |
| `attachment_resolver.py`|    64 |    3 |  95% | ≥98%      | ⚠      |
| `catenary.py`           |   116 |    8 |  93% | ≥98%      | ⚠      |
| `diagnostics.py`        |   116 |    2 |  98% | ≥98%      | ✅      |
| `elastic.py`            |    71 |    2 |  97% | ≥98%      | ⚠ -1pp |
| `equilibrium.py`        |   171 |   17 |  90% | ≥98%      | ⚠      |
| `friction.py`           |    33 |    3 |  91% | ≥98%      | ⚠      |
| `grounded_buoys.py`     |   167 |   11 |  93% | ≥98%      | ⚠      |
| `multi_line.py`         |    55 |    2 |  96% | ≥95%      | ✅      |
| `multi_segment.py`      |   564 |   65 |  88% | ≥98%      | ⚠      |
| `profile_type.py`       |    35 |    1 |  97% | ≥98%      | ⚠ -1pp |
| `seabed.py`             |   124 |   10 |  92% | ≥95%      | ⚠      |
| `seabed_sloped.py`      |   185 |   22 |  88% | ≥95%      | ⚠      |
| `solver.py`             |   246 |   35 |  86% | ≥98%      | ⚠      |
| `suspended_endpoint.py` |   137 |   21 |  85% | ≥98%      | ⚠      |
| `types.py`              |   266 |    1 |  99% | ≥95%      | ✅      |

## Cobertura por módulo (não-críticos)

| Módulo                  | Stmts | Miss | Cov  | Meta  | Status |
|-------------------------|------:|-----:|-----:|:-----:|:-------|
| `laid_line.py`          |    46 |   19 |  59% | ≥95%  | ⚠⚠     |
| `api/config.py`         |    26 |    5 |  81% | ≥95%  | ⚠      |
| `api/logging_config.py` |    32 |    1 |  97% | ≥95%  | ✅      |
| `api/main.py`           |    74 |    3 |  96% | ≥95%  | ✅      |

## Análise honesta do gap

**Meta de cobertura ≥98% nos críticos NÃO foi atingida** em 12 de 16
módulos (apenas `__init__`, `diagnostics`, `multi_line`, `types`
chegam ao alvo). 4 módulos críticos ficam <90%: `solver` (86%),
`suspended_endpoint` (85%), `multi_segment` (88%), `seabed_sloped` (88%).

Por que aconteceu:
1. **Volume de mudanças F-prof.0 a F8** introduziu novo código mais
   rápido do que o aumento de cobertura — particularmente em
   `solver.py`, `multi_segment.py`, `equilibrium.py`.
2. **Branches defensivos** (validações de input, fallbacks, paths de
   erro) representam ~50% dos missing statements e são difíceis de
   testar sem mocking pesado, que conflita com a regra "não mockar"
   da Fase 1 (decisão fechada).
3. **Modos não-MVP**: alguns paths em `solver.py` (e.g. multi-line
   coupling, attachments edge cases) exigem cenários complexos de
   integração que ainda não estão na suite.

## Decisão (per Q6 mini-plano F10)

**Aceito 96% agregado como métrica honesta v1.0**, com pendência
explícita rumo a 98% críticos para v1.1. Não há `# pragma: no cover`
adicionado neste commit pois auditoria das missing lines mostrou que
SÃO paths reais que merecem teste, não dead code.

Linhas missing por módulo crítico (referência para v1.1):
  - `solver.py`: 118, 131, 139, 148, 155, 219, 393, 410, 462,
    477-479, 530, 533, 543, 585-595, 650-654, 753-764, 832-833, 846,
    884, 892, 909, 917
  - `suspended_endpoint.py`: 76, 87, 162, 167, 173, 181, 208-209,
    276, 317-318, 324, 330, 339, 345, 352-354, 356, 368, 372
  - `multi_segment.py`: 65 linhas em vários blocos
  - `equilibrium.py`: 99, 125-126, 174, 202-204, 332-336, 346-348,
    351, 394-396, 486, 521, 528

## Backlog v1.1

Subir cobertura para ≥98% críticos:
- Adicionar 2-3 testes específicos para D004 surface violations
  em `solver.py:585-595` (~3% lift).
- Cobrir paths de fallback em `suspended_endpoint.py:317-356` (~10% lift).
- Casos de erro do `multi_segment._solve_multi_sloped` (~5% lift).
- Refactor opcional: extrair branches puramente defensivos em
  helpers privados marcáveis com `# pragma: no cover`.

Estimativa: 4-6 horas de trabalho focado em testes para fechar o gap.
