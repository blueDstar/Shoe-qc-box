import sys
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import pyvista as pv
from main import load_settings
from simulation import Simulation
from tools.prepare_cad import prepare_assets
from scene3d import Scene
from qc.preview import CameraPreview

settings=load_settings()
engine=Simulation(settings,prepare_assets(settings))
engine.start("ALTERNATING")
for _ in range(3000):
    engine.advance(1/30)
    if engine.fault:
        raise RuntimeError(engine.fault)
    if not engine.sequence.running:
        break
assert engine.sequence.completed==2 and len(engine.qc.records)==12
p=pv.Plotter(off_screen=True,window_size=(1280,720))
scene=Scene(p,engine.manifest)
scene.hide_panels=True
scene.sensors_visible=True
scene.update(engine)
p.show(auto_close=False,interactive=False)
p.screenshot(str(ROOT/"reports"/"qc_demo_closed.png"))
preview=CameraPreview(scene)
saved=[]
for rec in engine.qc.records:
    saved.append(preview.save_record(engine,rec,ROOT/"exports"/"qc_captures"))
middle=engine.qc.records[3]
for side,pose in middle["robots"].items():
    engine.robots[side].restore(pose)
for side,pos in middle["doors"].items():
    engine.doors[side].position=pos
engine.qc.face=middle["face"]
engine.time=middle["time_s"]
engine.owner=middle["side"]
engine.sequence.side=middle["side"]
engine.sequence.index=6
engine.qc.captured={r["face"] for r in engine.qc.records if r["side"]==middle["side"] and r["id"]<=middle["id"]}
engine.qc.exposure_until=engine.time+0.12
engine.sensors.update(engine)
scene.update(engine)
p.screenshot(str(ROOT/"reports"/"qc_demo_outsole.png"))
result={"cycles":2,"captures":len(saved),"images":len(saved)*2,"faces":[r["face"] for r in engine.qc.records],
        "alignment":[r["alignment_cos"] for r in engine.qc.records],"artifacts":saved}
(ROOT/"reports"/"qc_render_check.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
print(json.dumps({k:v for k,v in result.items() if k!="artifacts"}))
preview.close()
p.close()
