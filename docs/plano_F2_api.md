# Plano de execução — Fase 2 (API FastAPI)

Data: 2026-04-24
Status: planejamento. Nenhuma linha de código F2 escrita ainda.
Pré-requisitos: F1b concluída (solver testado, 45/45 verdes, 96% cobertura).

Este documento fecha as ambiguidades da Seção 7.2 do Documento A v2.2 antes do desenvolvimento começar.

---

## 1. Princípios

1. **Uso local, zero autenticação.** Servidor roda em `localhost:8000`. Sem tokens, cookies, basic auth. Firewall do macOS é a barreira.
2. **JSON em tudo.** Pydantic define schemas; FastAPI gera OpenAPI automaticamente.
3. **Um solver, duas camadas de validação.** Pydantic valida formato; solver valida física. Nunca crashar — retornar `SolverResult` com status apropriado.
4. **Unidades SI nas bordas do backend.** UI converte imperial↔métrico antes de enviar requests.
5. **CORS aberto para localhost.** Frontend (Vite, `localhost:5173`) consome `localhost:8000`.
6. **Versionamento na URL**: prefixo `/api/v1/…`. Evolução futura sem quebrar clientes legados.

---

## 2. Schema do banco SQLite

Tabela `line_types` já existe (F1a). Novas tabelas:

```sql
-- Casos de ancoragem salvos (um caso = um input de solver + metadados)
CREATE TABLE cases (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    description     TEXT,
    -- Entrada do solver serializada em JSON (LineSegment, BoundaryConditions,
    -- SeabedConfig, SolverConfig). O JSON é canônico; campos derivados abaixo
    -- são desnormalizações para consultas e listagens.
    input_json      TEXT NOT NULL,
    -- Desnormalizações para filtros/sort rápidos:
    line_type       TEXT,       -- ex: 'IWRCEIPS' (FK fraca para line_types.line_type)
    mode            TEXT NOT NULL,    -- 'Tension' | 'Range'
    water_depth     REAL NOT NULL,    -- m (= boundary.h)
    line_length     REAL NOT NULL,    -- m
    criteria_profile TEXT NOT NULL DEFAULT 'MVP_Preliminary',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_cases_name ON cases(name);
CREATE INDEX idx_cases_updated ON cases(updated_at DESC);

-- Histórico de execuções do solver (últimas 10 por caso)
CREATE TABLE executions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id         INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    -- SolverResult completo em JSON (inclui coords, tensions, ângulos, etc.)
    result_json     TEXT NOT NULL,
    -- Desnormalizações úteis para listagem rápida:
    status          TEXT NOT NULL,      -- converged | max_iterations | ...
    alert_level     TEXT,                -- ok | yellow | red | broken
    fairlead_tension REAL,               -- N
    total_horz_distance REAL,            -- m
    utilization     REAL,                -- 0..1
    executed_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_exec_case ON executions(case_id, executed_at DESC);

-- Configurações globais (chave/valor, uso livre)
CREATE TABLE app_config (
    key             TEXT PRIMARY KEY,
    value           TEXT NOT NULL,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Retenção: após INSERT em executions, trigger deleta a partir da 11ª
-- mais antiga do mesmo case_id. Implementado via Python no POST /solve
-- (não via trigger SQL, para manter o código auditável num só lugar).
```

**Decisão**: `input_json` + desnormalizações para filtros. Simples de migrar; não normaliza em cascata (cada mudança de schema em `LineSegment` quebra a tabela).

**Retenção**: últimas **10 execuções por caso**, truncagem feita em código após cada POST /solve bem-sucedido.

---

## 3. Endpoints REST

Prefixo: `/api/v1/`.

### 3.1 Casos (CRUD)

| Método | Rota | Descrição |
|--------|------|-----------|
| `GET`    | `/api/v1/cases`              | Listar casos (paginado) |
| `POST`   | `/api/v1/cases`              | Criar caso |
| `GET`    | `/api/v1/cases/{id}`         | Detalhar caso (inclui últimas execuções) |
| `PUT`    | `/api/v1/cases/{id}`         | Atualizar caso |
| `DELETE` | `/api/v1/cases/{id}`         | Remover caso (cascade em execuções) |
| `POST`   | `/api/v1/cases/{id}/solve`   | Executar solver, persistir execução, retornar resultado |

### 3.2 Catálogo de linhas

| Método | Rota | Descrição |
|--------|------|-----------|
| `GET`    | `/api/v1/line-types`                    | Listar (filtros: `category`, `diameter_min/max`, `search`) |
| `GET`    | `/api/v1/line-types/{id}`               | Detalhar por id |
| `GET`    | `/api/v1/line-types/lookup`             | Buscar por `(line_type, diameter)` — query params |
| `POST`   | `/api/v1/line-types`                    | Cadastrar novo tipo (data_source = 'user_input') |
| `PUT`    | `/api/v1/line-types/{id}`               | Editar (bloqueia edição de legacy_qmoor, apenas user_input) |
| `DELETE` | `/api/v1/line-types/{id}`               | Remover (apenas user_input) |

### 3.3 Import/export

| Método | Rota | Descrição |
|--------|------|-----------|
| `POST`   | `/api/v1/import/moor`                | Importa `.moor` (multipart/form-data), cria caso |
| `GET`    | `/api/v1/cases/{id}/export/moor`     | Download JSON compatível com schema MVP v2 Seção 5.2 |
| `GET`    | `/api/v1/cases/{id}/export/json`     | Download JSON normalizado (input + última execução) |
| `GET`    | `/api/v1/cases/{id}/export/pdf`      | Download PDF técnico (reportlab) |

### 3.4 Metadados da API

| Método | Rota | Descrição |
|--------|------|-----------|
| `GET`    | `/api/v1/health`          | Healthcheck (200 OK se DB responde) |
| `GET`    | `/api/v1/criteria-profiles`  | Lista perfis de utilização disponíveis |
| `GET`    | `/api/v1/version`         | Versão do app, do schema DB, e do solver |
| `GET`    | `/api/v1/docs`            | OpenAPI interativo (default do FastAPI) |

---

## 4. Schemas (Pydantic)

### 4.1 Caso

```python
class CaseInput(BaseModel):
    """Input canônico para criar/atualizar um caso."""
    name: str
    description: str | None = None
    # Entrada do solver
    segments: list[LineSegmentInput]       # exatamente 1 no v1
    boundary: BoundaryConditionsInput
    seabed: SeabedConfigInput = SeabedConfigInput()
    # Critério de utilização
    criteria_profile: Literal[
        "MVP_Preliminary", "API_RP_2SK", "DNV_placeholder", "UserDefined"
    ] = "MVP_Preliminary"
    user_defined_limits: UserLimits | None = None  # usado se criteria_profile=UserDefined


class LineSegmentInput(BaseModel):
    # Espelha backend.solver.types.LineSegment + campos opcionais
    line_type: str | None = None              # FK fraca para catálogo
    category: Literal["Wire", "StuddedChain", "StudlessChain", "Polyester"] | None = None
    length: float                              # m
    w: float                                   # N/m
    EA: float                                  # N
    MBL: float                                 # N


class BoundaryConditionsInput(BaseModel):
    h: float                                   # lâmina d'água (m)
    startpoint_depth: float = 0.0             # profundidade do fairlead (m) — sempre 0 no v1
    endpoint_depth: float | None = None       # profundidade do anchor; None = h (anchor no seabed)
    endpoint_grounded: bool = True            # v1: obrigatório True, rejeita False
    mode: SolutionMode
    input_value: float


class SeabedConfigInput(BaseModel):
    mu: float = 0.0
    soil_type: Literal["clay_soft", "clay_firm", "sand", "carbonate"] | None = None


class UserLimits(BaseModel):
    yellow_ratio: float = 0.50
    red_ratio: float = 0.60
    broken_ratio: float = 1.0
```

### 4.2 Caso — Output

```python
class CaseOutput(BaseModel):
    id: int
    name: str
    description: str | None
    input: CaseInput
    latest_executions: list[ExecutionOutput]   # últimas 10
    created_at: datetime
    updated_at: datetime


class ExecutionOutput(BaseModel):
    id: int
    case_id: int
    result: SolverResult                      # backend.solver.types.SolverResult
    executed_at: datetime
```

### 4.3 Paginação

```python
class PaginatedResponse[T](BaseModel):
    items: list[T]
    total: int
    page: int = 1
    page_size: int = 20
```

---

## 5. Códigos HTTP e erros

### 5.1 Sucesso

| Código | Uso |
|:------:|-----|
| 200 | GET/PUT/DELETE com sucesso |
| 201 | POST criou recurso (retorna Location header) |
| 204 | DELETE sem corpo de retorno (opcional; preferimos 200 com body confirmatório) |

### 5.2 Erros de cliente

| Código | Uso | Exemplo |
|:------:|-----|---------|
| 400 | Request malformado (JSON inválido, tipo errado além do Pydantic) | corpo não é JSON |
| 404 | Recurso inexistente | `GET /cases/999` quando não existe |
| 409 | Conflito | Criar caso com mesmo `name` duplicado (se tornarmos unique) |
| 413 | Payload grande demais | Upload `.moor` > 5 MB |
| 422 | Validação Pydantic falhou | `length: -1` |

### 5.3 Erros do solver

Solver **nunca crasha**: retorna `SolverResult` com `status` ∈ {`invalid_case`, `numerical_error`, `ill_conditioned`, `max_iterations`}. HTTP de `POST /solve` é:
- **200** se `status ∈ {converged, ill_conditioned}` — resultado usável.
- **200 com aviso no body** se `status = max_iterations` — parcial, consumir com cautela.
- **422 Unprocessable Entity** se `status ∈ {invalid_case, numerical_error}` — input inválido do ponto de vista físico. Body inclui `SolverResult` completo com a mensagem.

### 5.4 Erros do servidor

| Código | Uso |
|:------:|-----|
| 500 | Exceção não esperada (bug). Retorna `{error, request_id}`; detalhes completos em log. |
| 503 | DB indisponível (raro em SQLite) |

### 5.5 Formato de erro

```json
{
    "error": {
        "code": "solver_invalid_case",
        "message": "T_fl=4000.0 N <= w·h=5000.0 N: linha não sustenta ...",
        "detail": {"type": "SolverResult", "status": "invalid_case"}
    }
}
```

---

## 6. CORS

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type"],
)
```

---

## 7. Limites de payload

- Body JSON máximo: **2 MB** (FastAPI default).
- Upload `.moor`: **5 MB** (validado manualmente via `Content-Length`).
- `GET /cases` page_size máximo: **100** (default 20).

---

## 8. Exportação PDF

**Biblioteca escolhida: `reportlab`**. Justificativa:
- Puro Python, sem dependência de headless Chrome (weasyprint usa).
- Menor footprint de instalação (crucial em app local).
- Controle preciso de layout (tabelas + gráfico embebido como PNG).
- Maduro (>20 anos, BSD).

Adicionar a `backend/requirements.txt`:

```
reportlab>=4.0
matplotlib>=3.10   # já instalado (veio com moorpy)
```

Template mínimo do PDF (F5 polirá):
1. Header: nome do caso, timestamp, versão do solver.
2. Tabela de inputs.
3. Disclaimer obrigatório (Seção 10 do Documento A).
4. Gráfico de perfil 2D (matplotlib → PNG → embed).
5. Tabela de outputs principais: T_fl, T_anchor, X, L_g, L_s, elongation, ângulos, utilization, alert_level.
6. Status de convergência + mensagem.

---

## 9. Estrutura de pastas do backend/api/

```
backend/api/
├── __init__.py
├── main.py                 # app FastAPI, mount de routers, CORS, middleware
├── db.py                   # engine SQLAlchemy, Session factory
├── models/                 # SQLAlchemy models (Case, Execution, AppConfig)
│   ├── __init__.py
│   ├── case.py
│   ├── execution.py
│   └── line_type.py        # existente do catálogo
├── schemas/                # Pydantic (request/response)
│   ├── __init__.py
│   ├── case.py
│   ├── execution.py
│   ├── line_type.py
│   └── errors.py
├── routers/                # Endpoints agrupados
│   ├── __init__.py
│   ├── cases.py
│   ├── line_types.py
│   ├── import_export.py
│   └── health.py
├── services/               # Lógica de negócio (não roteamento)
│   ├── __init__.py
│   ├── solver_service.py   # wraps solve(), persiste execution
│   ├── criteria.py         # perfis de utilização e classificação
│   ├── moor_format.py      # import/export .moor
│   └── pdf_report.py       # geração PDF com reportlab
└── tests/
    ├── __init__.py
    ├── conftest.py         # client fixture
    ├── test_cases.py
    ├── test_line_types.py
    ├── test_solve_endpoint.py
    └── test_import_export.py
```

---

## 10. Estratégia de migração de schema

Para F2 em si: DROP + CREATE funciona (ambiente de dev pessoal). Para quando houver dados valiosos (F3+), migrar para **Alembic** (padrão SQLAlchemy). Decisão adiada; sem Alembic no F2.

---

## 11. Ordem de execução sugerida da F2

1. **F2.1 — Setup**: `backend/api/` com `main.py`, `db.py`, health endpoint, CORS. Alvo: `curl localhost:8000/api/v1/health` retorna 200.
2. **F2.2 — Catálogo**: routers de `/line-types` (CRUD + lookup). Consome tabela `line_types` já existente.
3. **F2.3 — Casos CRUD**: schema `cases`, routers, validações.
4. **F2.4 — Solve**: `POST /cases/{id}/solve` chamando `backend.solver.solver.solve()`, persistência em `executions`, retenção de 10.
5. **F2.5 — Critérios**: serviço `criteria.py` com os 4 perfis. `SolverResult` enriquecido com `alert_level`.
6. **F2.6 — Import/export JSON e `.moor`**.
7. **F2.7 — PDF** com reportlab.
8. **F2.8 — Testes de endpoint**: fixtures TestClient, cobrir happy path + 422 + 404 de cada rota.

Marco de validação F2: rodar os 9 BCs (BC-01..BC-09) via `POST /cases/{id}/solve` e confirmar mesmos resultados que o solver direto.

---

## 12. Itens que ficam para F3+

- Autenticação (se virar multiusuário).
- Alembic migrations.
- WebSocket para solver streaming (não necessário: solver é rápido, <100ms).
- Caching de execuções idênticas (desnecessário: solver é barato).
- Rate limiting.
- Observabilidade (logs estruturados, métricas) — mínimo via `logging` do Python no F2.

---

*Fim do plano F2.*
