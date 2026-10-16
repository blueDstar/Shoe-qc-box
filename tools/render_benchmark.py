from pathlib import Path
import sys
import json
import time
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import pyvista as pv
from main import load_settings
from tools.prepare_cad import prepare_assets
from simulation import Simulation
from scene3d import Scene

settings=load_settings()
manifest=prepare_assets(settings)
engine=Simulation(settings,manifest)
p=pv.Plotter(off_screen=True,window_size=[1280,720])
scene=Scene(p,manifest)
scene.update(engine)
p.show(auto_close=False,interactive=False)
engine.start()
times=[]
physics_times=[]
render_times=[]
for _ in range(120):
    start=time.perf_counter()
    engine.advance(1/30)
    rendered_start=time.perf_counter()
    scene.update(engine)
    times.append(time.perf_counter()-start)
    physics_times.append(rendered_start-start)
    render_times.append(time.perf_counter()-rendered_start)
result={"frames":120,"resolution":[1280,720],"scope":settings.mechanism_scope,
        "method":"wall time of engine.advance(1/30) + scene.update/render; offscreen; no UI/event pacing",
        "mean_fps":1/float(np.mean(times)),"median_frame_ms":float(np.median(times)*1000),
        "p95_frame_ms":float(np.percentile(times,95)*1000),
        "mean_physics_ms":float(np.mean(physics_times)*1000),"mean_scene_and_render_ms":float(np.mean(render_times)*1000),
        "gpu":p.ren_win.ReportCapabilities().split("OpenGL extensions:")[0].strip()}
(ROOT/"reports"/"render_benchmark.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
print(json.dumps(result))
p.close()
