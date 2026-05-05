#!/usr/bin/env bash
# Wrapper para regenerar docs/audit/moorpy_baseline_<DATE>.json.
#
# Substitui o "make moorpy-baseline" mencionado em
# docs/plano_profissionalizacao.md (decisão Fase 0 / Q5 = shell script).
#
# Pré-condição: tools/moorpy_env/ configurado conforme README desta pasta.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="${HERE}/venv"
PY="${VENV}/bin/python"

if [[ ! -x "${PY}" ]]; then
    echo "venv não encontrado em ${VENV}" >&2
    echo "Siga ${HERE}/README.md para configurar o ambiente." >&2
    exit 1
fi

if [[ ! -d "${HERE}/MoorPy" ]]; then
    echo "MoorPy não clonado em ${HERE}/MoorPy" >&2
    echo "Siga ${HERE}/README.md para configurar o ambiente." >&2
    exit 1
fi

exec "${PY}" "${HERE}/regenerate_baseline.py"
