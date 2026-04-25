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
| F5.4.2   | Solver dispatcher + agregação de forças + endpoints API             | ⬜ |
| F5.4.3   | BCs de validação (BC-MS-LINE-01..05, simetria/equilíbrio)           | ⬜ |
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

## Próximo passo: F5.4.2

Solver dispatcher + agregação:

1. `MooringSystemSolver.solve_all(msys)` chama o solver de cada linha,
   transforma o resultado para o frame da plataforma (rotação por
   `fairlead_azimuth_deg`).
2. Agregado: `H_total_xy = Σ H_i · (cos(az_i+180), sin(az_i+180))`,
   `M_z = Σ r_fl_i × H_i`. Magnitude da força resultante e azimuth.
3. Persiste em `mooring_system_executions` (JSON dos resultados +
   agregados desnormalizados).
4. Endpoints `POST /mooring-systems/solve` e
   `GET /mooring-systems/{id}` retornando `MooringSystemOutput +
   latest_execution`.
