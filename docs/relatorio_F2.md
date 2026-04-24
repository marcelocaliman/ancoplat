# Relatório Fase 2 — API FastAPI

Data: 2026-04-24
Status: ✅ **CONCLUÍDA**
Commits: `5ec88f2` (F2.1) → `764f10e` (F2.7) + polish final
Marco de validação F2 alcançado: os 9 BCs rodam via API e produzem resultados numericamente idênticos ao solver direto.

## Sumário executivo

Em 8 sub-fases granulares, a API REST foi construída do setup inicial ao PDF técnico. Todas respondem em `localhost:8000/api/v1/*` sem autenticação (uso local), com validação Pydantic em todas as entradas, envelope padronizado de erros em português, CORS restrito a localhost, e cobertura de testes 98% na camada API. As 145 suítes de teste (64 solver + 81 API) rodam em ~2.7 segundos. O marco crítico — rodar BC-01..BC-09 via `POST /cases/{id}/solve` e obter os mesmos resultados do solver direto — passou em 9/9 casos.

## Commits F2 (8)

| Commit | Sub-fase | Descrição |
|--------|----------|-----------|
| `5ec88f2` | F2.1 | Setup FastAPI + health/version/criteria-profiles + CORS + error handlers |
| `ddc2bd6` | F2.2 | Migrations + SQLAlchemy models (cases, executions, app_config) + PRAGMA fk=ON |
| `6bef593` | F2.3 | CRUD de casos com validação Pydantic e paginação |
| `65c89a6` | F2.4 | POST /cases/{id}/solve + persistência + retenção 10 + mapa status→HTTP |
| `ccd7242` | F2.5 | Catálogo de tipos de linha com proteção de legacy_qmoor (403 em edição) |
| `433fa58` | F2.6 | Import/export .moor (JSON + Pint) em imperial/metric |
| `764f10e` | F2.7 | PDF report com reportlab + matplotlib + disclaimer obrigatório |
| (próximo) | F2.8 | OpenAPI polish + README da API + este relatório |

## Endpoints (18)

Prefixo: `/api/v1/`.

### Metadata (3)

| Método | Rota | Descrição | Status |
|--------|------|-----------|:------:|
| GET | `/health` | Healthcheck DB | ✅ |
| GET | `/version` | Versão API/schema/solver | ✅ |
| GET | `/criteria-profiles` | 4 perfis (MVP, API RP 2SK, DNV, User) | ✅ |

### Casos (6)

| Método | Rota | Descrição | Status |
|--------|------|-----------|:------:|
| GET | `/cases` | Listar (paginado, search ILIKE) | ✅ |
| POST | `/cases` | Criar (Pydantic-validated) | ✅ |
| GET | `/cases/{id}` | Detalhe + últimas 10 execuções | ✅ |
| PUT | `/cases/{id}` | Atualizar input | ✅ |
| DELETE | `/cases/{id}` | Remover (cascade) | ✅ |
| POST | `/cases/{id}/solve` | Executar solver | ✅ |

### Catálogo (6)

| Método | Rota | Descrição | Status |
|--------|------|-----------|:------:|
| GET | `/line-types` | Listar (category/search/diameter filters) | ✅ |
| GET | `/line-types/lookup` | Busca (line_type, diameter) | ✅ |
| GET | `/line-types/{id}` | Detalhe | ✅ |
| POST | `/line-types` | Criar user_input | ✅ |
| PUT | `/line-types/{id}` | Editar (403 em legacy_qmoor) | ✅ |
| DELETE | `/line-types/{id}` | Remover (403 em legacy) | ✅ |

### Import/Export (4)

| Método | Rota | Descrição | Status |
|--------|------|-----------|:------:|
| POST | `/import/moor` | Importar JSON .moor (Seção 5.2 MVP v2) | ✅ |
| GET | `/cases/{id}/export/moor` | Exportar .moor em imperial ou metric | ✅ |
| GET | `/cases/{id}/export/json` | CaseOutput normalizado | ✅ |
| GET | `/cases/{id}/export/pdf` | Relatório técnico A4 (reportlab) | ✅ |

## Resultados de testes

| Métrica | Valor |
|---|---|
| Total | **145** (64 solver + **81 API**) |
| Passing | **145 (100%)** |
| Tempo total | 2,74 s |
| Cobertura API | **98%** (1397/1428 stmts) |
| Cobertura solver | **92%** (473/514 stmts) |
| Cobertura global | **97%** |

### Detalhes de cobertura da camada API

| Módulo | Cobertura |
|--------|----------:|
| `main.py` | 100% |
| `routers/*` | 100% |
| `schemas/*` | 100% |
| `services/case_service.py` | 95% |
| `services/execution_service.py` | 98% |
| `services/line_type_service.py` | 97% |
| `services/moor_service.py` | 84% (caminhos raros de erro Pint) |
| `services/pdf_report.py` | 99% |
| `db/models.py, session.py, migrations.py` | 100% |

## Decisões técnicas tomadas autonomamente

1. **Ordem de sub-fases trocada.** Plano original F2 listava F2.2=Catálogo, F2.3=Casos. Executei F2.2=Migrations+Models (cria as tabelas) antes de F2.3=Casos, que era a ordem natural e casava melhor com a mensagem do usuário. Plano interno permitia.
2. **SQLite `PRAGMA foreign_keys=ON` por event listener.** Default do SQLite não aplica FK; descoberto pelo teste de cascade. Habilitado em cada connect via listener; preserva ON DELETE CASCADE entre `cases` e `executions`.
3. **Lifespan em vez de `on_event`.** Migrei de `@app.on_event("startup")` (deprecated no FastAPI recente) para `asynccontextmanager` via `lifespan=`. Remove DeprecationWarning e é o padrão atual.
4. **Envelope de erro com serialização segura.** O `RequestValidationError` do Pydantic 2 inclui `ctx.error` como `ValueError` cru (não-JSON). Adicionado shim no handler que converte `ctx` para `str(v)` — evita 500 interno quando o validator do solver levanta ValueError.
5. **PDF: reportlab + matplotlib Agg.** Reportlab puro-Python e matplotlib com backend não-interativo "Agg" (thread-safe). Sem headless Chrome. Documento A4 com 6 seções (header, disclaimer, inputs, gráfico, resultados, mensagem).
6. **Validação do conteúdo do PDF.** Testes usam `pypdf` para extrair texto e confirmar que o disclaimer obrigatório aparece literal no documento. Adicionada ao `requirements.txt` como dep de teste.
7. **Upload .moor via JSON body, não multipart.** Decisão prática: multipart adiciona complexidade de parser de form-data e valida o `Content-Length`. Para uso pessoal via Swagger, JSON body é perfeitamente amigável. Se F3 precisar de upload de arquivo pela UI, migrar o endpoint é trivial.
8. **Tabela `line_type` referenciada pelo ORM, não recriada.** O seed F1a já criou a tabela com 522 entradas. O modelo `LineTypeRecord` apenas descreve o schema para consultas via ORM. Migrações idempotentes (`create_all(checkfirst=True)`) não duplicam.
9. **Retenção 10 via código Python, não trigger SQL.** Mantém lógica auditável em um único local (`_enforce_retention` no service) em vez de distribuir entre Python e SQLite triggers.
10. **Mensagens de erro em português.** Todos os envelopes retornam mensagem em pt-BR; códigos (`case_not_found`, `solver_invalid_case`, etc.) ficam em inglês (snake_case, amigável para logs).

## Dívida técnica e pontos de atenção para Fase 3

### Pequenos ajustes futuros (baixa prioridade)

- `services/moor_service.py` com 84% de cobertura — caminhos de erro raros do Pint (unidades desconhecidas) não exercitados. Adicionar parametrize test se houver valor. Baixa prioridade.
- Endpoint `/import/moor` aceita JSON body; multipart upload de arquivo `.moor` pode ser desejado se a UI (F3) quiser file picker nativo. ~30 min de trabalho.
- PDF usa defaults de fonte do reportlab (Helvetica) que não tem glifos para todos os acentos portugueses; a renderização funciona via fallback mas poderia usar fonte embutida (DejaVu) para melhor qualidade visual. Estético.
- `iterations_used` no SolverResult conta avaliações de F do brentq, não sub-iterações internas. Para dashboards de performance, pode ser interessante instrumentar.

### Preparação para F3 (frontend React)

- **CORS já habilitado** para `localhost:5173` (Vite dev default).
- **OpenAPI autodoc** em `/api/v1/openapi.json` — pode ser usado por `openapi-typescript` ou similar para gerar types TS automaticamente.
- **Tags organizadas** em 5 grupos (metadata, cases, solve, catalog, import-export) — facilita agrupamento nas telas.
- Todos os schemas têm `example` no JSON Schema — Swagger UI fica usável de imediato.

### Validações físicas ainda centralizadas no solver

O solver valida fisicamente (T_fl ≥ w·h, utilização rompida, etc.). A API propaga os status como HTTP apropriados. O frontend (F3) deve apresentar mensagens amigáveis para cada status/código sem duplicar a lógica. Formato: consumir `error.code` e mapear para texto localizado na UI.

## Estatísticas de código F2

| Tipo | Arquivos | Linhas (aprox.) |
|------|---------:|----------------:|
| `routers/*` | 6 | ~540 |
| `services/*` | 5 | ~660 |
| `schemas/*` | 3 | ~220 |
| `db/*` | 3 | ~230 |
| `main.py` | 1 | ~170 |
| Testes API | 6 | ~690 |
| **Total F2** | **24** | **~2.510** |

Estrutura em `backend/api/` conforme Seção 9 do plano F2.

## Como subir o servidor localmente

```bash
# Da raiz do projeto:
source venv/bin/activate

# Opção 1 — dev com auto-reload:
uvicorn backend.api.main:app --reload

# Opção 2 — produção local simples:
uvicorn backend.api.main:app --host 127.0.0.1 --port 8000

# Verificar que subiu:
curl -s http://127.0.0.1:8000/api/v1/health
# → {"status":"ok","db":"ok"}
```

Swagger interativo em **[http://127.0.0.1:8000/api/v1/docs](http://127.0.0.1:8000/api/v1/docs)** com todos os 18 endpoints, exemplos de request/response e botão "Try it out" para cada um.

## Smoke test manual sugerido (via Swagger)

1. `GET /health` → 200.
2. `POST /cases` com o exemplo do schema CaseInput → 201 com id.
3. `POST /cases/{id}/solve` → 200 com SolverResult (converged, alert=ok).
4. `GET /cases/{id}` → body inclui `latest_executions` com 1 item.
5. `GET /cases/{id}/export/pdf` → download do PDF (abrir no navegador).
6. `GET /line-types?category=Wire` → catálogo vazio em DB fresco; se rodou o seed, retorna 200 entradas Wire.
7. `POST /import/moor` com o exemplo do schema → 201, caso criado com valores em SI.

---

*Fim do relatório F2.*
