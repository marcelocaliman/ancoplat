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

## Gate 6 — Checklist UI manual 🔜

**Status:** PENDENTE — aguardando execução manual do usuário.

### 3 itens a executar via browser em https://ancoplat.duckdns.org

- [ ] **Item 1 — Abrir caso pré-existente.** Login com basic auth →
      sidebar "Casos" → clicar em qualquer caso da lista (existem 4
      cases pré-deploy + qualquer um seedado pós-deploy) → caso
      renderiza sem erro 5xx ou tela branca.
- [ ] **Item 2 — Ver plot 2D.** No caso aberto, aba "Plot" mostra
      catenária renderizada com touchdown marcado, grounded em
      pontilhado vermelho, suspended em azul sólido. Hover funciona
      mostrando coordenadas.
- [ ] **Item 3 — Exportar Memorial PDF.** Botão "Memorial PDF" →
      download inicia → arquivo `.pdf` abre em viewer → primeira
      página mostra cabeçalho com hash, solver_version, timestamp.

**Quando completar todos os 3:** reporte para mim. Avanço para Gate 7
(início da janela de 48h).

---

## Gate 7 — Início da janela de 48h uptime 🔜

**Status:** PENDENTE — só inicia após Gate 6 aprovado.

Vou registrar timestamp exato aqui quando você confirmar Gate 6.

```
DEPLOY_TIMESTAMP_START_48H: <a definir>
EXPECTED_END_48H: <DEPLOY_TIMESTAMP + 48h>
```

---

## Gate 8 — Encerramento das 48h 🔜

**Status:** PENDENTE.

Critérios de sucesso (verificados após 48h reais):

- [ ] `journalctl -u ancoplat-api --since "<DEPLOY_TIMESTAMP_START_48H>"`
      mostra **zero "Started"/"Stopped"** entries (nenhum restart).
- [ ] Healthcheck cron a cada 5min: 100% de respostas 200 no período
      (target: ~576 healthchecks em 48h).
- [ ] `grep "5[0-9][0-9]" /var/log/nginx/access.log` no período
      mostra **zero 5xx** (4xx é OK — cliente).

Evidências serão capturadas e pasted aqui antes de avançar para
Gate 9.

---

## Gate 9 — Tag v1.0.0 🔜

**Status:** PENDENTE — só sai após Gate 8 confirmado por evidências.

Comando preparado:
```bash
git tag -a v1.0.0 6d86021 \
    -m "AncoPlat v1.0.0 — primeiro release público estável"
git push origin v1.0.0
```

Tag aponta para o commit `6d86021` (commit exato em produção pós-validação).

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
