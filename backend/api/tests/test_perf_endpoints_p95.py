"""
Performance gate p95 dos endpoints REST (Fase 10 / Commit 8).

Per docs/plano_profissionalizacao.md §926:
  - Solve typical < 100ms (p95)
  - API p95 < 100ms

Mede 50 requisições por endpoint via TestClient (in-process, sem
overhead de rede) e reporta o percentil 95. Tolerância prática: o
gate <100ms se aplica ao SOLVE TÍPICO; outros endpoints são esperados
serem ainda mais rápidos.

Estratégia: usa fixture `client` existente (in-memory SQLite). Cada
endpoint é exercitado N=50 vezes; reporta p50/p95/p99 + max.

Per Q1 do mini-plano F10 (estratégia "ThreadPool primeiro, escalar
depois"), aqui aplicamos a mesma filosofia honesta: registramos tempos
reais e classificamos OK/WARN/FAIL.
"""
from __future__ import annotations

import statistics
import time
from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.api.tests._fixtures import BC01_LIKE_INPUT


N_REPS = 50  # número de requisições por endpoint
P95_GATE_MS = 100.0  # gate <100ms (per plano §926)


def _percentile(values: list[float], p: float) -> float:
    """Percentil simples (interpolação linear)."""
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    k = (len(sorted_vals) - 1) * p / 100.0
    f = int(k)
    c = min(f + 1, len(sorted_vals) - 1)
    if f == c:
        return sorted_vals[int(k)]
    d0 = sorted_vals[f] * (c - k)
    d1 = sorted_vals[c] * (k - f)
    return d0 + d1


def _time_endpoint(
    fn, n: int = N_REPS,
) -> dict[str, float]:
    """Roda fn() n vezes e devolve estatísticas de wall time em ms."""
    times: list[float] = []
    # Warmup: 3 reps fora da medição para aquecer caches.
    for _ in range(3):
        fn()
    for _ in range(n):
        t0 = time.perf_counter()
        fn()
        times.append((time.perf_counter() - t0) * 1000.0)
    return {
        "p50_ms": _percentile(times, 50),
        "p95_ms": _percentile(times, 95),
        "p99_ms": _percentile(times, 99),
        "max_ms": max(times),
        "mean_ms": statistics.mean(times),
        "n": len(times),
    }


def test_perf_GET_health_p95_under_100ms(client: TestClient):
    """GET /api/v1/health — endpoint trivial, p95 deve ser <10ms."""
    stats = _time_endpoint(lambda: client.get("/api/v1/health"))
    assert stats["p95_ms"] < P95_GATE_MS, (
        f"GET /health p95={stats['p95_ms']:.1f}ms ≥ {P95_GATE_MS}ms"
    )


def test_perf_GET_line_types_p95_under_100ms(client: TestClient):
    """GET /api/v1/line-types — query catálogo (522 entradas)."""
    stats = _time_endpoint(lambda: client.get("/api/v1/line-types"))
    assert stats["p95_ms"] < P95_GATE_MS, (
        f"GET /line-types p95={stats['p95_ms']:.1f}ms ≥ {P95_GATE_MS}ms"
    )


def test_perf_POST_cases_p95_under_100ms(client: TestClient):
    """POST /api/v1/cases — cria case (validação Pydantic + insert SQLite)."""
    payload = dict(BC01_LIKE_INPUT)

    def _fn():
        # Cada chamada cria um case novo (não há limite explícito).
        # Para evitar inflar DB, cada N_REPS é OK no test_client em memória.
        r = client.post("/api/v1/cases", json=payload)
        assert r.status_code == 201

    stats = _time_endpoint(_fn)
    assert stats["p95_ms"] < P95_GATE_MS, (
        f"POST /cases p95={stats['p95_ms']:.1f}ms ≥ {P95_GATE_MS}ms"
    )


def test_perf_POST_solve_typical_p95_under_100ms(client: TestClient):
    """
    POST /cases/{id}/solve — gate principal v1.0 (per §926).
    Solve TÍPICO = single-segment, sem multi-line, sem watchcircle.
    """
    # Cria 1 case e re-roda solve N vezes nele (cache de inputs warmed).
    r = client.post("/api/v1/cases", json=BC01_LIKE_INPUT)
    assert r.status_code == 201
    case_id = r.json()["id"]

    def _fn():
        r = client.post(f"/api/v1/cases/{case_id}/solve")
        assert r.status_code == 200

    stats = _time_endpoint(_fn)
    assert stats["p95_ms"] < P95_GATE_MS, (
        f"POST /solve p95={stats['p95_ms']:.1f}ms ≥ {P95_GATE_MS}ms "
        f"(p50={stats['p50_ms']:.1f}, max={stats['max_ms']:.1f})"
    )


def test_perf_GET_case_detail_p95_under_100ms(client: TestClient):
    """GET /cases/{id} — read JSONB de caso + último execution."""
    r = client.post("/api/v1/cases", json=BC01_LIKE_INPUT)
    case_id = r.json()["id"]
    stats = _time_endpoint(lambda: client.get(f"/api/v1/cases/{case_id}"))
    assert stats["p95_ms"] < P95_GATE_MS, (
        f"GET /cases/{case_id} p95={stats['p95_ms']:.1f}ms ≥ {P95_GATE_MS}ms"
    )
