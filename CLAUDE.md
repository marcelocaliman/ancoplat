# QMoor Web — Briefing para Claude Code

## Contexto

Este é um projeto de aplicação web pessoal para análise estática de linhas de ancoragem offshore. Detalhes completos em `docs/Documento_A_Especificacao_Tecnica_v2_2.docx`.

## Regras importantes

1. **Antes de qualquer tarefa significativa**, consulte `docs/Documento_A_Especificacao_Tecnica_v2_2.docx`. Esse é o briefing técnico definitivo.
2. **Não questione decisões marcadas como "Decisão fechada"** (caixas verdes no documento) sem motivo técnico claro.
3. **Stack:** Python 3.12 (backend), React + Vite + TypeScript (frontend), SQLite (banco), FastAPI (API).
4. **Solver:** catenária elástica com seabed, baseado em SciPy. Validação contra MoorPy (open-source).
5. **Catálogo de materiais:** importado integralmente de `docs/QMoor_database_inventory.xlsx` (522 entradas, 16 tipos).
6. **Unidades internas:** sempre SI (metros, Newtons, kg). Conversões só nas bordas (input/output).
7. **Comunicação:** o usuário não usa terminal. Sempre execute comandos por ele e mostre resultados visualmente.

## Estado atual

- ✅ F0 — Setup do ambiente (concluído)
- ⏳ F1a — Importação do catálogo QMoor para SQLite (próximo passo)
- ⬜ F1b — Implementação do solver
- ⬜ F2 — API FastAPI
- ⬜ F3 — Frontend React
- ⬜ F4 — Calibração com MoorPy
- ⬜ F5 — Polimento e exportações

## Decisões de projeto — Fase 1a (catálogo)

Tomadas após inspeção de `docs/QMoor_database_inventory.xlsx` (522 entradas, 16 tipos, 100% imperial, 100% `data_source=legacy_qmoor`). Substituem qualquer ambiguidade da Seção 4.2 do Documento A.

### Rigidez axial EA
- Schema preserva ambas as colunas `qmoor_ea` e `gmoor_ea` (nomes do xlsx mantidos).
- **Default do solver: `qmoor_ea`** — preserva comportamento do QMoor 0.8.5 original, que é o baseline de validação do projeto.
- Cada caso pode sobrescrever via campo `ea_source: "qmoor" | "gmoor"` (default `"qmoor"`).
- Motivação: poliéster exibe razão `gmoor_ea/qmoor_ea` de 10–22× (provável diferença estática vs dinâmica); wires EIPS ~1,45×; correntes ~0,88×. Não há base documental para escolher `gmoor_ea` — portanto default no legado.

### Atrito de seabed — anomalia R5Studless
- `seabed_friction_cf` é uniforme dentro de cada categoria exceto em `StudlessChain`:
  - R4Studless (63 entradas): μ = 1,0
  - R5Studless (41 entradas): μ = 0,6
- **Valores do catálogo preservados sem alteração.** Princípio: não modificar dado legado silenciosamente.
- Anomalia registrada aqui como pendência para validação com o engenheiro revisor.
- Hierarquia de precedência em runtime: solo informado pelo usuário > catálogo da linha (Seção 4.4 do Documento A).

### Primary key e rastreabilidade
- `id INTEGER PRIMARY KEY AUTOINCREMENT` (gerado pelo SQLite).
- **Extensão do schema**: adicionar coluna `legacy_id INTEGER` preservando o id original do xlsx (1–522). Permite auditoria contra o catálogo QMoor e evita colisões quando o usuário adicionar entradas próprias. Entradas criadas pelo usuário têm `legacy_id = NULL`.

### Conversão de unidades na seed
- Todas as 522 entradas estão em imperial — conversão para SI acontece no momento da importação (via Pint).
- `seabed_friction_cf` é adimensional — não converte.
- Armazenamento final: 100% SI (m, N, kg, Pa). `base_unit_system` da entrada reflete unidade **de origem**, não de armazenamento.

### Limpeza do xlsx
- Colunas fantasma do Excel (índices 17–26 sem cabeçalho) são descartadas.
- `comments`, `manufacturer`, `serial_number` estão 100% NULL no catálogo legado; importadas como NULL.

## Convenções de código

- Backend: type hints obrigatórios, docstrings em funções públicas
- Testes com pytest, casos de benchmark numerados BC-01 a BC-10
- Commits em português, padrão Conventional Commits (feat:, fix:, chore:, docs:, test:)
- Manter assinatura "Co-Authored-By: Claude Opus 4.7" nos commits

## Documentação técnica

- `docs/Documento_A_Especificacao_Tecnica_v2_2.docx` — briefing principal
- `docs/Documento_B_Checklist_Revisor-RESPONDIDO.docx` — respostas técnicas do engenheiro revisor
- `docs/QMoor_database_inventory.xlsx` — catálogo de materiais (fonte de dados)
- `docs/Documentacao_MVP_Versao_2_QMoor.pdf` — documentação original do escopo
- `docs/Cópia de Buoy_Calculation_Imperial_English.xlsx` — fórmulas de boia (uso futuro v2.1)
