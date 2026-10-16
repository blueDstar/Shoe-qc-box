from __future__ import annotations


SIGNALS = ["LEFT_APPROACH_SENSOR", "RIGHT_APPROACH_SENSOR", "LEFT_DOOR_OPEN_SENSOR", "LEFT_DOOR_CLOSED_SENSOR",
           "RIGHT_DOOR_OPEN_SENSOR", "RIGHT_DOOR_CLOSED_SENSOR", "LEFT_CLEAR_SENSOR", "RIGHT_CLEAR_SENSOR",
           "CHAMBER_OCCUPIED", "ROBOT_LEFT_REQUEST", "ROBOT_RIGHT_REQUEST",
           "CAMERA_FRONT_READY","CAMERA_TOP_READY","QC_EXPOSURE_ACTIVE","QC_ALL_FACES_CAPTURED"]


def prefix(side):
    return "LEFT" if side == "L" else "RIGHT"


class Sensors:
    def __init__(self, auto=True):
        self.auto = auto
        self.values = {name: False for name in SIGNALS}
        for name in ("LEFT_DOOR_CLOSED_SENSOR", "RIGHT_DOOR_CLOSED_SENSOR", "LEFT_CLEAR_SENSOR", "RIGHT_CLEAR_SENSOR"):
            self.values[name] = True
        self.overrides = {}
        self.measurements={}
        self._geometry_key=None
        self._geometry_signals={}

    def set(self, name, value):
        if name not in self.values or value not in (True, False, None):
            raise ValueError("Invalid sensor override")
        self.overrides[name] = value
        self.values[name] = value

    def clear_overrides(self):
        self.overrides.clear()

    def update(self, engine):
        if self.auto:
            key=tuple((r.x,r.yaw,r.pitch,r.roll,r.advanced) for r in engine.robots.values())+(engine.settings.approach_trigger_mm,)
            changed=key!=self._geometry_key
            for side in ("L", "R"):
                p = prefix(side)
                d, r = engine.doors[side], engine.robots[side]
                self.values[p + "_DOOR_OPEN_SENSOR"] = d.fully_open
                self.values[p + "_DOOR_CLOSED_SENSOR"] = d.fully_closed
                if r.advanced and changed:
                    from collision.checker import overlaps
                    threshold=engine.settings.approach_trigger_mm
                    zone=[-threshold,-165,160,-495,165,440] if side=="L" else [495,-165,160,threshold,165,440]
                    detected=any(overlaps(b,zone) for b in r.bodies()[:3])
                    nearest=min((abs(b[3]) if side=="L" else abs(b[0])) for b in r.bodies()[:3])
                    leading=max(b[3] for b in r.bodies()[:3]) if side=="L" else min(b[0] for b in r.bodies()[:3])
                    gap=max(0.0,(-leading if side=="L" else leading)-407.0)
                    self.values[p+"_APPROACH_SENSOR"]=detected
                    self.measurements[side]={"detected":detected,"nearest_x_mm":nearest,"zone_mm":zone,
                                             "door_gap_mm":gap,"trigger_gap_mm":threshold-407.0,"leading_x_mm":leading}
                elif not r.advanced:
                    self.values[p + "_APPROACH_SENSOR"] = r.phase not in ("IDLE", "RETREATED")
                if changed:
                    self.values[p + "_CLEAR_SENSOR"] = engine.collision.doorway_clear(side, engine.robots)
                self.values["ROBOT_" + p + "_REQUEST"] = side in engine.queue or engine.owner == side
            if changed:
                self.values["CHAMBER_OCCUPIED"] = any(r.in_chamber for r in engine.robots.values())
                geometry_names=["CHAMBER_OCCUPIED","LEFT_CLEAR_SENSOR","RIGHT_CLEAR_SENSOR"]
                geometry_names.extend(prefix(side)+"_APPROACH_SENSOR" for side,r in engine.robots.items() if r.advanced)
                self._geometry_signals={name:self.values[name] for name in geometry_names}
                self._geometry_key=key
            else:
                self.values.update(self._geometry_signals)
            self.values["CAMERA_FRONT_READY"]=engine.settings.qc_station_enabled and engine.qc.ready["FRONT"]
            self.values["CAMERA_TOP_READY"]=engine.settings.qc_station_enabled and engine.qc.ready["TOP"]
            self.values["QC_EXPOSURE_ACTIVE"]=engine.settings.qc_station_enabled and engine.time<engine.qc.exposure_until
            self.values["QC_ALL_FACES_CAPTURED"]=len(engine.qc.captured)==6
        self.values.update(self.overrides)

    def invalid(self, doors):
        for name, value in self.values.items():
            if value is None:
                return "Unknown sensor state: " + name
        for side, door in doors.items():
            p = prefix(side)
            op, cl = self.values[p+"_DOOR_OPEN_SENSOR"], self.values[p+"_DOOR_CLOSED_SENSOR"]
            if op and cl:
                return "Contradictory door endpoint sensors: " + p
            if op and not door.fully_open:
                return "Open sensor disagrees with physical position: " + p
            if cl and not door.fully_closed:
                return "Closed sensor disagrees with physical position: " + p
        return ""
