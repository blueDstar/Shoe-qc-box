"""World-space instrument aids; none of these are source CAD."""
import numpy as np
import pyvista as pv
from vtkmodules.vtkRenderingCore import vtkBillboardTextActor3D


def label(plotter,text,position,color="#CBD5E1",size=12):
    actor=vtkBillboardTextActor3D()
    actor.SetInput(text)
    actor.SetPosition(*position)
    actor.GetTextProperty().SetFontSize(size)
    actor.GetTextProperty().SetColor(*pv.Color(color).float_rgb)
    actor.GetTextProperty().SetBold(True)
    actor.SetPickable(False)
    plotter.renderer.AddActor(actor)
    return actor


def ruler(plotter,side,x=None,y=-290):
    sign=-1 if side=="L" else 1
    x=x if x is not None else sign*495
    points=[[x,y,300],[x,y,650]]
    for z in range(300,651,50):
        points.extend([[x,y,z],[x,y+13,z]])
    mesh=pv.PolyData(np.array(points,dtype=float),lines=np.hstack([[2,i,i+1] for i in range(0,len(points),2)]))
    scale=plotter.add_mesh(mesh,color="#CBD5E1",line_width=2,lighting=False,pickable=False,render=False)
    marker=plotter.add_mesh(pv.Sphere(radius=7,center=(x,y,300),theta_resolution=16,phi_resolution=12),color="#00D9FF",lighting=False,pickable=False,render=False)
    trail=plotter.add_mesh(pv.Line((x,y,300),(x,y,301)),color="#00D9FF",line_width=6,lighting=False,pickable=False,render=False)
    labels=[label(plotter,"0 mm",(x,y-10,290),size=11),label(plotter,"350 mm",(x,y-10,665),size=11)]
    value=label(plotter,side+" Z 0.0 mm",(x,y-24,410),"#00D9FF",12)
    return {"scale":scale,"marker":marker,"trail":trail,"labels":labels,"value":value,"x":x,"y":y,"last":None,"text_time":-1,"text_status":None}


def update_ruler(item,door,visible=True,clock=None,text_visible=True):
    for actor in (item["scale"],item["marker"],item["trail"]):
        actor.SetVisibility(visible)
    for actor in (item["value"],*item["labels"]):
        actor.SetVisibility(visible and text_visible)
    if not visible:
        item["last"]=None
        return
    key=(door.position,door.velocity,door.target,door.status)
    if item["last"]==key:
        return
    m=np.eye(4);m[2,3]=door.position
    item["marker"].user_matrix=m
    progress=np.eye(4);progress[2,2]=max(door.position,0.001);progress[2,3]=300*(1-progress[2,2])
    item["trail"].user_matrix=progress
    item["value"].SetPosition(item["x"],item["y"]-24,410+door.position)
    direction="UP +Z" if door.velocity>0 else "DOWN -Z" if door.velocity<0 else "HOLD"
    if text_visible and (clock is None or clock-item["text_time"]>=0.1 or item["text_status"]!=door.status):
        item["value"].SetInput(f"{door.side} {direction}\nZ {door.position:.1f} / {door.limit:.0f} mm\nv {door.velocity:.1f} mm/s")
        item["text_time"]=clock if clock is not None else 0
        item["text_status"]=door.status
    item["last"]=key
