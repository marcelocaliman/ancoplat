"""
F5.7.1 — Boias na região grounded com força de elevação.

Quando uma boia é posicionada num trecho onde, sem ela, o cabo estaria
apoiado no seabed, ela pode ter empuxo suficiente para LEVANTAR aquela
porção do cabo formando uma "ilha" suspensa (arco) no meio do trecho
apoiado. Isso é exatamente o que softwares profissionais de mooring
(p.ex. Orcaflex/MOSES) renderizam quando um buoy de subsuperfície é
colocado próximo da âncora.

Modelo físico (seabed plano)
----------------------------
Para uma boia com força de empuxo F_b e cabo de peso submerso w:

  s_arch = F_b / w        (comprimento total de cabo levantado)

Equilíbrio vertical na boia: a soma das componentes verticais da tensão
do cabo nos dois lados é igual à força da boia. Como cada metade do
arco é uma catenária com vértice no touchdown (V_local = 0 lá), a
componente vertical na boia (vinda de cada lado) é V = w · s_arch/2.
Por simetria com mesmo material:

  V_L + V_R = F_b   ⇒   2·(w·s_arch/2) = F_b   ⇒   s_arch = F_b / w

Cada metade do arco é uma catenária com parâmetro a = H/w (mesmo H
global da linha; sem força horizontal externa, H é constante em toda
a linha estática). Geometria de uma metade:

  Δx = a · sinh(s_arch/(2·a))      (extensão horizontal de uma metade)
  Δy = a · (cosh(s_arch/(2·a)) − 1)  (altura do pico acima do seabed)

Total: arco tem 2·Δx de extensão horizontal e Δy de altura no pico.

Modelo físico (seabed em rampa)
-------------------------------
No frame ROTACIONADO alinhado com o seabed, gravidade tem componentes:
  - perpendicular ao seabed: w·cos(slope) — esta é a que "puxa" o cabo
    contra o seabed e portanto a única que conta no balanço do arco;
  - tangencial ao seabed: w·sin(slope) — já é absorvida no termo de
    fricção/atrito do trecho plano (existente em multi_segment.py).

Empuxo da boia em coordenadas rotacionadas:
  - F_perp = F_b · cos(slope)  (componente normal ao seabed)
  - F_tang = F_b · sin(slope)  (componente tangente, somatório com peso)

Na fórmula de s_arch, a razão F_perp/w_perp = (F_b·cos)/(w·cos) = F_b/w
— os fatores cos cancelam. Logo a fórmula s_arch = F_b/w continua
válida; apenas a orientação do arco no plano global muda (o arco
"se curva" perpendicular ao seabed em vez da vertical absoluta).

Restrições da implementação
---------------------------
- Os arcos devem caber em [0, L_g_total]: arch.s_left ≥ 0 e
  arch.s_right ≤ L_g_total. Caso contrário, ValueError com mensagem
  pedindo afastamento da boia (perto do anchor / perto do touchdown
  principal).
- Arcos consecutivos não podem se sobrepor. Se ocorrer (boias muito
  próximas com forças grandes), ValueError pedindo afastamento.
- Slopes razoáveis (|slope_rad| ≤ π/4); o solver mais externo já
  garante essa amarração.

Integração no solver multi-segmento
-----------------------------------
Este módulo entrega `compute_grounded_arches` e
`integrate_grounded_zone`. O `_integrate_segments_with_grounded` em
multi_segment.py chama o segundo no lugar do walk linear atual quando
detecta arches; quando não há grounded buoys, mantém o caminho legado
(walk linear puro).

Tensão na âncora com arches:
  L_flat = L_g_total − Σ s_arch_i
  T_anchor = T_main_td − μ·w·cos(slope)·L_flat − w·sin(slope)·L_flat

Os arcos são "tension-transparent" — entram e saem com a mesma tensão
(= T_main_td seria essencialmente o mesmo valor nos touchdowns do arco
porque a tangente é à seabed, então T = H·sqrt(1+m²)). A friction só
atua nas porções planas.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

import numpy as np

from .types import LineAttachment, LineSegment


_TOL_S = 1e-6


@dataclass(frozen=True)
class GroundedArch:
    """
    Um arco no trecho grounded — uma boia descolou o cabo do seabed.

    Coordenadas em arc length não-esticada desde a âncora ao longo do
    cabo (frame anchor-fixo, pré-deformação elástica).
    """

    s_buoy: float        # posição da boia (arc length da âncora)
    s_arch: float        # comprimento total do arco (em metros)
    s_left: float        # touchdown esquerdo (lado anchor) em arc length
    s_right: float       # touchdown direito (lado fairlead) em arc length
    w_local: float       # peso submerso por metro do segmento contendo a boia
    F_buoy: float        # empuxo da boia (positivo, magnitude em N)
    junction_idx: int    # índice da junção em segments resolvidos


def compute_grounded_arches(
    segments: Sequence[LineSegment],
    L_effs: Sequence[float],
    attachments: Sequence[LineAttachment],
    L_g_total: float,
) -> list[GroundedArch]:
    """
    Identifica boias na região grounded e computa o arco de cada uma.

    `attachments` deve ter `position_index` válido (já passou pelo
    `resolve_attachments`). Apenas boias (`kind='buoy'`) cuja posição
    cai em [0, L_g_total] geram arcos. Clumps são ignorados (eles
    afundam ainda mais o cabo, sem efeito de levantamento).

    Retorna lista ordenada por `s_buoy`. Levanta ValueError se algum
    arco não cabe no trecho grounded ou se arcos se sobrepõem.
    """
    if L_g_total < 0:
        return []

    cum = [0.0]
    for L in L_effs:
        cum.append(cum[-1] + L)

    arches: list[GroundedArch] = []
    for att in attachments:
        if att.kind != "buoy":
            continue
        if att.position_index is None:
            continue
        s_b = cum[att.position_index + 1]
        if s_b > L_g_total + _TOL_S:
            continue  # boia em zona suspensa — não cria arco
        # Material local: usamos o sub-segmento à esquerda da junção.
        # Quando o resolver dividiu, ambos os lados têm mesmo material;
        # quando user definiu manualmente, o ponto é uma junção real
        # entre materiais possivelmente distintos.
        w_left = segments[att.position_index].w
        w_right = (
            segments[att.position_index + 1].w
            if att.position_index + 1 < len(segments)
            else w_left
        )
        # Heurística: arco só se forma quando a junção fica em material
        # uniforme (split do resolver) — o modelo de integração assume
        # w_local único. Em junção entre materiais distintos (e.g.,
        # chain/wire), tratamos como force jump legacy.
        if abs(w_left - w_right) > 1e-9:
            continue
        w_local = w_left
        if w_local <= 0:
            raise ValueError(
                f"Segmento contendo a boia tem w={w_local}; precisa > 0"
            )
        s_arch = att.submerged_force / w_local
        s_left = s_b - s_arch / 2.0
        s_right = s_b + s_arch / 2.0
        # Verifica que o arco inteiro atravessa só o mesmo material:
        # se algum sub-segmento entre s_left e s_right tem w diferente,
        # o arco não cabe (downgrade pra force jump legacy).
        arch_crosses_other_material = False
        for k, seg in enumerate(segments):
            if cum[k + 1] <= s_left + _TOL_S:
                continue
            if cum[k] >= s_right - _TOL_S:
                break
            if abs(seg.w - w_local) > 1e-9:
                arch_crosses_other_material = True
                break
        if arch_crosses_other_material:
            continue
        if s_left < -_TOL_S:
            raise ValueError(
                f"Boia '{att.name or 'anônima'}' em s={s_b:.1f}m: "
                f"empuxo {att.submerged_force / 1000:.1f}kN exigiria arco de "
                f"{s_arch:.1f}m, mas a boia está só a {s_b:.1f}m da âncora. "
                "Reduza o empuxo da boia ou afaste-a da âncora."
            )
        if s_right > L_g_total + _TOL_S:
            raise ValueError(
                f"Boia '{att.name or 'anônima'}' em s={s_b:.1f}m: arco "
                f"de {s_arch:.1f}m extrapola o trecho apoiado "
                f"({L_g_total:.1f}m total). A boia está perto demais do "
                "touchdown principal — o arco entra na zona suspensa. "
                "Afaste a boia da âncora ou reduza o empuxo."
            )
        arches.append(
            GroundedArch(
                s_buoy=s_b,
                s_arch=s_arch,
                s_left=max(0.0, s_left),
                s_right=min(L_g_total, s_right),
                w_local=w_local,
                F_buoy=att.submerged_force,
                junction_idx=att.position_index,
            )
        )

    arches.sort(key=lambda a: a.s_buoy)

    # Verifica não-sobreposição (cada arco deve terminar antes do próximo começar)
    for i in range(1, len(arches)):
        if arches[i].s_left < arches[i - 1].s_right - _TOL_S:
            raise ValueError(
                f"Arcos das boias em s={arches[i - 1].s_buoy:.1f}m e "
                f"s={arches[i].s_buoy:.1f}m se sobrepõem. Afaste-as ou "
                "reduza os empuxos."
            )

    return arches


def integrate_grounded_zone(
    segments: Sequence[LineSegment],
    H: float,
    L_g_total: float,
    slope_rad: float,
    mu: float,
    arches: list[GroundedArch],
    n_total_grounded: int,
) -> dict:
    """
    Integra o trecho grounded (de anchor até main_td) com arcos.

    Walk: anchor → flat → arch → flat → arch → ... → flat → main_td.

    Cada flat zone segue a rampa do seabed (linear em x, y); cada arch
    é uma catenária local com vértice em cada touchdown e pico na boia.
    Tensão tangencial cresce em flat zones por friction; arches passam
    a mesma tensão (transparentes).

    Retorna dict:
      coords_x[n], coords_y[n]: pontos da curva (frame anchor em (0, 0))
      tension_magnitude[n], tension_x[n], tension_y[n]
      x_main_td, y_main_td: posição global do touchdown principal (fim do trecho grounded)
      T_main_td, T_anchor: tensão (escalar) no main_td e na âncora
      L_flat_total: comprimento total efetivamente apoiado (sem arcos)
      arches: a mesma lista, retornada pra diagnóstico
    """
    if H <= 0:
        raise ValueError(f"H={H} deve ser > 0")
    if L_g_total < 0:
        raise ValueError(f"L_g_total={L_g_total} deve ser ≥ 0")

    m = math.tan(slope_rad)
    sqrt_1pm2 = math.sqrt(1.0 + m * m)
    cos_s = math.cos(slope_rad)
    sin_s = math.sin(slope_rad)

    # Tensão no main_td: T = H·√(1+m²) (tangente à rampa)
    T_main_td = H * sqrt_1pm2

    # L_flat_total = trechos planos ENTRE arcos (e nas pontas)
    L_arch_total = sum(a.s_arch for a in arches)
    L_flat_total = max(0.0, L_g_total - L_arch_total)

    # w do segmento 0 governa o flat (todos os sub-segmentos derivados
    # do segmento 0 têm o mesmo w).
    w_seg0 = segments[0].w

    # Tensão na âncora: friction só nas zonas planas
    T_anchor = max(
        0.0,
        T_main_td
        - mu * w_seg0 * cos_s * L_flat_total
        - w_seg0 * sin_s * L_flat_total,
    )

    coords_x: list[float] = []
    coords_y: list[float] = []
    tension_mag: list[float] = []
    tension_x: list[float] = []
    tension_y: list[float] = []
    # arc_length_at_coord[i]: arc length não-esticada da âncora até o
    # ponto i. Sincronizado com coords_x. Usado pelo caller para
    # localizar boundaries de sub-segmento (junções) em índices de coords.
    arc_length_at_coord: list[float] = []

    # Distribui pontos proporcionais ao comprimento
    if L_g_total > _TOL_S:
        density = max(2, n_total_grounded) / L_g_total
    else:
        density = 0.0

    # Construa as zonas em ordem
    zones: list[tuple] = []
    cur_s = 0.0
    for arch in arches:
        if arch.s_left > cur_s + _TOL_S:
            zones.append(("flat", cur_s, arch.s_left))
        zones.append(("arch", arch))
        cur_s = arch.s_right
    if cur_s < L_g_total - _TOL_S:
        zones.append(("flat", cur_s, L_g_total))

    # Walk: tensão tangencial (escalar). Em flat zone começa em T_anchor
    # à esquerda e cresce para a direita por friction. Em arch, T fica
    # transparente: entra com T_left e sai com T_left (catenária acima
    # eleva T transitoriamente, mas re-toca seabed com T_left).
    T_tang = T_anchor  # tensão tangencial no início da zona corrente
    x_cur = 0.0
    y_cur = 0.0
    # Adiciona o ponto da âncora (s=0). Próximas zonas estendem a curva
    # sem duplicar o ponto inicial.
    coords_x.append(x_cur)
    coords_y.append(y_cur)
    tension_mag.append(T_tang)
    tension_x.append(T_tang * cos_s)
    tension_y.append(T_tang * sin_s)
    arc_length_at_coord.append(0.0)

    for zone in zones:
        if zone[0] == "flat":
            _, s_a, s_b = zone
            L_f = s_b - s_a
            if L_f < _TOL_S:
                continue
            n_f = max(2, int(round(density * L_f))) if density > 0 else 2
            # Walk linear na rampa
            dx = L_f / sqrt_1pm2  # extensão horizontal (em x global)
            x_arr = np.linspace(x_cur, x_cur + dx, n_f)
            y_arr = y_cur + m * (x_arr - x_cur)
            # Tensão linear: T_left → T_right por friction acumulada
            T_inc = (
                mu * w_seg0 * cos_s * L_f + w_seg0 * sin_s * L_f
            )
            T_left = T_tang
            T_right = T_left + T_inc
            T_arr = np.linspace(T_left, T_right, n_f)
            Tx_arr = T_arr * cos_s
            Ty_arr = T_arr * sin_s
            # arc length em cada ponto (linear de s_a → s_b, skip first)
            s_arr = np.linspace(s_a, s_b, n_f)
            # Skip first point (já adicionado pela zona anterior ou pela âncora)
            coords_x.extend(x_arr[1:].tolist())
            coords_y.extend(y_arr[1:].tolist())
            tension_mag.extend(T_arr[1:].tolist())
            tension_x.extend(Tx_arr[1:].tolist())
            tension_y.extend(Ty_arr[1:].tolist())
            arc_length_at_coord.extend(s_arr[1:].tolist())
            x_cur = float(x_arr[-1])
            y_cur = float(y_arr[-1])
            T_tang = T_right
        else:
            arch = zone[1]
            # Catenária local com vértice em cada touchdown.
            # No frame ALINHADO COM O SEABED:
            #   metade esquerda: vértice em (0, 0); s ∈ [0, s_arch/2]
            #     x_local(s) = a · asinh(s/a)
            #     y_local(s) = sqrt(a² + s²) − a       (≥ 0, sobe da seabed)
            #   metade direita: espelhamento. Vértice em (2·x_half, 0).
            a_arch = H / arch.w_local
            half_s = arch.s_arch / 2.0
            x_half_local = a_arch * math.asinh(half_s / a_arch)
            # y_peak_local = math.sqrt(a_arch ** 2 + half_s ** 2) - a_arch  # diagnóstico

            # Discretiza meia-arc length [0, half_s]
            n_a = max(8, int(round(density * arch.s_arch))) if density > 0 else 12
            n_half = max(4, n_a // 2)
            s_loc_left = np.linspace(0.0, half_s, n_half)
            x_loc_left = a_arch * np.arcsinh(s_loc_left / a_arch)
            y_loc_left = (
                np.sqrt(a_arch * a_arch + s_loc_left * s_loc_left) - a_arch
            )

            # Metade direita (espelhada): s_loc decresce de half_s para 0,
            # x cresce de x_half para 2·x_half. y_loc(s_loc) tem o mesmo
            # formato (depende só de |s|).
            s_loc_right = np.linspace(half_s, 0.0, n_half)
            x_loc_right = (
                2.0 * x_half_local
                - a_arch * np.arcsinh(s_loc_right / a_arch)
            )
            y_loc_right = (
                np.sqrt(a_arch * a_arch + s_loc_right * s_loc_right) - a_arch
            )

            # Concatena (sem duplicar o ponto da boia que aparece em ambas)
            x_loc = np.concatenate([x_loc_left, x_loc_right[1:]])
            y_loc = np.concatenate([y_loc_left, y_loc_right[1:]])

            # Tensão local (catenária): T(s) = w · sqrt(a² + s²)
            T_loc_left = arch.w_local * np.sqrt(
                a_arch * a_arch + s_loc_left * s_loc_left
            )
            T_loc_right = arch.w_local * np.sqrt(
                a_arch * a_arch + s_loc_right * s_loc_right
            )
            T_loc = np.concatenate([T_loc_left, T_loc_right[1:]])

            # Componente vertical local (= w · s, mas com sinal: positiva
            # subindo no lado esquerdo, negativa descendo no direito).
            Vy_loc_left = arch.w_local * s_loc_left          # + (sobe)
            Vy_loc_right = -arch.w_local * s_loc_right       # - (desce)
            Vy_loc = np.concatenate([Vy_loc_left, Vy_loc_right[1:]])
            # Componente horizontal local: H constante
            Vx_loc = np.full_like(T_loc, H)

            # Rotaciona local → global (alinha "horizontal local" com a
            # direção do seabed). Translada para (x_cur, y_cur) que é o
            # touchdown esquerdo do arco, em coordenadas globais.
            #   x_g = x_cur + cos·x_loc − sin·y_loc
            #   y_g = y_cur + sin·x_loc + cos·y_loc
            x_glob = x_cur + cos_s * x_loc - sin_s * y_loc
            y_glob = y_cur + sin_s * x_loc + cos_s * y_loc
            # Tensão: rotaciona o vetor (Vx_loc, Vy_loc) também
            Tx_glob = cos_s * Vx_loc - sin_s * Vy_loc
            Ty_glob = sin_s * Vx_loc + cos_s * Vy_loc

            # arc length por ponto: na metade esquerda cresce de s_left
            # até s_buoy; na metade direita cresce de s_buoy até s_right.
            s_left_arr = arch.s_left + s_loc_left  # [s_left, s_left+half_s] = [s_left, s_buoy]
            s_right_arr = arch.s_buoy + (half_s - s_loc_right)  # [s_buoy, s_buoy+half_s]
            s_arc_full = np.concatenate([s_left_arr, s_right_arr[1:]])

            # Skip first (= último ponto da zona anterior; já adicionado)
            coords_x.extend(x_glob[1:].tolist())
            coords_y.extend(y_glob[1:].tolist())
            tension_mag.extend(T_loc[1:].tolist())
            tension_x.extend(Tx_glob[1:].tolist())
            tension_y.extend(Ty_glob[1:].tolist())
            arc_length_at_coord.extend(s_arc_full[1:].tolist())

            # Atualiza cursor: touchdown direito do arco
            x_cur = float(x_glob[-1])
            y_cur = float(y_glob[-1])
            # T_tang permanece (arch é transparente)

    return {
        "coords_x": coords_x,
        "coords_y": coords_y,
        "tension_magnitude": tension_mag,
        "tension_x": tension_x,
        "tension_y": tension_y,
        "arc_length_at_coord": arc_length_at_coord,
        "x_main_td": x_cur,
        "y_main_td": y_cur,
        "T_main_td": T_main_td,
        "T_anchor": T_anchor,
        "L_flat_total": L_flat_total,
        "L_arch_total": L_arch_total,
        "arches": arches,
    }


__all__ = [
    "GroundedArch",
    "compute_grounded_arches",
    "integrate_grounded_zone",
]
