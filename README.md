# AncoPlat

Ferramenta pessoal para análise estática de linhas de ancoragem offshore.

## Sobre o projeto

Aplicação web para cálculo de catenária elástica de linhas isoladas de ancoragem, com suporte a contato com seabed e atrito de Coulomb. Solver baseado em equações de catenária clássica e correções elásticas, validado contra [MoorPy](https://github.com/NREL/MoorPy) (referência open-source da NREL).

Desenvolvido como ferramenta de apoio à engenharia de ancoragem, sem fins comerciais nesta versão.

## Estrutura de pastas

- `backend/` — código Python do solver e da API REST
  - `solver/` — módulo do solver (catenária, elasticidade, seabed, atrito)
  - `api/` — endpoints FastAPI (Fase 2)
  - `models/` — schemas Pydantic
  - `data/` — banco SQLite e scripts de seed
- `frontend/` — aplicação React (Fase 3)
- `docs/` — documentação técnica do projeto

## Status

| Fase | Descrição | Estado |
|------|-----------|:------:|
| F0 | Setup do ambiente | ✅ |
| F1a | Importação do catálogo QMoor (legacy, 522 entradas em SQLite) | ✅ |
| F1b | Solver isolado (catenária + seabed + atrito + elástico) | ✅ |
| F2 | API FastAPI | ⏳ **em planejamento** |
| F3 | Frontend React + Vite + TypeScript | ⬜ |
| F4 | Calibração e benchmarks finais | ⬜ |
| F5 | Polimento e exportações (PDF, .moor, JSON) | ⬜ |

**Solver F1b**: 45 testes passando, 96% cobertura de código, 9 casos de benchmark (BC-01 a BC-09) validados contra MoorPy com desvio < 1% em força e < 0.5% em geometria.

## Documentação

- [CLAUDE.md](CLAUDE.md) — índice mestre + decisões fechadas
- [docs/Documento_A_Especificacao_Tecnica_v2_2.docx](docs/Documento_A_Especificacao_Tecnica_v2_2.docx) — especificação técnica canônica
- [docs/relatorio_F1b.md](docs/relatorio_F1b.md) — estado e validações do solver
- [docs/plano_F2_api.md](docs/plano_F2_api.md) — desenho da API REST
- [docs/auditoria_estrategica_pre_F2.md](docs/auditoria_estrategica_pre_F2.md) — auditoria do estado antes da F2
- [docs/Documento_B_Checklist_Revisor-RESPONDIDO.docx](docs/Documento_B_Checklist_Revisor-RESPONDIDO.docx) — respostas do engenheiro revisor

## Como instalar (dev)

```bash
python3.12 -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt
python backend/data/seed_catalog.py   # popula o SQLite
pytest backend/solver/tests/ -v        # valida o solver
```

## Como rodar

Por enquanto, o solver é uma biblioteca Python. Import direto:

```python
from backend.solver.solver import solve
from backend.solver.types import LineSegment, BoundaryConditions, SolutionMode

seg = LineSegment(length=450, w=201.1, EA=34.25e6, MBL=3.78e6)
bc = BoundaryConditions(h=300, mode=SolutionMode.TENSION, input_value=785_000)
result = solve([seg], bc)
print(result.status, result.total_horz_distance)
```

A API REST (F2) e o frontend (F3) virão na sequência.

## Licença

Uso pessoal, sem fins comerciais nesta versão.
