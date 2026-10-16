"""Actual perspective VTK camera images, rendered lazily from cached scene meshes."""
from __future__ import annotations

from pathlib import Path
import json
import numpy as np
import pyvista as pv
from vtkmodules.vtkRenderingCore import vtkActor, vtkProperty, vtkPolyDataMapper
from controllers.robot_demo import DemoRobot
from qc.station import CAMERA_POSES


class CameraPreview:
    def __init__(self,scene,width=400,height=300):
        self.scene=scene
        self.plotter=pv.Plotter(off_screen=True,window_size=(width,height))
        self.plotter.set_background("#192332")
        self.plotter.ren_win.SetMultiSamples(0)
        self.cad={}
        self.demo=[]
        self.hardware=[]
        for key,actor in scene.actors.items():
            self.cad[key]=self._clone(actor,cad=True)
        for record in scene.demo_records:
            self.demo.append((record,self._clone(record["actor"])))
        for side,actors in scene.demo_actors.items():
            self.hardware.append(self._clone(actors[-1]))
        for actor in scene.station_actors.values():
            self.hardware.append(self._clone(actor))
        self.plotter.camera.parallel_projection=False
        self.plotter.camera.clipping_range=(5,1500)
        self._initialized=False

    def _clone(self,source,cad=False):
        actor=vtkActor()
        # Share immutable geometry, not OpenGL mapper resources across render windows.
        mapper=vtkPolyDataMapper()
        mapper.SetInputData(source.GetMapper().GetInput())
        colored=cad or bool(source.GetMapper().GetInput().GetCellData().HasArray("DEMO_RGB"))
        if colored:
            mapper.SetScalarModeToUseCellFieldData()
            mapper.SetColorModeToDirectScalars()
            mapper.SelectColorArray("CAD_RGB" if cad else "DEMO_RGB")
            mapper.ScalarVisibilityOn()
        else:
            mapper.ScalarVisibilityOff()
        actor.SetMapper(mapper)
        prop=vtkProperty()
        prop.DeepCopy(source.GetProperty())
        prop.SetOpacity(1.0)
        actor.SetProperty(prop)
        actor.SetPickable(False)
        self.plotter.renderer.AddActor(actor)
        return actor

    @staticmethod
    def set_matrix(actor,array):
        from pyvista.core.utilities.arrays import vtkmatrix_from_array
        actor.SetUserMatrix(vtkmatrix_from_array(array))

    def render(self,engine,camera="FRONT",record=None):
        p=self.plotter
        doors=record["doors"] if record else {s:d.position for s,d in engine.doors.items()}
        robots={}
        for side,live in engine.robots.items():
            robot=DemoRobot(side)
            robot.restore(record["robots"][side] if record else live.snapshot())
            robots[side]=robot
        for key,actor in self.cad.items():
            row=self.scene.rows[key]
            group=row["group"]
            m=self.scene.base[key].copy()
            excluded=engine.settings.mechanism_scope=="PLATE_AND_BLOCKS" and row["part_id"] in ("P09","P11")
            z=doors["L" if group.startswith(("LEFT","L_")) else "R"] if group!="STATIC_FRAME" and not excluded else 0
            if group.endswith("ACTUATOR_ROD_PARAMETRIC"):
                param=np.eye(4)
                param[2,2]=(row["dimensions_mm"][2]+z)/row["dimensions_mm"][2]
                param[2,3]=row["bbox_mm"][2]*(1-param[2,2])
                m=param@m
            else:
                m[2,3]+=z
            self.set_matrix(actor,m)
            actor.SetVisibility(not excluded)
        matrices={s:r.matrices() for s,r in robots.items()}
        for source,actor in self.demo:
            m=matrices[source["side"]].get(source["role"])
            actor.SetVisibility(m is not None)
            if m is not None:
                self.set_matrix(actor,m)
        for actor in self.hardware:
            actor.SetVisibility(engine.settings.qc_station_enabled)
        cfg=CAMERA_POSES[camera]
        p.camera_position=(cfg["eye"],cfg["target"],cfg["up"])
        p.camera.parallel_projection=False
        p.camera.view_angle=record.get("camera_fov_deg",engine.settings.qc_camera_fov_deg) if record else engine.settings.qc_camera_fov_deg
        p.camera.clipping_range=(5,1500)
        if not self._initialized:
            p.show(auto_close=False,interactive=False)
            self._initialized=True
        else:
            p.render()
        return np.ascontiguousarray(p.screenshot(return_img=True)[:,:,:3])

    def save_record(self,engine,record,directory):
        import cv2
        directory=Path(directory)
        directory.mkdir(parents=True,exist_ok=True)
        stem=f"{record['id']:04d}_{record['side']}_{record['face']}"
        result={"metadata":record,"images":{}}
        for camera in CAMERA_POSES:
            path=directory/(stem+"_"+camera+".png")
            rgb=self.render(engine,camera,record)
            if not cv2.imwrite(str(path),cv2.cvtColor(rgb,cv2.COLOR_RGB2BGR)):
                raise RuntimeError("Unable to write QC capture image")
            result["images"][camera]=str(path)
        (directory/(stem+".json")).write_text(json.dumps(result,indent=2),encoding="utf-8")
        return result

    def close(self):
        self.plotter.close()
