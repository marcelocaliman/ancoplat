# docs/audit — snapshots de baseline

Snapshots imutáveis usados como teste de regressão durante a profissionalização do AncoPlat (ver [`docs/plano_profissionalizacao.md`](../plano_profissionalizacao.md)).

## Conteúdo

| Arquivo | Origem | Uso |
|---|---|---|
| `cases_baseline_<DATE>.json` | dump do SQLite local (`backend/data/ancoplat.db`) | Toda PR que mexe em solver/schema deve garantir que estes cases continuam abrindo e resolvendo com o mesmo resultado dentro de tolerância. |
| `moorpy_baseline_<DATE>.json` | rodada local do MoorPy (`tools/moorpy_env/`) sobre os 10 cases de `MoorPy/tests/test_catenary.py` | Referência numérica externa peer-reviewed. Vai virar o gate `BC-MOORPY-01..10` na Fase 1. |

## Regenerar

```
# cases_baseline (local SQLite → JSON)
venv/bin/python tools/dump_cases_baseline.py

# moorpy_baseline (precisa do tools/moorpy_env/ instalado — ver Fase 0 commit 3)
bash tools/moorpy_env/regenerate_baseline.sh
```

## Princípio

Estes arquivos são **fontes de verdade congeladas**. Não editar à mão. Para gerar uma nova versão:
1. Rode o regenerador.
2. Compare semânticamente com a versão anterior (não bytes — o `generated_at` muda).
3. Se a diferença for esperada (novo case adicionado, etc.), commite com mensagem explicando a mudança.
4. Se a diferença for inesperada (mesmo input → output diferente), **isso é uma regressão**: investigar antes de commitar.
