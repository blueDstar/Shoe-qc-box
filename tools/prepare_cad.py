from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from config import Settings
from cad_manifest.inspect import inspect
from cad_import.cache import prepare
from cad_import.step_reader import sha256
from collision.checker import preflight


def prepare_assets(settings,force=False,progress=None):
    notify=progress or (lambda message: None)
    manifest_path=ROOT/"config"/"cad_manifest.json"
    source=settings.cad_directory/settings.main_assembly
    if manifest_path.exists() and not force:
        existing=json.loads(manifest_path.read_text(encoding="utf-8"))
        record=next((x for x in existing["files"] if x["file"]==source.name),{})
        source_files_unchanged=all((settings.cad_directory/x["file"]).is_file() and sha256(settings.cad_directory/x["file"])==x["sha256"] for x in existing["files"] if "sha256" in x)
        if existing["cad_path"]==str(settings.cad_directory) and source_files_unchanged and record.get("sha256")==sha256(source) and all((ROOT/x["mesh"]).exists() for x in existing["components"]) and existing["tessellation"]["linear_deflection_mm"]==settings.linear_deflection_mm and existing["tessellation"]["angular_deflection_rad"]==settings.angular_deflection_rad:
            notify("Mesh cache verified against STEP SHA256")
            return existing
    notify("Reading STEP/XDE, BOM and alternate states…")
    report,assembly=inspect(settings.cad_directory)
    if report["main_assembly"]!=settings.main_assembly:
        raise ValueError("Choose the measured CLOSED main assembly; alternate states cannot be stacked.")
    notify("CAD collision preflight…")
    report["preflight"]=preflight(assembly,report,ROOT/"reports"/"collision_preflight.json")
    notify("Tessellating CAD faces and writing mesh/BRep cache…")
    manifest=prepare(report,assembly,ROOT/"cache",settings.linear_deflection_mm,settings.angular_deflection_rad)
    manifest_path.write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding="utf-8")
    return manifest


if __name__=="__main__":
    settings=Settings()
    manifest=prepare_assets(settings,progress=print)
    settings.kinematics_confirmed=True
    settings.confirmed_source_sha256=sha256(settings.cad_directory/settings.main_assembly)
    settings.save(ROOT/"config"/"default.json")
    print("Prepared",len(manifest["components"]),"source instances; approved plate/block/parametric-rod scope.")
