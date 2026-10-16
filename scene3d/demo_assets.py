"""Procedural low-poly DEMO assets; never substitutes any source STEP component."""
from collections import defaultdict
import numpy as np
import pyvista as pv


def loft(sections,n=32):
    points=[]
    for x,width,center,height in sections:
        for a in np.linspace(0,2*np.pi,n,endpoint=False):
            points.append([x,width*np.cos(a),center+height*np.sin(a)])
    faces=[]
    for row in range(len(sections)-1):
        for col in range(n):
            a=row*n+col;b=row*n+(col+1)%n;c=b+n;d=a+n
            faces.extend([4,a,b,c,d])
    faces.extend([n,*list(reversed(range(n)))])
    faces.extend([n,*range((len(sections)-1)*n,len(sections)*n)])
    return pv.PolyData(np.array(points,dtype=float),np.array(faces)).triangulate()


def tube(points,radius=1.8):
    line=pv.lines_from_points(np.array(points,dtype=float))
    return line.tube(radius=radius,n_sides=8)


def oval_ring(center,rx,ry,r,n=40):
    a=np.linspace(0,2*np.pi,n+1)
    return tube([[center[0]+rx*np.cos(t),center[1]+ry*np.sin(t),center[2]] for t in a],r)


def merge(meshes):
    return pv.merge(meshes,merge_points=False).extract_surface().triangulate()


def robot_assets(side):
    """Return (pose role, mesh, color). Merge same-material detailing for render speed."""
    groups=defaultdict(list)
    def add(role,color,mesh):
        groups[role,color].append(mesh)
    blue="#00BCD4" if side=="L" else "#9886FF"
    xs=[-132,-118,-94,-65,-32,0,40,82,112,129,135]
    widths=[4,25,37,40,43,48,54,52,42,24,2]
    heights=[3,22,40,46,42,32,25,18,13,8,2]
    upper=loft([(x,w,(-14+h-31)/2,(-14+h+31)/2) for x,w,h in zip(xs,widths,heights)])
    sole=loft([(x,min(w+2,57),-40+max(0,x-70)/20,8) for x,w in zip(xs,widths)])
    trim=loft([(x,min(w+3,57),-34+max(0,x-70)/20,2.6) for x,w in zip(xs,widths)])
    add("tool","#C8D5DF",upper)
    add("tool","#15202D",sole)
    add("tool",blue,trim)
    # Collar, tongue, heel reinforcement and textured outsole are distinct surfaces.
    add("tool","#263244",pv.ParametricEllipsoid(16,27,2,u_res=24,v_res=16).translate((-91,0,32)))
    add("tool",blue,oval_ring((-91,0,35),18,29,3))
    add("tool","#667D92",loft([(-70,15,27,4),(-45,18,31,5),(-20,18,27,4),(15,16,18,3)],24))
    for sign in (-1,1):
        path=[[-119,sign*28,-13],[-90,sign*39,-8],[-40,sign*44,-15],[18,sign*51,-20],[70,sign*53,-18],[118,sign*35,-15]]
        add("tool",blue,tube(path,2.6))
        for x in (-54,-38,-22,-6,10):
            z=30-(x+40)*0.12
            add("tool","#E2E8F0",tube([[x-5,sign*17,z+1],[x+6,-sign*17,z-1]],1.5))
            add("tool","#475569",oval_ring((x,sign*20,z),2.7,2.7,0.8,16))
    for x,w in zip(xs[1:-1],widths[1:-1]):
        add("tool","#03080D",pv.Box(bounds=(x-3,x+3,-w*.82,w*.82,-50,-47)))
    # Two heel jaws pinch the shoe while the wrist changes orientation.
    add("tool","#243B50",pv.Box(bounds=(-166,-142,-48,48,-24,24)))
    for sign in (-1,1):
        y=sign*45
        add("tool",blue,pv.Box(bounds=(-149,-95,y-7,y+7,-10,10)))
        add("tool","#111827",pv.Box(bounds=(-121,-95,sign*36-4,sign*36+4,-8,8)))
        for z in (-14,14):
            add("tool","#CBD5E1",pv.Cylinder(center=(-166.5,sign*26,z),direction=(1,0,0),radius=3,height=2,resolution=6))
    add("tool","#73889E",pv.Sphere(radius=27,center=(-188,0,0),theta_resolution=20,phi_resolution=16))
    add("tool","#283E52",pv.Cylinder(center=(-190,0,0),direction=(1,0,0),radius=24,height=35,resolution=24))
    for x in (-202,-191,-180):
        add("tool",blue,pv.Cylinder(center=(x,0,0),direction=(1,0,0),radius=25,height=3,resolution=24))
    # Rigid links are 650 mm; actor rotation/translation follows analytic joint positions.
    for role,radius in (("upper_arm",20),("forearm",16)):
        add(role,"#B5672A",pv.Cylinder(direction=(0,0,1),radius=radius,height=650,resolution=20))
        add(role,"#D79743",pv.Box(bounds=(-radius*.65,radius*.65,-radius*.7,radius*.7,-280,280)))
        for z in (-300,300):
            add(role,"#26394B",pv.Cylinder(center=(0,0,z),direction=(0,0,1),radius=radius+2,height=16,resolution=20))
        add(role,"#172B3D",tube([[radius,0,-285],[radius+2,0,0],[radius,0,285]],2))
    for role,radius in (("shoulder",30),("elbow",27)):
        add(role,"#283C50",pv.Cylinder(direction=(0,1,0),radius=radius,height=58,resolution=24))
        add(role,blue,pv.Cylinder(center=(0,-radius,0),direction=(0,1,0),radius=radius*.7,height=3,resolution=24))
        add(role,"#94A3B8",pv.Sphere(radius=radius*.8,theta_resolution=16,phi_resolution=12))
    # One immutable mesh/actor per rigid pose role, with per-cell RGB. This keeps
    # all detailing while avoiding dozens of material draw calls on Intel GPUs.
    roles=defaultdict(list)
    for (role,color),meshes in groups.items():
        rgb=np.array([int(color[k:k+2],16) for k in (1,3,5)],dtype=np.uint8)
        for mesh in meshes:
            mesh.cell_data["DEMO_RGB"]=np.tile(rgb,(mesh.n_cells,1))
            roles[role].append(mesh)
    return [(role,merge(meshes),None) for role,meshes in roles.items()]


def station_assets():
    from qc.station import HARDWARE
    assets=[]
    for name,box in HARDWARE:
        if "LENS" in name:
            center=(np.array(box[:3])+box[3:])/2
            direction=(0,1,0) if "FRONT" in name else (0,0,1)
            length=box[4]-box[1] if "FRONT" in name else box[5]-box[2]
            mesh=pv.Cylinder(center=center,direction=direction,radius=14,height=length,resolution=32)
            assets.append((name,mesh,"#192937"))
            center[1 if "FRONT" in name else 2]=box[4] if "FRONT" in name else box[2]
            assets.append((name+"_GLASS",pv.Cylinder(center=center,direction=direction,radius=10.5,height=0.8,resolution=32),"#1CD4E5"))
        else:
            assets.append((name,pv.Box(bounds=(box[0],box[3],box[1],box[4],box[2],box[5])),"#E7F3F8" if "LED" in name else "#334D65"))
    # Mounts stay inside the shell, LEDs next to each optical unit.
    assets.append(("TOP_MOUNT",pv.Box(bounds=(-42,42,-30,30,551,556)),"#687C8D"))
    for camera,x,y,z in (("FRONT",22,-242,320),("TOP",25,18,521)):
        assets.append((camera+"_STATUS",pv.Sphere(radius=2.5,center=(x,y,z),theta_resolution=12,phi_resolution=10),"#22C55E"))
    return assets
