"""Close views of the same source CAD instances, using the live door engine."""
import numpy as np
from vtkmodules.vtkRenderingCore import vtkActor,vtkPolyDataMapper,vtkProperty
from pyvista.core.utilities.arrays import vtkmatrix_from_array
from scene3d.annotations import ruler,update_ruler,label


class DoorDetail:
    def __init__(self,plotter,scene,side):
        self.plotter,self.scene,self.side=plotter,scene,side
        self.actors={};self.last={};self.rows={};self.outlines={}
        p=plotter;p.set_background("#080B10");p.ren_win.SetMultiSamples(0)
        for key,row in scene.rows.items():
            name=row["name"]
            if not (name.endswith("_"+side) or ("_"+side+"_") in name):
                continue
            source=scene.actors[key]
            mapper=vtkPolyDataMapper();mapper.SetInputData(source.GetMapper().GetInput())
            mapper.SetScalarModeToUseCellFieldData();mapper.SetColorModeToDirectScalars();mapper.SelectColorArray("CAD_RGB")
            actor=vtkActor();actor.SetMapper(mapper)
            prop=vtkProperty();prop.DeepCopy(source.GetProperty());prop.SetOpacity(1)
            actor.SetProperty(prop);actor.SetPickable(False);p.renderer.AddActor(actor)
            self.actors[key]=actor;self.rows[key]=row
            if key in scene.motion_outlines:
                clone=vtkActor();m=vtkPolyDataMapper();m.SetInputData(scene.motion_outlines[key].GetMapper().GetInput())
                clone.SetMapper(m);clone.GetProperty().SetRepresentationToWireframe();clone.GetProperty().SetColor(0,0.9,1)
                clone.GetProperty().SetLineWidth(2);clone.SetPickable(False);p.renderer.AddActor(clone)
                self.outlines[key]=clone
        sign=-1 if side=="L" else 1
        self.scale=ruler(p,side,x=sign*490,y=-300)
        p.camera_position=((sign*1850,-110,470),(sign*430,0,430),(0,0,1))
        p.camera.parallel_projection=True;p.camera.parallel_scale=490;p.add_axes()
        self.note=p.add_text("",position=(12,p.window_size[1]-18),font_size=10,color="#CBD5E1",render=False)
        self.note.GetTextProperty().SetVerticalJustificationToTop()
        self.labels=[label(p,"FIXED RAIL P07",(sign*482,237,890),"#B3C8D8",10),
                     label(p,"ACTUATOR BODY FIXED",(sign*482,300,45),"#B3C8D8",10)]

    def update(self,engine,render=True):
        widget=self.plotter.interactor
        ratio=widget.devicePixelRatioF()
        size=(max(1,int(widget.width()*ratio)),max(1,int(widget.height()*ratio)))
        if tuple(self.plotter.window_size)!=size:
            self.plotter.ren_win.SetSize(*size)
        d=engine.doors[self.side]
        for key,row in self.rows.items():
            m=np.array(row["base_transform"])
            moving=row["group"] in ("LEFT_DOOR_MOVING","RIGHT_DOOR_MOVING")
            excluded=engine.settings.mechanism_scope=="PLATE_AND_BLOCKS" and row["part_id"] in ("P09","P11")
            if row["group"].endswith("ACTUATOR_ROD_PARAMETRIC"):
                t=np.eye(4);t[2,2]=(row["dimensions_mm"][2]+d.position)/row["dimensions_mm"][2]
                t[2,3]=row["bbox_mm"][2]*(1-t[2,2]);m=t@m
            elif moving and not excluded:
                m[2,3]+=d.position
            if key not in self.last or not np.array_equal(self.last[key],m):
                self.actors[key].SetUserMatrix(vtkmatrix_from_array(m));self.last[key]=m.copy()
            self.actors[key].SetVisibility(not excluded and bool(row.get("visible",True)))
            if key in self.outlines:
                o=np.eye(4);o[2,3]=d.position if moving else 0
                self.outlines[key].SetUserMatrix(vtkmatrix_from_array(o))
                self.outlines[key].SetVisibility(engine.settings.kinematics_confirmed and not excluded)
        update_ruler(self.scale,d,clock=engine.time)
        self.note.SetDisplayPosition(12,self.plotter.window_size[1]-18)
        self.note.SetInput(f"{self.side} LINEAR MOTION +Z / mm\nP05/P08 MOVING — P07/P06/P10 FIXED\nP09/P11 source clashes: excluded")
        if render:
            self.plotter.render()
