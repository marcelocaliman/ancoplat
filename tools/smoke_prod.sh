#!/usr/bin/env bash
#
# Smoke test em produção — gate de release v1.0.0.
#
# Faz 7 asserções via curl + jq cobrindo o caminho crítico
# end-to-end:
#   1. GET /api/v1/health                         → API up
#   2. GET /api/v1/line-types                      → DB acessível
#   3. POST /api/v1/cases (BC01_LIKE)              → write path
#   4. POST /api/v1/cases/{id}/solve               → solver core
#   5. GET /api/v1/cases/{id}/export/memorial-pdf  → reports
#   6. POST /api/v1/import-moor (round-trip)       → import/export
#   7. POST /api/v1/mooring-systems/{id}/watchcircle → feature flagship
#
# Uso:
#   tools/smoke_prod.sh              # default produção
#   tools/smoke_prod.sh --base http://localhost:8000  # dry-run local
#
# Variáveis de ambiente:
#   ANCOPLAT_BASE_URL    — base URL (default: https://ancoplat.duckdns.org)
#   ANCOPLAT_BASIC_USER  — usuário do basic auth nginx
#   ANCOPLAT_BASIC_PASS  — senha do basic auth nginx
#
# Falha fechado (set -e + pipefail). Exit code não-zero em qualquer
# falha — deploy NÃO continua se este script falhar.

set -euo pipefail

# ─── Configuração ────────────────────────────────────────────────────
BASE_URL="${ANCOPLAT_BASE_URL:-https://ancoplat.duckdns.org}"
BASIC_USER="${ANCOPLAT_BASIC_USER:-}"
BASIC_PASS="${ANCOPLAT_BASIC_PASS:-}"

# Permite override do BASE_URL via flag --base.
while [[ $# -gt 0 ]]; do
    case "$1" in
        --base)
            BASE_URL="$2"
            shift 2
            ;;
        *)
            echo "Uso: $0 [--base URL]" >&2
            exit 2
            ;;
    esac
done

# Curl args com basic auth se configurado.
CURL_AUTH=()
if [[ -n "${BASIC_USER}" && -n "${BASIC_PASS}" ]]; then
    CURL_AUTH=(-u "${BASIC_USER}:${BASIC_PASS}")
fi

# Helper: curl silencioso com http_code separado de body.
_curl() {
    local method="$1"; shift
    local path="$1"; shift
    local tmp_body
    tmp_body=$(mktemp)
    local code
    code=$(curl -sS -o "$tmp_body" -w '%{http_code}' \
                -X "${method}" \
                ${CURL_AUTH[@]+"${CURL_AUTH[@]}"} \
                "${BASE_URL}${path}" \
                "$@")
    cat "$tmp_body"
    rm -f "$tmp_body"
    if [[ "$code" -ne 200 && "$code" -ne 201 ]]; then
        echo "" >&2
        echo "❌ ${method} ${path} → HTTP ${code}" >&2
        exit 10
    fi
}

# Helper: log de etapa.
_step() {
    echo ""
    echo "▶ $1"
}

_pass() {
    echo "  ✓ $1"
}

# ─── Pré-flight ──────────────────────────────────────────────────────
echo "═══════════════════════════════════════════════════════════════"
echo "  AncoPlat smoke test — gate de release v1.0"
echo "  Base URL: ${BASE_URL}"
echo "  Auth: $([[ -n "${BASIC_USER}" ]] && echo "basic (${BASIC_USER})" || echo "none")"
echo "  Started: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "═══════════════════════════════════════════════════════════════"

if ! command -v jq &> /dev/null; then
    echo "❌ jq não encontrado no PATH. Instale jq antes de rodar." >&2
    exit 3
fi

# ─── 1. GET /api/v1/health ──────────────────────────────────────────
_step "1/7 GET /api/v1/health"
HEALTH=$(_curl GET /api/v1/health)
STATUS=$(echo "$HEALTH" | jq -r '.status // empty')
if [[ "$STATUS" != "ok" ]]; then
    echo "❌ /health status='$STATUS' (esperado 'ok')" >&2
    exit 11
fi
_pass "health.status=ok"

# ─── 2. GET /api/v1/line-types ──────────────────────────────────────
_step "2/7 GET /api/v1/line-types (catálogo legacy QMoor)"
LINE_TYPES=$(_curl GET /api/v1/line-types?limit=1000)
N_TYPES=$(echo "$LINE_TYPES" | jq '. | length')
if [[ "$N_TYPES" -lt 500 ]]; then
    echo "❌ /line-types retornou $N_TYPES entries (esperado ≥500)" >&2
    exit 12
fi
_pass "line-types: $N_TYPES entries (≥500)"

# ─── 3. POST /api/v1/cases (BC01_LIKE) ──────────────────────────────
_step "3/7 POST /api/v1/cases (BC01_LIKE)"
CASE_PAYLOAD='{
    "name": "smoke-prod-bc01",
    "description": "Smoke test prod — BC-01 like",
    "segments": [{
        "length": 450.0,
        "w": 201.10404,
        "EA": 3.425e7,
        "MBL": 3.78e6,
        "category": "Wire",
        "line_type": "IWRCEIPS"
    }],
    "boundary": {
        "h": 300.0,
        "mode": "Tension",
        "input_value": 785000.0,
        "startpoint_depth": 0.0,
        "endpoint_grounded": true
    },
    "seabed": {"mu": 0.0},
    "criteria_profile": "MVP_Preliminary"
}'
CASE_RESP=$(_curl POST /api/v1/cases \
    -H "Content-Type: application/json" \
    -d "$CASE_PAYLOAD")
CASE_ID=$(echo "$CASE_RESP" | jq -r '.id')
if [[ -z "$CASE_ID" || "$CASE_ID" == "null" ]]; then
    echo "❌ POST /cases não retornou id válido" >&2
    exit 13
fi
_pass "case criado id=$CASE_ID"

# ─── 4. POST /api/v1/cases/{id}/solve ───────────────────────────────
_step "4/7 POST /api/v1/cases/${CASE_ID}/solve"
SOLVE_RESP=$(_curl POST /api/v1/cases/${CASE_ID}/solve \
    -H "Content-Type: application/json")
SOLVE_STATUS=$(echo "$SOLVE_RESP" | jq -r '.result.status // empty')
ALERT_LEVEL=$(echo "$SOLVE_RESP" | jq -r '.result.alert_level // empty')
if [[ "$SOLVE_STATUS" != "converged" ]]; then
    echo "❌ /solve status='$SOLVE_STATUS' (esperado 'converged')" >&2
    exit 14
fi
_pass "solve: status=converged, alert=$ALERT_LEVEL"

# ─── 5. GET /api/v1/cases/{id}/export/memorial-pdf ──────────────────
_step "5/7 GET /api/v1/cases/${CASE_ID}/export/memorial-pdf"
PDF_TMP=$(mktemp /tmp/smoke_memorial.XXXXXX.pdf)
HTTP_CODE=$(curl -sS -o "$PDF_TMP" -w '%{http_code}' \
    ${CURL_AUTH[@]+"${CURL_AUTH[@]}"} \
    "${BASE_URL}/api/v1/cases/${CASE_ID}/export/memorial-pdf")
if [[ "$HTTP_CODE" -ne 200 ]]; then
    echo "❌ /export/memorial-pdf HTTP $HTTP_CODE" >&2
    rm -f "$PDF_TMP"
    exit 15
fi
PDF_SIZE=$(wc -c < "$PDF_TMP")
PDF_HEAD=$(head -c 4 "$PDF_TMP")
rm -f "$PDF_TMP"
if [[ "$PDF_HEAD" != "%PDF" ]]; then
    echo "❌ /memorial-pdf não retornou PDF válido (head='$PDF_HEAD')" >&2
    exit 15
fi
if [[ "$PDF_SIZE" -lt 5000 ]]; then
    echo "❌ /memorial-pdf retornou $PDF_SIZE bytes (esperado ≥5KB)" >&2
    exit 15
fi
_pass "memorial PDF: $PDF_SIZE bytes, header %PDF válido"

# ─── 6. POST /api/v1/import-moor (round-trip) ───────────────────────
_step "6/7 Round-trip .moor v2 (export → import)"
MOOR_TMP=$(mktemp /tmp/smoke_export.XXXXXX.moor)
HTTP_CODE=$(curl -sS -o "$MOOR_TMP" -w '%{http_code}' \
    ${CURL_AUTH[@]+"${CURL_AUTH[@]}"} \
    "${BASE_URL}/api/v1/cases/${CASE_ID}/export/moor")
if [[ "$HTTP_CODE" -ne 200 ]]; then
    echo "❌ /export/moor HTTP $HTTP_CODE" >&2
    rm -f "$MOOR_TMP"
    exit 16
fi

# Round-trip: importa o que acabamos de exportar.
IMPORT_RESP=$(curl -sS -X POST \
    ${CURL_AUTH[@]+"${CURL_AUTH[@]}"} \
    -F "file=@${MOOR_TMP}" \
    "${BASE_URL}/api/v1/import-moor")
rm -f "$MOOR_TMP"
IMPORTED_ID=$(echo "$IMPORT_RESP" | jq -r '.case.id // empty')
if [[ -z "$IMPORTED_ID" || "$IMPORTED_ID" == "null" ]]; then
    echo "❌ /import-moor não retornou case.id" >&2
    echo "   resposta: $IMPORT_RESP" >&2
    exit 16
fi
_pass "round-trip .moor v2: imported_id=$IMPORTED_ID"

# ─── 7. POST mooring-systems watchcircle (feature flagship) ─────────
# Cria mooring system simples (1 linha) e roda watchcircle leve
# (n_steps=8, magnitude pequena) para validar o caminho ProcessPool.
_step "7/7 POST /api/v1/mooring-systems/{id}/watchcircle (n_steps=8)"
MSYS_PAYLOAD='{
    "name": "smoke-prod-msys",
    "description": "Smoke test prod — single line msys",
    "platform_radius": 30.0,
    "lines": [{
        "name": "L1",
        "fairlead_azimuth_deg": 0.0,
        "fairlead_radius": 30.0,
        "segments": [{
            "length": 800.0,
            "w": 1100.0,
            "EA": 5.83e8,
            "MBL": 5.57e6
        }],
        "boundary": {
            "h": 300.0,
            "mode": "Tension",
            "input_value": 1200000.0,
            "startpoint_depth": 0.0,
            "endpoint_grounded": true
        },
        "seabed": {"mu": 0.6, "slope_rad": 0.0}
    }]
}'
MSYS_RESP=$(_curl POST /api/v1/mooring-systems \
    -H "Content-Type: application/json" \
    -d "$MSYS_PAYLOAD")
MSYS_ID=$(echo "$MSYS_RESP" | jq -r '.id')
if [[ -z "$MSYS_ID" || "$MSYS_ID" == "null" ]]; then
    echo "❌ POST /mooring-systems não retornou id" >&2
    exit 17
fi

WC_RESP=$(_curl POST /api/v1/mooring-systems/${MSYS_ID}/watchcircle \
    -H "Content-Type: application/json" \
    -d '{"magnitude_n": 100000.0, "n_steps": 8}')
WC_N_POINTS=$(echo "$WC_RESP" | jq -r '.points | length')
if [[ "$WC_N_POINTS" != "8" ]]; then
    echo "❌ watchcircle retornou $WC_N_POINTS pontos (esperado 8)" >&2
    exit 17
fi
_pass "watchcircle: 8 azimutes resolvidos"

# ─── Cleanup (deleta cases criados) ──────────────────────────────────
_step "Cleanup — deleta cases de teste"
curl -sS -X DELETE ${CURL_AUTH[@]+"${CURL_AUTH[@]}"} "${BASE_URL}/api/v1/cases/${CASE_ID}" > /dev/null || true
[[ -n "$IMPORTED_ID" && "$IMPORTED_ID" != "null" ]] && \
    curl -sS -X DELETE ${CURL_AUTH[@]+"${CURL_AUTH[@]}"} "${BASE_URL}/api/v1/cases/${IMPORTED_ID}" > /dev/null || true
curl -sS -X DELETE ${CURL_AUTH[@]+"${CURL_AUTH[@]}"} "${BASE_URL}/api/v1/mooring-systems/${MSYS_ID}" > /dev/null || true
_pass "cleanup OK"

# ─── Sumário ──────────────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  ✅ Smoke test PASSOU — 7/7 asserções"
echo "  Finished: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "Próximos gates de release (manuais):"
echo "  - Checklist UI (3 itens): abrir caso, ver plot, exportar PDF."
echo "  - 48h uptime: monitorar journalctl + healthcheck logs."
echo "  - Tag v1.0.0 + GitHub release."
echo ""
exit 0
