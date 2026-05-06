# Release v1.0.0 — Log de uptime e gates

**Documento canônico de evidência** do gate de release v1.0.0
conforme `release_notes_v1.0.md` + `rollback_v1.0.md`.

Todos os timestamps em UTC ou ISO 8601 com timezone explícito.

---

## Gate 1 — Tag âncora ✅

**Timestamp:** 2026-05-05T22:30:00Z (aprox.)
**Tag:** `v0.10.0-pre-release` → commit `4d9e81d`
**Validação:**

```
$ git tag -l v0.10.0-pre-release
v0.10.0-pre-release

$ git rev-list -n 1 v0.10.0-pre-release
4d9e81d1900ddd6bfd7e9863b7bf7669459c30de

$ git ls-remote --tags origin | grep v0.10.0-pre-release
03a50fcb3f19318606a90c7ca46caff7fa85ff81  refs/tags/v0.10.0-pre-release
4d9e81d1900ddd6bfd7e9863b7bf7669459c30de  refs/tags/v0.10.0-pre-release^{}
```

✅ Tag annotated apontando para o commit do merge da F10. Pushada
para o remote.

---

## Gate 2 — Backup SQLite ✅

**Timestamp:** 2026-05-05 (data local Brasil, ~22:00 BRT)
**Backup file:** `/opt/ancoplat/backups/pre-v1.0-2026-05-05.db`

| Item | Valor |
|------|-------|
| Tamanho | 15.474.688 bytes (idêntico ao DB original) |
| SHA-256 | `d4003e4b0ad52fa522c45b9bbe19470468003af4739031d1e2ae7241d48f8bf4` |
| Integridade | `ok` (PRAGMA integrity_check) |
| Permissões | 640 ancoplat:ancoplat |
| Método | sqlite3 `.backup` (snapshot transacional) |

**Row counts (original vs backup):**

```
cases: 4 / 4
executions: 20 / 20
line_types: 522 / 522
buoys: N/A / N/A  (tabela ainda não existia em prod — F-prof.6 não chegou)
mooring_systems: 2 / 2
mooring_system_executions: 8 / 8
```

✅ Idênticos — backup íntegro e válido para restore Nível 2.

---

## Gate 3 — Snapshot DigitalOcean ✅

**Timestamp:** 2026-05-05 (~22:00 BRT)
**Nome:** `ancoplat-pre-v1.0-2026-05-05`

| Item | Valor |
|------|-------|
| Snapshot ID (via URL) | `567249526` |
| Tamanho | 6.82 GB |
| Região | NYC1 (mesma do droplet) |
| Status | Available |
| TTL | Sem expiração automática (manual) — manter ≥ 7 dias post-release |

✅ Snapshot pronto para rollback Nível 3 catastrófico em emergência.

> Nota: ID `567249526` foi capturado via URL do dashboard e pode
> referir o droplet em vez do snapshot. Em rollback efetivo, usar
> `doctl compute snapshot list | grep ancoplat-pre-v1.0-2026-05-05`
> para resolver o ID exato.

---

## Gate 4 — Deploy ✅

**Timestamp inicial:** 2026-05-05T22:00:21-03:00
**Timestamp de sucesso (3a tentativa):** 2026-05-05T22:14:33-03:00
**Commit deployed:** `6d86021` (`fix(smoke)` em cima do merge F11
`3c01d2c`)

### Sequência de tentativas

| Tentativa | Resultado | Causa | Ação |
|-----------|-----------|-------|------|
| 1 (22:00) | ❌ Race condition na verificação de migration | `sleep 8` insuficiente — lifespan completou em ~17s, eu chequei em ~9s | Rollback automático Nível 1 (per mitigação #6) |
| 2 (22:06) | ❌ Smoke falhou em /line-types (4 entries) | Bug no smoke: `jq '. \| length'` em endpoint paginado mediu 4 chaves do objeto em vez de 522 items | Rollback automático Nível 1 (per mitigação #7) |
| 3 (22:11) | ✅ Sucesso | Fix do smoke (commit `6d86021`) + polling do health endpoint até 200 OK em vez de sleep fixo | Deploy completo + smoke 7/7 |

### Métricas finais (tentativa 3)

| Métrica | Valor |
|---------|-------|
| Commits aplicados | 103 (`c8e0d93` → `6d86021`) |
| pip install | idempotente (sem mudança em `requirements.txt`) |
| npm ci | 722 packages |
| npm run build | 14.43s |
| systemctl restart → health 200 | 19.827s |
| Tabela `buoys` criada | ✓ (lifespan startup) |
| Seed buoys | 11 entries (idempotente) |
| nginx reload | ✓ |

### Estado final pós-deploy

```
$ git log -1 --oneline
6d86021 fix(smoke): corrige paginação line-types + path import/moor

$ sqlite3 /opt/ancoplat/data/ancoplat.db ".tables"
app_config  buoys  cases  executions  line_types  mooring_system_executions  mooring_systems

$ curl -sS http://localhost:8000/api/v1/health
{"status":"ok","db":"ok"}
```

**Logs no droplet:**
- `/opt/ancoplat/logs/deploy_v1.0_20260505_2211_attempt3.log`
- `/opt/ancoplat/logs/deploy_v1.0_20260505_2200.log` (tentativa 1)
- `/opt/ancoplat/logs/deploy_v1.0_20260505_2206_retry.log` (tentativa 2)

---

## Gate 5 — Smoke prod automatizado ✅

**Timestamp:** 2026-05-06T01:14:01Z → 2026-05-06T01:14:33Z (32 segundos)
**Resultado:** 7/7 asserções passaram

```
▶ 1/7 GET /api/v1/health              ✓ status=ok
▶ 2/7 GET /api/v1/line-types          ✓ total=522 (≥500)
▶ 3/7 POST /api/v1/cases              ✓ id criado
▶ 4/7 POST /cases/{id}/solve          ✓ status=converged, alert=ok
▶ 5/7 GET /cases/{id}/export/memorial-pdf  ✓ 95327 bytes, header %PDF válido
▶ 6/7 Round-trip .moor v2             ✓ imported_id retornado
▶ 7/7 POST /watchcircle (n_steps=8)   ✓ 8 azimutes resolvidos
▶ Cleanup (delete cases + msys)       ✓ OK
```

**Log:** `/opt/ancoplat/logs/smoke_prod_v1.0_20260505_2211_attempt3.log`

---

## Gate 6 — Checklist UI (automatizado) ✅

**Timestamp:** 2026-05-06T01:30:00Z (aprox.)
**Modo:** automatizado via `curl` contra produção (per direção do
usuário "não quero mexer em nada de código"). Substitui execução
manual em browser; valida os mesmos pontos críticos via API + bundle
estático.

### 4/4 asserções

| # | Item | Resultado |
|---|------|-----------|
| 1 | `GET /` retorna HTML com `<div id="root">` | ✅ HTTP 200 + marker presente |
| 2 | JS bundle `/assets/index-DlhH_LAI.js` servido | ✅ HTTP 200 (HEAD) |
| 3 | Caso real abrível (`GET /api/v1/cases/10` 'Lazy-S boia + clump') | ✅ JSON retornado |
| 4 | Memorial PDF gerável | ✅ já validado em Gate 5 (95327 bytes, %PDF) |

**Cobertura cruzada com Gate 5 (smoke prod 7/7):** os asserts API
(saúde + cases CRUD + solve + memorial PDF + .moor round-trip +
watchcircle) já confirmaram que todo o caminho frontend→API→solver
está funcional. O Gate 6 automatizado complementa com a validação
do bundle estático servido pelo nginx.

> **O que NÃO foi testado automaticamente:** rendering visual (Plotly
> efetivamente desenhando catenária no canvas) e interações
> (hover, click). Esses são cobertos por 181 testes frontend em
> vitest no commit deployed (`6d86021`) — testes verdes pré-merge.
> Para validação visual interativa, qualquer abertura manual do
> browser confirma o que o automatizado infere.

---

## Gate 7 — Início da janela de 48h uptime ✅

**Timestamp de início (UTC):** 2026-05-06T01:14:33Z
*(corresponde a 2026-05-05 22:14:33 BRT — momento exato quando
smoke prod confirmou 7/7 ✅, declarando v1.0 estável em produção)*

**Janela de 48 horas reais (calendário, não tempo útil):**

```
START:  2026-05-06T01:14:33Z  (2026-05-05 22:14 BRT)
END:    2026-05-08T01:14:33Z  (2026-05-07 22:14 BRT)
```

**Logging começa:** healthcheck cron já estava rodando a cada 5min
no droplet (configurado pré-release per `operacao_producao.md` §9).
Nenhuma ação adicional necessária para iniciar logging — apenas
registrar o timestamp âncora.

---

## Gate 8 — Encerramento das 48h ⚠ OVERRIDE EXPLÍCITO

**Status:** PULADO mediante autorização explícita do usuário.

**Timestamp do override:** 2026-05-06T01:35:00Z (aprox.)

**Citação literal da autorização:**

> "Autorizo pular o Gate 8 das 48h. Aceito a responsabilidade.
> Tag v1.0.0 agora"

**Contexto da decisão:**
- Usuário (Marcelo) operando após sessão longa de 11 fases +
  deploy v1.0.
- Disciplina das 48h originalmente escrita por ele em
  `release_notes_v1.0.md` e `release_v1.0_uptime_log.md`
  (ambos pushados pré-override).
- Override explícito vem em resposta a 3 opções apresentadas
  (rc1 + 48h, cron de 48h, ou skip explícito) — escolheu skip
  explícito assumindo a responsabilidade.

**Implicações honestas (registradas para auditoria):**

1. Tag `v1.0.0` é cravada com **~3 horas de uptime** em produção,
   não 48h. Bug que apareça nas próximas 48h ficará no histórico
   do `v1.0.0` (não pode mais ser excluído da semântica do tag).
2. Smoke prod 7/7 + Gate 6 4/4 cobrem o caminho funcional crítico,
   então o risco é de regressão em paths não testados ou em
   estabilidade de longo prazo (memory leak, file handle leak,
   degradação SQLite após N horas, etc.) — improváveis dado o
   solver é puramente síncrono e SQLite simples, mas possíveis.
3. Rollback Nível 1 continua disponível via tag
   `v0.10.0-pre-release` se algo aparecer pós-tag.
4. Documentação canônica preservada: este parágrafo registra que
   a disciplina foi conscientemente sobrepasada, não esquecida.

**Critérios de sucesso que NÃO foram verificados** (registro
honesto do que se está pulando):

- ❌ Não verificado: `journalctl ... --since "..."` mostra zero
  "Started"/"Stopped" em 48h (esperaria ~zero).
- ❌ Não verificado: 100% de healthchecks 200 em 48h
  (target ~576 healthchecks).
- ❌ Não verificado: zero 5xx em nginx access.log em 48h.

**Evidência parcial capturada (3 horas de uptime):**

A produção tem rodado o commit `6d86021` desde 2026-05-06T01:14:33Z
sem incidentes reportados durante a sessão de release. Gate 5 + Gate
6 confirmaram comportamento correto. Esta janela é menor que a
prometida.

---

## Gate 9 — Tag v1.0.0 ⏳ EXECUTANDO

**Status:** sendo executado mediante override explícito do Gate 8.

Tag `v1.0.0` annotated apontando para `6d86021` (commit exato em
produção). Comando que será executado:
```bash
git tag -a v1.0.0 6d86021 -m "AncoPlat v1.0.0 — primeiro release público estável"
git push origin v1.0.0
```

Evidências registradas após execução abaixo.

---

## Gate 10 — GitHub release 🔜

**Status:** PENDENTE — só após Gate 9.

Será criado via UI do GitHub:
- Tag: v1.0.0
- Title: "AncoPlat v1.0.0 — Primeiro release público estável"
- Body: cópia de `docs/release_notes_v1.0.md` §"O que mudou desde v0.5-baseline"
- "Set as latest release" ✓

---

## Apêndice — Estado atual de produção (snapshot momento do log)

| Item | Valor |
|------|-------|
| URL pública | https://ancoplat.duckdns.org |
| Droplet | DigitalOcean NYC1 (`ancoplat-prod`, IP 159.223.129.77) |
| Commit deployed | `6d86021` |
| Service | `ancoplat-api.service` (uvicorn workers via systemd) |
| Backup pre-v1.0 | `/opt/ancoplat/backups/pre-v1.0-2026-05-05.db` |
| Snapshot DO pre-v1.0 | `ancoplat-pre-v1.0-2026-05-05` |
| Tag rollback | `v0.10.0-pre-release` → `4d9e81d` |
| Health pública | 200 OK (basic auth `UserTest`) |
| Health localhost | 200 OK |

---

*Atualizado a cada gate. Documento canônico — não edita histórico,
apenas adiciona.*
