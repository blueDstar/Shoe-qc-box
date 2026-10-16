"""Continuous, camera-facing six-surface presentation and a neutral return pose."""
from __future__ import annotations
import math

FACES=("INNER", "UPPER", "OUTER", "OUTSOLE", "TOE", "HEEL")


def poses(side):
    sign=-1 if side=="L" else 1
    return [(0,0,0 if side=="L" else 180),(0,0,90),(0,0,180 if side=="L" else 0),
            (0,0,-90),(90*sign,0,0),(-90*sign,0,0)]


def smooth(t):
    t=max(0.0,min(1.0,t))
    return t*t*(3-2*t)


def interpolate(a,b,t):
    result=[]
    for start,end in zip(a,b):
        delta=(end-start+180)%360-180
        if abs(delta+180)<1e-8:
            delta=math.copysign(180,end-start)
        result.append(start+delta*smooth(t))
    return tuple(result)


def presentation(side,elapsed,move_s,hold_s):
    schedule=poses(side)
    duration=move_s+hold_s
    index=min(int(max(0,elapsed)/duration),6)
    local=elapsed-index*duration
    previous=(0,0,0) if index==0 else schedule[index-1]
    target=schedule[index] if index<6 else (0,0,0)
    return {"orientation":interpolate(previous,target,local/move_s),"index":index,
            "face":FACES[index] if index<6 else "RETURN_NEUTRAL","stable":index<6 and local>=move_s,
            "done":index==6 and local>=move_s}
