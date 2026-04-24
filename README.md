# QMoor Web

Ferramenta pessoal para análise estática de linhas de ancoragem offshore.

## Sobre o projeto

Aplicação web para cálculo de catenária elástica de linhas isoladas de ancoragem, com suporte a contato com seabed e atrito de Coulomb. Solver baseado em equações de catenária clássica e correções elásticas, validado contra MoorPy (referência open-source).

Desenvolvido como ferramenta de apoio à engenharia de ancoragem, sem fins comerciais nesta versão.

## Estrutura de pastas

- `backend/` — código Python do solver e da API REST
  - `solver/` — módulo do solver (catenária, elasticidade, seabed)
  - `api/` — endpoints FastAPI
  - `models/` — schemas Pydantic
  - `data/` — banco SQLite e scripts de seed
- `frontend/` — aplicação React (a ser criada na Fase 3)
- `docs/` — documentação técnica do projeto

## Status

🚧 Em desenvolvimento — Fase 1: solver isolado.

## Como instalar

(A ser preenchido quando o ambiente estiver estabilizado)

## Como rodar

(A ser preenchido quando a primeira versão funcional estiver pronta)

## Documentação

Ver pasta `docs/` para especificação técnica completa.
