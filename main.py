from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_API","pyside6")
os.environ.setdefault("PYQTGRAPH_QT_LIB","PySide6")

from config import Settings, ROOT


def load_settings(path=None):
    if path:
        return Settings.load(path)
    for candidate in (ROOT/"config"/"user.json",ROOT/"config"/"default.json"):
        if candidate.exists():
            return Settings.load(candidate)
    return Settings()


def run():
    parser=argparse.ArgumentParser(description="Hilykan | Shoe QC Box Simulator — authentic STEP CAD")
    parser.add_argument("--config")
    parser.add_argument("--inspect",action="store_true")
    parser.add_argument("--prepare",action="store_true")
    parser.add_argument("--headless-cycle",action="store_true")
    parser.add_argument("--export-video",metavar="MP4")
    parser.add_argument("--smoke-test",action="store_true")
    args=parser.parse_args()
    settings=load_settings(args.config)
    if args.inspect:
        from cad_manifest.inspect import inspect
        report,_=inspect(settings.cad_directory)
        print(json.dumps({"instances":len(report["components"]),"dimensions_mm":report["assembly_dimensions_mm"],"warnings":report["warnings"]},indent=2))
        return 0
    if args.prepare or args.headless_cycle or args.export_video:
        from tools.prepare_cad import prepare_assets
        manifest=prepare_assets(settings,progress=print)
        if args.prepare:
            print("Prepared",len(manifest["components"]),"STEP/XDE instances")
            return 0
        if args.headless_cycle:
            from simulation import Simulation
            engine=Simulation(settings,manifest)
            if not engine.start():
                raise RuntimeError(engine.last_rejection)
            for _ in range(30*180):
                engine.advance(1/30)
                if engine.fault:
                    raise RuntimeError(engine.fault)
                if not engine.sequence.running:
                    break
            result={"cycles":engine.sequence.completed,"state":engine.sequence.state,"simulation_s":engine.time,
                    "left_mm":engine.doors["L"].position,"right_mm":engine.doors["R"].position,"fault":engine.fault}
            (ROOT/"reports"/"headless_cycle.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
            print(json.dumps(result))
            return 0
        from export.video import export_video
        export_video(settings,manifest,args.export_video,lambda data:print(json.dumps(data),flush=True))
        return 0
    from PySide6 import QtWidgets as W
    from gui.main_window import MainWindow
    app=W.QApplication(sys.argv[:1])
    app.setApplicationName("Hilykan | Shoe QC Box Simulator")
    app.setOrganizationName("Hilykan")
    window=MainWindow(settings)
    window.show()
    if args.smoke_test:
        from tools.gui_smoke import SmokeRunner
        runner=SmokeRunner(window,app)
        window.smoke_runner=runner
        runner.start()
    return app.exec()


if __name__=="__main__":
    try:
        sys.exit(run())
    except Exception as exc:
        import traceback
        traceback.print_exc()
        sys.exit(1)
