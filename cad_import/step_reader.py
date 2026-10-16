from __future__ import annotations

import hashlib
import re
from pathlib import Path
from dataclasses import dataclass

import numpy as np
from OCP.STEPCAFControl import STEPCAFControl_Reader
from OCP.IFSelect import IFSelect_RetDone
from OCP.TDocStd import TDocStd_Document
from OCP.TCollection import TCollection_ExtendedString
from OCP.XCAFDoc import XCAFDoc_DocumentTool, XCAFDoc_ColorType
from OCP.TDF import TDF_Label, TDF_LabelSequence
from OCP.TDataStd import TDataStd_Name
from OCP.TopLoc import TopLoc_Location
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.BRep import BRep_Tool
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_FACE, TopAbs_REVERSED, TopAbs_SOLID
from OCP.TopoDS import TopoDS
from OCP.Quantity import Quantity_Color, Quantity_TOC_sRGB


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bounds(shape):
    b = Bnd_Box()
    BRepBndLib.AddOptimal_s(shape, b, False, False)
    return [float(v) for v in b.Get()]


def matrix(loc):
    tr = loc.Transformation()
    out = np.eye(4)
    for r in range(3):
        for c in range(4):
            out[r, c] = tr.Value(r + 1, c + 1)
    return out


def metadata(path):
    raw = Path(path).read_text(encoding="utf-8", errors="replace")
    return {
        "file": Path(path).name, "bytes": Path(path).stat().st_size,
        "sha256": sha256(path),
        "schema": re.findall(r"FILE_SCHEMA\(\((.*?)\)\)", raw, re.S),
        "unit": "mm" if "SI_UNIT(.MILLI.,.METRE.)" in raw else "UNCONFIRMED",
        "products": re.findall(r"PRODUCT\('([^']*)'", raw),
        "assembly_occurrences": raw.count("NEXT_ASSEMBLY_USAGE_OCCURRENCE("),
        "has_color": "COLOUR_RGB(" in raw,
    }


@dataclass
class Component:
    id: str
    name: str
    shape: object
    base_transform: np.ndarray
    color: tuple
    color_source: str
    label: object
    definition: object
    color_tool: object
    source: str

    def world_shape(self):
        from OCP.gp import gp_Trsf
        t = gp_Trsf()
        t.SetValues(*self.base_transform[:3, :].ravel().tolist())
        return self.shape.Moved(TopLoc_Location(t))

    def bbox(self):
        return bounds(self.world_shape())


class StepAssembly:
    def __init__(self, path):
        self.path = Path(path).resolve()
        self.meta = metadata(path)
        self.doc = TDocStd_Document(TCollection_ExtendedString("MDTV-XCAF"))
        reader = STEPCAFControl_Reader()
        reader.SetColorMode(True)
        reader.SetNameMode(True)
        reader.SetLayerMode(True)
        if reader.ReadFile(str(self.path)) != IFSelect_RetDone:
            raise ValueError("Cannot read STEP: " + str(self.path))
        if not reader.Transfer(self.doc):
            raise ValueError("STEP transfer failed: " + str(self.path))
        self.shape_tool = XCAFDoc_DocumentTool.ShapeTool_s(self.doc.Main())
        self.color_tool = XCAFDoc_DocumentTool.ColorTool_s(self.doc.Main())
        self.components = []
        roots = TDF_LabelSequence()
        self.shape_tool.GetFreeShapes(roots)
        for i in range(1, roots.Length() + 1):
            self._walk(roots.Value(i), np.eye(4), str(i), None)
        if not self.components:
            raise ValueError("STEP has no renderable shapes: " + str(self.path))

    @staticmethod
    def name(label):
        a = TDataStd_Name()
        return str(a.Get().ToExtString()) if label.FindAttribute(TDataStd_Name.GetID_s(), a) else ""

    def color(self, *items):
        for item in items:
            if item is None:
                continue
            for kind in (XCAFDoc_ColorType.XCAFDoc_ColorSurf, XCAFDoc_ColorType.XCAFDoc_ColorGen):
                c = Quantity_Color()
                get = self.color_tool.GetColor_s if isinstance(item, TDF_Label) else self.color_tool.GetColor
                if get(item, kind, c):
                    return tuple(c.Values(Quantity_TOC_sRGB)), "STEP"
        return (0.65, 0.72, 0.79), "fallback"

    def _walk(self, label, parent, path, occurrence_name):
        st = self.shape_tool
        if st.IsReference_s(label):
            referred = TDF_Label()
            st.GetReferredShape_s(label, referred)
            placed = parent @ matrix(st.GetLocation_s(label))
            self._walk(referred, placed, path, (self.name(label), label))
            return
        if st.IsAssembly_s(label):
            children = TDF_LabelSequence()
            st.GetComponents_s(label, children, False)
            for i in range(1, children.Length() + 1):
                self._walk(children.Value(i), parent, path + "/" + str(i), None)
            return
        shape = st.GetShape_s(label)
        if shape.IsNull():
            return
        name = occurrence_name[0] if occurrence_name and occurrence_name[0] else self.name(label)
        occ_label = occurrence_name[1] if occurrence_name else label
        color, source = self.color(occ_label, label, shape)
        self.components.append(Component(path, name or "Component_" + path, shape, parent,
                                         color, source, occ_label, label, self.color_tool, str(self.path)))


def tessellate(component, linear=0.15, angular=0.25):
    """Faces are tessellated in definition coordinates; instance placement stays separate."""
    import pyvista as pv
    BRepMesh_IncrementalMesh(component.shape, linear, False, angular, True).Perform()
    points, faces, rgb = [], [], []
    ex = TopExp_Explorer(component.shape, TopAbs_FACE)
    while ex.More():
        face = TopoDS.Face_s(ex.Current())
        loc = TopLoc_Location()
        tri = BRep_Tool.Triangulation_s(face, loc)
        if tri is not None and tri.NbNodes():
            start = len(points)
            for n in range(1, tri.NbNodes() + 1):
                p = tri.Node(n).Transformed(loc.Transformation())
                points.append([p.X(), p.Y(), p.Z()])
            color = component.color
            c = Quantity_Color()
            if component.color_tool.GetColor(face, XCAFDoc_ColorType.XCAFDoc_ColorSurf, c):
                color = tuple(c.Values(Quantity_TOC_sRGB))
            for t in range(1, tri.NbTriangles() + 1):
                inds = list(tri.Triangle(t).Get())
                if face.Orientation() == TopAbs_REVERSED:
                    inds.reverse()
                faces.extend([3] + [start + k - 1 for k in inds])
                rgb.append([round(v * 255) for v in color])
        ex.Next()
    if not points:
        raise ValueError("No triangulation for " + component.name)
    mesh = pv.PolyData(np.array(points), np.array(faces))
    mesh.cell_data["CAD_RGB"] = np.array(rgb, dtype=np.uint8)
    return mesh


def solid_count(shape):
    count, ex = 0, TopExp_Explorer(shape, TopAbs_SOLID)
    while ex.More():
        count += 1
        ex.Next()
    return count


def is_valid(shape):
    return BRepCheck_Analyzer(shape).IsValid()
