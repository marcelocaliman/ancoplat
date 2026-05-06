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


def synthetic_qmoor_v0_8_kar006_real() -> dict[str, Any]:
    """
    Espelha a ESTRUTURA REAL do JSON KAR006 (QMoor 0.8.0) reportada
    pelo usuário em Sprint 2 / Commit 20:

      • `QMoorVersion` (não `version`) no top-level.
      • `mooringLines[]` é um GRUPO de profiles (Operational / Preset);
        seu `segments` é VAZIO. Os segments reais estão em
        `mooringLines[i].profiles[j].segments[]`.
      • Cada `segment` tem `length` no top + props físicas em
        `lineProps.{wetWeight, qmoorEA, breakStrength, ...}` como
        STRINGS COM UNIDADE (ex.: "475.0 m", "150.66 kgf / m",
        "81018.96 te").
      • Boias em `profile.buoys[]` (não `attachments[]`) com
        `pennantLine.segments[]` para o pendant multi-trecho e
        `distFromEnd` (m) para a posição.

    Versão simplificada (1 grupo × 1 profile × 3 segments + 1 boia)
    para testes; o caso real KAR006 tem 2 grupos × 4 profiles cada.
    """
    return {
        "filename": "test-kar006.moor",
        "QMoorVersion": "0.8.0",
        "unitSystem": "metric",
        "name": "Karoon Energy Equipment Study (test)",
        "rig": "Maersk Developer",
        "location": "7-PRA-2-SPS, Bauna Field",
        "region": "BR-Sul",
        "engineer": "D. Ralha",
        "number": "KAR006",
        "vessels": [],
        "mooringLines": [
            {
                "name": "Operational Profiles",
                "segments": [],  # VAZIO no top — segments reais nos profiles
                "boundary": {
                    "startpointDepth": None,
                    "horzDistance": None,
                    "endpointGrounded": True,
                    "startpointType": "Semi-Sub Fairlead",
                },
                "profiles": [
                    {
                        "name": "ML3",
                        "displayName": "Operational Profiles - ML3",
                        "segments": [
                            {
                                "category": "StuddedChain",
                                "length": "475.0 m",
                                "name": "Rig Chain",
                                "lineProps": {
                                    "wetWeight": "150.66171764698163 kgf / m",
                                    "qmoorEA": "81018.96002399089 te",
                                    "category": "StuddedChain",
                                    "dryWeight": "173.177638113189 kgf / m",
                                    "diameter": "88.89999999999998 mm",
                                    "breakStrength": "815.1553840507001 te",
                                    "modulus": "128001.16914767069 MPa",
                                    "seabedFrictionCF": 1.0,
                                    "lineType": "R4Chain",
                                },
                            },
                            {
                                "category": "Wire",
                                "length": "609.0 m",
                                "name": "Insert Wire",
                                "lineProps": {
                                    "wetWeight": "33.97113378709231 kgf / m",
                                    "qmoorEA": "51992.85222853726 te",
                                    "category": "Wire",
                                    "dryWeight": "40.929280349982584 kgf / m",
                                    "diameter": "97.99999999999997 mm",
                                    "breakStrength": "732.5808007477774 te",
                                    "modulus": "67596.20050222265 MPa",
                                    "seabedFrictionCF": 0.6,
                                    "lineType": "EIPS20",
                                },
                            },
                            {
                                "category": "StuddedChain",
                                "length": "488.0 m",
                                "name": "Anchor Chain",
                                "lineProps": {
                                    "wetWeight": "134.51347927617243 kgf / m",
                                    "qmoorEA": "72333.87217716347 te",
                                    "category": "StuddedChain",
                                    "dryWeight": "154.61398693229873 kgf / m",
                                    "diameter": "83.99999999999999 mm",
                                    "breakStrength": "735.561012739019 te",
                                    "modulus": "128001.1691476707 MPa",
                                    "seabedFrictionCF": 1.0,
                                    "lineType": "R4Chain",
                                },
                            },
                        ],
                        "boundary": {
                            "startpointDepth": "284.0 m",
                            "horzDistance": "1829.0 m",
                            "endpointGrounded": True,
                            "endpointDepth": "311.0 m",
                            "fairleadOffset": {
                                "x": "0.0 m",
                                "y": "2.438399999999999 m",
                            },
                            "startpointType": "Semi-Sub Fairlead",
                        },
                        "solution": {
                            "inputParam": "tension",
                            "fairleadTension": "150.0 te",
                            "rangeToAnchor": None,
                        },
                        "vessels": [],
                        "horzForces": [],
                        "buoys": [
                            {
                                "weightInAir": "6.847884009890001 te",
                                "endType": "Elliptical",
                                "buoyType": "Submersible",
                                "length": "3.6308226898410076 m",
                                "distFromEnd": "1088.0 m",
                                "diameter": "3.047999999999999 m",
                                "name_id": "B1018",
                                "pennantLine": {
                                    "segments": [
                                        {
                                            "category": "StuddedChain",
                                            "length": "6.0 m",
                                            "name": "Buoy Chain",
                                            "lineProps": {
                                                "wetWeight": "129.91 kgf / m",
                                                "qmoorEA": "69858.18 te",
                                                "category": "StuddedChain",
                                                "diameter": "82.55 mm",
                                                "breakStrength": "712.54 te",
                                                "lineType": "R4Chain",
                                            },
                                        },
                                        {
                                            "category": "Wire",
                                            "length": "92.0 m",
                                            "name": "Pendant Wire",
                                            "lineProps": {
                                                "wetWeight": "11.51 kgf / m",
                                                "qmoorEA": "17589.0 te",
                                                "category": "Wire",
                                                "diameter": "57.0 mm",
                                                "breakStrength": "268.29 te",
                                                "lineType": "EIPS20",
                                            },
                                        },
                                    ],
                                },
                            },
                        ],
                        "clumps": [],
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
