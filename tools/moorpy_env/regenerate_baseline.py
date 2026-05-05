"""
Regenera o baseline numérico do MoorPy para os 10 catenary cases
parametrizados em MoorPy/tests/test_catenary.py.

Estes 10 cases viram o gate `BC-MOORPY-01..10` na Fase 1 do plano de
profissionalização (ver docs/plano_profissionalizacao.md).

Princípio (alinhado com a decisão do usuário no protocolo de Fase 0):
    Importa `indata` e `desired` DIRETAMENTE do arquivo
    `MoorPy/tests/test_catenary.py` em vez de transcrever os literais.
    Assim, se o MoorPy atualizar `test_catenary.py`, basta rodar este
    script de novo para regenerar o baseline.

Saída:
    docs/audit/moorpy_baseline_<DATE>.json — array de 10 entradas
    com inputs, outputs canônicos (fAH, fAV, fBH, fBV, LBot),
    ProfileType, e o `desired` array do upstream para auditoria
    cruzada.

Uso:
    venv/bin/python regenerate_baseline.py
"""
from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


HERE = Path(__file__).resolve().parent
MOORPY_DIR = HERE / "MoorPy"
TEST_FILE = MOORPY_DIR / "tests" / "test_catenary.py"
COMMIT_FILE = HERE / "moorpy_commit.txt"

REPO_ROOT = HERE.parent.parent  # tools/moorpy_env/ -> tools/ -> repo root


def _load_test_module():
    """Importa test_catenary.py por path para acessar `indata` e `desired`."""
    if not TEST_FILE.exists():
        sys.exit(
            f"MoorPy não encontrado em {TEST_FILE}.\n"
            "Rode primeiro: bash tools/moorpy_env/regenerate_baseline.sh "
            "(ou siga o README para clonar o MoorPy)."
        )
    spec = importlib.util.spec_from_file_location("moorpy_test_catenary", TEST_FILE)
    if spec is None or spec.loader is None:
        sys.exit(f"Falha ao montar spec do módulo {TEST_FILE}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _moorpy_commit() -> str:
    if COMMIT_FILE.exists():
        return COMMIT_FILE.read_text(encoding="utf-8").strip()
    return "unknown"


def _to_python(obj):
    """Converte numpy types para tipos Python serializáveis."""
    try:
        import numpy as np
    except ImportError:
        return obj
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.integer):
        return int(obj)
    return obj


def main() -> None:
    test_module = _load_test_module()
    indata = test_module.indata
    desired = test_module.desired

    if len(indata) != len(desired):
        sys.exit(f"indata({len(indata)}) != desired({len(desired)}) — incoerência")

    from moorpy.Catenary import catenary  # type: ignore

    cases: list[dict] = []
    for i, (ins, des) in enumerate(zip(indata, desired)):
        # ins = [x, z, L, EA, w, CB, HF0, VF0]
        x, z, L, EA, w, CB, HF0, VF0 = ins
        fAH, fAV, fBH, fBV, info = catenary(
            x, z, L, EA, w,
            CB=CB, HF0=HF0, VF0=VF0,
            Tol=1e-4, MaxIter=50, plots=0,
        )
        case = {
            "case_id": f"BC-MOORPY-{i + 1:02d}",
            "source_index": i,
            "inputs": {
                "x": float(x),
                "z": float(z),
                "L": float(L),
                "EA": float(EA),
                "w": float(w),
                "CB": float(CB),
                "HF0": float(HF0),
                "VF0": float(VF0),
            },
            "outputs": {
                "fAH": _to_python(fAH),
                "fAV": _to_python(fAV),
                "fBH": _to_python(fBH),
                "fBV": _to_python(fBV),
                "LBot": _to_python(info["LBot"]),
                "ProfileType": int(info["ProfileType"]),
                "HF": _to_python(info["HF"]),
                "VF": _to_python(info["VF"]),
                "HA": _to_python(info["HA"]),
                "VA": _to_python(info["VA"]),
            },
            "desired_upstream": [float(v) for v in des],
        }
        cases.append(case)

    payload = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "moorpy_commit": _moorpy_commit(),
        "moorpy_source": "https://github.com/NREL/MoorPy",
        "test_source_file": "tests/test_catenary.py",
        "tolerance_used_in_catenary": 1e-4,
        "n_cases": len(cases),
        "cases": cases,
    }

    date_str = datetime.now().strftime("%Y-%m-%d")
    out_path = REPO_ROOT / f"docs/audit/moorpy_baseline_{date_str}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"OK — {out_path}")
    print(f"    {len(cases)} casos · MoorPy commit {payload['moorpy_commit'][:8]}")


if __name__ == "__main__":
    main()
