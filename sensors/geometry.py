"""Separate DEMO sensor mounts, outside the source door and robot corridor."""
import numpy as np

DOOR_PLANE_X_MM=407.0


def origin(side):
    return np.array([(-1 if side=="L" else 1)*520.0,-320.0,320.0])


def lens(side):
    p=origin(side)
    direction=np.array([(-1 if side=="L" else 1)*650.0,0,300])-p
    return p+20*direction/np.linalg.norm(direction)


def hardware():
    result=[]
    for side in ("L","R"):
        x=origin(side)[0]
        result.extend([(side+"_LASER_HEAD",[x-35,-345,296,x+35,-280,346]),
                       (side+"_SENSOR_POST",[x-6,-326,0,x+6,-314,318]),
                       (side+"_SENSOR_BASE",[x-28,-350,-5,x+28,-290,2])])
    return result
