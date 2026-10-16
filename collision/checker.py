from __future__ import annotations

import json
from pathlib import Path
import numpy as np


def overlaps(a, b, tolerance=1e-6):
    return all(min(a[i + 3], b[i + 3]) - max(a[i], b[i]) > tolerance for i in range(3))


def union(a, b):
    return [*[min(a[i], b[i]) for i in range(3)], *[max(a[i+3], b[i+3]) for i in range(3)]]


def translated(b, z):
    out = list(b)
    out[2] += z
    out[5] += z
    return out


def segment_hits_box(a,b,box,radius=0):
    """Slab intersection against an inflated box, conservative for a capsule."""
    a,b=np.array(a),np.array(b)
    lo,hi=np.array(box[:3])-radius,np.array(box[3:])+radius
    t0,t1=0.0,1.0
    for i in range(3):
        delta=b[i]-a[i]
        if abs(delta)<1e-10:
            if a[i]<lo[i] or a[i]>hi[i]:
                return False
        else:
            u,v=(lo[i]-a[i])/delta,(hi[i]-a[i])/delta
            t0,t1=max(t0,min(u,v)),min(t1,max(u,v))
            if t0>t1:
                return False
    return True


def capsule_slice(old,new,xmin,xmax):
    movement=max(np.linalg.norm(np.array(new[k])-old[k]) for k in ("a","b"))
    radius=old["radius"]+movement
    a,b=np.array(old["a"]),np.array(old["b"])
    dx=b[0]-a[0]
    if abs(dx)<1e-10:
        if not xmin-radius<=a[0]<=xmax+radius:
            return None
        p,q=a,b
    else:
        t0,t1=sorted(((xmin-radius-a[0])/dx,(xmax+radius-a[0])/dx))
        t0,t1=max(0,t0),min(1,t1)
        if t0>t1:
            return None
        p,q=a+(b-a)*t0,a+(b-a)*t1
    return [*(np.minimum(p,q)-radius),*(np.maximum(p,q)+radius)]


def common_volume(a, b):
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps
    op = BRepAlgoAPI_Common(a, b)
    if not op.IsDone():
        raise ValueError("CAD boolean common failed")
    props = GProp_GProps()
    BRepGProp.VolumeProperties_s(op.Shape(), props)
    return abs(props.Mass())


def moved(shape, z):
    from OCP.gp import gp_Trsf, gp_Vec
    from OCP.TopLoc import TopLoc_Location
    tr = gp_Trsf()
    tr.SetTranslation(gp_Vec(0, 0, z))
    return shape.Moved(TopLoc_Location(tr))


def preflight(assembly, manifest, output, step=10):
    """CAD broad phase then exact solid boolean at <=10 mm intervals.

    Source overlaps are reported, never silently repaired or presented as validated joints.
    Shutter-vs-fixed geometry must have zero penetration through the complete travel.
    Other generic source contacts remain a documented CAD limitation.
    """
    lookup = {c.id: c for c in assembly.components}
    rows = manifest["components"]
    statics = [x for x in rows if x["group"] == "STATIC_FRAME"]
    results, critical = [], []
    for row in rows:
        if row["group"] not in ("LEFT_DOOR_MOVING", "RIGHT_DOOR_MOVING"):
            continue
        a = lookup[row["id"]].world_shape()
        sweep = union(row["bbox_mm"], translated(row["bbox_mm"], 350))
        for fixed in statics:
            if not overlaps(sweep, fixed["bbox_mm"]):
                continue
            b = lookup[fixed["id"]].world_shape()
            volumes = []
            for pos in np.linspace(0, 350, int(350 / step) + 1):
                if overlaps(translated(row["bbox_mm"], pos), fixed["bbox_mm"]):
                    vol = common_volume(moved(a, float(pos)), b)
                    if vol > 1e-4:
                        volumes.append((float(pos), round(vol, 6)))
            if volumes:
                item = {"moving": row["name"], "fixed": fixed["name"],
                        "samples_with_penetration": len(volumes), "first": volumes[0], "last": volumes[-1],
                        "min_volume_mm3": min(v for _, v in volumes), "max_volume_mm3": max(v for _, v in volumes),
                        "classification": "source_envelope_overlap_unvalidated"}
                results.append(item)
                if row["part_id"] == "P05":
                    critical.append(item)
    data = {"method": "swept AABB broad phase + OpenCascade solid common at 10 mm poses",
            "continuous_proof": False, "critical_shutter_collisions": critical,
            "source_envelope_overlaps": results,
            "note": "Source envelope contacts are not verified assembly mates. They are highlighted and retained without geometry edits."}
    Path(output).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


class CollisionChecker:
    """Runtime conservative swept AABB checks, with aperture containment for DEMO.

    CAD door plates vs fixed obstacles use preflight and stored bounds. All checks
    apply to source positions, independent of exploded/hidden viewport settings.
    """
    def __init__(self, manifest=None):
        self.rows = manifest.get("components", []) if manifest else []
        self.doorways = {"L": [-495, -190, 145, -385, 190, 455],
                         "R": [385, -190, 145, 495, 190, 455]}
        self.chamber = [-397, -257, 3, 397, 257, 557]
        self.auxiliary=[]
        self.fixed_obstacles=[row for row in self.rows if row["part_id"] in ("P06","P07","P10","P13")]

    def doorway_clear(self, side, robots):
        return not any(overlaps(b, self.doorways[side]) for robot in robots.values() for b in robot.bodies())

    def check_door(self, side, old, new, robots):
        name = "SHUTTER_" + side
        row = next((x for x in self.rows if x["name"] == name), None)
        bb = row["bbox_mm"] if row else ([-409,-215,120,-405,215,480] if side == "L" else [405,-215,120,409,215,480])
        sweep = union(translated(bb, old), translated(bb, new))
        for robot in robots.values():
            for b in robot.bodies():
                if overlaps(sweep, b):
                    return "Door vs DEMO shoe/gripper/wrist swept volume"
        for fixed in self.rows:
            if fixed["group"] == "STATIC_FRAME" and overlaps(sweep, fixed["bbox_mm"]):
                return "Door vs fixed CAD component: " + fixed["name"]
        return ""

    def check_robot(self, side, old_bodies, new_bodies, doors, robots,old_parts=None,new_parts=None):
        for i,(old,new) in enumerate(zip(old_bodies,new_bodies)):
            sweep = union(old, new)
            capsule=bool(old_parts and old_parts[i]["kind"]=="capsule")
            previous,current=(old_parts[i],new_parts[i]) if capsule else (None,None)
            for s, zone in self.doorways.items():
                if overlaps(sweep, zone):
                    if not doors[s].fully_open:
                        return "DEMO robot cannot enter until door fully open: " + s
                    aperture=(capsule_slice(previous,current,-411,-394) if s=="L" else capsule_slice(previous,current,394,411)) if capsule else sweep
                    if aperture and (aperture[1] < -185 or aperture[4] > 185 or aperture[2] < 150 or aperture[5] > 450):
                        return "DEMO body outside aperture clearance"
            # Only the volume that projects into the shell must fit the inner chamber.
            if sweep[0] < 400 and sweep[3] > -400:
                chamber_slice=capsule_slice(previous,current,-397,397) if capsule else sweep
                if chamber_slice and (chamber_slice[1] < -252 or chamber_slice[4] > 252 or chamber_slice[2] < 8 or chamber_slice[5] > 552):
                    return "DEMO shoe/gripper/wrist vs enclosure"
            for other_side, robot in robots.items():
                if other_side != side:
                    for b in robot.bodies():
                        if overlaps(sweep, b):
                            return "Left DEMO robot vs right DEMO robot"
            for row in self.fixed_obstacles:
                if overlaps(sweep, row["bbox_mm"]):
                    if capsule and not self._capsule_obstacle(previous,current,row["bbox_mm"]):
                        continue
                    return "DEMO body vs fixed rail/actuator/frame: " + row["name"]
            for name,box in self.auxiliary:
                if overlaps(sweep,box):
                    if capsule and not self._capsule_obstacle(previous,current,box):
                        continue
                    return "DEMO body vs QC camera/lighting hardware: "+name
        return ""

    @staticmethod
    def _capsule_obstacle(old,new,box):
        movement=max(np.linalg.norm(np.array(new[k])-old[k]) for k in ("a","b"))
        return segment_hits_box(old["a"],old["b"],box,old["radius"]+movement)
