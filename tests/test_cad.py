import json
import numpy as np
import pytest
from cad_import.step_reader import StepAssembly, sha256
from config import ROOT


def test_actual_cad_inventory_bom_units_and_geometry(manifest):
    assert manifest["unit"]=="mm"
    assert len([x for x in manifest["files"] if x.get("readable")])==17
    assert len(manifest["components"])==48
    assert all(x["matched"] for x in manifest["bom"])
    assert all(x["valid"] for x in manifest["components"])
    assert manifest["assembly_dimensions_mm"]==pytest.approx([954,572,890])
    left=next(x for x in manifest["components"] if x["name"]=="SHUTTER_L")
    right=next(x for x in manifest["components"] if x["name"]=="SHUTTER_R")
    assert left["dimensions_mm"]==right["dimensions_mm"]==[4,430,360]
    assert (left["bbox_mm"][0]+left["bbox_mm"][3])/2==-407
    assert (right["bbox_mm"][0]+right["bbox_mm"][3])/2==407
    assert all(x["group"]=="STATIC_FRAME" for x in manifest["components"] if x["part_id"] in ("P07","P10","P06"))


def test_step_color_and_tessellation_preserved(manifest):
    import pyvista as pv
    for row in manifest["components"]:
        assert row["color_source"]=="STEP"
        mesh=pv.read(str(ROOT/row["mesh"]))
        assert mesh.n_points>0 and mesh.n_cells>0
        assert "CAD_RGB" in mesh.cell_data
        m=np.array(row["base_transform"])
        points=np.c_[mesh.points,np.ones(mesh.n_points)]@m.T
        box=[*points[:,:3].min(axis=0),*points[:,:3].max(axis=0)]
        assert np.max(np.abs(np.array(box)-row["bbox_mm"]))<=0.16
    door=next(x for x in manifest["components"] if x["part_id"]=="P05")
    assert door["color"]==pytest.approx([240/255,163/255,74/255],abs=1e-6)


def test_alternate_states_measure_travel_and_rod_extension(manifest):
    for file,side in (("GA_ASSEMBLY_L_OPEN.step","L"),("GA_ASSEMBLY_R_OPEN.step","R")):
        changes=manifest["state_comparisons"][file]
        assert len(changes)==11
        assert changes["SHUTTER_"+side]==[0,0,350,0,0,350]
        assert changes["ACT_ROD_"+side]==[0,0,0,0,0,350]
        assert not any(name.startswith("RAIL") for name in changes)


def test_original_cad_files_have_not_changed(manifest):
    for record in manifest["files"]:
        if "sha256" in record:
            assert sha256(ROOT/"Shoe_QC_Dual_Shutter_STEP_CAD_BOM_RevA"/"STEP"/record["file"])==record["sha256"]


def test_real_source_collisions_are_reported(manifest):
    p=manifest["preflight"]
    assert p["critical_shutter_collisions"]==[]
    assert len(p["source_envelope_overlaps"])==14
    assert any(x["fixed"]=="RAIL_L_B" for x in p["source_envelope_overlaps"])


def test_xde_repeated_instances_not_lost():
    a=StepAssembly(ROOT/"Shoe_QC_Dual_Shutter_STEP_CAD_BOM_RevA"/"STEP"/"GA_ASSEMBLY_CLOSED.step")
    assert len(a.components)==48
    assert len({c.id for c in a.components})==48
    assert len([c for c in a.components if c.name.startswith("BLOCK_")])==8
