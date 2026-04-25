# Relatório F5.4 — Sistema multi-linha (mooring system)

> Iteração atual: **F5.4.1 — schemas + persistência (backend)**

## Escopo da fase

Conforme [roadmap interno do relatorio_F5_3.md](relatorio_F5_3.md#L165-L169):

> Multi-linha (mooring system) sem equilíbrio de plataforma. Cada linha
> resolvida independentemente; agregado de forças. Visualização polar
> (planta) das linhas saindo da plataforma.

Faseamento adotado:

| Slice    | Conteúdo                                                            | Status |
|----------|---------------------------------------------------------------------|--------|
| F5.4.1   | Modelo + persistência (Pydantic, SQLAlchemy, CRUD service, testes)  | ✅ |
| F5.4.2   | Solver dispatcher + agregação de forças + endpoints API + retenção  | ✅ |
| F5.4.3   | BCs de validação adicionais (simetria/equilíbrio, asymm extremos)   | ⬜ |
| F5.4.4   | Frontend: lista + edição                                            | ⬜ |
| F5.4.5   | Frontend: plan view polar                                           | ⬜ |

---

## F5.4.1 — entrega

### Schema Pydantic

[`backend/api/schemas/mooring_systems.py`](../backend/api/schemas/mooring_systems.py)

Dois tipos:

- **`SystemLineSpec`** — uma linha dentro do sistema. Reúne uma definição
  completa de caso (`segments` / `boundary` / `seabed` /
  `criteria_profile` / `user_defined_limits` / `attachments`) acrescida
  das coordenadas polares no plano da plataforma (`fairlead_azimuth_deg`
  ∈ `[0, 360)` e `fairlead_radius` > 0).
- **`MooringSystemInput`** — sistema completo: `name`, `description`,
  `platform_radius`, `lines` (1..16). Validators:
  - Nomes de linha únicos (case-insensitive).
  - Linhas com `criteria_profile=UserDefined` exigem `user_defined_limits`.

Convenção do plano horizontal (documentada na docstring):

> Origem no centro da plataforma. +X = proa (azimuth 0°). Anti-horário
> proa→bombordo→popa. Linha sai radialmente; âncora no prolongamento.

### Persistência

[`backend/api/db/models.py`](../backend/api/db/models.py)

Novo modelo `MooringSystemRecord` segue o padrão de `CaseRecord`: input
completo em `config_json` + colunas desnormalizadas para listagem
(`platform_radius`, `line_count`, `name`, timestamps).

CHECK constraints:
- `length(name) >= 1`
- `platform_radius > 0`
- `line_count >= 1`

Índices: `name` e `updated_at`.

[`backend/api/db/migrations.py`](../backend/api/db/migrations.py) já é
idempotente (`Base.metadata.create_all`) — não precisou de mudança.

### Service CRUD

[`backend/api/services/mooring_system_service.py`](../backend/api/services/mooring_system_service.py)

API mínima (sem router ainda — fica para F5.4.2):

- `create_mooring_system(db, msys_input) -> MooringSystemRecord`
- `get_mooring_system(db, id) -> MooringSystemRecord | None`
- `list_mooring_systems(db, *, page, page_size, search) -> (items, total)`
- `update_mooring_system(db, id, msys_input) -> MooringSystemRecord | None`
- `delete_mooring_system(db, id) -> bool`
- Hidratadores: `mooring_system_record_to_summary` e `mooring_system_record_to_output`.

### Testes

[`backend/api/tests/test_mooring_systems_f5_4_1.py`](../backend/api/tests/test_mooring_systems_f5_4_1.py) — 15 testes verde.

| Categoria | Cobertura |
|-----------|-----------|
| Migration | tabela criada com colunas certas; idempotente; CHECK constraints recusam inválido |
| Pydantic  | aceita payload válido; rejeita nome duplicado, azimuth ≥ 360, raio ≤ 0, lista vazia, UserDefined sem limits |
| CRUD      | round-trip preserva todos os campos; summary omite `config_json`; paginação + busca; update recalcula `line_count`; update id inexistente → None; delete idempotente |

Suite total backend: **206 testes verde** (190 da F5.3.y + 1 já existente desde F5.3.z + **15 desta entrega**).

### Decisões técnicas

1. **Inline vs FK para o caso de cada linha.** Cada `SystemLineSpec`
   tem a definição inline (não FK para `cases`). Motivo: cases existem
   primariamente como sandbox de uma linha isolada e podem ser
   alterados/deletados sem propagar para o sistema. Reusar via "salvar
   como template" pode entrar futuramente sem mudar este schema.

2. **Sem `MooringSystemExecutionRecord` ainda.** Persistência de
   resultados (executions multi-linha + agregados) é da F5.4.2 — fica
   acoplada ao solver dispatcher.

3. **`platform_radius` ≠ `fairlead_radius`.** O primeiro é informativo
   (visualização da plataforma na plan view); o segundo é o raio
   efetivo até o ponto de fixação da linha. Nada impede que sejam
   diferentes (ex.: FPSO com fairleads externos no casco).

4. **JSON pelo `model_dump_json()` do Pydantic.** Mesma estratégia do
   `CaseRecord.input_json`. Round-trip via `model_validate_json()` é
   exato — testado no `test_crud_round_trip`.

---

---

## F5.4.2 — entrega

### Tipos de resultado

[`backend/solver/types.py`](../backend/solver/types.py) ganhou:

- **`MooringLineResult`** — encapsula `SolverResult` + posição polar
  (`fairlead_xy`, `anchor_xy`) + força horizontal sobre o casco
  (`horz_force_xy`).
- **`MooringSystemResult`** — lista de `MooringLineResult` + agregados:
  `aggregate_force_xy`, `aggregate_force_magnitude`,
  `aggregate_force_azimuth_deg`, `max_utilization`, `worst_alert_level`,
  `n_converged`, `n_invalid`, `solver_version`.

### Solver dispatcher

[`backend/solver/multi_line.py`](../backend/solver/multi_line.py) — função
`solve_mooring_system(msys_input)`. Pseudocódigo:

```python
for line in msys.lines:
    res = solver.solve(line.segments, line.boundary, line.seabed, ...)
    θ = radians(line.fairlead_azimuth_deg)
    fairlead_xy = R · (cos θ, sin θ)
    anchor_xy   = (R + X_solver) · (cos θ, sin θ)
    H_xy        = res.H · (cos θ, sin θ)        # 0 se não convergiu
F_total = Σ H_xy_i              # ignora linhas inválidas
```

Convenção: força horizontal sobre a plataforma aponta radialmente para
fora (do fairlead em direção à âncora). Em spread simétrico balanceado,
soma vetorial cancela.

### Persistência (executions)

Nova tabela `mooring_system_executions` em
[`backend/api/db/models.py`](../backend/api/db/models.py):

- FK `mooring_system_id` → `mooring_systems.id` com `ON DELETE CASCADE`.
- `result_json` (MooringSystemResult completo) + desnormalizações:
  `aggregate_force_magnitude`, `aggregate_force_azimuth_deg`,
  `max_utilization`, `worst_alert_level`, `n_converged`, `n_invalid`.
- Índice em `(mooring_system_id, executed_at)`.
- Política de retenção: 10 mais recentes por sistema, truncagem aplicada
  após cada `solve_and_persist`.

### Service

[`backend/api/services/mooring_system_service.py`](../backend/api/services/mooring_system_service.py)
ganhou:

- `solve_and_persist(db, msys_id) -> tuple[record, exec_record] | None`
- `preview_solve(msys_input) -> MooringSystemResult` (sem persistir)
- `_prune_old_executions(db, msys_id)` aplicando retenção de 10
- Hidratação de `latest_executions` em `mooring_system_record_to_output`

### Endpoints REST

[`backend/api/routers/mooring_systems.py`](../backend/api/routers/mooring_systems.py)
montado em `/api/v1`:

| Método  | Rota                                  | Função |
|---------|---------------------------------------|--------|
| GET     | `/mooring-systems`                    | Listar (paginado + busca) |
| POST    | `/mooring-systems`                    | Criar |
| GET     | `/mooring-systems/{id}`               | Detalhar (inclui últimas 10 execuções) |
| PUT     | `/mooring-systems/{id}`               | Atualizar |
| DELETE  | `/mooring-systems/{id}`               | Remover (cascade) |
| POST    | `/mooring-systems/{id}/solve`         | Resolver e persistir |
| POST    | `/mooring-systems/preview-solve`      | Resolver sem persistir (preview UI) |

Tag `mooring-systems` registrada em `main.py` para o OpenAPI.

### Testes

[`backend/api/tests/test_mooring_systems_f5_4_2.py`](../backend/api/tests/test_mooring_systems_f5_4_2.py) — 15 testes verde.

| Categoria          | Cobertura |
|--------------------|-----------|
| Solver puro        | spread simétrico 4× → resultante ≈ 0; assimétrico 2× → magnitude H·√2 a 45°; linha inválida fica fora do agregado; posição radial; alert hierarchy; solver_version propagado |
| Service            | solve_and_persist cria execução com desnormalizações corretas; sistema inexistente → None; retenção de 10 (rodando 12 solves restam 10) |
| API                | POST create → 201; POST /solve → execução persistida + GET vê em latest_executions; 404 em id inexistente; preview não persiste; PUT recalcula line_count; DELETE cascade |

Suite total backend após F5.4.2: **221 testes verde** (206 da F5.4.1 + **15 desta entrega**).

### Decisões técnicas

1. **Força aponta radialmente para fora.** A linha pesa contra a
   plataforma puxando-a em direção à âncora. Em spread balanceado, as
   contribuições cancelam — `aggregate_force_magnitude ≈ 0` é o sinal
   de que o sistema está em equilíbrio com cargas externas zero. Isso
   coincide com a convenção do MoorPy quando a plataforma está na
   posição de offset zero.

2. **Linhas inválidas entram no resultado mas não no agregado.** Se uma
   das N linhas não converge, persistimos a execução com `n_invalid > 0`
   e mantemos as forças das linhas que convergiram. Alternativa
   (rejeitar a execução inteira) seria mais agressiva e impediria a UI
   de mostrar parcialmente o sistema.

3. **`Mz = 0` por construção.** Como cada linha sai radialmente,
   `r_fairlead × F_horz = 0` (vetores paralelos). Não exposto no
   `MooringSystemResult` para não confundir; vira útil só em F5.4 v2+
   se permitirmos linhas tangenciais (ex.: turret com fairleads não
   centrados).

4. **Preview separado de solve.** Mesma lógica de cases: `/preview-solve`
   recebe o input completo e devolve o resultado sem tocar no banco.
   Útil pra UI live (mudar azimuth e ver o resultante atualizar).

---

## Próximo passo: F5.4.4 — Frontend

(F5.4.3 — BCs analíticos extras — ficou implícito na cobertura BC-MS-LINE-01..03
do F5.4.2; pode ganhar BCs adicionais em iterações futuras se preciso.)

1. Página `/mooring-systems` com listagem (cards mostrando nome,
   line_count, último resultante).
2. Página de edição reaproveitando `SegmentEditor` e `BoundaryConditions`
   por linha (tabs ou accordion por linha).
3. Plan view polar (Plotly ou SVG nativo): círculo da plataforma +
   linhas radiais até as âncoras, color-coded por
   `worst_alert_level`/utilização individual.
4. Tela de detalhe com tabela de execuções e métricas agregadas.
