from __future__ import annotations

import math
from pathlib import Path
import numpy as np
import pyvista as pv
from config import ROOT
from scene3d.demo_assets import robot_assets,station_assets
from scene3d.annotations import label,ruler,update_ruler
from sensors.geometry import origin as sensor_origin,lens as sensor_lens
from controllers.robot_demo import segment_matrix


class Scene:
    """CAD instance meshes are immutable. Only actor matrices change per frame."""
    def __init__(self,plotter,manifest,selected=None):
        self.plotter,self.manifest,self.selected_callback=plotter,manifest,selected
        self.actors={}
        self.rows={x["id"]:x for x in manifest["components"]}
        self.base={}
        self.selected=None
        self.hide_panels=False
        self.opacity=1.0
        self.explosion=0.0
        self.demo_enabled=True
        self.sensors_visible=False
        self.demo_actors={}
        self.demo_records=[]
        self.station_actors={}
        self.sensor_actors={}
        self.approach_actors={}
        self.fov_visible=False
        self.rig_visible=True
        self.fov_actors=[]
        self._fov_configs=[]
        self._last_fov=None
        self._last_approach=None
        self._visibility={}
        self._opacity={}
        self._led_states={}
        self.zone_actors={}
        self.overlay=True
        self._last_matrices={}
        self._last_demo_matrices={}
        self._last_overlay=""
        self._overlay_actor=None
        self.sensor_emphasis=True
        self.motion_guides=False
        self.external_sensors={}
        self.motion_rulers={}
        self.motion_outlines={}
        self._outline_state={}
        p=plotter
        p.set_background("#080B10")
        p.ren_win.SetMultiSamples(0)
        for row in manifest["components"]:
            mesh=pv.read(str(ROOT/row["mesh"]))
            actor=p.add_mesh(mesh,scalars="CAD_RGB",rgb=True,show_scalar_bar=False,
                             smooth_shading=False,ambient=0.28,diffuse=0.75,specular=0.25,
                             name=row["id"],pickable=True,render=False)
            actor.user_matrix=np.array(row["base_transform"])
            self.actors[row["id"]]=actor
            self.base[row["id"]]=np.array(row["base_transform"])
            self._last_matrices[row["id"]]=self.base[row["id"]].copy()
        # Reference grid and arrows are viewer aids, not CAD.
        points=[]
        for value in range(-1000,1001,100):
            points.extend([[-1000,value,-6],[1000,value,-6],[value,-1000,-6],[value,1000,-6]])
        pts=np.array(points,dtype=float)
        lines=np.hstack([[2,i,i+1] for i in range(0,len(pts),2)])
        grid=pv.PolyData(pts,lines=lines)
        p.add_mesh(grid,color="#203147",opacity=0.4,line_width=1,pickable=False,render=False)
        p.add_axes(line_width=2,labels_off=False)
        for side,x in (("L",-520),("R",520)):
            arrow=pv.Arrow(start=(x,-300,160),direction=(0,0,1),scale=350,tip_length=0.08,shaft_radius=0.008,tip_radius=0.025)
            p.add_mesh(arrow,color="#00D9FF",opacity=0.7,pickable=False,render=False)
        self._build_demo()
        self._build_zones()
        self._build_station()
        self._build_instruments()
        if selected:
            p.enable_mesh_picking(callback=self.pick,use_actor=True,show=False,left_clicking=True,
                                  show_message=False)
        self.camera("Isometric")

    def _build_demo(self):
        p=self.plotter
        for side,sign in (("L",-1),("R",1)):
            self.demo_actors[side]=[]
            for i,(role,mesh,color) in enumerate(robot_assets(side)):
                actor=p.add_mesh(mesh,scalars="DEMO_RGB",rgb=True,show_scalar_bar=False,smooth_shading=True,
                                 pickable=False,name=f"DEMO_{side}_{i}",render=False)
                self.demo_actors[side].append(actor)
                self.demo_records.append({"side":side,"role":role,"actor":actor,"color":color})
            base=pv.Box(bounds=(sign*1180-75,sign*1180+75,-80,80,-5,12))
            self.demo_actors[side].append(p.add_mesh(base,color="#314A60",pickable=False,render=False))

    def _build_zones(self):
        for side,x in (("L",-407),("R",407)):
            mesh=pv.Box(bounds=(x-55,x+55,-190,190,145,455))
            actor=self.plotter.add_mesh(mesh,color="#22C55E",opacity=0.09,style="wireframe",line_width=2,
                                        pickable=False,render=False)
            actor.visibility=False
            self.zone_actors[side]=actor
            for kind,z,y in (("CLOSED",120,-222),("OPEN",470+360,-222)):
                mesh=pv.Box(bounds=(x-10,x+10,y-7,y+7,z-8,z+8))
                housing=self.plotter.add_mesh(mesh,color="#2B475C",pickable=False,render=False)
                led=self.plotter.add_mesh(pv.Sphere(radius=3.8,center=(x-11 if side=="L" else x+11,y,z),theta_resolution=12,phi_resolution=10),color="#22C55E",pickable=False,render=False)
                self.sensor_actors[side,kind]=(housing,led)
            zone=pv.Box(bounds=((-750,-495,-165,165,160,440) if side=="L" else (495,750,-165,165,160,440)))
            self.approach_actors[side]=self.plotter.add_mesh(zone,style="wireframe",color="#FACC15",opacity=0.4,pickable=False,render=False)
            # Optical curtain is a virtual sensor aid; housings are outside the aperture.
            curtain=[]
            for zz in np.linspace(150,450,11):
                curtain.extend([[x,-190,zz],[x,190,zz]])
            data=pv.PolyData(np.array(curtain,dtype=float),lines=np.hstack([[2,i,i+1] for i in range(0,len(curtain),2)]))
            actor=self.plotter.add_mesh(data,color="#00D9FF",opacity=0.45,pickable=False,render=False)
            self.sensor_actors[side,"CURTAIN"]=(actor,actor)

    def _build_instruments(self):
        p=self.plotter
        for side in ("L","R"):
            point=sensor_origin(side);x,y,z=point
            aim=sensor_lens(side)-point;aim/=np.linalg.norm(aim)
            meshes=[pv.Box(bounds=(x-28,x+28,y-15,y+15,z-20,z+20)),
                    pv.Cylinder(center=point+aim*10,direction=aim,radius=11,height=20,resolution=20)]
            housing=p.add_mesh(pv.merge(meshes),color="#EF3340",ambient=0.65,diffuse=0.35,pickable=False,render=False)
            stand=p.add_mesh(pv.merge([pv.Cylinder(center=(x,y,155),direction=(0,0,1),radius=5,height=310,resolution=12),
                                      pv.Box(bounds=(x-28,x+28,y-30,y+30,-5,2))]),color="#6B8094",pickable=False,render=False)
            optic=p.add_mesh(pv.Cylinder(center=sensor_lens(side),direction=aim,radius=8,height=1,resolution=20),color="#FF1744",lighting=False,pickable=False,render=False)
            laser=p.add_mesh(pv.Line((0,0,-0.5),(0,0,0.5)),color="#FF1744",line_width=3,lighting=False,pickable=False,render=False)
            spot=p.add_mesh(pv.Sphere(radius=6,theta_resolution=12,phi_resolution=10),color="#FF1744",lighting=False,pickable=False,render=False)
            caption=p.add_text(side+" LASER DEMO",position=(14,72),font_size=10,color="#FF6872",render=False)
            self.external_sensors[side]={"housing":housing,"stand":stand,"optic":optic,"laser":laser,"spot":spot,"label":caption,"last_text":None,"last_pose":None,"last_state":None}
            self.motion_rulers[side]=ruler(p,side)
        for key,row in self.rows.items():
            if row["part_id"] in ("P05","P08"):
                b=row["bbox_mm"]
                outline=pv.Box(bounds=(b[0]-0.6,b[3]+0.6,b[1]-0.6,b[4]+0.6,b[2]-0.6,b[5]+0.6))
                self.motion_outlines[key]=p.add_mesh(outline,style="wireframe",color="#00E5FF",line_width=2,
                                                   opacity=1.0,lighting=False,pickable=False,render=False)

    def _update_instruments(self,engine):
        for side,item in self.external_sensors.items():
            visible=self.sensor_emphasis and engine.robots[side].advanced
            for name in ("housing","stand","optic","laser","spot","label"):
                item[name].SetVisibility(visible)
            data=engine.sensors.measurements.get(side,{})
            signal=engine.sensors.values[("LEFT" if side=="L" else "RIGHT")+"_APPROACH_SENSOR"]
            hit=data.get("detected",False)
            target=np.array([data.get("leading_x_mm",(-1 if side=="L" else 1)*engine.settings.approach_trigger_mm),0,300],dtype=float) if hit else np.array([(-1 if side=="L" else 1)*engine.settings.approach_trigger_mm,0,300],dtype=float)
            # The visible detection ray stays in the external scan zone; it is a
            # DEMO indication of bounding-volume detection, not optical ray tracing.
            target[0]=np.clip(target[0],-engine.settings.approach_trigger_mm,-495) if side=="L" else np.clip(target[0],495,engine.settings.approach_trigger_mm)
            start=sensor_lens(side)
            pose=tuple(target)
            if item["last_pose"]!=pose:
                m=segment_matrix(start,target);m[:3,2]*=np.linalg.norm(target-start)
                item["laser"].user_matrix=m
                spot=np.eye(4);spot[:3,3]=target;item["spot"].user_matrix=spot
                item["last_pose"]=pose
            color="#FF1744" if signal is not True else "#FF6572"
            if item["last_state"]!=signal:
                item["laser"].prop.color=color
                item["spot"].prop.color="#4ADE80" if signal is True else "#FF1744"
                item["optic"].prop.color="#FFF176" if signal is True else "#FF1744"
                item["last_state"]=signal
            text=f"{side} LASER DEMO\nTRIGGER {engine.settings.approach_trigger_mm-407:.0f} mm\n"+("DETECTED - OPEN REQUEST" if signal is True else "UNKNOWN / FAULT" if signal is None else "SCAN / NO TARGET")
            if ("LEFT" if side=="L" else "RIGHT")+"_APPROACH_SENSOR" in engine.sensors.overrides:
                text=f"{side} LASER DEMO / TEST INPUT\nGAP {data.get('door_gap_mm',0):.0f} / {engine.settings.approach_trigger_mm-407:.0f} mm\nRAW {signal}"
            if item["last_text"]!=text:
                item["label"].SetInput(text);item["last_text"]=text
            item["label"].SetDisplayPosition(14 if side=="L" else max(14,self.plotter.window_size[0]-315),18)
            update_ruler(self.motion_rulers[side],engine.doors[side],self.motion_guides,engine.time,text_visible=False)
            # Numeric live readouts are in the sidebar and close-view tab. Main
            # view retains ticks/marker without repainting moving text every frame.
        for key,actor in self.motion_outlines.items():
            row=self.rows[key];side="L" if row["group"].startswith("LEFT") else "R"
            state=(engine.doors[side].position,self.motion_guides and self.explosion==0 and bool(row.get("visible",True)))
            if self._outline_state.get(key)!=state:
                actor.visibility=state[1]
                if state[1]:
                    m=np.eye(4);m[2,3]=state[0];actor.user_matrix=m
                self._outline_state[key]=state

    def _build_station(self):
        for name,mesh,color in station_assets():
            self.station_actors[name]=self.plotter.add_mesh(mesh,color=color,smooth_shading="LENS" in name,
                                                           pickable=False,name="DEMO_"+name,render=False)
        from qc.station import CAMERA_POSES
        for cfg in CAMERA_POSES.values():
            eye=np.array(cfg["eye"],dtype=float)
            forward=np.array(cfg["target"])-eye;forward/=np.linalg.norm(forward)
            right=np.cross(forward,cfg["up"]);right/=np.linalg.norm(right)
            up=np.cross(right,forward)
            center=eye+forward*180
            corners=[center+sx*240*right+sy*180*up for sx,sy in ((-1,-1),(1,-1),(1,1),(-1,1))]
            pts=np.array([eye,*corners])
            edges=[[0,1],[0,2],[0,3],[0,4],[1,2],[2,3],[3,4],[4,1]]
            mesh=pv.PolyData(pts,lines=np.hstack([[2,a,b] for a,b in edges]))
            self.fov_actors.append(self.plotter.add_mesh(mesh,color="#00D9FF",opacity=0.5,pickable=False,render=False))
            self._fov_configs.append((eye,np.c_[right,up,forward]))

    def pick(self,actor):
        for key,item in self.actors.items():
            if item==actor:
                self.select(key)
                if self.selected_callback:
                    self.selected_callback(key)
                break

    def select(self,key):
        if self.selected in self.actors:
            self.actors[self.selected].mapper.scalar_visibility=True
        self.selected=key
        if key in self.actors:
            actor=self.actors[key]
            actor.mapper.scalar_visibility=False
            actor.prop.color="#00FFBC"
        self.plotter.render()

    def camera(self,view):
        p=self.plotter
        # CAMERA positions use the full CAD envelope; DEMO proxies do not distort Fit All.
        targets={"Isometric":((-1550,-1550,1350),(0,0,420),(0,0,1)),
                 "Front":((0,-1900,430),(0,0,430),(0,0,1)),
                 "Top":((0,0,2400),(0,0,350),(0,1,0)),
                 "Left":((-2200,0,430),(0,0,430),(0,0,1)),
                 "Right":((2200,0,430),(0,0,430),(0,0,1))}
        if view in ("Fit All","Reset Camera"):
            view="Isometric"
        p.camera_position=targets[view]
        p.camera.parallel_projection=True
        p.camera.parallel_scale=850
        p.render()

    def restore(self):
        self.hide_panels=False
        self.explosion=0
        self.opacity=1
        for row in self.rows.values():
            row["visible"]=True
        self.select(None)
        self.camera("Isometric")

    def update(self,engine,render=True):
        self._update_instruments(engine)
        for key,row in self.rows.items():
            actor=self.actors[key]
            m=self.base[key].copy()
            group=row["group"]
            excluded=engine.settings.mechanism_scope=="PLATE_AND_BLOCKS" and row["part_id"] in ("P09","P11")
            z=engine.doors["L" if group.startswith(("LEFT","L_")) else "R"].position if group!="STATIC_FRAME" and not excluded else 0
            if group.endswith("ACTUATOR_ROD_PARAMETRIC"):
                # Dedicated parametric rod: measured radius and fixed lower endpoint.
                # Scaling is only for this explicitly parameterized envelope, never a rigid CAD part.
                local_min=row["bbox_mm"][2]
                length=row["dimensions_mm"][2]
                param=np.eye(4)
                param[2,2]=(length+z)/length
                param[2,3]=local_min*(1-param[2,2])
                m=param@m
            elif group!="STATIC_FRAME":
                motion=np.eye(4)
                motion[:3,3]=np.linalg.solve(m[:3,:3],np.array([0,0,z]))
                m=m@motion
            if self.explosion:
                b=row["bbox_mm"]
                center=(np.array(b[:3])+np.array(b[3:]))/2-np.array([0,0,280])
                norm=np.linalg.norm(center)
                if norm:
                    m[:3,3]+=self.explosion*center/norm
            if not np.array_equal(self._last_matrices[key],m):
                actor.user_matrix=m
                self._last_matrices[key]=m.copy()
            panel_hidden=self.hide_panels and row["part_id"] in ("P02","P03")
            visible=bool(row.get("visible",True)) and not excluded and not panel_hidden
            if self._visibility.get(key)!=visible:
                actor.visibility=visible
                self._visibility[key]=visible
            opacity=self.opacity if row["part_id"] in ("P01","P02","P03","P04") else 1.0
            if self._opacity.get(key)!=opacity:
                actor.prop.opacity=opacity
                self._opacity[key]=opacity
        matrices={s:r.matrices() for s,r in engine.robots.items()}
        for i,record in enumerate(self.demo_records):
            actor=record["actor"]
            m=matrices[record["side"]].get(record["role"])
            visible=self.demo_enabled and m is not None
            if actor.visibility!=visible:
                actor.visibility=visible
            if m is not None and (i not in self._last_demo_matrices or not np.array_equal(self._last_demo_matrices[i],m)):
                actor.user_matrix=m
                self._last_demo_matrices[i]=m.copy()
        for side,actors in self.demo_actors.items():
            actors[-1].visibility=self.demo_enabled and engine.robots[side].advanced
        for side,actor in self.zone_actors.items():
            if actor.visibility!=self.sensors_visible:
                actor.visibility=self.sensors_visible
            if self.sensors_visible:
                actor.prop.color="#22C55E" if engine.sensors.values[("LEFT" if side=="L" else "RIGHT")+"_CLEAR_SENSOR"] else "#EF4444"
        for (side,kind),(housing,led) in self.sensor_actors.items():
            visible=engine.robots[side].advanced and (self.sensors_visible if kind=="CURTAIN" else True)
            if housing.visibility!=visible:
                housing.visibility=visible
            if led.visibility!=visible:
                led.visibility=visible
            signal=("CLEAR_SENSOR" if kind=="CURTAIN" else "DOOR_"+kind+"_SENSOR" if kind in ("OPEN","CLOSED") else "APPROACH_SENSOR")
            value=engine.sensors.values[("LEFT" if side=="L" else "RIGHT")+"_"+signal]
            color="#22C55E" if value else "#EF4444"
            if self._led_states.get((side,kind),"unset")!=value:
                led.prop.color=color
                self._led_states[side,kind]=value
        for side,actor in self.approach_actors.items():
            actor.visibility=self.sensors_visible and engine.robots[side].advanced
            if self._last_approach!=engine.settings.approach_trigger_mm:
                scale=(engine.settings.approach_trigger_mm-495)/255
                m=np.eye(4);m[0,0]=scale;m[0,3]=(-1 if side=="L" else 1)*495*(1-scale)
                actor.user_matrix=m
        self._last_approach=engine.settings.approach_trigger_mm
        for name,actor in self.station_actors.items():
            actor.visibility=self.rig_visible and engine.settings.qc_station_enabled
            if "STATUS" in name:
                active=engine.time<engine.qc.exposure_until
                color="#00D9FF" if active else "#22C55E" if engine.qc.ready[name.split('_')[0]] else "#EF4444"
                if self._led_states.get(name)!=color:
                    actor.prop.color=color
                    self._led_states[name]=color
        for actor,(eye,basis) in zip(self.fov_actors,self._fov_configs):
            actor.visibility=self.fov_visible and self.rig_visible and engine.settings.qc_station_enabled
            if self._last_fov!=engine.settings.qc_camera_fov_deg:
                scale=math.tan(math.radians(engine.settings.qc_camera_fov_deg)/2)
                m=np.eye(4);m[:3,:3]=basis@np.diag([scale,scale,1])@basis.T
                m[:3,3]=eye-m[:3,:3]@eye
                actor.user_matrix=m
        self._last_fov=engine.settings.qc_camera_fov_deg
        if self.overlay:
            text=(f"HILYKAN   /   STEP Rev A   /   mm\n"
                  f"L {engine.doors['L'].position:6.1f} mm    R {engine.doors['R'].position:6.1f} mm\n"
                  f"{engine.sequence.state}   |   t {engine.time:6.2f} s\n"
                  f"{engine.settings.mechanism_scope} — P09/P11 excluded" if engine.settings.mechanism_scope=="PLATE_AND_BLOCKS" else "FULL CAD — source clash check")
            if engine.settings.mechanism_scope=="FULL_ASSEMBLY":
                text=f"HILYKAN / STEP / mm\nL {engine.doors['L'].position:.1f}   R {engine.doors['R'].position:.1f}\nFULL ASSEMBLY — source clashes block motion"
            if self.demo_enabled:
                text+="\nDEMO: fixed-link arm / held sneaker / optical sensors"
                if engine.settings.qc_station_enabled:
                    text+=f"\nQC {engine.qc.face} | {len(engine.qc.captured)}/6 views | FRONT + TOP cameras"
            if engine.fault:
                text+="\nFAULT: "+engine.fault
            if self._overlay_actor is None:
                self._overlay_actor=self.plotter.add_text(text,position=(14,self.plotter.window_size[1]-20),font_size=10,
                                                         color="#CBD5E1",name="motion_overlay",render=False)
                self._overlay_actor.GetTextProperty().SetVerticalJustificationToTop()
            elif self._last_overlay!=text:
                self._overlay_actor.SetInput(text)
            self._overlay_actor.SetDisplayPosition(14,self.plotter.window_size[1]-20)
            self._last_overlay=text
            self._overlay_actor.SetVisibility(True)
        else:
            if self._overlay_actor is not None:
                self._overlay_actor.SetVisibility(False)
        if render:
            self.plotter.render()

    def orbit(self,angle):
        a=math.radians(angle)
        self.plotter.camera.position=(-1850*math.cos(a),-1850*math.sin(a),1300)
        self.plotter.camera.focal_point=(0,0,420)
        self.plotter.camera.up=(0,0,1)
