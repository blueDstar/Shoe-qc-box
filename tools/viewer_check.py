import sys
import os
from pathlib import Path
os.environ["QT_API"]="pyside6"
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import numpy as np
from PySide6 import QtCore,QtWidgets as W,QtGui
from main import load_settings
from gui.main_window import MainWindow

app=W.QApplication([])
w=MainWindow(load_settings())
w.show()
ticks=0


def check():
    global ticks
    if not w.scene:
        return
    ticks+=1
    if ticks<5:
        return
    w.scene.update(w.engine)
    frame=w.viewport.screenshot(str(ROOT/"reports"/"viewport_closed.png"),return_img=True)
    timer.stop()
    print("RENDER",frame.shape,"RGB range",int(frame.min()),int(frame.max()),"unique",len(np.unique(frame.reshape(-1,3),axis=0)),flush=True)
    print("CAPABILITIES",w.viewport.ren_win.ReportCapabilities().split("OpenGL extensions:")[0],flush=True)
    # QWidget.grab excludes a native OpenGL surface. Documentation captures composite
    # the actual framebuffer at the widget rectangle; this does not change the live UI.
    shot=w.grab()
    frame=np.ascontiguousarray(frame)
    qimage=QtGui.QImage(frame.data,frame.shape[1],frame.shape[0],frame.strides[0],QtGui.QImage.Format_RGB888).copy()
    painter=QtGui.QPainter(shot)
    widget=w.viewport.interactor
    point=widget.mapTo(w,QtCore.QPoint(0,0))
    painter.drawImage(QtCore.QRect(point,widget.size()),qimage)
    painter.end()
    shot.save(str(ROOT/"reports"/"gui_viewer_verified.png"))
    timer.stop()
    w.close()
    app.quit()


timer=QtCore.QTimer()
timer.timeout.connect(check)
timer.start(250)
app.exec()
