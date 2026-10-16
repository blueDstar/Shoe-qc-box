from __future__ import annotations

from sensors.signals import prefix
import math
from controllers.inspection import presentation,interpolate

STEPS = ["REQUEST", "CHECK_OPPOSITE_DOOR_CLOSED", "CHECK_CHAMBER_AVAILABLE", "OPEN_DOOR", "WAIT_DOOR_FULLY_OPEN",
         "ROBOT_INSERT", "SHOE_INSPECTION", "ROBOT_EXTRACT", "WAIT_DOORWAY_CLEAR", "CLOSE_DOOR",
         "WAIT_DOOR_FULLY_CLOSED", "CYCLE_COMPLETED"]


class Sequence:
    def __init__(self, engine):
        self.engine = engine
        self.index = -1
        self.elapsed = 0.0
        self.watchdog_elapsed=0.0
        self.running = self.paused = self.single_step = self.stopped = False
        self.completed = 0
        self.cycle_started = 0.0
        self.last_cycle_s = 0.0
        self.side = None
        self.last_result = "—"
        self.start_x=0.0
        self.start_orientation=(0,0,0)

    @property
    def state(self):
        if self.engine.fault:
            return "FAULT"
        if self.side is None:
            return "IDLE"
        return prefix(self.side) + "_" + STEPS[self.index]

    @property
    def progress(self):
        return 0 if self.index < 0 else (self.index+1)/len(STEPS)

    def transition(self,index):
        self.index, self.elapsed = index, 0.0
        self.watchdog_elapsed=0.0
        if self.side:
            self.start_x=self.engine.robots[self.side].x
            robot=self.engine.robots[self.side]
            self.start_orientation=(robot.yaw,robot.pitch,robot.roll)
            if index==6:
                self.engine.qc.begin(prefix(self.side)+"_"+str(self.completed+1))
        self.engine.log.add(self.engine.time,"STATE",self.state)
        if self.single_step:
            self.paused = True
            self.single_step = False

    def tick(self,dt):
        e = self.engine
        if not self.running or self.paused or self.stopped or e.fault:
            return
        if self.side is None:
            if not e.queue:
                self.running = False
                return
            side = e.queue[0]
            from controllers.interlocks import opening_allowed
            if opening_allowed(e,side):
                self.elapsed += dt
                self.watchdog_elapsed+=dt
                if self.watchdog_elapsed > e.settings.timeout_s:
                    e.trip("Queued robot cannot acquire chamber / opposite door not closed")
                return
            self.side = e.queue.popleft()
            e.approaches.pop(self.side,None)
            e.owner = self.side
            self.cycle_started = e.time
            self.transition(0)
            return
        self.elapsed += dt
        self.watchdog_elapsed+=dt
        if self.watchdog_elapsed > e.settings.timeout_s:
            e.trip("Sequence timeout at " + self.state)
            return
        side = self.side
        d, r, s = e.doors[side],e.robots[side],e.sensors.values
        p = prefix(side)
        step = STEPS[self.index]
        done = False
        if step == "REQUEST":
            r.phase = "APPROACH"
            t=min(self.elapsed/1.0,1.0)
            fraction=(3*t*t-2*t*t*t) if r.advanced else t
            done = e.robot_pose(side,self.start_x+(r.sign*650-self.start_x)*fraction,0,0)
            done = done and self.elapsed >= 1.0 and s[p+"_APPROACH_SENSOR"] is True
            if done:
                r.phase = "WAIT_DOOR_OPEN"
        elif step == "CHECK_OPPOSITE_DOOR_CLOSED":
            other = "R" if side == "L" else "L"
            done = e.doors[other].fully_closed and s[prefix(other)+"_DOOR_CLOSED_SENSOR"] is True
        elif step == "CHECK_CHAMBER_AVAILABLE":
            done = e.owner == side and not s["CHAMBER_OCCUPIED"]
        elif step == "OPEN_DOOR":
            if s[p+"_APPROACH_SENSOR"] is True:
                done = e.command(side,"OPEN",internal=True)
        elif step == "WAIT_DOOR_FULLY_OPEN":
            if d.profile is None and not d.fully_open and e.injected_fault != "DOOR_STALL":
                e.command(side,"OPEN",internal=True)
            done = d.fully_open and s[p+"_DOOR_OPEN_SENSOR"] is True
        elif step == "ROBOT_INSERT":
            if not d.fully_open or s[p+"_DOOR_OPEN_SENSOR"] is not True:
                e.trip("Door OPEN confirmation lost during robot insertion")
                return
            r.phase = "INSERT"
            t = min(self.elapsed/3,1)
            done = e.robot_pose(side,self.start_x*(1-(3*t*t-2*t*t*t)),0,0) and t>=1
        elif step == "SHOE_INSPECTION":
            if not d.fully_open or s[p+"_DOOR_OPEN_SENSOR"] is not True:
                e.trip("Door OPEN confirmation lost during inspection")
                return
            r.phase = "INSPECT"
            if r.advanced:
                pose=presentation(side,self.elapsed,e.settings.inspection_move_s,e.settings.inspection_hold_s)
                e.qc.face=pose["face"]
                done=e.robot_pose(side,0,*pose["orientation"])
                if pose["stable"] and pose["face"] not in e.qc.captured:
                    e.qc.capture(e,side,pose["face"])
                done=done and pose["done"] and len(e.qc.captured)==6
            else:
                t = min(self.elapsed/4,1)
                done = e.robot_pose(side,0,12*math.sin(2*math.pi*t),9*math.sin(4*math.pi*t)) and t>=1
        elif step == "ROBOT_EXTRACT":
            if not d.fully_open or s[p+"_DOOR_OPEN_SENSOR"] is not True:
                e.trip("Door OPEN confirmation lost during extraction")
                return
            r.phase = "EXTRACT"
            t = min(self.elapsed/3,1)
            x = self.start_x+(r.sign*650-self.start_x)*(3*t*t-2*t*t*t)
            if e.injected_fault == "ROBOT_NOT_WITHDRAWN":
                x = r.sign*410*min(t,1)
            angles=interpolate(self.start_orientation,(0,0,0),min(self.elapsed/0.5,1))
            done = e.robot_pose(side,x,*angles) and t>=1
        elif step == "WAIT_DOORWAY_CLEAR":
            r.phase = "CLEAR_DOOR"
            from controllers.interlocks import closing_allowed
            done = not closing_allowed(e,side)
        elif step == "CLOSE_DOOR":
            done = e.command(side,"CLOSE",internal=True)
        elif step == "WAIT_DOOR_FULLY_CLOSED":
            if d.profile is None and not d.fully_closed:
                e.command(side,"CLOSE",internal=True)
            done = d.fully_closed and s[p+"_DOOR_CLOSED_SENSOR"] is True
        elif step == "CYCLE_COMPLETED":
            r.phase = "RETREAT"
            t = min(self.elapsed/1,1)
            done = e.robot_pose(side,self.start_x+(r.sign*900-self.start_x)*(3*t*t-2*t*t*t),0,0) and t>=1
            if done:
                r.phase = "RETREATED"
                self.completed += 1
                self.last_cycle_s = e.time-self.cycle_started
                self.last_result = e.settings.qc_result if not r.advanced or len(e.qc.captured)==6 else "INCOMPLETE"
                e.log.add(e.time,"QC_RESULT",self.last_result,side=side,cycle=self.completed,duration_s=self.last_cycle_s)
                e.owner = None
                self.side = None
                self.index = -1
                self.elapsed = 0
                e.log.add(e.time,"STATE","IDLE")
                if e.settings.loop:
                    next_side = ("R" if side == "L" else "L") if e.settings.cycle_mode == "ALTERNATING" else side
                    e.request(next_side)
                if self.single_step:
                    self.paused=True
                    self.single_step=False
                return
        if done and not e.fault:
            self.transition(self.index+1)
