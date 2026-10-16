from sensors.signals import prefix

RULES = [
    "Only one door may be away from CLOSED.",
    "LEFT opens only when RIGHT is physically closed, sensor-confirmed and chamber available.",
    "RIGHT opens only when LEFT is physically closed, sensor-confirmed and chamber available.",
    "Robot cannot cross a closed shutter.",
    "Robot enters only with physical OPEN and OPEN sensor.",
    "Door remains fully open through INSERT / INSPECT / EXTRACT.",
    "Close requires complete shoe / gripper / wrist withdrawal.",
    "Blocked doorway rejects closing.",
    "Unknown, contradictory sensors or collision risk cause FAULT and hold.",
    "Concurrent requests are serialized through a FIFO chamber lease.",
]


def opening_allowed(engine, side):
    other = "R" if side == "L" else "L"
    s = engine.sensors.values
    if not engine.doors[other].fully_closed or s[prefix(other)+"_DOOR_CLOSED_SENSOR"] is not True:
        return "Opposite door must be fully CLOSED with sensor confirmation"
    if engine.owner not in (None, side):
        return "Chamber reserved by opposite robot"
    if s["CHAMBER_OCCUPIED"] and engine.owner != side:
        return "Chamber is occupied"
    return ""


def closing_allowed(engine, side):
    if engine.sensors.values[prefix(side)+"_CLEAR_SENSOR"] is not True:
        return "Doorway CLEAR sensor is blocked or unknown"
    if not engine.collision.doorway_clear(side, engine.robots):
        return "Shoe, gripper or wrist remains in door swept zone"
    if any(not r.withdrawn for r in engine.robots.values()):
        return "Robot not fully withdrawn"
    if engine.sensors.values["CHAMBER_OCCUPIED"] is not False:
        return "Chamber occupied or unknown; complete withdrawal first"
    return ""
