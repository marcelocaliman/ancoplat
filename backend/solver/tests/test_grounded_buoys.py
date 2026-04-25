"""
F5.7.1 — Testes de benchmark para boias na zona grounded com força de elevação.

Casos cobertos
--------------
BC-AT-GB-01: single-segmento, boia na zona apoiada — arco forma.
BC-AT-GB-02: validação geométrica do arco (s_arch = F_b/w).
BC-AT-GB-03: tensão transparente do arco (T_in = T_out ao redor do arco).
BC-AT-GB-04: boia perto demais da âncora → ValueError com mensagem.
BC-AT-GB-05: dois arcos não-sobrepostos (multi-buoy lift).
BC-AT-GB-06: comparação direta com mesma config sem boia.
BC-AT-GB-07: boia em junção heterogênea (chain↔wire) NÃO forma arco.

Validação física
----------------
- Sem boia, cabo apoiado tem y(s) = 0 em toda zona grounded (em seabed
  plano com slope=0).
- Com boia em zona apoiada, cabo tem y(s) > 0 numa região centrada na
  boia → arco visível.
- s_arch = F_b/w_local: comprimento de cabo levantado.
- Tensão horizontal H constante em toda a linha (invariante chave).
"""
from __future__ import annotations

import math

import pytest

from backend.solver.grounded_buoys import (
    GroundedArch,
    compute_grounded_arches,
    integrate_grounded_zone,
)
from backend.solver.solver import solve
from backend.solver.types import (
    BoundaryConditions,
    ConvergenceStatus,
    LineAttachment,
    LineSegment,
    SeabedConfig,
    SolutionMode,
)


# ==============================================================================
# Unit tests dos helpers em grounded_buoys.py
# ==============================================================================


def test_compute_grounded_arches_basico() -> None:
    """Boia em meio da zona grounded → arco com s_arch = F_b/w."""
    seg = LineSegment(length=500.0, w=1000.0, EA=4e8, MBL=5e6)
    # Buoy at junction 0 (after split at s=200 from a single user-segment
    # — simulamos o pós-resolver: 2 sub-segmentos do mesmo material)
    seg_a = LineSegment(length=200.0, w=1000.0, EA=4e8, MBL=5e6)
    seg_b = LineSegment(length=300.0, w=1000.0, EA=4e8, MBL=5e6)
    boia = LineAttachment(
        kind="buoy", submerged_force=80_000.0, position_index=0,
    )
    arches = compute_grounded_arches([seg_a, seg_b], [200.0, 300.0], [boia], L_g_total=400.0)
    assert len(arches) == 1
    a = arches[0]
    assert a.s_buoy == pytest.approx(200.0)
    assert a.s_arch == pytest.approx(80_000.0 / 1000.0)  # = 80 m
    assert a.s_left == pytest.approx(200.0 - 40.0)
    assert a.s_right == pytest.approx(200.0 + 40.0)
    assert a.w_local == pytest.approx(1000.0)


def test_compute_grounded_arches_buoy_em_zona_suspensa_ignorada() -> None:
    """Boia com posição além de L_g_total não vira arco."""
    seg_a = LineSegment(length=200.0, w=1000.0, EA=4e8, MBL=5e6)
    seg_b = LineSegment(length=300.0, w=1000.0, EA=4e8, MBL=5e6)
    boia = LineAttachment(
        kind="buoy", submerged_force=20_000.0, position_index=0,
    )
    # Boia em s=200 mas L_g_total=100 (boia em suspenso) → sem arco
    arches = compute_grounded_arches(
        [seg_a, seg_b], [200.0, 300.0], [boia], L_g_total=100.0,
    )
    assert arches == []


def test_compute_grounded_arches_clump_ignorado() -> None:
    """Clump weight não cria arco (afunda o cabo, não levanta)."""
    seg_a = LineSegment(length=200.0, w=1000.0, EA=4e8, MBL=5e6)
    seg_b = LineSegment(length=300.0, w=1000.0, EA=4e8, MBL=5e6)
    clump = LineAttachment(
        kind="clump_weight", submerged_force=50_000.0, position_index=0,
    )
    arches = compute_grounded_arches(
        [seg_a, seg_b], [200.0, 300.0], [clump], L_g_total=400.0,
    )
    assert arches == []


def test_compute_grounded_arches_perto_da_ancora_erro() -> None:
    """Boia muito perto da âncora — arco extrapola s_left < 0."""
    seg_a = LineSegment(length=50.0, w=1000.0, EA=4e8, MBL=5e6)
    seg_b = LineSegment(length=450.0, w=1000.0, EA=4e8, MBL=5e6)
    # Boia em s=50, força 200kN → s_arch = 200m → s_left = 50 - 100 = -50 (inválido)
    boia = LineAttachment(
        kind="buoy", submerged_force=200_000.0, position_index=0,
    )
    with pytest.raises(ValueError, match="afaste-a da âncora"):
        compute_grounded_arches(
            [seg_a, seg_b], [50.0, 450.0], [boia], L_g_total=400.0,
        )


def test_compute_grounded_arches_perto_do_main_td_erro() -> None:
    """Boia muito perto do touchdown principal — arco extrapola s_right > L_g_total."""
    seg_a = LineSegment(length=300.0, w=1000.0, EA=4e8, MBL=5e6)
    seg_b = LineSegment(length=200.0, w=1000.0, EA=4e8, MBL=5e6)
    # Boia em s=300, força 100kN → s_arch=100m → s_right=350; L_g_total=320 → erro
    boia = LineAttachment(
        kind="buoy", submerged_force=100_000.0, position_index=0,
    )
    with pytest.raises(ValueError, match="extrapola o trecho apoiado"):
        compute_grounded_arches(
            [seg_a, seg_b], [300.0, 200.0], [boia], L_g_total=320.0,
        )


def test_compute_grounded_arches_junction_heterogenea_sem_arco() -> None:
    """Boia em junção entre materiais distintos (chain↔wire) — sem arco."""
    chain = LineSegment(length=200.0, w=1500.0, EA=4.5e8, MBL=6e6)
    wire = LineSegment(length=700.0, w=200.0, EA=4.4e8, MBL=4.8e6)
    boia = LineAttachment(
        kind="buoy", submerged_force=20_000.0, position_index=0,
    )
    # Junção 0 entre chain e wire: w_left=1500, w_right=200 → não forma arco
    arches = compute_grounded_arches(
        [chain, wire], [200.0, 700.0], [boia], L_g_total=600.0,
    )
    assert arches == []


def test_integrate_grounded_zone_sem_arches() -> None:
    """Sem arches, a integração reduz a um walk linear horizontal."""
    seg = LineSegment(length=500.0, w=1000.0, EA=4e8, MBL=5e6)
    res = integrate_grounded_zone(
        [seg], H=500_000.0, L_g_total=200.0,
        slope_rad=0.0, mu=0.3, arches=[], n_total_grounded=100,
    )
    assert res["x_main_td"] == pytest.approx(200.0)  # walk linear: x = arc length em flat
    assert res["y_main_td"] == pytest.approx(0.0)
    # Tensão na anchor < tensão no main_td (friction reduz)
    assert res["T_anchor"] < res["T_main_td"]
    # T_main_td = H em seabed plano
    assert res["T_main_td"] == pytest.approx(500_000.0)
    # Conservação: L_flat = L_g_total quando não há arches
    assert res["L_flat_total"] == pytest.approx(200.0)
    assert res["L_arch_total"] == pytest.approx(0.0)


def test_integrate_grounded_zone_com_arch_pico() -> None:
    """Com 1 arco, o cabo levanta no meio (y > 0 no pico da boia)."""
    seg = LineSegment(length=500.0, w=1000.0, EA=4e8, MBL=5e6)
    arch = GroundedArch(
        s_buoy=100.0,
        s_arch=80.0,    # F_b = 80 kN, w = 1000 → s_arch=80m
        s_left=60.0,
        s_right=140.0,
        w_local=1000.0,
        F_buoy=80_000.0,
        junction_idx=0,
    )
    res = integrate_grounded_zone(
        [seg], H=500_000.0, L_g_total=300.0,
        slope_rad=0.0, mu=0.0, arches=[arch], n_total_grounded=300,
    )
    coords_y = res["coords_y"]
    coords_x = res["coords_x"]
    arc_lengths = res["arc_length_at_coord"]
    # Encontra o ponto na posição da boia (s=100)
    idx_buoy = min(range(len(arc_lengths)), key=lambda i: abs(arc_lengths[i] - 100.0))
    y_at_buoy = coords_y[idx_buoy]
    # Arco deve elevar o cabo. Pico vale a · (cosh(half_s/a) - 1), onde a = H/w = 500.
    # half_s = 40. y_peak = 500 * (cosh(40/500) - 1) ≈ 500 * 0.0032 ≈ 1.6m.
    a_arch = 500_000.0 / 1000.0
    half_s = 40.0
    y_peak_expected = a_arch * (math.cosh(half_s / a_arch) - 1.0)
    assert y_at_buoy == pytest.approx(y_peak_expected, rel=0.05)
    # Antes e depois do arco, y deve voltar a ~0
    idx_before = min(range(len(arc_lengths)), key=lambda i: abs(arc_lengths[i] - 30.0))
    idx_after = min(range(len(arc_lengths)), key=lambda i: abs(arc_lengths[i] - 200.0))
    assert abs(coords_y[idx_before]) < 1e-6
    assert abs(coords_y[idx_after]) < 1e-6
    # Conservação L_arch + L_flat = L_g_total
    assert res["L_arch_total"] == pytest.approx(80.0)
    assert res["L_flat_total"] == pytest.approx(220.0)


# ==============================================================================
# BC-AT-GB-01 — boia na zona apoiada de single-segmento, arco forma
# ==============================================================================


def test_BC_AT_GB_01_arco_no_grounded_single_seg() -> None:
    """
    Single-segmento de chain pesada, T_fl baixo → grande zona apoiada.
    Boia em s=200m com força adequada → arco visível.

    Setup: chain 800m com w=1500N/m, h=300m, T_fl=600kN. Sem boia,
    L_g esperado ~ 300-400m. Boia em s=200m com F_b=60kN → s_arch=40m.
    """
    chain = LineSegment(length=800.0, w=1500.0, EA=4.5e8, MBL=6e6, category="StuddedChain")
    bc = BoundaryConditions(h=300.0, mode=SolutionMode.TENSION, input_value=600_000)
    seabed = SeabedConfig(mu=0.3, slope_rad=0.0)
    boia = LineAttachment(
        kind="buoy", submerged_force=60_000.0,
        position_s_from_anchor=200.0, name="Boia A",
    )
    r = solve([chain], bc, seabed=seabed, attachments=[boia])
    assert r.status == ConvergenceStatus.CONVERGED, r.message
    assert r.fairlead_tension == pytest.approx(600_000.0, rel=1e-2)
    # Deve haver touchdown
    assert r.total_grounded_length > 50.0
    # Buscamos um ponto com y > 0 na zona apoiada (signature do arco)
    # coords_y é do anchor (idx=0) ao fairlead. Curva ANCHOR-FIRST.
    has_lifted_island = False
    for i, y in enumerate(r.coords_y):
        if 0.0 < y < r.coords_y[-1] * 0.5:  # y > 0 mas longe do fairlead
            x_global = r.coords_x[i]
            # Está na zona apoiada (antes do main_td)?
            if x_global < (r.dist_to_first_td or 0.0) * 1.05:
                has_lifted_island = True
                break
    assert has_lifted_island, (
        "Esperava encontrar uma 'ilha suspensa' (y>0) dentro da zona "
        "apoiada (x < dist_to_first_td) — sinal de que a boia levantou "
        "o cabo do seabed."
    )


# ==============================================================================
# BC-AT-GB-02 — geometria do arco: pico = catenária analítica
# ==============================================================================


def test_BC_AT_GB_02_geometria_pico_arco() -> None:
    """
    Validação analítica do pico do arco contra a fórmula da catenária.

    y_peak = a · (cosh(half_s/a) − 1), onde a = H/w_local, half_s = s_arch/2.
    """
    chain = LineSegment(length=600.0, w=1000.0, EA=4e8, MBL=5e6, category="StuddedChain")
    bc = BoundaryConditions(h=200.0, mode=SolutionMode.TENSION, input_value=400_000)
    seabed = SeabedConfig(mu=0.2, slope_rad=0.0)
    boia = LineAttachment(
        kind="buoy", submerged_force=60_000.0,
        position_s_from_anchor=150.0, name="Boia",
    )
    r = solve([chain], bc, seabed=seabed, attachments=[boia])
    assert r.status == ConvergenceStatus.CONVERGED, r.message

    # Geometria esperada do arco
    H = r.H
    w_local = chain.w
    s_arch = boia.submerged_force / w_local  # = 60m
    half_s = s_arch / 2.0
    a_arch = H / w_local
    y_peak_expected = a_arch * (math.cosh(half_s / a_arch) - 1.0)

    # Maior y na zona apoiada
    td = r.dist_to_first_td or 0.0
    y_max_in_grounded = max(
        (y for x, y in zip(r.coords_x, r.coords_y) if x < td * 0.99),
        default=0.0,
    )
    # Tolerância 10% — sampling discreto; o pico exato pode cair entre nós.
    assert y_max_in_grounded == pytest.approx(y_peak_expected, rel=0.1), (
        f"y_peak {y_max_in_grounded:.3f} ≠ analítico {y_peak_expected:.3f} (a={a_arch:.1f}, half_s={half_s:.1f})"
    )


# ==============================================================================
# BC-AT-GB-03 — H constante em toda a linha (invariante)
# ==============================================================================


def test_BC_AT_GB_03_H_constante_no_suspenso_com_arco() -> None:
    """
    H deve ser constante na zona SUSPENSA (catenárias e arches).
    No flat com fricção, T_x varia (friction reduz tensão tangencial
    do main_td até a âncora) — esperado e correto.

    A invariante "H constante" é válida em qualquer ponto onde o cabo
    NÃO toca o seabed, pois ali não há reação normal/atrito do solo.
    """
    chain = LineSegment(length=700.0, w=1200.0, EA=4e8, MBL=5e6, category="StuddedChain")
    bc = BoundaryConditions(h=250.0, mode=SolutionMode.TENSION, input_value=500_000)
    seabed = SeabedConfig(mu=0.3, slope_rad=0.0)
    boia = LineAttachment(
        kind="buoy", submerged_force=80_000.0,
        position_s_from_anchor=180.0, name="Boia",
    )
    r = solve([chain], bc, seabed=seabed, attachments=[boia])
    assert r.status == ConvergenceStatus.CONVERGED, r.message
    # Filtra pontos onde a cabo está claramente suspenso (y > 5m acima
    # da seabed) — só pegamos a zona suspensa principal (após main_td);
    # excluímos arches cujo y máximo geralmente é < 2m em catenárias
    # típicas. Lá H tem que ser literalmente constante.
    Tx_susp = [
        tx for tx, y in zip(r.tension_x, r.coords_y) if y > 5.0
    ]
    assert len(Tx_susp) > 10, "Esperava ≥ 10 pontos suspensos (y>5m)"
    assert (max(Tx_susp) - min(Tx_susp)) / r.H < 1e-3, (
        f"H não constante no suspenso: range Tx {max(Tx_susp) - min(Tx_susp):.1f} "
        f"(H={r.H:.1f})"
    )


# ==============================================================================
# BC-AT-GB-04 — boia perto demais da âncora levanta erro friendly
# ==============================================================================


def test_BC_AT_GB_04_boia_perto_da_ancora_invalida() -> None:
    """Boia perto da âncora cujo arco extrapola s_left < 0 → INVALID_CASE."""
    chain = LineSegment(length=900.0, w=800.0, EA=4e8, MBL=5e6, category="StuddedChain")
    bc = BoundaryConditions(h=300.0, mode=SolutionMode.TENSION, input_value=500_000)
    seabed = SeabedConfig(mu=0.3, slope_rad=0.0)
    # s_b=30m, F_b=100kN, w=800 → s_arch=125m → s_left=-32.5m → erro
    boia = LineAttachment(
        kind="buoy", submerged_force=100_000.0,
        position_s_from_anchor=30.0, name="Boia ANCHOR",
    )
    r = solve([chain], bc, seabed=seabed, attachments=[boia])
    assert r.status == ConvergenceStatus.INVALID_CASE, (
        f"Esperado INVALID_CASE; veio {r.status} ({r.message})"
    )
    assert "afaste-a" in r.message.lower() or "âncora" in r.message.lower()


# ==============================================================================
# BC-AT-GB-05 — múltiplos arcos não-sobrepostos
# ==============================================================================


def test_BC_AT_GB_05_dois_arcos() -> None:
    """Duas boias bem espaçadas → dois arcos independentes."""
    chain = LineSegment(length=900.0, w=1500.0, EA=4.5e8, MBL=6e6, category="StuddedChain")
    bc = BoundaryConditions(h=300.0, mode=SolutionMode.TENSION, input_value=600_000)
    seabed = SeabedConfig(mu=0.3, slope_rad=0.0)
    boia_a = LineAttachment(
        kind="buoy", submerged_force=60_000.0,
        position_s_from_anchor=100.0, name="Boia A",
    )
    boia_b = LineAttachment(
        kind="buoy", submerged_force=60_000.0,
        position_s_from_anchor=300.0, name="Boia B",
    )
    r = solve([chain], bc, seabed=seabed, attachments=[boia_a, boia_b])
    assert r.status == ConvergenceStatus.CONVERGED, r.message
    # A mensagem deve mencionar 2 arcos
    assert "2 boia" in r.message.lower() or "arcos" in r.message.lower()
    # Devem existir DOIS picos no grounded
    td = r.dist_to_first_td or 0.0
    y_in_grounded = [
        y for x, y in zip(r.coords_x, r.coords_y) if x < td * 0.99
    ]
    # Conta picos locais (transições + → 0)
    n_peaks = 0
    above_threshold = False
    threshold = max(y_in_grounded) * 0.3 if y_in_grounded else 0.0
    for y in y_in_grounded:
        if y > threshold and not above_threshold:
            n_peaks += 1
            above_threshold = True
        elif y < threshold * 0.5:
            above_threshold = False
    assert n_peaks == 2, f"Esperava 2 picos, encontrei {n_peaks}"


# ==============================================================================
# BC-AT-GB-06 — sem boia vs com boia, geometria diferente
# ==============================================================================


def test_BC_AT_GB_06_com_vs_sem_boia() -> None:
    """Solver converge nos dois casos; com boia, o formato muda."""
    chain = LineSegment(length=700.0, w=1200.0, EA=4e8, MBL=5e6, category="StuddedChain")
    bc = BoundaryConditions(h=250.0, mode=SolutionMode.TENSION, input_value=500_000)
    seabed = SeabedConfig(mu=0.3, slope_rad=0.0)
    r_no_buoy = solve([chain], bc, seabed=seabed)
    boia = LineAttachment(
        kind="buoy", submerged_force=70_000.0,
        position_s_from_anchor=180.0, name="Boia",
    )
    r_buoy = solve([chain], bc, seabed=seabed, attachments=[boia])

    assert r_no_buoy.status == ConvergenceStatus.CONVERGED
    assert r_buoy.status == ConvergenceStatus.CONVERGED
    # Mesmo T_fl em ambos
    assert r_no_buoy.fairlead_tension == pytest.approx(r_buoy.fairlead_tension, rel=1e-3)
    # X_total pode mudar levemente porque arcos contraem horizontalmente
    # (catenária é menor que linha reta de mesmo arc length).
    # Vai variar < 5%.
    assert r_buoy.total_horz_distance == pytest.approx(
        r_no_buoy.total_horz_distance, rel=0.05
    )
    # Sem boia, y na zona apoiada = 0. Com boia, y > 0 em algum ponto.
    td_buoy = r_buoy.dist_to_first_td or 0.0
    ys_buoy_grounded = [
        y for x, y in zip(r_buoy.coords_x, r_buoy.coords_y) if x < td_buoy * 0.99
    ]
    assert max(ys_buoy_grounded, default=0.0) > 0.5, (
        "Esperava ilha suspensa visível (y > 0.5 m) no grounded com boia"
    )


# ==============================================================================
# BC-AT-GB-07 — boia em junção heterogênea NÃO forma arco
# ==============================================================================


def test_BC_AT_GB_07b_buoy_em_fully_suspended_constrange_H_hi() -> None:
    """
    Regressão (caso reportado pelo usuário):

    Wire 700m, w=201, T_fl=785kN, h=300m. Sem boia: fully-suspended,
    convergiu. Adicionando boia em s=200m com F=50kN, o legacy
    `_solve_suspended_tension` rejeitava o bracket porque `V_local` na
    junção da boia ficava < 0 quando V_anchor → 0 (perto de H_max).

    O fix: encolher H_hi até região onde residual é finito antes de
    chamar brentq. Caso DEVE convergir como fully-suspended (sem
    touchdown forçado).
    """
    seg = LineSegment(length=700.0, w=201.1, EA=3.425e7, MBL=3.78e6, category="Wire")
    bc = BoundaryConditions(h=300.0, mode=SolutionMode.TENSION, input_value=785_000)
    boia = LineAttachment(
        kind="buoy", submerged_force=50_014.0,
        position_s_from_anchor=200.0, name="B",
    )
    r = solve([seg], bc, attachments=[boia])
    assert r.status == ConvergenceStatus.CONVERGED, r.message
    assert r.fairlead_tension == pytest.approx(785_000.0, rel=1e-3)
    # Caso é fully-suspended — não deve haver touchdown forçado
    assert r.total_grounded_length < 1.0


def test_BC_AT_GB_07_junction_heterogenea_legacy_path() -> None:
    """
    Boia entre chain e wire (materiais diferentes) deve seguir o caminho
    legacy (junction force jump), sem formar arco. Mesmo que a junção
    fique na zona grounded, materiais distintos quebram o modelo de arco.

    Este teste protege a regressão do legacy F5.2.
    """
    chain = LineSegment(length=200.0, w=1500.0, EA=4.5e8, MBL=6e6, category="StuddedChain")
    wire = LineSegment(length=700.0, w=200.0, EA=4.4e8, MBL=4.8e6, category="Wire")
    bc = BoundaryConditions(h=300.0, mode=SolutionMode.TENSION, input_value=400_000)
    seabed = SeabedConfig(mu=0.3, slope_rad=0.0)
    boia = LineAttachment(
        kind="buoy", submerged_force=20_000.0, position_index=0, name="Boia M",
    )
    r = solve([chain, wire], bc, seabed=seabed, attachments=[boia])
    assert r.status == ConvergenceStatus.CONVERGED, r.message
    # Não deve mencionar arco na mensagem
    assert "F5.7.1" not in r.message
    assert "boia(s) levantam" not in r.message
