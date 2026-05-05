# Relatório F11 — Documentação & lançamento v1.0

**Branch:** `feature/fase-11-lancamento-v1.0`
**Data:** 2026-05-05
**Commits atômicos pré-merge:** 9 (este é o nono)
**Status:** pronto para merge → execução do gate de release v1.0.0
(post-merge).

---

## Sumário executivo

Última fase do v1.0. Pura **documentação consolidada + tooling de
release + plano de rollback + tags**. Zero feature nova de código —
princípio anti-erro absoluto cumprido. Suite preserved: 698 backend
+ 5 skipped + 6 xfailed + 181 frontend verdes (zero regressão da
F10).

| Item Q-confirmação | Atendimento |
|--------------------|-------------|
| Q1 — PT-BR consistente | ✅ Todo material em PT-BR; termos técnicos canônicos preservam inglês (catenary, fairlead, anchor uplift, bollard pull). |
| Q2 — v1.0.0 semver formal | ✅ Tag adicional `v0.10.0-pre-release` planejada como âncora de rollback. |
| Q3 — manual rewrite estruturado | ✅ 12 seções, anchor uplift §6 antes de AHV §7 conforme reforço. |
| Q4 — seção AHV nos 6 pontos | ✅ §7 do manual: domínio (7.1), idealização vs real (7.2), quando usar (7.3), quando NÃO usar (7.4), D018/D019 (7.5), exemplo BC-AHV-01 (7.6), referências (7.7). |
| Q5 — Keep a Changelog 1.1.0 com hash+tag | ✅ 7 mudanças numéricas catalogadas com commit hash + tag de origem. |
| Q6 — decisoes_fechadas.md vs CLAUDE.md | ✅ Dois documentos com propósitos distintos. 13 decisões com decisão #13 (H per-segmento) adicionada. |
| Q7 — lista canônica de mudanças numéricas | ✅ 7 catalogadas; cases v0.x preservam quando NÃO ativam features novas. |
| Q8 — rollback 3 níveis + critério escalação | ✅ Tempo máximo por nível explícito (15min N1 / 30min N2). |
| Q9 — smoke prod set -e + 7 asserções | ✅ `tools/smoke_prod.sh` falha fechado, dry-run local validado. |
| Q10 — release_v1.0_uptime_log.md | 🔜 Será criado durante o gate post-merge (registra evidências do uptime real). |

---

## Commits pré-merge (em ordem)

### Commit 1 — `docs(decisoes): consolida 13 decisões fechadas`
Hash: `67ddb4e`. **381 linhas** em `docs/decisoes_fechadas.md`.

Documento canônico para auditoria científica externa. Cada decisão
tem: fase de origem, decisão (1 frase), justificativa técnica,
referência canônica (paper, código MoorPy, Excel), link para
relatório de fase. **Decisão #13 (H per-segmento)** adicionada per
Q6 reinforcement — não estava no escopo original do CLAUDE.md.

### Commit 2 — `docs(manual): rewrite estruturado v1.0 cobrindo F5-F10`
Hash: `e79bd2b`. **+480/-225 linhas** em `docs/manual_usuario.md`.

Substitui manual da F4 (293 linhas, parou em v0.1.0) por documento
estruturado em 12 seções. Conceitos físicos antes das features.
Glossário e diagnostics como referência transversal. Anchor uplift
§6 ANTES de AHV §7 per Q3 reinforcement (progressão didática
universal → especializada).

### Commit 3 — `docs(manual): seção AHV completa (mitigação obrigatória F8)`
Hash: `edcea0a`. **+149 linhas** em `docs/manual_usuario.md`.

**Fecha o gate F8 retroativamente** — última peça da mitigação
obrigatória D018 + Memorial PDF + manual. Os 6 pontos:
7.1 Domínio (3 parágrafos)
7.2 Idealização vs real (tabela 7 aspectos físicos)
7.3 Quando usar (4 cenários positivos)
7.4 Quando NÃO usar (5 cenários negativos com peso igual)
7.5 D018 (sempre dispara) + D019 (projeção <30%)
7.6 Exemplo BC-AHV-01 (lateral pura, 0.0000% erro)
7.7 Referências (Memorial PDF + relatório técnico + spec)

### Commit 4 — `docs(changelog): CHANGELOG.md inicial v1.0.0`
Hash: `4e789aa`. **234 linhas** em `CHANGELOG.md`.

Keep a Changelog 1.1.0 format. Seção destacada **"⚠ Mudanças
numéricas"** com 7 mudanças, cada uma citando commit hash + tag de
origem per Q5 reinforcement:
- Atrito per-segmento (`e83c6b5`, `v0.6-fase1`)
- Toggle ea_source qmoor/gmoor (`4ea2a47` + `76176c0`, `v0.6-fase1`)
- Batimetria 2 pontos (`85511c5`)
- Lifted arches (`a271ca8`)
- ProfileType taxonomy (`613727b`) — labeling, não numérica
- Anchor uplift single-seg (`dc03b9b` + `d21916c`)
- AHV H per-segmento (`18da690`)

Seção `[Unreleased]` lista as 5 pendências v1.1 não-bloqueantes da
Fase 10. Convenção semver explícita ao final.

### Commit 5 — `docs(release): release_notes_v1.0.md`
Hash: `02b0009`. **257 linhas** em `docs/release_notes_v1.0.md`.

Release notes públicas para usuário final. Inclui:
- Sumário do release (paridade total QMoor + 36 BCs validados)
- Mudanças desde v0.5-baseline (físicas + features + UX + perf)
- **Migração v0.x → v1.0** com matriz de compatibilidade backward
- 14 pendências v1.1 não-bloqueantes (5 da F10 + 9 herdadas)
- Roadmap v1.0.x (patches) → v1.1.0 (features) → v2.0.0 (Fase 12
  sem timeline)
- Decisões de escopo fechadas não-negociáveis em v1.0
- Como usar v1.0 pela primeira vez (tour, samples, manual)

### Commit 6 — `tools(prod): smoke_prod.sh`
Hash: `8334eaa`. **280 linhas** em `tools/smoke_prod.sh`.

`set -euo pipefail` (per Q9 reinforcement: falha fechado). 7
asserções via curl+jq:
1. GET /api/v1/health
2. GET /api/v1/line-types (≥500 entries em prod)
3. POST /cases (BC01_LIKE)
4. POST /cases/{id}/solve
5. GET /cases/{id}/export/memorial-pdf (header %PDF + ≥5KB)
6. POST /import-moor (round-trip)
7. POST /mooring-systems/{id}/watchcircle (n_steps=8, ProcessPool path)

Cleanup ao final (idempotente). Exit codes 10-17 conforme asserção
falhada para diagnóstico em pipeline. Dry-run local validado:
asserção #1 passa, #2 falha corretamente em DB sem catálogo
(comportamento esperado).

### Commit 7 — `docs(rollback): plano de rollback v1.0.0`
Hash: `ade2502`. **350 linhas** em `docs/rollback_v1.0.md`.

3 níveis bottom-up com critério explícito de escalação per Q8
reinforcement:
- **Nível 1** (código): git checkout v0.10.0-pre-release + restart.
  Tempo máximo 15min antes de escalar.
- **Nível 2** (DB): restore backup pre-v1.0-YYYY-MM-DD.db. Tempo
  máximo 30min antes de escalar.
- **Nível 3** (catastrófico): rebuild snapshot DigitalOcean. ~30min
  provisioning.

Pré-deploy obrigatório (3 itens): tag âncora + backup SQLite +
snapshot DO. Sem isso, **NÃO PROSSEGUIR com deploy**. Comunicação
ao usuário documentada por nível. Checklist impresso ao final.

### Commit 8 — `docs(claude): CLAUDE.md final pós-F11`
Hash: `032fa00`. **+20/-8 linhas** em `CLAUDE.md`.

Nova entrada da Fase 11 no índice. Seção "Documentação de
referência" reorganizada em 3 grupos (para Claude / para humano /
spec + revisor / operações) com `decisoes_fechadas.md` e
`rollback_v1.0.md` como novos pontos de entrada.

### Commit 9 — `docs(f11): relatório final F11`
**Este commit.** Documento que você está lendo.

---

## Validação consolidada

### Suite de testes (zero regressão da F10)

| Bloco | Estado pré-F11 | Estado pós-F11 | Δ |
|-------|---------------:|---------------:|---|
| Backend | 665 passed + 5 skipped + 6 xfailed | 698 passed + 5 skipped + 6 xfailed | +33 (test_perf novo de F10 agora roda na suíte completa graças ao fix do limiter) |
| Frontend | 181 passed | 181 passed | 0 |
| Tempo total | ~30s | ~35s | +5s |

Princípio "documentação ≠ código" cumprido: zero mudança em
solver, API ou frontend. Apenas docs e tooling.

### Ferramentas validadas

- `tools/smoke_prod.sh` — bash -n syntax OK + dry-run local
  exercitando asserções 1-2.
- `docs/decisoes_fechadas.md` — 13 decisões com referências
  cruzadas testadas (links relativos válidos no repo).
- Manual com 12 seções — toda referência cruzada validada (samples,
  glossário, decisões fechadas, rollback).

---

## Gate pós-merge (a ser executado após OK do usuário)

> **NÃO executado neste relatório.** Apenas planejado para
> referência. O usuário valida cada etapa.

### 9. Tag âncora `v0.10.0-pre-release`
```bash
git tag -a v0.10.0-pre-release \
    -m "Âncora de rollback do release v1.0.0" \
    <hash-do-merge-da-F10>  # último commit pré-F11 em main
git push origin v0.10.0-pre-release
```

### 10. Backup SQLite produção
```bash
ssh -i ~/.ssh/id_ancoplat ancoplat@159.223.129.77
DATE=$(date +%Y-%m-%d)
sudo cp /opt/ancoplat/data/cases.db \
        /opt/ancoplat/backups/pre-v1.0-${DATE}.db
sudo sqlite3 /opt/ancoplat/backups/pre-v1.0-${DATE}.db \
    "PRAGMA integrity_check;"
```

### 11. Snapshot DigitalOcean
Via web console ou doctl. TTL 7 dias.

### 12. Deploy via `operacao_producao.md` §4
```bash
ssh -i ~/.ssh/id_ancoplat ancoplat@159.223.129.77
cd /opt/ancoplat
sudo systemctl stop ancoplat-api
sudo -u ancoplat git pull
sudo -u ancoplat /opt/ancoplat/venv/bin/pip install \
    -r backend/requirements.txt
sudo systemctl start ancoplat-api
```

### 13. `tools/smoke_prod.sh` em produção
```bash
ANCOPLAT_BASIC_USER=<user> \
ANCOPLAT_BASIC_PASS=<pass> \
tools/smoke_prod.sh 2>&1 | tee \
    docs/smoke_prod_output_v1.0.0_$(date +%Y%m%dT%H%M%S).log
```

Falha fechado: se `exit != 0`, **NÃO PROSSEGUIR para item 14**.
Acionar [`rollback_v1.0.md`](rollback_v1.0.md) Nível 1.

### 14. Checklist manual UI (3 itens)
- [ ] Abrir caso salvo em produção (qualquer pré-existente)
  → renderiza sem erro.
- [ ] Plot 2D mostra catenária + touchdown + grounded vermelho.
- [ ] "Memorial PDF" download funciona, abre em viewer, conteúdo
  legível.

### 15. 48h uptime
Cron de healthcheck a cada 5min já configurado. Monitorar:
- `journalctl -u ancoplat-api --since <deploy_timestamp>` mostra
  zero "Started"/"Stopped" entries.
- `tail /opt/ancoplat/logs/healthcheck.log` mostra 100% 200.
- `grep "5[0-9][0-9]"
  /var/log/nginx/access.log` mostra zero 5xx no período.

### 16. `docs/release_v1.0_uptime_log.md` (per Q10 reinforcement)
Documento canônico de evidência:
- Timestamp do deploy.
- Output `journalctl` ao final das 48h.
- Counter healthchecks 200 vs falhados.
- Notas de quaisquer 4xx (cliente — OK) ou 5xx (problema).
- Nota: "Smoke test passou em <timestamp>; smoke prod log em
  `docs/smoke_prod_output_v1.0.0_<ts>.log`".

### 17. Tag `v1.0.0` SOBRE COMMIT EXATO PÓS-VALIDAÇÃO
> Princípio anti-erro: tag = exact commit. Nada de "depois mergeio
> mais um fix antes da tag".
```bash
git tag -a v1.0.0 \
    -m "AncoPlat v1.0.0 — primeiro release público estável" \
    <hash-do-merge-da-F11>
git push origin v1.0.0
```

### 18. GitHub release publicado
Via UI do GitHub:
- Title: "AncoPlat v1.0.0 — Primeiro release público estável"
- Body: cole conteúdo de `docs/release_notes_v1.0.md` §"O que mudou
  desde v0.5-baseline".
- Anexar: nenhum (release é apenas a tag + release notes).
- "Set as latest release" ✓.

---

## Princípios anti-erro reforçados (cumpridos)

- ✅ **Zero feature nova em F11.** Apenas docs + tooling + tag.
  Nenhuma mudança em `backend/solver/`, `backend/api/`, ou
  `frontend/src/components/` (exceto testes que já estavam na F10).
- 🔜 **Tag `v1.0.0` sobre commit exato pós-validação.** Será
  executada APÓS smoke prod + 48h uptime, NÃO antes.
- ✅ **Documentação É produto.** 1972 linhas novas distribuídas em
  6 documentos canônicos + 1 script + atualizações em CLAUDE.md.
- 🔜 **Smoke prod é gate de release.** Script pronto e validado em
  dry-run; será executado em produção real durante o gate.
- 🔜 **48h uptime é tempo real, não negociável.** Tag `v1.0.0`
  apenas após 48h efetivas, não promessa.

---

## Checklist final pré-merge

Conforme você pediu no fechamento da F11:

- [x] Manual de usuário rewrite estruturado, **12 seções**,
  cobrindo F5.1-F5.7 + F6 + F7 + F8 com seção AHV completa nos
  6 pontos.
- [x] CHANGELOG.md formato Keep a Changelog 1.1.0 com seção
  ⚠ Mudanças numéricas citando **commit hash + tag**.
- [x] `docs/decisoes_fechadas.md` com **13 decisões** consolidadas
  (12 propostas + #13 sobre H per-segmento).
- [x] `docs/release_notes_v1.0.md` com migração v0.x → v1.0.
- [x] `tools/smoke_prod.sh` com **set -e** e 7 asserções, dry-run
  em local validado.
- [x] `docs/rollback_v1.0.md` com 3 níveis + critério de escalação
  entre níveis.
- [x] CLAUDE.md final consolidado pós-F11.
- [x] Suite completa verde (698 backend + 181 frontend + zero
  regressão).

---

## Próximos passos (após seu OK)

1. **Merge `feature/fase-11-lancamento-v1.0` em `main`** (você
   confirma).
2. **Executo o gate de release pós-merge** (itens 9-18 acima),
   pausando em cada gate manual (smoke prod, checklist UI, 48h
   uptime) para sua confirmação.
3. **Aguardo 48h reais** com monitoramento.
4. **Tag `v1.0.0` + GitHub release publicado** após validação
   completa.

**Aguardando seu OK para merge.**
