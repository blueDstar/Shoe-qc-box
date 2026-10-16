from __future__ import annotations

import json
from pathlib import Path
from cad_import.step_reader import tessellate, sha256


def prepare(report, assembly, directory, linear=0.15, angular=0.25):
    from OCP.BRepTools import BRepTools
    directory = Path(directory)
    key = sha256(assembly.path)[:16] + f"_{linear}_{angular}_srgb_v2"
    destination = directory / key
    destination.mkdir(parents=True, exist_ok=True)
    records = []
    for component, row in zip(assembly.components, report["components"]):
        safe = component.id.replace("/", "_")
        mesh_path = destination / (safe + ".vtp")
        brep_path = destination / (safe + ".brep")
        if not mesh_path.exists():
            tessellate(component, linear, angular).save(str(mesh_path))
        if not brep_path.exists():
            BRepTools.Write_s(component.shape, str(brep_path))
        record = dict(row)
        record["mesh"] = str(mesh_path.relative_to(directory.parent))
        record["brep"] = str(brep_path.relative_to(directory.parent))
        records.append(record)
    manifest = dict(report)
    manifest["components"] = records
    manifest["tessellation"] = {"linear_deflection_mm": linear, "angular_deflection_rad": angular,
                                "placement": "definition mesh; base_transform applied once"}
    return manifest
