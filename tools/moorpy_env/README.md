# tools/moorpy_env — Ambiente isolado para validação contra MoorPy

[MoorPy](https://github.com/NREL/MoorPy) (NREL, open-source, peer-reviewed em ASME 2025) é a referência canônica de mooring quasi-estático em Python e é adotado neste projeto como **fonte de validação numérica externa** durante o plano de profissionalização (ver [`docs/plano_profissionalizacao.md`](../../docs/plano_profissionalizacao.md)).

Este diretório contém um **ambiente Python totalmente isolado** do venv principal do AncoPlat. MoorPy não é dependência de runtime — é dependência de validação. Não importe `moorpy` no código do AncoPlat.

## Estrutura

```
tools/moorpy_env/
├── README.md                  # este arquivo
├── .gitignore                 # exclui venv/ e MoorPy/ do git
├── moorpy_commit.txt          # commit hash do MoorPy usado (pinning)
├── requirements-bench.txt     # pip freeze do venv para reprodutibilidade
├── regenerate_baseline.py     # gera docs/audit/moorpy_baseline_<DATE>.json
├── regenerate_baseline.sh     # wrapper humano de regenerate_baseline.py
├── venv/                      # ⨯ não versionado (gerado por setup)
└── MoorPy/                    # ⨯ não versionado (clonado de github.com/NREL/MoorPy)
```

## Setup (primeira vez ou após clonar o repo)

```bash
cd tools/moorpy_env

# 1. Clonar MoorPy no commit fixado em moorpy_commit.txt
git clone https://github.com/NREL/MoorPy.git
git -C MoorPy checkout "$(cat moorpy_commit.txt)"

# 2. Criar venv Python 3.12 isolado (qualquer 3.10+ funciona; 3.12 é o
#    que está pinado no requirements; ver decisão Q1 da Fase 0)
python3.12 -m venv venv

# 3. Instalar MoorPy editable + dependências congeladas
venv/bin/pip install --upgrade pip
venv/bin/pip install -e ./MoorPy
venv/bin/pip install pytest

# 4. Sanidade — os 12 testes do MoorPy devem passar
cd MoorPy && ../venv/bin/python -m pytest tests/test_catenary.py -v
```

## Uso — regenerar baseline

```bash
# Da raiz do repo:
bash tools/moorpy_env/regenerate_baseline.sh
```

Saída: `docs/audit/moorpy_baseline_<DATE>.json` com os 10 catenary cases parametrizados em `MoorPy/tests/test_catenary.py`. Estes vão virar `BC-MOORPY-01..10` na Fase 1.

## Por que clone editável e não `pip install moorpy`?

Decisão da Fase 0 / Q2 = (b):
- Acesso aos `tests/test_catenary.py` (necessário para `regenerate_baseline.py` importar `indata` e `desired` diretamente).
- Pin por commit hash é mais granular e auditável que pin por versão PyPI.
- Permite navegar o código-fonte ao validar comportamento em fases futuras (Fase 4 ProfileType, Fase 10 V&V).

## Princípio de imutabilidade

Os JSONs em `docs/audit/moorpy_baseline_*.json` são **fontes de verdade congeladas**. Não editar à mão. Para gerar uma nova versão (ex: após bump do commit do MoorPy):

1. Atualize `moorpy_commit.txt` com o novo hash.
2. Faça checkout do MoorPy no novo commit.
3. Reinstale: `venv/bin/pip install -e ./MoorPy`.
4. Rode `regenerate_baseline.sh`.
5. Compare semanticamente com a versão anterior — diferenças no campo `desired_upstream` indicam que o upstream mudou; diferenças no campo `outputs` (com mesmo input + commit) indicam regressão local.
