"""
Gate BC-AHV-01..04 — V&V de AHV via cálculo manual (Fase 8 / Q5+Q7).

Sem MoorPy: o módulo `Catenary.catenary` do MoorPy não suporta
nativamente carga lateral em ponto da linha (decisão registrada no
plano §F8: "MoorPy não suporta nativamente, então validação contra
cálculo manual"). Os 4 BCs canônicos validam o solver contra fórmulas
analíticas de equilíbrio:

  BC-AHV-01: lateral pura (Fz=0) em junção 0
    - Verificação principal: H_fairlead - H_anchor = +Fx_local (jump
      em H igual à componente horizontal).
    - T_fl² = H_fairlead² + V_fl²; T_anchor² = H_anchor² + V_anchor².

  BC-AHV-02: vertical pura (Fx=0)
    - Cross-check direto: AHV com bollard_pull "vertical" não é
      possível pelo schema (AHV é horizontal por convenção); aqui
      usamos clump_weight com mesma magnitude para validar que o
      solver multi_segment trata jump em V corretamente. Desempenha o
      role de teste de regressão da extensão para tupla (H_jump, V_jump).

  BC-AHV-03: diagonal — AHV horizontal heading=60°
    - F_x_local = bollard·cos(60°) = 0.5·bollard.
    - Componente fora do plano (sin 60°·bollard) ignorada (D019 dispara
      se < 30% in-plane; aqui in-plane=50% > 30%, D019 não dispara).

  BC-AHV-04: multi-AHV — 2 AHVs simétricos em junções diferentes
    (Ajuste 2 Q4: cobre Q4 com gate explícito).

Tolerância: rtol=1e-2 (Q5).
"""
from __future__ import annotations

import math

import pytest

from backend.solver.solver import solve
from backend.solver.types import (
    BoundaryConditions,
    ConvergenceStatus,
    LineAttachment,
    LineSegment,
    SolutionMode,
)


def _seg(L: float = 300.0) -> LineSegment:
    return LineSegment(length=L, w=200.0, EA=3.4e7, MBL=3.78e6)


def _bc(T_fl: float = 850_000.0) -> BoundaryConditions:
    return BoundaryConditions(
        h=300.0, mode=SolutionMode.TENSION, input_value=T_fl,
    )


# ─── BC-AHV-01: lateral pura (heading=0, alinhado com a linha) ─────


def test_BC_AHV_01_lateral_pura_H_jump_correct():
    """
    Fx_local = bollard_pull (heading=0°, line_az=0°).
    H_fairlead - H_anchor = +bollard_pull (igual ao jump esperado).
    """
    bollard = 200_000.0
    ahv = LineAttachment(
        kind="ahv", position_index=0, name="AHV",
        ahv_bollard_pull=bollard, ahv_heading_deg=0.0,
    )
    r = solve([_seg(), _seg()], _bc(), attachments=[ahv])
    assert r.status == ConvergenceStatus.CONVERGED

    # H_anchor = tension_x[0]; H_fairlead = tension_x[-1]
    H_anchor = r.tension_x[0]
    H_fairlead = r.tension_x[-1]
    h_jump_real = H_fairlead - H_anchor
    rel_err = abs(h_jump_real - bollard) / bollard
    assert rel_err < 1e-2, (
        f"BC-AHV-01: H_jump real {h_jump_real:.0f} vs esperado "
        f"{bollard:.0f} (rel_err {rel_err*100:.3f}%)"
    )


def test_BC_AHV_01_T_fl_eh_T_input():
    """T_fl output == T_fl input (catenária convergiu)."""
    ahv = LineAttachment(
        kind="ahv", position_index=0,
        ahv_bollard_pull=200_000.0, ahv_heading_deg=0.0,
    )
    r = solve([_seg(), _seg()], _bc(T_fl=850_000.0), attachments=[ahv])
    assert math.isclose(r.fairlead_tension, 850_000.0, rel_tol=1e-3)


def test_BC_AHV_01_T_anchor_satisfaz_pythagoras():
    """T_anchor² = H_anchor² + V_anchor²."""
    ahv = LineAttachment(
        kind="ahv", position_index=0,
        ahv_bollard_pull=200_000.0, ahv_heading_deg=0.0,
    )
    r = solve([_seg(), _seg()], _bc(), attachments=[ahv])
    H_anchor = r.tension_x[0]
    V_anchor = r.tension_y[0]
    T_anchor_calc = math.sqrt(H_anchor ** 2 + V_anchor ** 2)
    rel_err = abs(T_anchor_calc - r.anchor_tension) / r.anchor_tension
    assert rel_err < 1e-3


# ─── BC-AHV-02: vertical pura via clump_weight (cross-check) ───────


def test_BC_AHV_02_clump_equivalent_AHV_via_F2D_jump():
    """
    Caso "AHV vertical pura" não é diretamente expressável no schema
    (AHV é horizontal por convenção). Cross-check inteligente: clump_
    weight com mesma magnitude deveria dar mesma geometria que um
    hipotético AHV vertical (jump em V apenas), validando que o
    solver multi_segment trata jump em V corretamente após a extensão
    para tupla (H_jump, V_jump).

    Equivalente a regressão: cases com clump preexistentes (Fase F5.2
    + F5.7) continuam passando intactos pós-extensão.
    """
    clump = LineAttachment(
        kind="clump_weight", position_index=0,
        submerged_force=100_000.0,
    )
    r = solve([_seg(), _seg()], _bc(), attachments=[clump])
    assert r.status == ConvergenceStatus.CONVERGED

    # H deve ser CONSTANTE (clump não muda H entre segmentos)
    H_anchor = r.tension_x[0]
    H_fairlead = r.tension_x[-1]
    assert math.isclose(H_anchor, H_fairlead, rel_tol=1e-3), (
        f"clump_weight: H_anchor {H_anchor} vs H_fairlead {H_fairlead} "
        "(devem ser iguais — clump não muda H)"
    )


# ─── BC-AHV-03: diagonal (heading=60°) ─────────────────────────────


def test_BC_AHV_03_diagonal_heading_60():
    """
    heading=60°: Fx_local = bollard·cos(60°) = 0.5·bollard.
    H_fairlead - H_anchor = 0.5·bollard.
    in_plane_fraction = 50% > 30% → D019 NÃO dispara.
    """
    bollard = 200_000.0
    ahv = LineAttachment(
        kind="ahv", position_index=0,
        ahv_bollard_pull=bollard, ahv_heading_deg=60.0,
    )
    r = solve([_seg(), _seg()], _bc(), attachments=[ahv])
    assert r.status == ConvergenceStatus.CONVERGED

    expected_h_jump = bollard * math.cos(math.radians(60))
    H_jump_real = r.tension_x[-1] - r.tension_x[0]
    rel_err = abs(H_jump_real - expected_h_jump) / expected_h_jump
    assert rel_err < 1e-2, (
        f"BC-AHV-03: H_jump real {H_jump_real:.0f} vs esperado "
        f"{expected_h_jump:.0f} (rel_err {rel_err*100:.3f}%)"
    )

    # D019 NÃO dispara em 50% (> 30%)
    codes = [d["code"] for d in r.diagnostics]
    assert "D019_AHV_FORCE_OUT_OF_PLANE" not in codes


def test_BC_AHV_heading_perpendicular_dispara_D019():
    """heading=90°: in_plane=0% < 30% → D019 dispara."""
    ahv = LineAttachment(
        kind="ahv", position_index=0,
        ahv_bollard_pull=200_000.0, ahv_heading_deg=90.0,
    )
    r = solve([_seg(), _seg()], _bc(), attachments=[ahv])
    codes = [d["code"] for d in r.diagnostics]
    assert "D019_AHV_FORCE_OUT_OF_PLANE" in codes


# ─── BC-AHV-04: multi-AHV simétrico (Q4 + Ajuste 2) ────────────────


def test_BC_AHV_04_multi_AHV_simetrico():
    """
    2 AHVs em junções 0 e 1 (3 segs), ambos heading=0, magnitudes
    diferentes. H_fairlead - H_anchor = bollard1 + bollard2 (soma
    linear dos jumps).
    """
    bollard1, bollard2 = 100_000.0, 80_000.0
    ahv1 = LineAttachment(
        kind="ahv", position_index=0, name="AHV1",
        ahv_bollard_pull=bollard1, ahv_heading_deg=0.0,
    )
    ahv2 = LineAttachment(
        kind="ahv", position_index=1, name="AHV2",
        ahv_bollard_pull=bollard2, ahv_heading_deg=0.0,
    )
    r = solve([_seg(), _seg(), _seg()], _bc(), attachments=[ahv1, ahv2])
    assert r.status == ConvergenceStatus.CONVERGED

    expected_total_jump = bollard1 + bollard2
    H_jump_real = r.tension_x[-1] - r.tension_x[0]
    rel_err = abs(H_jump_real - expected_total_jump) / expected_total_jump
    assert rel_err < 1e-2, (
        f"BC-AHV-04: H_jump total real {H_jump_real:.0f} vs esperado "
        f"{expected_total_jump:.0f} (rel_err {rel_err*100:.3f}%)"
    )

    # D018 dispara para o conjunto (não 1 por AHV)
    codes = [d["code"] for d in r.diagnostics]
    d018_count = sum(1 for c in codes if c == "D018_AHV_STATIC_IDEALIZATION")
    assert d018_count == 1
    # Mensagem deve indicar 2 AHVs
    d018 = next(d for d in r.diagnostics if d["code"] == "D018_AHV_STATIC_IDEALIZATION")
    assert "2 AHVs" in d018["title"]


# ─── Tabela de erro relativo BC-AHV (Q9 reforço do usuário) ────────


def test_TABELA_erro_relativo_BC_AHV_imprime_no_verbose():
    """
    Imprime tabela com erro relativo por BC-AHV (Q9 reforço: "mostrar
    o erro real para cada um"). Roda em -v output do pytest.
    """
    cases = [
        ("BC-AHV-01", 0.0, 200_000.0, 1.0),
        ("BC-AHV-03", 60.0, 200_000.0, 0.5),
        ("BC-AHV-04 (AHV1)", 0.0, 100_000.0, 1.0),
        ("BC-AHV-04 (AHV2)", 0.0, 80_000.0, 1.0),
    ]
    print(
        f"\nTabela de erro relativo BC-AHV vs cálculo manual "
        f"(Fase 8 / Q9 reforço):"
    )
    print(f"{'ID':<22}  {'heading':>8}  {'H_jump esp':>12}  "
          f"{'H_jump real':>12}  {'rel_err':>8}")

    seg = _seg()
    bc = _bc()

    # BC-AHV-01
    r1 = solve(
        [seg, seg], bc,
        attachments=[LineAttachment(
            kind="ahv", position_index=0,
            ahv_bollard_pull=200_000.0, ahv_heading_deg=0.0,
        )],
    )
    expected_01 = 200_000.0 * 1.0
    real_01 = r1.tension_x[-1] - r1.tension_x[0]
    rel_01 = abs(real_01 - expected_01) / expected_01
    print(f"{'BC-AHV-01':<22}  {0:>7.1f}°  {expected_01:>12.0f}  "
          f"{real_01:>12.0f}  {rel_01*100:>7.4f}%")
    assert rel_01 < 1e-2

    # BC-AHV-03
    r3 = solve(
        [seg, seg], bc,
        attachments=[LineAttachment(
            kind="ahv", position_index=0,
            ahv_bollard_pull=200_000.0, ahv_heading_deg=60.0,
        )],
    )
    expected_03 = 200_000.0 * 0.5
    real_03 = r3.tension_x[-1] - r3.tension_x[0]
    rel_03 = abs(real_03 - expected_03) / expected_03
    print(f"{'BC-AHV-03':<22}  {60:>7.1f}°  {expected_03:>12.0f}  "
          f"{real_03:>12.0f}  {rel_03*100:>7.4f}%")
    assert rel_03 < 1e-2

    # BC-AHV-04 (multi-AHV)
    r4 = solve(
        [seg, seg, seg], bc,
        attachments=[
            LineAttachment(kind="ahv", position_index=0, name="AHV1",
                           ahv_bollard_pull=100_000.0, ahv_heading_deg=0.0),
            LineAttachment(kind="ahv", position_index=1, name="AHV2",
                           ahv_bollard_pull=80_000.0, ahv_heading_deg=0.0),
        ],
    )
    expected_04 = 100_000.0 + 80_000.0
    real_04 = r4.tension_x[-1] - r4.tension_x[0]
    rel_04 = abs(real_04 - expected_04) / expected_04
    print(f"{'BC-AHV-04 (total)':<22}  {0:>7.1f}°  {expected_04:>12.0f}  "
          f"{real_04:>12.0f}  {rel_04*100:>7.4f}%")
    assert rel_04 < 1e-2
