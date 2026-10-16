from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
import numpy as np
from cad_import.step_reader import StepAssembly, bounds, is_valid, metadata, solid_count

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CAD = ROOT / "Shoe_QC_Dual_Shutter_STEP_CAD_BOM_RevA" / "STEP"
MOVING = ("SHUTTER_", "BLOCK_", "BRACKET_", "DRIVE_LINK_")


def group_for(name):
    for side, group in (("L", "LEFT_DOOR_MOVING"), ("R", "RIGHT_DOOR_MOVING")):
        if name.startswith(tuple(prefix + side for prefix in MOVING)):
            return group
        if name == "ACT_ROD_" + side:
            return side + "_ACTUATOR_ROD_PARAMETRIC"
    return "STATIC_FRAME"


def dimensions(b):
    return [b[i + 3] - b[i] for i in range(3)]


def inspect(cad=DEFAULT_CAD, output=None):
    cad = Path(cad).resolve()
    output = Path(output or ROOT / "reports")
    output.mkdir(parents=True, exist_ok=True)
    spec_path = cad.parent / "model_spec.json"
    spec = json.loads(spec_path.read_text(encoding="utf-8")) if spec_path.exists() else {}
    names = {x["name"]: x["pid"] for x in spec.get("assembly", [])}
    files = []
    loaded = {}
    for path in sorted(cad.iterdir()):
        rec = {"file": path.name, "bytes": path.stat().st_size,
               "classification": "native_reference"}
        if path.suffix.lower() in (".step", ".stp"):
            rec.update(metadata(path))
            rec["classification"] = "assembly_state" if rec["assembly_occurrences"] else "part"
            try:
                a = StepAssembly(path)
                loaded[path.name] = a
                b = np.array([x.bbox() for x in a.components])
                rec.update(readable=True, instances=len(a.components),
                           bbox_mm=[*b[:, :3].min(axis=0).tolist(), *b[:, 3:].max(axis=0).tolist()],
                           valid=all(is_valid(x.shape) for x in a.components))
                rec["dimensions_mm"] = dimensions(rec["bbox_mm"])
            except Exception as e:
                rec.update(readable=False, error=str(e))
        files.append(rec)
    main = loaded.get("GA_ASSEMBLY_CLOSED.step")
    if main is None:
        candidates = [a for a in loaded.values() if a.meta["assembly_occurrences"]]
        if not candidates:
            raise ValueError("No main assembly found; choose geometry and assign components manually.")
        main = candidates[0]
    components = []
    for c in main.components:
        b = c.bbox()
        components.append({"id": c.id, "name": c.name, "part_id": names.get(c.name, "UNMAPPED"),
                           "source": main.path.name, "group": group_for(c.name),
                           "bbox_mm": b, "dimensions_mm": dimensions(b),
                           "base_transform": c.base_transform.tolist(), "color": list(c.color),
                           "color_source": c.color_source, "solids": solid_count(c.shape),
                           "valid": is_valid(c.shape), "visible": True,
                           "mechanical_validated":False,
                           "simulation_exclusion":"Source CAD bracket/drive-link interference" if names.get(c.name) in ("P09","P11") else None,
                           "confidence": "STEP_XDE + source mapping" if c.name in names else "manual_assignment_required"})
    quantities = Counter(c["part_id"] for c in components)
    bom = []
    bom_path = cad.parent / "BOM.csv"
    if bom_path.exists():
        with bom_path.open(encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                pid = row["Part"]
                qty = int(row["SL"])
                bom.append({"part_id": pid, "bom_quantity": qty, "assembly_quantity": quantities[pid],
                            "part_file_exists": (cad / (pid + ".step")).exists(),
                            "matched": qty == quantities[pid] and (cad / (pid + ".step")).exists()})
    comparisons = {}
    for fn, a in loaded.items():
        if fn != main.path.name and a.meta["assembly_occurrences"]:
            other = {x.name: x for x in a.components}
            comparisons[fn] = {c.name: (np.array(other[c.name].bbox()) - c.bbox()).round(6).tolist()
                               for c in main.components if c.name in other and
                               not np.allclose(c.bbox(), other[c.name].bbox(), atol=1e-5)}
    b = np.array([c["bbox_mm"] for c in components])
    envelope = [*b[:, :3].min(axis=0).tolist(), *b[:, 3:].max(axis=0).tolist()]
    warnings = [
        "Rev A source identifies rails, blocks and actuator as generic envelopes, not vendor-validated mechanisms.",
        "Measured OPEN rod is 425 mm vs CLOSED 75 mm; fixed lower end Z=363 mm. Source make_cad.py differs from actual STEP. Parametric rod display uses measured STEP endpoints.",
        "No robot or sensor CAD is present. All robot/gripper/shoe and sensor zones are DEMO overlays.",
    ]
    enclosure_rows=[x for x in components if x["part_id"] in ("P01","P02","P03","P04")]
    shell=np.array([x["bbox_mm"] for x in enclosure_rows])
    shell_dimensions=(shell[:,3:].max(axis=0)-shell[:,:3].min(axis=0)).tolist() if len(shell) else []
    by_pid={x["part_id"]:x for x in components}
    aperture=None
    if "P04.step" in loaded:
        from OCP.TopExp import TopExp_Explorer
        from OCP.TopAbs import TopAbs_WIRE
        ex=TopExp_Explorer(loaded["P04.step"].components[0].shape,TopAbs_WIRE)
        while ex.More():
            wire_bounds=bounds(ex.Current())
            dims=dimensions(wire_bounds)
            if abs(dims[0])<1e-5 and dims[1]>100 and dims[2]>100 and dims[1]<510:
                aperture=dims[1:]
                break
            ex.Next()
    measured={"box_mm":shell_dimensions,"opening_yz_mm":aperture,
              "door_xyz_mm":by_pid.get("P05",{}).get("dimensions_mm"),
              "rail_length_mm":by_pid.get("P07",{}).get("dimensions_mm",[0,0,None])[2],
              "tower_length_mm":by_pid.get("P06",{}).get("dimensions_mm",[0,0,None])[2]}
    references={"box_mm":[800,520,560],"opening_yz_mm":[380,310],"door_xyz_mm":[4,430,360],"rail_length_mm":820,"tower_length_mm":880}
    checks={k:{"measured":v,"reference":references[k],"matched":v is not None and np.allclose(v,references[k],atol=1e-5)} for k,v in measured.items()}
    for k,v in checks.items():
        if not v["matched"]:
            warnings.append("Measured / reference discrepancy: "+k+"; explicit kinematics confirmation required.")
    report = {"cad_path": str(cad), "main_assembly": main.path.name,
              "unit": main.meta["unit"], "coordinate_system": "right-handed X/Y/Z; Z up; box centered in X/Y; base Z=0",
              "files": files, "components": components, "bom": bom,
              "assembly_envelope_mm": envelope, "assembly_dimensions_mm": dimensions(envelope),
              "state_comparisons": comparisons, "warnings": warnings,
              "reference_checks":checks,
              "source_parameters": spec.get("params", {}), "geometry_is_modified": False}
    (output / "cad_inspection.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    lines = ["# CAD inspection — Hilykan Rev A", "", "Source geometry is read-only.",
             f"Main: `{main.path.name}` · unit: {main.meta['unit']} · instances: {len(components)}", "",
             f"Measured assembly envelope: {dimensions(envelope)} mm. Includes towers and drive hardware.", "",
             "| File | Kind | Instances | Measured X/Y/Z mm | Readable |", "|---|---|---:|---|---|"]
    for x in files:
        lines.append(f"| {x['file']} | {x['classification']} | {x.get('instances','—')} | {x.get('dimensions_mm','—')} | {x.get('readable','native')} |")
    lines += ["", "## BOM", "", *[f"- {x['part_id']}: BOM {x['bom_quantity']} / STEP {x['assembly_quantity']} / matched {x['matched']}" for x in bom],
              "", "## Alternate states", "", *[f"- {fn}: {len(changes)} changed instances; deltas recorded in JSON." for fn, changes in comparisons.items()],
              "", "## Data limitations", "", *["- " + w for w in warnings]]
    lines += ["", "## Measured reference checks", "", "Opening is measured from the rectangular inner wire of P04, not substituted from the source JSON.", "",
              *[f"- {k}: measured {v['measured']}; reference {v['reference']}; matched {v['matched']}" for k,v in checks.items()]]
    (output / "CAD_INSPECTION.md").write_text("\n".join(lines), encoding="utf-8")
    return report, main


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--cad", default=str(DEFAULT_CAD))
    p.add_argument("--output", default=str(ROOT / "reports"))
    args = p.parse_args()
    report, _ = inspect(args.cad, args.output)
    print(json.dumps({"instances": len(report["components"]), "dimensions_mm": report["assembly_dimensions_mm"],
                      "all_bom_matched": all(x["matched"] for x in report["bom"]),
                      "unreadable": [x["file"] for x in report["files"] if x.get("readable") is False]}))
