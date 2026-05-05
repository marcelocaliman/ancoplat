"""
Dump dos cases + execuções + mooring systems do SQLite local em JSON
estruturado, para uso como teste de regressão nas próximas fases do
plano de profissionalização.

Uso:
    python tools/dump_cases_baseline.py [DB_PATH] [OUTPUT_PATH]

Defaults:
    DB_PATH      = backend/data/ancoplat.db
    OUTPUT_PATH  = docs/audit/cases_baseline_<DATE>.json

Comportamento:
    1. Abre SQLite em modo somente-leitura.
    2. Para cada caso: extrai input_json + última execução (se houver).
    3. Para cada mooring system: extrai config_json + última execução.
    4. Serializa em JSON com keys ordenadas, indent=2.
    5. Se DB estiver vazio (cases=0 E mooring_systems=0), aborta com
       mensagem orientadora — sem produzir JSON inútil.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path


def _row_to_dict(cursor: sqlite3.Cursor, row: tuple) -> dict:
    return {col[0]: row[i] for i, col in enumerate(cursor.description)}


def _decode_json_field(value: str | None) -> dict | None:
    if value is None:
        return None
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return {"_raw": value, "_decode_error": True}


def dump_baseline(db_path: Path, output_path: Path) -> dict:
    if not db_path.exists():
        raise SystemExit(f"DB não encontrado: {db_path}")

    uri = f"file:{db_path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Cases + última execução. Materializa a outer query em list ANTES
    # de fazer queries internas — sqlite3 Python clobra o iterador se
    # o mesmo cursor for reusado.
    cases_out: list[dict] = []
    case_rows = cur.execute("SELECT * FROM cases ORDER BY id").fetchall()
    for case_row in case_rows:
        case = dict(case_row)
        case["input_json"] = _decode_json_field(case["input_json"])

        last_exec_row = cur.execute(
            "SELECT * FROM executions WHERE case_id = ? "
            "ORDER BY executed_at DESC LIMIT 1",
            (case["id"],),
        ).fetchone()
        if last_exec_row is not None:
            last_exec = dict(last_exec_row)
            last_exec["result_json"] = _decode_json_field(last_exec["result_json"])
            case["latest_execution"] = last_exec
            case["execution_count"] = cur.execute(
                "SELECT COUNT(*) FROM executions WHERE case_id = ?",
                (case["id"],),
            ).fetchone()[0]
        else:
            case["latest_execution"] = None
            case["execution_count"] = 0
        cases_out.append(case)

    # Mooring systems + última execução
    systems_out: list[dict] = []
    system_rows = cur.execute("SELECT * FROM mooring_systems ORDER BY id").fetchall()
    for sys_row in system_rows:
        system = dict(sys_row)
        system["config_json"] = _decode_json_field(system["config_json"])

        last_exec_row = cur.execute(
            "SELECT * FROM mooring_system_executions WHERE mooring_system_id = ? "
            "ORDER BY executed_at DESC LIMIT 1",
            (system["id"],),
        ).fetchone()
        if last_exec_row is not None:
            last_exec = dict(last_exec_row)
            last_exec["result_json"] = _decode_json_field(last_exec["result_json"])
            system["latest_execution"] = last_exec
            system["execution_count"] = cur.execute(
                "SELECT COUNT(*) FROM mooring_system_executions WHERE mooring_system_id = ?",
                (system["id"],),
            ).fetchone()[0]
        else:
            system["latest_execution"] = None
            system["execution_count"] = 0
        systems_out.append(system)

    # Sanidade — não escrever JSON vazio
    if not cases_out and not systems_out:
        raise SystemExit(
            "DB local não tem cases nem mooring systems. "
            "Não vou criar JSON vazio. Confirme com a fonte de produção "
            "antes de seguir."
        )

    payload = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_db": str(db_path),
        "counts": {
            "cases": len(cases_out),
            "executions_total": sum(c["execution_count"] for c in cases_out),
            "mooring_systems": len(systems_out),
            "mooring_system_executions_total": sum(
                s["execution_count"] for s in systems_out
            ),
        },
        "cases": cases_out,
        "mooring_systems": systems_out,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    return payload["counts"]


def main() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    db_path = Path(sys.argv[1]) if len(sys.argv) > 1 else repo_root / "backend/data/ancoplat.db"
    if len(sys.argv) > 2:
        output_path = Path(sys.argv[2])
    else:
        date_str = datetime.now().strftime("%Y-%m-%d")
        output_path = repo_root / f"docs/audit/cases_baseline_{date_str}.json"

    counts = dump_baseline(db_path, output_path)
    print(f"OK — {output_path}")
    for k, v in counts.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
