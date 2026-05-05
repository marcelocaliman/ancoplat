# Plano de rollback — Deploy v1.0.0

**Branch alvo:** `main` no commit pós-merge da F11.
**Tag de release:** `v1.0.0`.
**Tag âncora de rollback:** `v0.10.0-pre-release` (commit
imediatamente anterior à F11 em `main`).
**Backup obrigatório:** `/opt/ancoplat/backups/pre-v1.0-YYYY-MM-DD.db`.

---

## TL;DR — fluxo de decisão sob pressão

```
┌─ Smoke prod falhou ou usuário reportou bug crítico ────────────┐
│                                                                  │
│ 1. Tente NÍVEL 1 (código) primeiro. SEMPRE.                     │
│    Tempo máximo: 15 minutos.                                    │
│    ↓                                                             │
│ 2. Resolveu? → Pare. Documente em release_v1.0_uptime_log.md.  │
│    Não resolveu em 15min OU sintoma de DB → NÍVEL 2.            │
│    ↓                                                             │
│ 3. NÍVEL 2 (DB) — restore do backup + restart.                  │
│    Tempo máximo: 30 minutos.                                    │
│    ↓                                                             │
│ 4. Resolveu? → Pare. Documente.                                 │
│    Não resolveu OU droplet inacessível → NÍVEL 3.               │
│    ↓                                                             │
│ 5. NÍVEL 3 (catastrófico) — rebuild snapshot DigitalOcean.      │
│    Tempo: ~30 minutos (provisioning + DNS).                     │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

**Princípio:** sempre escala bottom-up. Não pule níveis exceto
quando o nível inferior não tem como ser executado (e.g. SSH não
responde — pula para Nível 3).

---

## Pré-deploy obrigatório (antes de tagear v1.0.0)

Estas ações são pré-condições para qualquer rollback ser possível.
Se faltar qualquer uma, **NÃO PROSSEGUIR com o deploy**.

### 1. Tag âncora `v0.10.0-pre-release`

Tag git no commit imediatamente anterior à F11 em `main`.

```bash
# Identifica commit pré-F11 (último commit pré-feature/fase-11):
COMMIT_PRE_F11=$(git rev-parse main~1)

# Cria tag âncora.
git tag -a v0.10.0-pre-release -m "Âncora de rollback do release v1.0.0" \
    "$COMMIT_PRE_F11"

# Push da tag para o remoto (obrigatório — produção precisa puxar).
git push origin v0.10.0-pre-release
```

> Verificação: `git show v0.10.0-pre-release` deve mostrar o commit
> de merge da Fase 10, **não** commits da F11.

### 2. Backup do SQLite de produção

```bash
# No servidor de produção:
ssh -i ~/.ssh/id_ancoplat ancoplat@159.223.129.77

DATE=$(date +%Y-%m-%d)
sudo cp /opt/ancoplat/data/cases.db \
        /opt/ancoplat/backups/pre-v1.0-${DATE}.db

# Verifica integridade.
sudo sqlite3 /opt/ancoplat/backups/pre-v1.0-${DATE}.db \
    "PRAGMA integrity_check;"
# → deve retornar "ok"
```

### 3. Snapshot DigitalOcean

Via web console DigitalOcean (`https://cloud.digitalocean.com/`):
1. Droplets → `ancoplat-prod` → "Snapshots".
2. "Take Snapshot" com nome `ancoplat-pre-v1.0-${DATE}`.
3. Aguarde provisioning (~5 minutos).
4. **TTL do snapshot: 7 dias** — retentar caso v1.0 não estabilize
   nesse período.

### 4. Verificação cruzada

```bash
# Confirma os 3 itens em uma linha:
ssh -i ~/.ssh/id_ancoplat ancoplat@159.223.129.77 \
    "ls -la /opt/ancoplat/backups/pre-v1.0-*.db" \
    && git tag -l "v0.10.0-pre-release" \
    && echo "Snapshot DigitalOcean: confirmar manualmente no console"
```

---

## NÍVEL 1 — Rollback de código (reversão do deploy)

**Quando aplicar:**
- `tools/smoke_prod.sh` falhou após o deploy.
- Endpoint retorna 5xx em volume após deploy.
- Bug visual reportado pelo usuário em feature crítica.
- Diagnostic não dispara onde deveria (V&V quebrou).

**Quando NÃO aplicar (pular para Nível 2):**
- SQLite reporta corruption ou schema mismatch.
- Cases salvos em v0.x não abrem mais em produção.
- DB não acessível a qualquer query.

### Procedimento

```bash
# 1. Conectar como usuário da aplicação.
ssh -i ~/.ssh/id_ancoplat ancoplat@159.223.129.77

# 2. Parar API.
sudo systemctl stop ancoplat-api

# 3. Reverter código para a tag âncora.
cd /opt/ancoplat
sudo -u ancoplat git fetch origin
sudo -u ancoplat git checkout v0.10.0-pre-release

# 4. Rebuild (caso houver dependências novas).
sudo -u ancoplat /opt/ancoplat/venv/bin/pip install \
    -r /opt/ancoplat/backend/requirements.txt

# 5. Reiniciar API.
sudo systemctl start ancoplat-api

# 6. Smoke test rápido.
curl -s https://ancoplat.duckdns.org/api/v1/health
# → {"status":"ok","db":"ok"}

# 7. Verifica logs.
journalctl -u ancoplat-api -n 50 --no-pager
```

**Tempo esperado: ~5 minutos.**

### Critério de escalação para Nível 2

Após o rollback de código, se algum dos abaixo for verdadeiro:
- API em loop de restart (`systemctl status ancoplat-api` mostra
  reinicializações repetidas).
- Health check retorna `{"status":"ok","db":"error"}` ou `db:"degraded"`.
- Endpoint `/cases/{id}` retorna 500 ao acessar caso v0.x salvo.
- Endpoint `/import-moor` retorna erro de schema ao re-importar
  case que funcionava em v0.10.0.

→ **Escalar para Nível 2.**

**Tempo máximo no Nível 1 antes de escalar: 15 minutos.** Se
diagnóstico inconclusivo, escala — não fica iterando.

---

## NÍVEL 2 — Rollback de banco (restore do backup)

**Quando aplicar:**
- Nível 1 não resolveu OU sintoma indica corrupção/schema mismatch
  do DB.
- Cases v0.x não carregam após restart.
- Migration falhou parcialmente (tabela parcialmente alterada).
- Erros sistemáticos em queries que funcionavam pré-deploy.

**Quando NÃO aplicar (pular para Nível 3):**
- Droplet inacessível via SSH.
- Filesystem corrompido (`df` falha, mounts perdidos).
- I/O errors no journal.

### Procedimento

```bash
# 1. Conectar.
ssh -i ~/.ssh/id_ancoplat ancoplat@159.223.129.77

# 2. Parar API.
sudo systemctl stop ancoplat-api

# 3. Identificar backup correto (mais recente pre-v1.0).
ls -la /opt/ancoplat/backups/pre-v1.0-*.db
BACKUP=/opt/ancoplat/backups/pre-v1.0-YYYY-MM-DD.db  # SUBSTITUIR

# 4. Verificar integridade do backup ANTES de restaurar.
sudo sqlite3 "$BACKUP" "PRAGMA integrity_check;"
# → deve retornar "ok". Se não, abortar e ir para Nível 3.

# 5. Mover DB atual para arquivo de quarentena (não deleta).
sudo mv /opt/ancoplat/data/cases.db \
        /opt/ancoplat/data/cases.db.broken-$(date +%s)

# 6. Restaurar backup.
sudo cp "$BACKUP" /opt/ancoplat/data/cases.db
sudo chown ancoplat:ancoplat /opt/ancoplat/data/cases.db
sudo chmod 644 /opt/ancoplat/data/cases.db

# 7. Confirmar que código também está em v0.10.0-pre-release.
cd /opt/ancoplat
sudo -u ancoplat git rev-parse HEAD
# → deve coincidir com `git rev-parse v0.10.0-pre-release`

# 8. Reiniciar API.
sudo systemctl start ancoplat-api

# 9. Smoke + logs.
curl -s https://ancoplat.duckdns.org/api/v1/health
journalctl -u ancoplat-api -n 50 --no-pager
```

**Tempo esperado: ~10 minutos.**

> **Atenção:** o DB com problema fica preservado em
> `/opt/ancoplat/data/cases.db.broken-<timestamp>` para diagnóstico
> post-mortem. Não deletar até a causa raiz ser identificada.

### Critério de escalação para Nível 3

- Smoke test continua falhando após restore.
- API em estado inconsistente (logs mostram errors persistentes
  não-relacionados a DB).
- SSH instável (timeouts, lag de seconds).
- `journalctl` mostra OOM kills ou disk-full antes do problema.

→ **Escalar para Nível 3.**

**Tempo máximo no Nível 2 antes de escalar: 30 minutos.**

---

## NÍVEL 3 — Catastrófico (rebuild do snapshot DigitalOcean)

**Quando aplicar:**
- Droplet não responde a SSH/comando.
- Filesystem corrompido a ponto de não permitir restore.
- Multi-tenant infrastructure failure que impacta o droplet
  (raríssimo).
- Decisão pragmática após >30min em Nível 2 sem resolver.

### Procedimento

#### Via web console DigitalOcean

1. Login em `https://cloud.digitalocean.com/`.
2. Droplets → `ancoplat-prod` → "Snapshots".
3. Localizar `ancoplat-pre-v1.0-YYYY-MM-DD`.
4. Clicar em "Restore".
5. **Confirmar overwrite do droplet atual** — destrutivo, sem
   undo. Toda mudança feita após o snapshot é perdida.
6. Aguardar provisioning (5-15 minutos).
7. DNS já aponta para o droplet (mesmo IP) — não precisa atualizar.

#### Via doctl (CLI alternativa)

```bash
# Lista snapshots.
doctl compute snapshot list --resource droplet

# Restore — substitui droplet atual.
doctl compute droplet-action restore <DROPLET_ID> \
    --image-id <SNAPSHOT_ID> \
    --wait
```

#### Pós-restore

```bash
# Aguarda droplet voltar.
sleep 60

# Verifica SSH.
ssh -i ~/.ssh/id_ancoplat ancoplat@159.223.129.77 "uptime"

# Verifica serviços.
ssh -i ~/.ssh/id_ancoplat root@159.223.129.77 \
    "systemctl status ancoplat-api nginx"

# Smoke test.
curl -s https://ancoplat.duckdns.org/api/v1/health
```

**Tempo esperado: 30 minutos** (provisioning + boot + verificação).

### Critério de escalação para humano (eu)

Se o Nível 3 falhar (snapshot corrompido, DigitalOcean fora,
DNS quebrado por outro motivo):

→ **Escalar para o usuário (Marcelo).** Possíveis ações:
- Provisionar droplet novo do zero (estimativa: 4 horas para deploy
  completo do AncoPlat seguindo `operacao_producao.md`).
- Verificar status DigitalOcean (`https://status.digitalocean.com/`).
- Acionar suporte DigitalOcean caso seja issue da plataforma.

---

## Comunicação ao usuário durante rollback

Se o usuário (Marcelo) está acessando o app durante um rollback:

- **Nível 1**: app fica fora ~5 min. Comunicar via mensagem direta
  ("Estou rebootando o servidor, volta em 5 minutos").
- **Nível 2**: app fica fora ~10-15 min. Comunicar e marcar uptime
  log como "Manutenção emergencial — rollback Nível 2 — DB
  restaurado de backup".
- **Nível 3**: app fica fora ~30-60 min. Comunicar status, deadline
  esperado, e ação seguinte.

---

## Pós-rollback (em qualquer nível)

1. **Documentar o ocorrido** em
   `docs/release_v1.0_uptime_log.md` com:
   - Timestamp do incidente.
   - Sintoma observado.
   - Nível executado.
   - Tempo decorrido até resolução.
   - Causa raiz identificada (ou "indeterminada — investigando").
2. **Investigar causa raiz** antes de tentar deploy novamente.
3. **Bug fix em branch dedicada** (`fix/rollback-vN-issue-X`) com
   teste de regressão.
4. **Re-tentar deploy v1.0.X** apenas após causa raiz resolvida e
   teste de regressão passando.

---

## Checklist de rollback (impressão recomendada)

- [ ] Identifiquei o sintoma (smoke prod fail / 5xx / bug crítico).
- [ ] Verifiquei o nível apropriado (1 → 2 → 3 bottom-up).
- [ ] Cronômetro iniciado (15min Nível 1 / 30min Nível 2).
- [ ] Pré-condições do nível atendidas (backup existe, snapshot
      existe, tag âncora existe).
- [ ] Procedimento executado.
- [ ] Smoke test pós-rollback executado.
- [ ] Healthcheck verificado.
- [ ] Logs verificados (`journalctl -u ancoplat-api`).
- [ ] Documentação `release_v1.0_uptime_log.md` atualizada.
- [ ] Causa raiz identificada (ou em investigação).

---

*Plano de rollback canônico v1.0.0. Atualizar em casos de mudanças
significativas na infra produção (e.g. migração para Postgres em
v1.1+).*
