"""
Cálculo de empuxo de boias (F6).

Fórmulas espelham `docs/Cópia de Buoy_Calculation_Imperial_English.xlsx`,
sheet **Formula Guide**, linhas 4-7 — fonte primária citável. Cada
end_type tem volume calculado a partir de cilindro reto + duas tampas
geometricamente bem definidas.

Convenção:
    L = comprimento total da boia (m)        — incluído tampas
    D = diâmetro externo (m)                  — r = D/2
    h = projeção da tampa por extremidade (m) — depende de end_type
    Lc = L − 2·h (comprimento da parte cilíndrica reta)
    V_total = π·r²·Lc + 2·V_tampa

Fórmulas por `end_type` (ref. Excel Formula Guide):
    flat          (R4): h=0,    V_tampa = 0,                       Lc = L
    hemispherical (R5): h=D/2,  V_tampa = (2/3)·π·r³,              Lc = L − D
    elliptical    (R6): h=D/4,  V_tampa = (2/3)·π·r²·(D/4),        Lc = L − D/2
    semi_conical  (R7): h=D/4,  V_tampa = (1/3)·π·r²·(D/4),        Lc = L − D/2

(NB: Excel apresenta "End Pair Volume" = 2·V_tampa, então a fórmula final
no sheet aparece como `4/3·π·r²·h` para elliptical, etc. Aqui escrevemos
explicitamente V_tampa para ficar didático no código.)

Constantes:
    ρ_seawater = 1025 kg/m³ (default convenção SI; o Excel usa
    0.06423837 kip/ft³ ≈ 1029 kg/m³ — diferença <1% e dentro do AC)
    g = 9.80665 m/s²

Empuxo líquido (submerged_force, positivo se boia flutua):
    F_b = V_total · ρ_seawater · g − weight_in_air_N
"""
from __future__ import annotations

import math
from typing import Literal

EndType = Literal["flat", "hemispherical", "elliptical", "semi_conical"]

# Gravidade padrão (m/s²) — ISO 80000-3.
G = 9.80665

# Densidade da água do mar em SI (kg/m³).
# O Excel usa 0.06423837 kip/ft³ → 1029 kg/m³ (diferença < 0.4%).
# Adotamos o valor SI canônico 1025 kg/m³ (ISO 19901-1, ITTC).
SEAWATER_DENSITY_SI = 1025.0


def compute_volume(end_type: EndType, outer_diameter: float, length: float) -> float:
    """
    Volume deslocado da boia em m³.

    Args:
        end_type: forma das tampas (`flat | hemispherical | elliptical | semi_conical`).
        outer_diameter: D (m), > 0.
        length: L (m), > 0. Deve ser ≥ projeção das duas tampas (`L ≥ 2·h`).

    Returns:
        Volume total deslocado em m³.

    Raises:
        ValueError: se end_type desconhecido ou geometria inválida
            (`L < 2·h` impossibilita cilindro central).
    """
    if outer_diameter <= 0:
        raise ValueError(f"outer_diameter deve ser > 0 (recebido {outer_diameter})")
    if length <= 0:
        raise ValueError(f"length deve ser > 0 (recebido {length})")

    r = outer_diameter / 2.0

    if end_type == "flat":
        # Excel Formula Guide R4: h=0, V_total = π·r²·L
        return math.pi * r * r * length

    if end_type == "hemispherical":
        # Excel Formula Guide R5: h=D/2, Lc = L−D, V_tampas = (4/3)·π·r³
        h = outer_diameter / 2.0
        lc = length - 2 * h  # = L − D
        if lc < 0:
            raise ValueError(
                f"hemispherical: length={length} < D={outer_diameter} "
                "(tampas hemisféricas exigem L ≥ D)"
            )
        v_caps = (4.0 / 3.0) * math.pi * r ** 3
        return math.pi * r * r * lc + v_caps

    if end_type == "elliptical":
        # Excel Formula Guide R6: h=D/4, Lc = L−D/2, V_tampas = (4/3)·π·r²·(D/4)
        h = outer_diameter / 4.0
        lc = length - 2 * h  # = L − D/2
        if lc < 0:
            raise ValueError(
                f"elliptical: length={length} < D/2={outer_diameter / 2.0} "
                "(tampas elípticas exigem L ≥ D/2)"
            )
        v_caps = (4.0 / 3.0) * math.pi * r * r * h
        return math.pi * r * r * lc + v_caps

    if end_type == "semi_conical":
        # Excel Formula Guide R7: h=D/4, Lc = L−D/2, V_tampas = (2/3)·π·r²·(D/4)
        h = outer_diameter / 4.0
        lc = length - 2 * h  # = L − D/2
        if lc < 0:
            raise ValueError(
                f"semi_conical: length={length} < D/2={outer_diameter / 2.0} "
                "(tampas cônicas exigem L ≥ D/2)"
            )
        v_caps = (2.0 / 3.0) * math.pi * r * r * h
        return math.pi * r * r * lc + v_caps

    raise ValueError(
        f"end_type desconhecido: {end_type!r}. "
        "Esperado: flat | hemispherical | elliptical | semi_conical."
    )


def compute_submerged_force(
    end_type: EndType,
    outer_diameter: float,
    length: float,
    weight_in_air: float,
    seawater_density: float = SEAWATER_DENSITY_SI,
) -> float:
    """
    Empuxo líquido (submerged_force) em N.

    F_b = V · ρ · g − weight_in_air

    Pode retornar valor **negativo** quando o peso domina o empuxo —
    nesse caso o objeto é fisicamente um clump_weight, não buoy. Caller
    decide o `kind`.

    Args:
        end_type: forma das tampas.
        outer_diameter: D (m), > 0.
        length: L (m), > 0, ≥ 2·h.
        weight_in_air: peso seco (N). ≥ 0.
        seawater_density: kg/m³ (default 1025).

    Returns:
        Empuxo líquido em N (positivo = flutua).
    """
    if weight_in_air < 0:
        raise ValueError(
            f"weight_in_air deve ser ≥ 0 (recebido {weight_in_air})"
        )
    volume = compute_volume(end_type, outer_diameter, length)
    return volume * seawater_density * G - weight_in_air


__all__ = [
    "EndType",
    "G",
    "SEAWATER_DENSITY_SI",
    "compute_submerged_force",
    "compute_volume",
]
