from __future__ import annotations

from collections import deque
from dataclasses import asdict
from pathlib import Path
import json
import math

from config import Settings
from motion import DoorMotion
from sensors import Sensors
from sensors.signals import prefix
from controllers.robot_demo import DemoRobot
from controllers.interlocks import opening_allowed, closing_allowed
from collision.checker import CollisionChecker, overlaps, union
from state_machine import Sequence
from logs import EventLog
from qc import QCStation
from qc.station import HARDWARE
from controllers.inspection import interpolate
from sensors.geometry import hardware as sensor_hardware


class Simulation:
    fixed_dt = 1/120

    def __init__(self, settings=None, manifest=None, logger=None):
        self.settings = (settings or Settings()).validate()
        self.manifest = manifest
        if manifest and self.settings.kinematics_confirmed:
            source=next((x.get("sha256","") for x in manifest.get("files",[]) if x["file"]==self.settings.main_assembly),"")
            if self.settings.confirmed_source_sha256!=source or manifest.get("unit")!="mm":
                self.settings.kinematics_confirmed=False
        self.time = 0.0
        self.doors = {s:DoorMotion(s,self.settings.travel_mm,self.settings.velocity_mm_s,
                                 self.settings.acceleration_mm_s2,self.settings.sensor_tolerance_mm) for s in ("L","R")}
        self.robots = {s:DemoRobot(s,self.settings.advanced_demo) for s in ("L","R")}
        self.sensors = Sensors(self.settings.auto_sensors)
        self.collision = CollisionChecker(manifest)
        self.qc=QCStation(self.settings)
        if self.settings.qc_station_enabled:
            self.collision.auxiliary=list(HARDWARE)
        if self.settings.advanced_demo:
            self.collision.auxiliary.extend(sensor_hardware())
        self.approaches={}
        self.log = logger or EventLog()
        self.queue = deque()
        self.owner = None
        self.fault = ""
        self.injected_fault = ""
        self.last_rejection = ""
        self.sequence = Sequence(self)
        self.history = deque(maxlen=18000)
        self._sensor_previous = {}
        self.proximity_notices={}
        self.log.add(0,"SYSTEM","Engine initialized; units mm; both doors CLOSED")
        self.sensors.update(self)

    def reject(self,message):
        self.last_rejection=message
        self.log.add(self.time,"INTERLOCK",message)
        return False

    def trip(self,message):
        if not self.fault:
            self.fault=message
            for door in self.doors.values():
                door.stop()
            self.sequence.paused=True
            self.log.add(self.time,"FAULT",message)
        return False

    def command(self,side,action,target=None,internal=False):
        d=self.doors[side]
        if action=="STOP":
            d.stop()
            if self.sequence.running:
                self.pause()
            self.log.add(self.time,"MOTION",side+" STOP; hold current pose")
            return True
        if self.fault:
            return self.reject("Reset FAULT after resolving cause")
        if not self.settings.kinematics_confirmed:
            return self.reject("Confirm measured CAD kinematics in CAD & Components first")
        self.sensors.update(self)
        if self.settings.mechanism_scope=="FULL_ASSEMBLY" and self.manifest and self.manifest.get("preflight",{}).get("source_envelope_overlaps"):
            return self.trip("Rev A source bracket / drive link intersects fixed CAD. Full mechanism motion is blocked; use approved PLATE_AND_BLOCKS scope.")
        invalid=self.sensors.invalid(self.doors)
        if invalid:
            return self.trip(invalid)
        if self.sequence.running and not internal:
            return self.reject("AUTO owns motion; STOP or finish sequence before manual command")
        if action in ("CLOSE","HOME","RESET"):
            target=0
        elif action=="OPEN":
            target=d.limit
        elif action=="JOG UP":
            target=min(d.limit,d.position+10)
        elif action=="JOG DOWN":
            target=max(0,d.position-10)
        if target is None or not math.isfinite(float(target)) or not 0<=target<=d.limit:
            return self.reject("Target outside measured travel limit")
        reason = opening_allowed(self,side) if target>d.position else closing_allowed(self,side) if target<d.position else ""
        if reason:
            return self.reject(reason)
        if target>d.position:
            self.owner=side
        d.go(float(target))
        if not internal and not self.sequence.running:
            self.sequence.paused=self.sequence.stopped=False
        self.log.add(self.time,"MOTION",side+" "+action,target_mm=target)
        self.last_rejection=""
        return True

    def request(self,side):
        if side not in ("L","R"):
            raise ValueError("Unknown side")
        if side not in self.queue and self.sequence.side!=side:
            self.queue.append(side)
            self.log.add(self.time,"REQUEST",side+" queued",queue=list(self.queue))

    def begin_approach(self,side):
        if self.fault or not self.settings.kinematics_confirmed:
            return self.reject(self.fault or "Confirm CAD before DEMO approach")
        if not self.robots[side].withdrawn or self.sequence.side==side:
            return self.reject("Robot is already active / must withdraw before another approach")
        if self.sequence.side is not None and self.sequence.paused:
            return self.reject("RESUME the paused sequence first")
        self.robots[side].phase="APPROACH"
        self.approaches[side]={"start_x":self.robots[side].x,"elapsed":0.0}
        if self.sequence.side is None:
            self.sequence.paused=self.sequence.stopped=False
        self.log.add(self.time,"DEMO","Robot "+side+" approach; waiting for measured proximity signal")
        return True

    def _advance_approaches(self,dt):
        for side,data in list(self.approaches.items()):
            if self.sequence.side==side:
                self.approaches.pop(side,None)
                continue
            data["elapsed"]+=dt
            if data["elapsed"]-data.get("watchdog_origin",0)>self.settings.timeout_s and side not in self.queue:
                self.trip("Approach sensor / chamber lease timeout: "+side)
                return
            t=min(data["elapsed"]/1.5,1)
            q=data["start_x"]+(self.robots[side].sign*650-data["start_x"])*(t*t*(3-2*t))
            if not self.robot_pose(side,q,0,0,0):
                return
            if t>=1:
                self.robots[side].phase="WAIT_DOOR_OPEN"
            if self.settings.approach_auto_open and self.sensors.values[prefix(side)+"_APPROACH_SENSOR"] is True:
                self.request(side)
                self.sequence.running=True

    def start(self,mode=None,cycles=None):
        if self.fault or not self.settings.kinematics_confirmed:
            return self.reject(self.fault or "CAD kinematics confirmation required")
        if self.sequence.side is not None:
            return self.reject("Sequence already active; use RESUME")
        mode=mode or self.settings.cycle_mode
        self.settings.cycle_mode=mode
        if not self.queue:
            if cycles is None:
                cycles=2 if mode=="ALTERNATING" else 1
            for i in range(cycles):
                # Deliberately retain repeated requests in a plan; external requests are deduplicated.
                self.queue.append(("L" if i%2==0 else "R") if mode=="ALTERNATING" else ("L" if mode=="LEFT" else "R"))
        self.sequence.running=True
        self.sequence.elapsed=self.sequence.watchdog_elapsed=0.0
        self.sequence.paused=self.sequence.stopped=False
        self.log.add(self.time,"SYSTEM","AUTO START "+mode)
        return True

    def pause(self):
        self.sequence.paused=True
        self.log.add(self.time,"SYSTEM","PAUSE; simulation clock and all bodies held")

    def resume(self):
        if self.fault:
            return self.reject(self.fault)
        self.sequence.paused=self.sequence.stopped=False
        self.sequence.running = self.sequence.side is not None or bool(self.queue)
        if self.sequence.side and self.sequence.index==8 and not self.robots[self.sequence.side].withdrawn:
            self.sequence.transition(7)
        if self.sequence.side and self.sequence.index==6 and self.sequence.elapsed>=self.settings.inspection_duration_s and len(self.qc.captured)<6:
            self.sequence.transition(6)
        if not self.sequence.running:
            for side,d in self.doors.items():
                if abs(d.target-d.position)>1e-6:
                    self.command(side,"GO TO",d.target)
        self.log.add(self.time,"SYSTEM","RESUME")
        return True

    def stop(self):
        for d in self.doors.values():
            d.stop()
        self.sequence.stopped=True
        self.sequence.paused=True
        self.log.add(self.time,"SYSTEM","STOP; all poses held, chamber lease retained; RESUME to recover")

    def step(self):
        if self.fault:
            return self.reject(self.fault)
        if not self.sequence.running:
            if not self.start():
                return False
        self.sequence.stopped=False
        self.sequence.single_step=True
        self.sequence.paused=False
        return True

    def robot_pose(self,side,x,yaw,pitch,roll=0):
        r=self.robots[side]
        old=r.snapshot()
        old_parts=r.parts()
        old_bodies=r.bodies()
        if not all(math.isfinite(v) for v in (x,yaw,pitch,roll)):
            return self.trip("Invalid DEMO robot pose")
        r.x,r.yaw,r.pitch,r.roll=x,yaw,pitch,roll
        try:
            new_parts=r.parts()
        except ValueError as exc:
            r.restore(old)
            return self.trip(str(exc))
        for old_body,new_body in zip(old_bodies,r.bodies()):
            swept=union(old_body,new_body)
            for doorway_side,zone in self.collision.doorways.items():
                if overlaps(swept,zone) and self.sensors.values[prefix(doorway_side)+"_DOOR_OPEN_SENSOR"] is not True:
                    r.restore(old)
                    return self.trip("DEMO entry requires OPEN sensor confirmation: "+doorway_side)
        if r.in_chamber and self.owner!=side:
            r.restore(old)
            return self.trip("DEMO robot has no chamber lease")
        reason=self.collision.check_robot(side,old_bodies,r.bodies(),self.doors,self.robots,old_parts,new_parts)
        if reason:
            r.restore(old)
            return self.trip(reason)
        return True

    def advance(self,dt):
        if not math.isfinite(dt) or dt<0:
            raise ValueError("Invalid simulation dt")
        remaining=dt
        while remaining>1e-10:
            sub=min(self.fixed_dt,remaining)
            self._tick(sub)
            remaining-=sub

    def _tick(self,dt):
        if self.fault or self.sequence.paused or self.sequence.stopped:
            return
        self.sensors.update(self)
        invalid=self.sensors.invalid(self.doors)
        if invalid:
            self.trip(invalid)
            return
        for side,d in self.doors.items():
            if d.profile:
                if d.target<d.position:
                    reason=closing_allowed(self,side)
                    if reason:
                        self.trip(reason)
                        return
                else:
                    reason=opening_allowed(self,side)
                    if reason:
                        self.trip(reason)
                        return
                new,_,_=d.proposal(dt)
                reason=self.collision.check_door(side,d.position,new,self.robots)
                if reason:
                    self.trip(reason)
                    return
                if not (self.injected_fault=="DOOR_STALL" and new>50):
                    d.advance(dt)
        self.time+=dt
        self._advance_approaches(dt)
        self.sensors.update(self)
        self.sequence.tick(dt)
        self.sensors.update(self)
        if self.owner and not self.sequence.running and self.doors[self.owner].fully_closed and all(r.withdrawn for r in self.robots.values()):
            self.owner=None
        for name,value in self.sensors.values.items():
            if self._sensor_previous.get(name,"unset")!=value:
                self.log.add(self.time,"SENSOR",name,value=value)
                if name in ("LEFT_APPROACH_SENSOR","RIGHT_APPROACH_SENSOR") and value is True:
                    side="L" if name.startswith("LEFT") else "R"
                    measured=dict(self.sensors.measurements.get(side,{}))
                    self.proximity_notices[side]={"time_s":self.time,**measured}
                    self.log.add(self.time,"PROXIMITY_DETECTED",prefix(side)+" target seen; door request uses interlocks",
                                 side=side,door_gap_mm=measured.get("door_gap_mm"),trigger_gap_mm=measured.get("trigger_gap_mm"))
        self._sensor_previous=dict(self.sensors.values)
        self.history.append({"time_s":self.time,"left_mm":self.doors["L"].position,"right_mm":self.doors["R"].position,
                             "left_v":self.doors["L"].velocity,"right_v":self.doors["R"].velocity,
                             "left_a":self.doors["L"].accel,"right_a":self.doors["R"].accel,
                             "state":self.sequence.state,"step":self.sequence.index,
                             "left_clear":int(self.sensors.values["LEFT_CLEAR_SENSOR"] is True),
                             "right_clear":int(self.sensors.values["RIGHT_CLEAR_SENSOR"] is True)})

    def inject(self,name,side="L"):
        self.injected_fault=name
        self.log.add(self.time,"DEMO_FAULT",name,side=side)
        if name=="SENSOR_NO_OPEN":
            self.sensors.set(prefix(side)+"_DOOR_OPEN_SENSOR",False)
        elif name=="SENSOR_NO_APPROACH":
            self.sensors.set(prefix(side)+"_APPROACH_SENSOR",False)
        elif name=="CAMERA_NOT_READY":
            self.qc.ready["FRONT"]=False
        elif name=="DOORWAY_BLOCKED":
            self.sensors.set(prefix(side)+"_CLEAR_SENSOR",False)
        elif name=="UNKNOWN_SENSOR":
            self.sensors.set(prefix(side)+"_CLEAR_SENSOR",None)
        elif name=="SIMULTANEOUS_REQUESTS":
            self.request("L")
            self.request("R")

    def clear_fault_source(self):
        self.injected_fault=""
        self.qc.ready={"FRONT":True,"TOP":True}
        self.sensors.clear_overrides()
        self.sensors.update(self)
        self.log.add(self.time,"SYSTEM","DEMO fault sources cleared; FAULT still requires RESET")

    def reset_fault(self):
        self.sensors.update(self)
        invalid=self.sensors.invalid(self.doors)
        if invalid or self.injected_fault:
            return self.reject(invalid or "Clear DEMO fault source first")
        for side,d in self.doors.items():
            if d.position>0 and not self.doors["R" if side=="L" else "L"].fully_closed:
                return self.reject("Both doors away from CLOSED")
        self.log.add(self.time,"SYSTEM","RESET FAULT; poses preserved; resume or recover manually")
        self.fault=""
        self.last_rejection=""
        self.sequence.watchdog_elapsed=0.0
        for data in self.approaches.values():
            data["watchdog_origin"]=data["elapsed"]
        return True

    def snapshot(self):
        source=next((x.get("sha256","") for x in self.manifest.get("files",[]) if x["file"]==self.settings.main_assembly),"") if self.manifest else ""
        return {"version":2,"source_sha256":source,
                "time_s":self.time,"doors":{s:{"position":d.position,"target":d.target,"speed":d.speed,"acceleration":d.acceleration} for s,d in self.doors.items()},
                "robots":{s:r.snapshot() for s,r in self.robots.items()},"sensors":self.sensors.values,
                "overrides":self.sensors.overrides,"queue":list(self.queue),"owner":self.owner,"fault":self.fault,
                "injected_fault":self.injected_fault,"sequence":{"side":self.sequence.side,"index":self.sequence.index,
                "elapsed":self.sequence.elapsed,"running":self.sequence.running,"completed":self.sequence.completed,
                "cycle_started":self.sequence.cycle_started,"last_result":self.sequence.last_result,"start_x":self.sequence.start_x,
                "start_orientation":self.sequence.start_orientation},
                "watchdog_elapsed":self.sequence.watchdog_elapsed,
                "qc":self.qc.snapshot(),"approaches":self.approaches,
                "proximity_notices":self.proximity_notices,
                "resume_policy":"loaded paused; motion is replanned from held pose on explicit RESUME"}

    def save_state(self,path):
        Path(path).write_text(json.dumps(self.snapshot(),indent=2),encoding="utf-8")

    def load_state(self,path):
        data=json.loads(Path(path).read_text(encoding="utf-8"))
        if data.get("version") not in (1,2):
            raise ValueError("Unsupported state format")
        if data.get("source_sha256","")!=self.snapshot()["source_sha256"]:
            raise ValueError("Saved state belongs to a different CAD source")
        seq=data["sequence"]
        if seq["side"] not in (None,"L","R") or not isinstance(seq["index"],int) or not -1<=seq["index"]<12:
            raise ValueError("Invalid saved sequence")
        if seq["side"] is not None and seq["index"]<0:
            raise ValueError("Invalid saved active state")
        if data["owner"] not in (None,"L","R") or any(x not in ("L","R") for x in data["queue"]):
            raise ValueError("Invalid saved chamber lease / requests")
        if not math.isfinite(float(data["time_s"])) or float(data["time_s"])<0:
            raise ValueError("Invalid saved time")
        for s in ("L","R"):
            pos=float(data["doors"][s]["position"])
            if not math.isfinite(pos) or not 0<=pos<=self.doors[s].limit:
                raise ValueError("Invalid saved door position")
        if data["doors"]["L"]["position"]>self.settings.sensor_tolerance_mm and data["doors"]["R"]["position"]>self.settings.sensor_tolerance_mm:
            raise ValueError("Unsafe saved state: both doors open")
        # Validate into a fresh engine before altering the live session.
        candidate=Simulation(self.settings,self.manifest)
        candidate.time=float(data["time_s"])
        for s in ("L","R"):
            d=candidate.doors[s]
            row=data["doors"][s]
            d.position=float(row["position"])
            d.target=float(row["target"])
            d.speed=float(row["speed"])
            d.acceleration=float(row["acceleration"])
            if not all(math.isfinite(v) for v in (d.target,d.speed,d.acceleration)) or not 0<=d.target<=d.limit or d.speed<=0 or d.acceleration<=0:
                raise ValueError("Invalid saved motion parameters")
            d.status="HOLD"
            candidate.robots[s].restore(data["robots"][s])
        for s in ("L","R"):
            r=candidate.robots[s]
            if not all(math.isfinite(v) for v in (r.x,r.yaw,r.pitch,r.roll)):
                raise ValueError("Invalid robot pose")
            reason=candidate.collision.check_robot(s,r.bodies(),r.bodies(),candidate.doors,candidate.robots,r.parts(),r.parts())
            if reason:
                raise ValueError(reason)
        candidate.sensors.overrides=data["overrides"]
        candidate.sensors.values=data["sensors"]
        candidate.sensors.update(candidate)
        if candidate.sensors.invalid(candidate.doors):
            raise ValueError(candidate.sensors.invalid(candidate.doors))
        self.time=candidate.time
        self.doors,self.robots,self.sensors=candidate.doors,candidate.robots,candidate.sensors
        self.queue=deque(data["queue"])
        self.owner=data["owner"]
        self.approaches=data.get("approaches",{})
        self.proximity_notices=data.get("proximity_notices",{})
        if "qc" in data:
            self.qc.restore(data["qc"])
        self.fault,self.injected_fault=data["fault"],data["injected_fault"]
        for key,value in data["sequence"].items():
            setattr(self.sequence,key,value)
        self.sequence.watchdog_elapsed=data.get("watchdog_elapsed",self.sequence.elapsed)
        self.sequence.paused=True
        self.sequence.stopped=True
        self.log.add(self.time,"SYSTEM","State loaded paused; inspect before RESUME")
