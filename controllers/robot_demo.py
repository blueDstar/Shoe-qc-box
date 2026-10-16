from __future__ import annotations

import math
import numpy as np


def rotation(yaw,pitch,roll=0):
    y,p,r=map(math.radians,(yaw,pitch,roll))
    rz=np.array([[math.cos(y),-math.sin(y),0],[math.sin(y),math.cos(y),0],[0,0,1]])
    ry=np.array([[math.cos(p),0,math.sin(p)],[0,1,0],[-math.sin(p),0,math.cos(p)]])
    rx=np.array([[1,0,0],[0,math.cos(r),-math.sin(r)],[0,math.sin(r),math.cos(r)]])
    return rz@ry@rx


def corners(center,extent):
    return np.array([[center[0]+sx*extent[0],center[1]+sy*extent[1],center[2]+sz*extent[2],1]
                     for sx in (-1,1) for sy in (-1,1) for sz in (-1,1)])


def segment_matrix(a,b):
    a,b=np.array(a),np.array(b)
    direction=b-a
    direction/=np.linalg.norm(direction)
    x=np.cross([0,1,0],direction)
    x/=np.linalg.norm(x)
    y=np.cross(direction,x)
    m=np.eye(4)
    m[:3,:3]=np.c_[x,y,direction]
    m[:3,3]=(a+b)/2
    return m


class DemoRobot:
    """Fixed-length two-link DEMO positioning arm and orientable held-shoe wrist.

    Analytic positioning IK; no vendor robot or certified robot dynamics claim.
    """
    link_length=650.0
    wrist_anchor=np.array([-188.0,0,0,1])

    def __init__(self,side,advanced=True):
        self.side,self.sign=side,(-1 if side=="L" else 1)
        self.advanced=advanced
        self.x=self.sign*900.0
        self.yaw=self.pitch=self.roll=0.0
        self.phase="IDLE"
        self._key=None
        self._m=self._parts=self._joints=None
        self._shoe=corners([0,0,7.5],[135,58,57.5])

    def _update(self):
        key=(self.x,self.yaw,self.pitch,self.roll,self.advanced)
        if key==self._key:
            return
        m=np.eye(4)
        m[:3,:3]=rotation(self.yaw,self.pitch,self.roll)
        if self.advanced and self.side=="R":
            m[:3,:3]=m[:3,:3]@np.diag([-1,-1,1])
        m[:3,3]=[self.x,0,300]
        self._m=m
        if not self.advanced:
            boxes=[corners([0,0,0],[135,58,50]),corners([self.sign*155,0,0],[70,72,60]),
                   corners([self.sign*270,0,0],[80,55,60])]
            self._parts=[self._box("legacy_"+str(i),box,m) for i,box in enumerate(boxes)]
            self._joints=None
        else:
            self._parts=[self._box("shoe",self._shoe,m),self._box("gripper",corners([-130,0,0],[40,55,30]),m),
                         self._box("wrist",corners([-188,0,0],[29,29,29]),m)]
            shoulder=np.array([self.sign*1180.0,0,40.0])
            wrist=(m@self.wrist_anchor)[:3]
            vector=wrist-shoulder
            distance=np.linalg.norm(vector)
            if distance>2*self.link_length+1e-6 or distance<1e-6:
                raise ValueError("DEMO wrist target exceeds fixed-link reach")
            direction=vector/distance
            up=np.array([0,0,1])-direction*direction[2]
            up/=np.linalg.norm(up)
            elbow=(shoulder+wrist)/2+up*math.sqrt(max(0,self.link_length**2-(distance/2)**2))
            self._joints=(shoulder,elbow,wrist)
            for name,a,b,radius in (("upper_arm",shoulder,elbow,25),("forearm",elbow,wrist,21)):
                box=[*(np.minimum(a,b)-radius).tolist(),*(np.maximum(a,b)+radius).tolist()]
                self._parts.append({"name":name,"kind":"capsule","bbox":box,"a":a.tolist(),"b":b.tolist(),"radius":radius})
            for name,p,radius in (("shoulder",shoulder,33),("elbow",elbow,30)):
                self._parts.append({"name":name,"kind":"box","bbox":[*(p-radius).tolist(),*(p+radius).tolist()]})
        self._key=key

    @staticmethod
    def _box(name,local,m):
        pts=local@m.T
        return {"name":name,"kind":"box","bbox":[*pts[:,:3].min(axis=0).tolist(),*pts[:,:3].max(axis=0).tolist()]}

    def matrix(self):
        self._update()
        return self._m

    def parts(self):
        self._update()
        return self._parts

    def bodies(self):
        return [p["bbox"] for p in self.parts()]

    def shoe_corners(self):
        return (self._shoe@self.matrix().T)[:,:3]

    def joint_positions(self):
        self._update()
        return self._joints

    def matrices(self):
        output={"tool":self.matrix()}
        if self.advanced:
            a,b,c=self.joint_positions()
            for name,p in (("shoulder",a),("elbow",b)):
                m=np.eye(4)
                m[:3,3]=p
                output[name]=m
            output["upper_arm"]=segment_matrix(a,b)
            output["forearm"]=segment_matrix(b,c)
        return output

    @property
    def withdrawn(self):
        return abs(self.x)>=650-1e-6 and all(abs((a+180)%360-180)<1e-5 for a in (self.yaw,self.pitch,self.roll))

    @property
    def in_chamber(self):
        return any(b[0]<397 and b[3]>-397 for b in self.bodies())

    def snapshot(self):
        return {"x":self.x,"yaw":self.yaw,"pitch":self.pitch,"roll":self.roll,"phase":self.phase,"advanced":self.advanced}

    def restore(self,data):
        self.x,self.yaw,self.pitch,self.phase=data["x"],data["yaw"],data["pitch"],data["phase"]
        self.roll=data.get("roll",0)
        self.advanced=data.get("advanced",self.advanced)
        self._key=None
