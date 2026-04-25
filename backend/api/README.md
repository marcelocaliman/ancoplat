# AncoPlat API

REST API built with FastAPI on top of the solver from `backend/solver/`.
Uso local, sem autenticação; servidor em `localhost:8000`.

## Como rodar

```bash
# Da raiz do projeto:
venv/bin/uvicorn backend.api.main:app --reload
```

A aplicação sobe em `http://127.0.0.1:8000`. Swagger UI fica em
[http://127.0.0.1:8000/api/v1/docs](http://127.0.0.1:8000/api/v1/docs) e
ReDoc em [/api/v1/redoc](http://127.0.0.1:8000/api/v1/redoc).

## Como testar

```bash
venv/bin/pytest backend/api/tests/           # 81 testes API
venv/bin/pytest backend/                     # suíte completa (145)
venv/bin/pytest backend/api/ --cov=backend/api  # cobertura
```

## Endpoints (18)

Prefixo: `/api/v1/`.

### Metadata (3)
- `GET /health` — healthcheck (200 ok se DB responde; 503 se não)
- `GET /version` — versões da API / schema / solver
- `GET /criteria-profiles` — perfis de utilização disponíveis

### Casos (5 + 1 solve = 6)
- `GET /cases` — paginado (page, page_size ≤ 100, search)
- `POST /cases` — cria caso
- `GET /cases/{id}` — detalhe com até 10 últimas execuções
- `PUT /cases/{id}` — atualiza input
- `DELETE /cases/{id}` — cascade em executions
- `POST /cases/{id}/solve` — executa solver, persiste execução

### Catálogo (6)
- `GET /line-types` — paginado com filtros (category, search, diameter_min/max)
- `GET /line-types/lookup` — busca por (line_type, diameter)
- `GET /line-types/{id}` — detalhe por id
- `POST /line-types` — cria `user_input`
- `PUT /line-types/{id}` — edita `user_input` (403 para legacy_qmoor)
- `DELETE /line-types/{id}` — remove `user_input` (403 para legacy)

### Import/Export (4)
- `POST /import/moor` — importa JSON no schema Seção 5.2 MVP v2
- `GET /cases/{id}/export/moor?unit_system=imperial|metric`
- `GET /cases/{id}/export/json` — CaseOutput completo
- `GET /cases/{id}/export/pdf` — PDF técnico (A4, com disclaimer, gráfico)

## Padrões e decisões

| Tema | Decisão |
|------|---------|
| Auth | Nenhuma — `localhost` only |
| CORS | Apenas `localhost:5173` (Vite) e `localhost:8000` |
| Versionamento | Prefixo `/api/v1/` em todas as rotas |
| Erros | Envelope `{error: {code, message, detail?}}`; sem stack trace |
| Validação | Pydantic no request + validação física no solver |
| Persistência | SQLite em `backend/data/ancoplat.db`; 4 tabelas |
| Retenção execs | Últimas 10 por caso (trunca em POST /solve) |
| Upload .moor | JSON body (multipart adiado para F3) |
| PDF | reportlab A4, disclaimer Seção 10 Documento A v2.2 |

## Mapeamento de status do solver → HTTP

| `ConvergenceStatus` | HTTP | Observação |
|---------------------|:----:|------------|
| `converged` | 200 | Resultado usável |
| `ill_conditioned` | 200 | Alta sensibilidade — usar com cautela |
| `max_iterations` | 200 | Parcial; body contém snapshot |
| `invalid_case` | 422 | Input físico inviável (ex: T_fl ≤ w·h) |
| `numerical_error` | 422 | Overflow / div-0 |

## Estrutura interna

```
backend/api/
├── main.py               — app factory, CORS, error handlers
├── db/
│   ├── session.py        — engine + SessionLocal (+ PRAGMA foreign_keys=ON)
│   ├── migrations.py     — create_all idempotente
│   └── models.py         — LineTypeRecord, CaseRecord, ExecutionRecord, AppConfigRecord
├── schemas/              — Pydantic request/response
│   ├── cases.py
│   ├── line_types.py
│   └── errors.py
├── routers/              — endpoints por recurso
│   ├── health.py
│   ├── cases.py
│   ├── solve.py
│   ├── line_types.py
│   ├── moor_io.py
│   └── reports.py
├── services/             — lógica de negócio
│   ├── case_service.py
│   ├── execution_service.py
│   ├── line_type_service.py
│   ├── moor_service.py
│   └── pdf_report.py
└── tests/                — 81 testes, cobertura 98%
```
