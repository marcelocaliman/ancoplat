#!/usr/bin/env bash
# Regenera o conjunto completo de baselines V&V v1.0 (Fase 10 / Commit 2).
#
# O catálogo VV-01..14 (ver docs/plano_profissionalizacao.md §10.3) consome
# três baselines distintos:
#
#   1. moorpy_baseline_<DATE>.json   — 10 cases catenária (Fase 1)
#                                       cobre VV-01..04 e parcial VV-05.
#   2. moorpy_uplift_baseline_<DATE>.json — 5 cases anchor uplift (Fase 7)
#                                       cobre VV-14.
#   3. (futuro) moorpy_subsystem_baseline.json — multi-segmento via
#                                       MoorPy Subsystem para VV-07/08.
#                                       NÃO regenerado aqui — atualmente
#                                       VV-07/08 usam cross-check interno
#                                       (conservação de L, balanço peso↔ΔV).
#
# Cobertura adicional sem dependência de MoorPy:
#   - VV-06 (slope mirror): test_vv_v1.py::test_VV_06_slope_mirror_symmetry
#   - VV-09..14 (manual): test_vv_v1.py::TestVV09a14 (Commit 3)
#
# Pré-condição: tools/moorpy_env/ configurado conforme README desta pasta.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==> 1/2 Regenerando baseline catenária (BC-MOORPY-01..10) →"
echo "        docs/audit/moorpy_baseline_<DATE>.json"
"${HERE}/regenerate_baseline.sh"

echo ""
echo "==> 2/2 Regenerando baseline anchor uplift (BC-UP-01..05) →"
echo "        docs/audit/moorpy_uplift_baseline_<DATE>.json"
VENV="${HERE}/venv"
PY="${VENV}/bin/python"
exec "${PY}" "${HERE}/regenerate_uplift_baseline.py"
