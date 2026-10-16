from pathlib import Path
import sys
import os
import time
import json
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
os.environ["QT_API"]="pyside6"
from PySide6 import QtCore,QtWidgets as W
from main import load_settings
from gui.main_window import MainWindow

app=W.QApplication([])
w=MainWindow(load_settings())
w.show()
original_tick=w.tick
records=[]
physics_times=[]
scene_times=[]
render_times=[]
started=False
warmup=0


def tick():
    global started,warmup
    if not w.engine:
        original_tick()
        return
    if not started:
        w.auto_start("ALTERNATING")
        started=True
        original_advance=w.engine.advance
        original_scene=w.scene.update
        def advance(dt):
            a=time.perf_counter();original_advance(dt);physics_times.append(time.perf_counter()-a)
        def update(engine,render=True):
            a=time.perf_counter();original_scene(engine,False);scene_times.append(time.perf_counter()-a)
            if render:
                a=time.perf_counter();w.viewport.render();render_times.append(time.perf_counter()-a)
        w.engine.advance=advance
        w.scene.update=update
    start=time.perf_counter()
    original_tick()
    duration=time.perf_counter()-start
    warmup+=1
    if warmup<=20:
        return
    records.append((start,duration))
    if len(records)>=180:
        intervals=np.diff([r[0] for r in records])
        result={"method":"actual visible Qt main-loop timer callbacks; includes render and UI updates; isolated run",
                "samples":len(records),"viewport_size":list(w.viewport.window_size),
                "mean_gui_fps":1/float(np.mean(intervals)),"median_interval_ms":float(np.median(intervals)*1000),
                "p95_interval_ms":float(np.percentile(intervals,95)*1000),
                "mean_callback_ms":float(np.mean([r[1] for r in records])*1000),
                "mean_physics_step_ms":float(np.mean(physics_times)*1000),
                "mean_scene_update_ms":float(np.mean(scene_times)*1000),
                "mean_render_ms":float(np.mean(render_times)*1000),
                "state":w.engine.sequence.state,"fault":w.engine.fault,
                "note":"Timer target is 60 Hz; performance depends on GPU, DPI, UI and concurrent export."}
        (ROOT/"reports"/"gui_benchmark.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
        print(json.dumps(result),flush=True)
        w.close()
        app.quit()


w.timer.timeout.disconnect(w.tick)
w.timer.timeout.connect(tick)
app.exec()
