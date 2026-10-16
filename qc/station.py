from __future__ import annotations

from collections import deque
import math
import numpy as np

CAMERA_POSES={"FRONT":{"eye":(0,-235,300),"target":(0,0,300),"up":(0,0,1)},
              "TOP":{"eye":(0,0,507),"target":(0,0,300),"up":(0,1,0)}}
HARDWARE=[("FRONT_CAMERA_BODY",[-32,-255,275,32,-243,325]),("FRONT_CAMERA_LENS",[-15,-243,285,15,-235,315]),
          ("TOP_CAMERA_BODY",[-35,-25,520,35,25,552]),("TOP_CAMERA_LENS",[-16,-16,507,16,16,520]),
          ("FRONT_LED_LEFT",[-195,-253,180,-179,-240,420]),("FRONT_LED_RIGHT",[179,-253,180,195,-240,420])]
NORMALS={"INNER":np.array([0,-1,0]),"OUTER":np.array([0,1,0]),"UPPER":np.array([0,0,1]),
         "OUTSOLE":np.array([0,0,-1]),"TOE":np.array([1,0,0]),"HEEL":np.array([-1,0,0])}


def projection(camera,points,fov_deg,width=400,height=300):
    cfg=CAMERA_POSES[camera]
    eye=np.array(cfg["eye"],dtype=float)
    forward=np.array(cfg["target"])-eye
    forward/=np.linalg.norm(forward)
    right=np.cross(forward,cfg["up"])
    right/=np.linalg.norm(right)
    up=np.cross(right,forward)
    delta=np.array(points)-eye
    depth=delta@forward
    vertical=math.tan(math.radians(fov_deg)/2)
    horizontal=vertical*width/height
    x=(delta@right)/np.maximum(depth,1e-9)/horizontal
    y=(delta@up)/np.maximum(depth,1e-9)/vertical
    return np.c_[width*(x+1)/2,height*(1-y)/2],bool(np.all(depth>5) and np.all(np.abs(x)<=1) and np.all(np.abs(y)<=1))


class QCStation:
    def __init__(self,settings):
        self.settings=settings
        self.ready={"FRONT":True,"TOP":True}
        self.records=deque(maxlen=240)
        self.captured=set()
        self.face="IDLE"
        self.exposure_until=0.0
        self.cycle_id=None
        self.serial=0

    def begin(self,cycle_id):
        self.cycle_id=cycle_id
        self.captured.clear()
        self.face="ALIGN"

    def capture(self,engine,side,face):
        if not self.settings.qc_station_enabled:
            self.captured.add(face)
            return True
        if not all(self.ready.values()) or any(engine.sensors.values.get("CAMERA_"+name+"_READY") is not True for name in CAMERA_POSES):
            return False
        robot=engine.robots[side]
        m=robot.matrix()
        normal=m[:3,:3]@NORMALS[face]
        toward=np.array(CAMERA_POSES["FRONT"]["eye"])-m[:3,3]
        toward/=np.linalg.norm(toward)
        alignment=float(normal@toward)
        views={}
        for camera in CAMERA_POSES:
            pixels,in_frame=projection(camera,robot.shoe_corners(),self.settings.qc_camera_fov_deg)
            views[camera]={"ready":self.ready[camera],"shoe_in_frame":in_frame,
                           "projected_bounds_px":[*pixels.min(axis=0).tolist(),*pixels.max(axis=0).tolist()]}
        if alignment<0.97 or not views["FRONT"]["shoe_in_frame"]:
            return engine.trip("QC face is not aligned / inside camera field of view: "+face)
        self.serial+=1
        record={"id":self.serial,"cycle_id":self.cycle_id,"time_s":engine.time,"side":side,"face":face,
                "alignment_cos":alignment,"views":views,"robots":{s:r.snapshot() for s,r in engine.robots.items()},
                "doors":{s:d.position for s,d in engine.doors.items()},"camera_fov_deg":self.settings.qc_camera_fov_deg,
                "result":engine.settings.qc_result,"source_sha256":engine.settings.confirmed_source_sha256,
                "scope":engine.settings.mechanism_scope,"note":"DEMO geometric capture; gripper may occlude contact area; no defect classifier"}
        self.records.append(record)
        self.captured.add(face)
        self.exposure_until=engine.time+0.12
        engine.log.add(engine.time,"QC_CAPTURE",side+" "+face,cameras=list(views),alignment=alignment,cycle=self.cycle_id)
        return True

    def snapshot(self):
        return {"ready":dict(self.ready),"records":list(self.records),"captured":sorted(self.captured),"face":self.face,
                "cycle_id":self.cycle_id,"serial":self.serial,"exposure_until":self.exposure_until}

    def restore(self,data):
        self.ready=dict(data["ready"])
        self.records=deque(data["records"],maxlen=240)
        self.captured=set(data["captured"])
        self.face=data["face"]
        self.cycle_id=data["cycle_id"]
        self.serial=data.get("serial",len(self.records))
        self.exposure_until=data["exposure_until"]
