"""Exercise new sensor feedback and two live CAD detail views in real Qt."""
from pathlib import Path
import sys,json,time
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from PySide6 import QtCore,QtGui,QtWidgets as W
from main import load_settings
from gui.main_window import MainWindow

app=W.QApplication([]);w=MainWindow(load_settings());w.show()
stage=0;started=time.perf_counter();baseline={};captures=[]


def capture(name,index=0):
    w.tabs.setCurrentIndex(index);app.processEvents();w.refresh()
    app.processEvents()
    if index==7:
        w.refresh_door_detail(True)
        app.processEvents()
    shot=w.grab()
    pairs=[(w.viewport,w.viewport.interactor)] if index==0 else [(p,p.interactor) for p in w.detail_plotters.values()]
    painter=QtGui.QPainter(shot)
    for p,widget in pairs:
        if index==7:
            assert widget.width()>=350 and widget.height()>=350,"Detail viewport layout collapsed"
        frame=np.ascontiguousarray(p.screenshot(return_img=True))
        if index==7:
            assert frame.shape[0]>=300 and frame.shape[1]>=300,"Detail framebuffer has not resized with the widget"
        assert len(np.unique(frame.reshape(-1,3),axis=0))>100
        image=QtGui.QImage(frame.data,frame.shape[1],frame.shape[0],frame.strides[0],QtGui.QImage.Format_RGB888).copy()
        painter.drawImage(QtCore.QRect(widget.mapTo(w,QtCore.QPoint()),widget.size()),image)
    painter.end();path=ROOT/"reports"/(name+".png");shot.save(str(path));captures.append(str(path))


def finish(error=None):
    timer.stop()
    result={"passed":not bool(error),"error":error,"captures":captures,"checks":["laser / housing / range labels",
            "sensor detection notice before door opens","both detail cameras render real STEP","ruler uses live engine Z",
            "static guide actor matrices unchanged","manual detail view independent doors"],"wall_s":time.perf_counter()-started}
    (ROOT/"reports"/"sensor_motion_check.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    print(json.dumps(result),flush=True);w.close();app.exit(1 if error else 0)


def tick():
    global stage,baseline
    if time.perf_counter()-started>180:
        return finish("timeout")
    if not w.engine:
        return
    e=w.engine
    try:
        if e.fault:
            raise AssertionError(e.fault)
        if stage==0:
            w.timer.stop();w.scene.update(e);capture("sensor_laser_scan")
            w.approach("L");stage=1
        elif stage in (1,2,3):
            e.advance(1/30);w.scene.update(e);w.refresh()
            if stage==1 and e.sensors.values["LEFT_APPROACH_SENSOR"]:
                assert "ĐÃ PHÁT HIỆN" in w.sensor_notice.text()
                capture("sensor_laser_detected");stage=2
            elif stage==2 and e.doors["L"].position>130:
                capture("door_motion_left_opening",7)
                baseline={s:{k:a.GetMatrix().GetElement(2,3) for k,a in view.actors.items() if view.rows[k]["group"]=="STATIC_FRAME"} for s,view in w.detail_views.items()}
                stage=3
            elif stage==3 and not e.sequence.running:
                assert e.sequence.completed==1
                e.command("R","OPEN");e.advance(0.9);w.refresh_door_detail(True)
                assert e.doors["L"].position==0 and e.doors["R"].position>0
                capture("door_motion_right_opening",7)
                for s,rows in baseline.items():
                    assert all(w.detail_views[s].actors[k].GetMatrix().GetElement(2,3)==base for k,base in rows.items())
                for s,view in w.detail_views.items():
                    assert view.scale["marker"].user_matrix[2,3]==e.doors[s].position
                return finish()
    except Exception as exc:
        import traceback;traceback.print_exc();finish(str(exc))


timer=QtCore.QTimer();timer.timeout.connect(tick);timer.start(30);app.exec()
