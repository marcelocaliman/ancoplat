"""
Fixtures sintéticos do QMoor 0.8.0 para Sprint 1 / Commit 6.

⚠ Sintético — construído sem amostra do KAR006 real. Quando o JSON
real estiver disponível, ele entra como teste E2E adicional em
Commit 11 sem necessidade de modificar este fixture.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any


def synthetic_qmoor_v0_8_minimal() -> dict[str, Any]:
    """Mínimo válido: 1 line × 1 profile × 1 segmento."""
    return {
        "version": "0.8.0",
        "unitSystem": "metric",
        "name": "Synthetic Project",
        "mooringLines": [
            {
                "name": "ML1",
                "profiles": [
                    {
                        "name": "Operational",
                        "type": "operational",
                        "segments": [
                            {
                                "length": 600.0,
                                "wetWeight": 1500.0,
                                "EA": 6.0e8,
                                "MBL": 1.0e7,
                                "lineType": "R4Studless",
                                "category": "studless",
                                "diameter": 0.076,
                            },
                        ],
                        "boundary": {
                            "h": 300.0,
                            "mode": "Tension",
                            "fairleadTension": 800_000.0,
                        },
                        "seabed": {"mu": 0.3},
                    },
                ],
            },
        ],
    }


def synthetic_qmoor_v0_8_kar006_like() -> dict[str, Any]:
    """
    Estrutura mais rica espelhando KAR006:
      • Top metadata: rig, location, region, engineer, number.
      • Vessel top-level (P-77 semisub).
      • 2 mooringLines (ML3, ML4).
      • 2 profiles cada (Operational, Preset).
      • Pendant multi-segmento + horzForces V(z).
    """
    pendant_seg_a = {"length": 12.0, "lineType": "R4Studless", "diameter": 0.076}
    pendant_seg_b = {"length": 8.0, "lineType": "IWRCEIPS", "diameter": 0.080}

    horz_forces = [
        {"depth": 0.0, "speed": 1.5, "heading": 45.0},
        {"depth": 100.0, "speed": 0.8, "heading": 45.0},
        {"depth": 300.0, "speed": 0.1, "heading": 45.0},
    ]

    base_segments = [
        {
            "length": 100.0, "wetWeight": 1500.0, "EA": 6.0e8, "MBL": 1.0e7,
            "lineType": "R4Studless", "category": "studless",
            "diameter": 0.076,
        },
        {
            "length": 400.0, "wetWeight": 200.0, "EA": 3.4e7, "MBL": 3.78e6,
            "lineType": "IWRCEIPS", "category": "wire",
            "diameter": 0.080,
        },
        {
            "length": 100.0, "wetWeight": 1500.0, "EA": 6.0e8, "MBL": 1.0e7,
            "lineType": "R4Studless", "category": "studless",
            "diameter": 0.076,
        },
    ]

    profile_op = {
        "name": "Operational Profile 1",
        "type": "operational",
        "segments": deepcopy(base_segments),
        "boundary": {
            "h": 300.0, "mode": "Tension",
            "fairleadTension": 850_000.0,
        },
        "seabed": {"mu": 0.3},
        "horzForces": horz_forces,
        "attachments": [
            {
                "name": "Buoy A",
                "kind": "buoy",
                "submergedForce": 50_000.0,
                "positionFromAnchor": 250.0,
                "buoyType": "submersible",
                "buoyEndType": "hemispherical",
                "buoyOuterDiameter": 1.5,
                "buoyLength": 3.0,
                "pendantSegments": [pendant_seg_a, pendant_seg_b],
            },
        ],
    }
    profile_preset = {
        "name": "Preset Profile",
        "type": "preset",
        "segments": deepcopy(base_segments),
        "boundary": {
            "h": 300.0, "mode": "Tension",
            "fairleadTension": 700_000.0,
        },
        "seabed": {"mu": 0.3},
        "horzForces": horz_forces,
    }

    return {
        "version": "0.8.0",
        "unitSystem": "metric",
        "name": "Karoon Energy Equipment Study (synthetic)",
        "rig": "P-77",
        "location": "Bacia de Santos",
        "region": "BR-Sul",
        "engineer": "F. Silva",
        "number": "KAR006",
        "vessels": [
            {
                "name": "P-77",
                "type": "Semisubmersible",
                "displacement": 4.5e7,
                "loa": 120.0,
                "breadth": 80.0,
                "draft": 22.0,
                "heading": 0.0,
                "operator": "Petrobras",
            },
        ],
        "mooringLines": [
            {
                "name": "ML3",
                "profiles": [profile_op, profile_preset],
            },
            {
                "name": "ML4",
                "profiles": [
                    {
                        **profile_op,
                        "name": "Operational Profile 1",
                    },
                ],
            },
        ],
    }
