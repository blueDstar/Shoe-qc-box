from __future__ import annotations

import json
import time
import numpy as np
from PySide6 import QtCore, QtTest, QtWidgets as W, QtGui
from config import ROOT


class SmokeRunner(QtCore.QObject):
    """Exercise actual Qt widgets and VTK renderer, then record visual artifacts."""
    def __init__(self,window,app):
        super().__init__(window)
        self.window,self.app=window,app
        self.timer=QtCore.QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.stage=0
        self.wall_start=time.perf_counter()
        self.artifacts=[]
        self.static_matrices={}
        self.frames=0

    def start(self):
        self.timer.start(30)

    def capture(self,name):
        w=self.window
        w.scene.update(w.engine)
        png=ROOT/"reports"/(name+".png")
        # QVTK uses a native OpenGL surface excluded by QWidget.grab(). Capture the
        # real VTK framebuffer as well and composite it only for documentation.
        screenshot=w.grab()
        if w.tabs.currentIndex()==0:
            viewport_png=ROOT/"reports"/(name+"_viewport.png")
            frame=w.viewport.screenshot(str(viewport_png),return_img=True)
            assert len(np.unique(frame.reshape(-1,frame.shape[2]),axis=0))>100,"Empty VTK framebuffer"
            frame=np.ascontiguousarray(frame)
            qimage=QtGui.QImage(frame.data,frame.shape[1],frame.shape[0],frame.strides[0],QtGui.QImage.Format_RGB888).copy()
            painter=QtGui.QPainter(screenshot)
            widget=w.viewport.interactor
            point=widget.mapTo(w,QtCore.QPoint(0,0))
            painter.drawImage(QtCore.QRect(point,widget.size()),qimage)
            painter.end()
            self.artifacts.append(str(viewport_png))
        screenshot.save(str(png))
        self.artifacts.append(str(png))

    def fail(self,message):
        self.timer.stop()
        (ROOT/"reports"/"gui_smoke.json").write_text(json.dumps({"passed":False,"error":message}),encoding="utf-8")
        print("GUI_SMOKE_FAIL",message,flush=True)
        self.window.close()
        self.app.exit(1)

    def tick(self):
        w=self.window
        if time.perf_counter()-self.wall_start>180:
            self.fail("Smoke test wall-clock timeout")
            return
        if not w.engine:
            return
        e=w.engine
        try:
            if e.fault:
                raise AssertionError(e.fault)
            if self.stage==0:
                w.timer.stop()
                self.capture("gui_closed")
                assert len(w.scene.actors)==48
                self.static_matrices={key:actor.user_matrix.copy() for key,actor in w.scene.actors.items() if w.scene.rows[key]["group"]=="STATIC_FRAME"}
                # Locate and click actual OPEN button in the LEFT card.
                left_box=next(b for b in w.findChildren(W.QGroupBox) if b.title()=="LEFT DOOR CONTROL")
                open_button=next(b for b in left_box.findChildren(W.QPushButton) if b.text()=="OPEN")
                QtTest.QTest.mouseClick(open_button,QtCore.Qt.LeftButton)
                assert e.doors["L"].profile is not None
                e.advance(0.7)
                held=e.doors["L"].position
                stop_button=next(b for b in left_box.findChildren(W.QPushButton) if b.text()=="STOP")
                QtTest.QTest.mouseClick(stop_button,QtCore.Qt.LeftButton)
                e.advance(1)
                assert e.doors["L"].position==held
                assert not e.command("R","OPEN")
                assert e.command("L","CLOSE")
                e.advance(5)
                assert e.doors["L"].fully_closed
                # Slider uses the same command path as the buttons.
                ctl=w.door_controls["L"]
                ctl["slider"].setValue(1000)
                ctl["slider"].sliderMoved.emit(1000)
                ctl["slider"].sliderReleased.emit()
                e.advance(4)
                assert abs(e.doors["L"].position-100)<1e-7
                e.command("L","CLOSE")
                e.advance(4)
                w.auto_start("ALTERNATING")
                self.stage=1
            else:
                e.advance(1/15)
                self.frames+=1
                w.scene.update(e)
                w.refresh()
                if self.stage==1 and e.sequence.state=="LEFT_SHOE_INSPECTION":
                    w.hide_panels.setChecked(True)
                    self.capture("gui_left_inspection")
                    pose=e.snapshot()
                    e.pause()
                    e.advance(2)
                    assert e.time==pose["time_s"]
                    assert e.robots["L"].snapshot()==pose["robots"]["L"]
                    e.resume()
                    self.stage=2
                if self.stage==2 and e.sequence.state=="RIGHT_SHOE_INSPECTION":
                    self.capture("gui_right_inspection")
                    self.stage=3
                if self.stage==3 and not e.sequence.running:
                    assert e.sequence.completed==2
                    assert all(d.fully_closed for d in e.doors.values())
                    for key,base in self.static_matrices.items():
                        assert np.array_equal(w.scene.actors[key].user_matrix,base)
                    for index,name in ((1,"gui_motion"),(2,"gui_components"),(3,"gui_sequence"),(4,"gui_settings"),(5,"gui_logs")):
                        w.tabs.setCurrentIndex(index)
                        w.refresh()
                        self.app.processEvents()
                        self.capture(name)
                    w.tabs.setCurrentIndex(6)
                    w.refresh()
                    assert len(e.qc.records)==12
                    w.capture_table.selectRow(3)
                    self.app.processEvents()
                    self.capture("gui_camera_qc")
                    assert all(label.pixmap() is not None and not label.pixmap().isNull() for label in w.camera_labels.values())
                    w.save_qc_capture()
                    data={"passed":True,"source_instances":48,"cycles":e.sequence.completed,"fault":e.fault,
                          "final_left_mm":e.doors["L"].position,"final_right_mm":e.doors["R"].position,
                          "checks":["actual OPEN/STOP widget clicks","slider GO TO","opposite-door refusal","pause clock and robot pose",
                                    "alternating FSM","static actor matrices unchanged","seven Qt tabs rendered",
                                    "12 multi-face QC poses","actual FRONT/TOP images","camera capture save"],
                          "render_updates":self.frames,"artifacts":self.artifacts,"wall_s":time.perf_counter()-self.wall_start}
                    (ROOT/"reports"/"gui_smoke.json").write_text(json.dumps(data,indent=2),encoding="utf-8")
                    print(json.dumps(data),flush=True)
                    self.timer.stop()
                    w.close()
                    self.app.quit()
        except Exception as exc:
            import traceback
            traceback.print_exc()
            self.fail(str(exc))
