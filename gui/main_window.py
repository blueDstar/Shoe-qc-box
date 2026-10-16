from __future__ import annotations

import json
import time
from pathlib import Path
import numpy as np
from PySide6 import QtCore, QtGui, QtWidgets as W
from pyvistaqt import QtInteractor
import pyqtgraph as pg

from config import Settings, ROOT
from cad_import.step_reader import sha256
from logs import EventLog
from simulation import Simulation
from scene3d import Scene
from state_machine import STEPS
from sensors.signals import SIGNALS, prefix
from controllers.interlocks import RULES
from motion.profile import Trapezoid
from tools.prepare_cad import prepare_assets
from gui.theme import STYLE


def button(text,callback,kind=None):
    b=W.QPushButton(text)
    if kind:
        b.setObjectName(kind)
    b.clicked.connect(callback)
    return b


def spin(value,maximum=1000,minimum=0,suffix="",decimals=1):
    s=W.QDoubleSpinBox()
    s.setRange(minimum,maximum)
    s.setDecimals(decimals)
    s.setValue(value)
    s.setSuffix(suffix)
    return s


def card(title):
    box=W.QGroupBox(title)
    layout=W.QVBoxLayout(box)
    layout.setSpacing(7)
    layout.setSizeConstraint(W.QLayout.SetMinimumSize)
    box.setSizePolicy(W.QSizePolicy.Expanding,W.QSizePolicy.Minimum)
    return box,layout


def row(layout,*widgets):
    r=W.QHBoxLayout()
    for widget in widgets:
        r.addWidget(widget)
    layout.addLayout(r)


class CADWorker(QtCore.QThread):
    progress=QtCore.Signal(str)
    result=QtCore.Signal(object)
    error=QtCore.Signal(str)

    def __init__(self,settings,force=False):
        super().__init__()
        self.settings,self.force=settings,force

    def run(self):
        try:
            self.result.emit(prepare_assets(self.settings,self.force,self.progress.emit))
        except Exception as exc:
            self.error.emit(str(exc))


class MainWindow(W.QMainWindow):
    def __init__(self,settings):
        super().__init__()
        self.setWindowTitle("Hilykan | Shoe QC Box Simulator")
        self.resize(1550,960)
        self.setMinimumSize(1150,720)
        self.setStyleSheet(STYLE)
        self.settings=settings
        self.engine=self.scene=self.manifest=None
        self.worker=None
        self.video_process=None
        self.door_controls={}
        self.sensor_labels={}
        self.component_items={}
        self.last_log_count=0
        self.accumulator=0.0
        self.last_wall=time.perf_counter()
        self.ui_ticks=0
        self._sensor_display={}
        self.camera_preview=None
        self._preview_wall=0.0
        self._capture_serial=-1
        self._qc_export_busy=False
        self.detail_views={}
        self.detail_plotters={}
        self._detail_wall=0.0
        self._build()
        self.timer=QtCore.QTimer(self)
        self.timer.setTimerType(QtCore.Qt.PreciseTimer)
        self.timer.timeout.connect(self.tick)
        self.timer.start(16)
        QtCore.QTimer.singleShot(0,self.load_cad)

    def _build(self):
        central=W.QWidget()
        self.setCentralWidget(central)
        main=W.QVBoxLayout(central)
        main.setContentsMargins(14,12,14,8)
        head=W.QHBoxLayout()
        brand=W.QLabel("HILYKAN  |  SHOE QC BOX")
        brand.setObjectName("Brand")
        head.addWidget(brand)
        head.addStretch()
        self.clock_label=W.QLabel("OFFLINE  •  STEP / mm  •  120 Hz physics")
        head.addWidget(self.clock_label)
        main.addLayout(head)
        self.banner=W.QLabel("Reading real STEP geometry…")
        self.banner.setObjectName("Banner")
        self.banner.setWordWrap(True)
        main.addWidget(self.banner)
        self.sensor_notice=W.QLabel("LASER DEMO • L/R: đang quét — chưa phát hiện cụm tay/giày")
        self.sensor_notice.setWordWrap(True)
        self.sensor_notice.setStyleSheet("background: #25131C; color: #FF8290; padding: 7px; border-left: 3px solid #FF1744;")
        main.addWidget(self.sensor_notice)
        self.tabs=W.QTabWidget()
        main.addWidget(self.tabs,1)
        self._simulation_tab()
        self._analysis_tab()
        self._cad_tab()
        self._sequence_tab()
        self._settings_tab()
        self._export_tab()
        self._qc_tab()
        self._door_detail_tab()
        self.statusBar().showMessage("Loading CAD")

    def _simulation_tab(self):
        tab=W.QWidget()
        layout=W.QHBoxLayout(tab)
        layout.setContentsMargins(0,8,0,0)
        splitter=W.QSplitter()
        left=W.QWidget()
        vl=W.QVBoxLayout(left)
        vl.setContentsMargins(0,0,0,0)
        toolbar=W.QHBoxLayout()
        for name in ("Isometric","Front","Top","Left","Right","Fit All"):
            toolbar.addWidget(button(name,lambda checked=False,n=name:self.view(n)))
        self.lock_camera=W.QCheckBox("Lock camera")
        self.lock_camera.setChecked(self.settings.camera_locked)
        self.lock_camera.toggled.connect(self.camera_lock)
        toolbar.addWidget(self.lock_camera)
        vl.addLayout(toolbar)
        self.viewport=QtInteractor(left,auto_update=False)
        vl.addWidget(self.viewport.interactor,1)
        self.viewport_note=W.QLabel("Orbit: left drag  •  Pan: middle / Shift + drag  •  Zoom: wheel  •  Click: select CAD component")
        self.viewport_note.setObjectName("Sub")
        vl.addWidget(self.viewport_note)
        splitter.addWidget(left)
        scroll=W.QScrollArea()
        scroll.setWidgetResizable(True)
        sidebar=W.QWidget()
        self.sidebar=W.QVBoxLayout(sidebar)
        self.sidebar.setContentsMargins(5,0,5,0)
        for side in ("L","R"):
            self._door_card(side)
        self._sensor_card()
        self._auto_card()
        self._view_card()
        self._qc_card()
        self._status_card()
        self.sidebar.addStretch()
        scroll.setWidget(sidebar)
        scroll.setMinimumWidth(365)
        splitter.addWidget(scroll)
        splitter.setSizes([1050,430])
        splitter.setStretchFactor(0,7)
        splitter.setStretchFactor(1,3)
        layout.addWidget(splitter)
        self.tabs.addTab(tab,"3D SIMULATION")

    def _door_card(self,side):
        box,vl=card(prefix(side)+" DOOR CONTROL")
        status=W.QLabel("CLOSED  ·  0.0 / 350.0 mm")
        status.setStyleSheet("color: white; font-size: 15px; font-weight: 600;")
        vl.addWidget(status)
        for actions in (("OPEN","CLOSE","STOP"),("HOME","JOG UP","JOG DOWN")):
            row(vl,*[button(a,lambda checked=False,s=side,act=a:self.door_command(s,act),"Primary" if a=="OPEN" else "Stop" if a=="STOP" else None) for a in actions])
        form=W.QFormLayout()
        target=spin(0,350,suffix=" mm")
        speed=spin(self.settings.velocity_mm_s,1000,1," mm/s")
        accel=spin(self.settings.acceleration_mm_s2,5000,1," mm/s²")
        form.addRow("Target",target)
        form.addRow("Speed",speed)
        form.addRow("Acceleration",accel)
        vl.addLayout(form)
        row(vl,button("GO TO",lambda checked=False,s=side:self.door_command(s,"GO TO")),
            button("RESET / HOME",lambda checked=False,s=side:self.door_command(s,"RESET")))
        slider=W.QSlider(QtCore.Qt.Horizontal)
        slider.setRange(0,3500)
        slider.sliderMoved.connect(lambda value,t=target:t.setValue(value/10))
        slider.sliderReleased.connect(lambda s=side:self.door_command(s,"GO TO"))
        vl.addWidget(slider)
        extra=W.QLabel("V 0 mm/s  |  A 0 mm/s²  |  HOLD")
        extra.setWordWrap(True)
        extra.setMinimumHeight(36)
        vl.addWidget(extra)
        self.door_controls[side]={"status":status,"target":target,"speed":speed,"accel":accel,"slider":slider,"extra":extra}
        self.sidebar.addWidget(box)

    def _sensor_card(self):
        box,vl=card("SENSOR SIMULATION · DEMO")
        for side in ("L","R"):
            row(vl,button(prefix(side)+" Approach",lambda checked=False,s=side:self.approach(s)),
                button(prefix(side)+" Withdrawal",lambda checked=False,s=side:self.withdraw(s)))
        self.auto_sensor=W.QCheckBox("Auto Sensor Mode")
        self.auto_sensor.setChecked(self.settings.auto_sensors)
        self.auto_sensor.toggled.connect(lambda value:self.set_sensor_mode(value))
        vl.addWidget(self.auto_sensor)
        self.proximity_auto=W.QCheckBox("Proximity sensor → automatic door request")
        self.proximity_auto.setChecked(self.settings.approach_auto_open)
        self.proximity_auto.toggled.connect(lambda v:setattr(self.settings,"approach_auto_open",v))
        vl.addWidget(self.proximity_auto)
        self.trigger_gap=spin(self.settings.approach_trigger_mm-407,443,243," mm")
        self.trigger_gap.valueChanged.connect(self.set_trigger_gap)
        row(vl,W.QLabel("Trigger gap to door (X)"),self.trigger_gap)
        self.laser_check=W.QCheckBox("Red external sensors / laser / distance labels")
        self.laser_check.setChecked(True)
        self.laser_check.toggled.connect(lambda v:self.scene_set("sensor_emphasis",v))
        vl.addWidget(self.laser_check)
        self.proximity_labels={}
        for side in ("L","R"):
            indicator=W.QLabel(prefix(side)+": đang quét")
            indicator.setWordWrap(True);vl.addWidget(indicator);self.proximity_labels[side]=indicator
        self.chamber_checkbox=W.QCheckBox("Manual test: chamber occupied")
        self.chamber_checkbox.toggled.connect(lambda v:self.override("CHAMBER_OCCUPIED",v))
        vl.addWidget(self.chamber_checkbox)
        for side in ("L","R"):
            cb=W.QCheckBox(prefix(side)+" doorway CLEAR test")
            cb.setChecked(True)
            cb.toggled.connect(lambda v,s=side:self.override(prefix(s)+"_CLEAR_SENSOR",v))
            vl.addWidget(cb)
        self.sensor_pick=W.QComboBox()
        self.sensor_pick.addItems(SIGNALS)
        self.sensor_value=W.QComboBox()
        self.sensor_value.addItems(["TRUE","FALSE","UNKNOWN / FAULT"])
        vl.addWidget(self.sensor_pick)
        row(vl,self.sensor_value,button("Apply Test",self.sensor_test))
        vl.addWidget(button("Clear manual overrides",self.clear_fault_sources))
        note=W.QLabel("CLEAR input cannot bypass measured shoe/gripper/wrist occupancy. Sensors are virtual signals.")
        note.setWordWrap(True)
        vl.addWidget(note)
        self.sidebar.addWidget(box)

    def _auto_card(self):
        box,vl=card("AUTOMATIC QC CYCLE")
        self.cycle_mode=W.QComboBox()
        self.cycle_mode.addItems(["ALTERNATING","LEFT","RIGHT"])
        self.cycle_mode.setCurrentText(self.settings.cycle_mode)
        vl.addWidget(self.cycle_mode)
        row(vl,button("AUTO START",self.auto_start,"Primary"),button("STOP",self.stop,"Stop"))
        row(vl,button("PAUSE",lambda:self.call_engine("pause")),button("RESUME",lambda:self.call_engine("resume")),
            button("STEP",lambda:self.call_engine("step")))
        row(vl,button("LEFT CYCLE",lambda:self.auto_start("LEFT")),button("RIGHT CYCLE",lambda:self.auto_start("RIGHT")))
        row(vl,button("ALTERNATING",lambda:self.auto_start("ALTERNATING")),button("RESET FAULT",lambda:self.call_engine("reset_fault")))
        self.loop_check=W.QCheckBox("Loop Enable")
        self.loop_check.setChecked(self.settings.loop)
        self.loop_check.toggled.connect(lambda v:setattr(self.settings,"loop",v))
        vl.addWidget(self.loop_check)
        self.sim_speed=spin(self.settings.simulation_speed,8,0.1," ×")
        self.sim_speed.valueChanged.connect(lambda v:setattr(self.settings,"simulation_speed",v))
        row(vl,W.QLabel("Simulation speed"),self.sim_speed)
        self.cycle_label=W.QLabel("IDLE")
        self.cycle_label.setWordWrap(True)
        vl.addWidget(self.cycle_label)
        self.cycle_progress=W.QProgressBar()
        self.cycle_progress.setRange(0,100)
        vl.addWidget(self.cycle_progress)
        self.fault_pick=W.QComboBox()
        self.fault_pick.addItems(["DOOR_STALL","SENSOR_NO_OPEN","SENSOR_NO_APPROACH","CAMERA_NOT_READY","DOORWAY_BLOCKED","ROBOT_NOT_WITHDRAWN","UNKNOWN_SENSOR","SIMULTANEOUS_REQUESTS"])
        row(vl,self.fault_pick,button("Inject DEMO",self.inject_fault))
        vl.addWidget(button("Clear DEMO cause",self.clear_fault_sources))
        self.sidebar.addWidget(box)

    def _view_card(self):
        box,vl=card("3D VIEW")
        row(vl,button("Reset Camera",lambda:self.view("Reset Camera")),button("Restore Assembly",self.restore_view))
        row(vl,button("Door motion detail",lambda:self.tabs.setCurrentIndex(7)),button("Focus LEFT",lambda:self.focus_door("L")),button("Focus RIGHT",lambda:self.focus_door("R")))
        self.motion_guide_check=W.QCheckBox("Travel rulers / moving carriage outlines")
        self.motion_guide_check.setChecked(False)
        self.motion_guide_check.toggled.connect(lambda v:self.scene_set("motion_guides",v))
        vl.addWidget(self.motion_guide_check)
        self.hide_panels=W.QCheckBox("Hide roof / front / rear panels")
        self.hide_panels.toggled.connect(lambda v:self.scene_set("hide_panels",v))
        vl.addWidget(self.hide_panels)
        self.demo_check=W.QCheckBox("Virtual Robot Demonstration · DEMO")
        self.demo_check.setChecked(self.settings.demo_enabled)
        self.demo_check.toggled.connect(lambda v:self.scene_set("demo_enabled",v))
        vl.addWidget(self.demo_check)
        self.zone_check=W.QCheckBox("Show virtual sensor zones · DEMO")
        self.zone_check.toggled.connect(lambda v:self.scene_set("sensors_visible",v))
        vl.addWidget(self.zone_check)
        self.transparency=spin(1,1,0.05,"",2)
        self.transparency.valueChanged.connect(lambda v:self.scene_set("opacity",v))
        self.explosion=spin(0,250,0," mm")
        self.explosion.valueChanged.connect(lambda v:self.scene_set("explosion",v))
        row(vl,W.QLabel("Shell opacity"),self.transparency)
        row(vl,W.QLabel("Exploded display"),self.explosion)
        vl.addWidget(W.QLabel("Exploded display never changes collision geometry."))
        self.sidebar.addWidget(box)

    def _status_card(self):
        box,vl=card("STATUS MONITOR")
        self.monitor=W.QLabel("—")
        self.monitor.setWordWrap(True)
        vl.addWidget(self.monitor)
        for name in SIGNALS:
            label=W.QLabel("○  "+name)
            label.setStyleSheet("font-size: 10px;")
            vl.addWidget(label)
            self.sensor_labels[name]=label
        self.sidebar.addWidget(box)

    def _qc_card(self):
        box,vl=card("QC CAMERA / OPTICAL SENSORS · DEMO")
        self.qc_sidebar=W.QLabel("FRONT + TOP cameras • multi-face presentation")
        self.qc_sidebar.setWordWrap(True)
        vl.addWidget(self.qc_sidebar)
        self.rig_check=W.QCheckBox("Show camera bodies / LED lighting")
        self.rig_check.setChecked(True)
        self.rig_check.toggled.connect(lambda v:self.scene_set("rig_visible",v))
        self.fov_check=W.QCheckBox("Show virtual optical fields of view")
        self.fov_check.toggled.connect(lambda v:self.scene_set("fov_visible",v))
        vl.addWidget(self.rig_check)
        vl.addWidget(self.fov_check)
        row(vl,button("CAMERA QC",lambda:self.tabs.setCurrentIndex(6)),button("QC cutaway",lambda:self.hide_panels.setChecked(True)))
        self.sidebar.addWidget(box)

    def _qc_tab(self):
        tab=W.QWidget()
        vl=W.QVBoxLayout(tab)
        self.qc_status=W.QLabel("DEMO optics • real 3D renders • QC PASS/FAIL is simulated, no defect classifier")
        self.qc_status.setWordWrap(True)
        vl.addWidget(self.qc_status)
        self.camera_labels={}
        previews=W.QHBoxLayout()
        for camera,title in (("FRONT","FRONT — main multi-face QC camera"),("TOP","TOP — supplementary upper / profile view")):
            box,bl=card(title)
            image=W.QLabel("Camera feed loading…")
            image.setAlignment(QtCore.Qt.AlignCenter)
            image.setMinimumSize(400,300)
            image.setStyleSheet("background: #060A10; border: 1px solid #25354C;")
            bl.addWidget(image,1)
            self.camera_labels[camera]=image
            previews.addWidget(box)
        vl.addLayout(previews,2)
        controls=W.QHBoxLayout()
        self.live_preview=W.QCheckBox("Live preview (5 FPS, only in this tab)")
        self.live_preview.setChecked(True)
        controls.addWidget(self.live_preview)
        controls.addWidget(button("Refresh camera views",lambda:self.refresh_camera(True)))
        controls.addWidget(button("Save selected capture PNG + JSON",self.save_qc_capture,"Primary"))
        controls.addWidget(button("Save all QC captures",lambda:self.save_qc_capture(True)))
        vl.addLayout(controls)
        self.capture_table=W.QTableWidget(0,7)
        self.capture_table.setHorizontalHeaderLabels(["Capture","Cycle / robot","Shoe face","Simulation s","Alignment","Front / Top FOV","QC demo result"])
        self.capture_table.horizontalHeader().setSectionResizeMode(W.QHeaderView.Stretch)
        self.capture_table.setSelectionBehavior(W.QAbstractItemView.SelectRows)
        self.capture_table.setEditTriggers(W.QAbstractItemView.NoEditTriggers)
        self.capture_table.itemSelectionChanged.connect(self.select_qc_capture)
        vl.addWidget(self.capture_table,2)
        note=W.QLabel("Six presentations: INNER → UPPER → OUTER → OUTSOLE → TOE → HEEL → neutral return. The gripper keeps the shoe; its contact area may be occluded. Camera images are rendered from cached CAD/DEMO meshes at the stored capture pose.")
        note.setWordWrap(True)
        vl.addWidget(note)
        self.tabs.addTab(tab,"CAMERA QC")

    def _analysis_tab(self):
        tab=W.QWidget()
        vl=W.QVBoxLayout(tab)
        row(vl,W.QLabel("Live fixed-step physics history"),button("Preview velocity profile",self.profile_preview),button("Export motion CSV",self.export_motion))
        pg.setConfigOptions(antialias=True,background="#080B10",foreground="#CBD5E1")
        self.plots=[]
        self.curves={}
        for title,keys,unit in (("Door position",("left_mm","right_mm"),"mm"),("Door velocity",("left_v","right_v"),"mm/s"),
                                ("Door acceleration",("left_a","right_a"),"mm/s²"),("Sensor / state activation",("left_clear","right_clear","step"),"signal / step")):
            plot=pg.PlotWidget(title=title)
            plot.setLabel("left",unit)
            plot.setLabel("bottom","Simulation time","s")
            plot.showGrid(x=True,y=True,alpha=0.15)
            plot.addLegend()
            for i,key in enumerate(keys):
                self.curves[key]=plot.plot(pen=pg.mkPen(["#00D9FF","#9A8AFF","#FACC15"][i],width=2),name=key)
            vl.addWidget(plot,1)
            self.plots.append(plot)
        self.tabs.addTab(tab,"MOTION ANALYSIS")

    def _door_detail_tab(self):
        tab=W.QWidget();vl=W.QVBoxLayout(tab)
        note=W.QLabel("Same STEP geometry / live engine. Rulers measure Z displacement from CLOSED; cyan outlines identify the shutter and moving blocks. Guide rails and actuator bodies remain fixed.")
        note.setWordWrap(True);vl.addWidget(note)
        panels=W.QHBoxLayout();self.detail_panels={};self.detail_status={}
        for side in ("L","R"):
            box,bl=card(prefix(side)+" — LINEAR MOTION")
            box.setSizePolicy(W.QSizePolicy.Expanding,W.QSizePolicy.Expanding)
            bl.setSizeConstraint(W.QLayout.SetDefaultConstraint)
            self.detail_status[side]=W.QLabel("CAD detail loading on demand…")
            self.detail_status[side].setWordWrap(True);self.detail_status[side].setMinimumHeight(42);bl.addWidget(self.detail_status[side])
            self.detail_panels[side]=W.QWidget();W.QVBoxLayout(self.detail_panels[side]).setContentsMargins(0,0,0,0)
            self.detail_panels[side].setSizePolicy(W.QSizePolicy.Expanding,W.QSizePolicy.Expanding)
            bl.addWidget(self.detail_panels[side],1)
            row(bl,button("OPEN",lambda checked=False,s=side:self.door_command(s,"OPEN"),"Primary"),
                button("CLOSE",lambda checked=False,s=side:self.door_command(s,"CLOSE")),
                button("STOP",lambda checked=False,s=side:self.door_command(s,"STOP"),"Stop"))
            panels.addWidget(box)
        vl.addLayout(panels,1)
        row(vl,button("LEFT Approach",lambda:self.approach("L")),button("RIGHT Approach",lambda:self.approach("R")),
            button("ALTERNATING AUTO",lambda:self.auto_start("ALTERNATING")),button("PAUSE",lambda:self.call_engine("pause")),button("RESUME",lambda:self.call_engine("resume")))
        self.tabs.addTab(tab,"DOOR MOTION")

    def refresh_door_detail(self,force=False):
        if not self.scene:
            return
        now=time.perf_counter()
        if not force and now-self._detail_wall<1/30:
            return
        self._detail_wall=now
        from scene3d.door_detail import DoorDetail
        for side in ("L","R"):
            if side not in self.detail_views:
                plotter=QtInteractor(self.detail_panels[side],auto_update=False)
                plotter.interactor.setMinimumSize(350,350)
                plotter.interactor.setSizePolicy(W.QSizePolicy.Expanding,W.QSizePolicy.Expanding)
                self.detail_panels[side].layout().addWidget(plotter.interactor,1)
                self.detail_plotters[side]=plotter;self.detail_views[side]=DoorDetail(plotter,self.scene,side)
            self.detail_views[side].update(self.engine)
            d=self.engine.doors[side]
            self.detail_status[side].setText(f"{d.status} • {d.position:.1f}/{d.limit:.0f} mm • target {d.target:.1f} mm • {d.direction}\nv {d.velocity:.1f} mm/s • a {d.accel:.1f} mm/s² • remaining {abs(d.target-d.position):.1f} mm • rod {75+d.position:.1f} mm")

    def focus_door(self,side):
        if self.scene:
            sign=-1 if side=="L" else 1
            self.viewport.camera_position=((sign*1450,-700,850),(sign*430,0,440),(0,0,1))
            self.viewport.camera.parallel_projection=True;self.viewport.camera.parallel_scale=520;self.viewport.render()

    def set_trigger_gap(self,value):
        if self.engine and not self.idle_configuration():
            self.trigger_gap.blockSignals(True);self.trigger_gap.setValue(self.settings.approach_trigger_mm-407);self.trigger_gap.blockSignals(False)
            self.engine.reject("Change proximity threshold only at CLOSED / withdrawn / IDLE")
            return
        self.settings.approach_trigger_mm=value+407
        if hasattr(self,"setting_fields") and "approach_trigger_mm" in self.setting_fields:
            self.setting_fields["approach_trigger_mm"].setValue(value+407)

    def _cad_tab(self):
        tab=W.QWidget()
        vl=W.QVBoxLayout(tab)
        self.cad_summary=W.QLabel("STEP structure loading…")
        self.cad_summary.setWordWrap(True)
        vl.addWidget(self.cad_summary)
        self.scope_combo=W.QComboBox()
        self.scope_combo.addItems(["PLATE_AND_BLOCKS","FULL_ASSEMBLY"])
        self.scope_combo.setCurrentText(self.settings.mechanism_scope)
        row(vl,W.QLabel("Mechanism scope"),self.scope_combo,button("Apply scope",self.apply_scope),
            button("Confirm measured kinematics",self.confirm_kinematics))
        self.component_tree=W.QTreeWidget()
        self.component_tree.setColumnCount(7)
        self.component_tree.setHeaderLabels(["Component / part","Source","ID","Motion group","X / Y / Z mm","Visible","Confidence"])
        self.component_tree.setAlternatingRowColors(True)
        self.component_tree.currentItemChanged.connect(self.component_selected)
        self.component_tree.itemChanged.connect(self.component_visibility)
        vl.addWidget(self.component_tree,3)
        self.component_detail=W.QPlainTextEdit()
        self.component_detail.setReadOnly(True)
        self.component_detail.setMaximumHeight(165)
        vl.addWidget(self.component_detail,1)
        self.assign_combo=W.QComboBox()
        self.assign_combo.addItems(["STATIC_FRAME","LEFT_DOOR_MOVING","RIGHT_DOOR_MOVING","L_ACTUATOR_ROD_PARAMETRIC","R_ACTUATOR_ROD_PARAMETRIC"])
        row(vl,button("Reload CAD",lambda:self.load_cad(True)),self.assign_combo,
            button("Assign Component Group",self.assign_group),button("Export Manifest",self.export_manifest),
            button("Restore Assembly",self.restore_view))
        self.tabs.addTab(tab,"CAD & COMPONENTS")

    def _sequence_tab(self):
        tab=W.QWidget()
        vl=W.QVBoxLayout(tab)
        self.sequence_status=W.QLabel("IDLE")
        vl.addWidget(self.sequence_status)
        self.graph_scene=W.QGraphicsScene()
        self.graph_view=W.QGraphicsView(self.graph_scene)
        self.graph_view.setRenderHint(QtGui.QPainter.Antialiasing)
        self.graph_nodes={}
        for s_idx,side in enumerate(("L","R")):
            for i,name in enumerate(STEPS):
                x=(i%6)*196
                y=s_idx*190+(i//6)*85
                rect=self.graph_scene.addRect(x,y,181,63,QtGui.QPen(QtGui.QColor("#304158")),QtGui.QBrush(QtGui.QColor("#111827")))
                text=self.graph_scene.addText(prefix(side)+"\n"+name.replace("_"," "),QtGui.QFont("Segoe UI",9))
                text.setDefaultTextColor(QtGui.QColor("#CBD5E1"))
                text.setTextWidth(174)
                text.setPos(x+4,y+3)
                self.graph_nodes[side,i]=rect
                if i%6!=5:
                    self.graph_scene.addLine(x+181,y+32,x+196,y+32,QtGui.QPen(QtGui.QColor("#00D9FF")))
                if i==5:
                    self.graph_scene.addLine(x+180,y+63,x+180,y+74,QtGui.QPen(QtGui.QColor("#00D9FF")))
                    self.graph_scene.addLine(0,y+74,x+180,y+74,QtGui.QPen(QtGui.QColor("#00D9FF")))
                    self.graph_scene.addLine(0,y+74,0,y+85,QtGui.QPen(QtGui.QColor("#00D9FF")))
        vl.addWidget(self.graph_view,2)
        self.conditions=W.QTableWidget(len(STEPS),2)
        self.conditions.setHorizontalHeaderLabels(["State","Transition condition"])
        conditions=["FIFO lease acquired; DEMO approaches waiting pose","Opposite door physical CLOSED + closed sensor",
                    "Chamber available, correct robot lease","OPEN passes interlocks","Physical OPEN + open sensor",
                    "Door remains OPEN; swept DEMO path clear","Six camera-facing surfaces; dual-camera capture; return neutral",
                    "Door OPEN; extract shoe, gripper and wrist","CLEAR sensor + physical withdrawal + chamber empty",
                    "CLOSE passes all interlocks","Physical CLOSED + closed sensor","DEMO retreats; QC result logged; release lease"]
        for i,(name,condition) in enumerate(zip(STEPS,conditions)):
            self.conditions.setItem(i,0,W.QTableWidgetItem(name))
            self.conditions.setItem(i,1,W.QTableWidgetItem(condition))
        self.conditions.setEditTriggers(W.QAbstractItemView.NoEditTriggers)
        self.conditions.horizontalHeader().setSectionResizeMode(1,W.QHeaderView.Stretch)
        vl.addWidget(self.conditions,2)
        rules=W.QLabel("\n".join(f"{i+1}. {text}" for i,text in enumerate(RULES)))
        rules.setWordWrap(True)
        rules.setStyleSheet("font-size: 11px; color: #94A3B8;")
        vl.addWidget(rules)
        row(vl,button("NEXT STATE",lambda:self.call_engine("step"),"Primary"),
            button("PAUSE",lambda:self.call_engine("pause")),button("RESUME",lambda:self.call_engine("resume")),
            button("STOP",self.stop,"Stop"))
        self.tabs.addTab(tab,"SEQUENCE CONTROL")

    def _settings_tab(self):
        tab=W.QWidget()
        content=W.QWidget()
        vl=W.QVBoxLayout(content)
        scroll=W.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(content)
        W.QVBoxLayout(tab).addWidget(scroll)
        form=W.QFormLayout()
        self.path_field=W.QLineEdit(self.settings.cad_path)
        holder=W.QWidget()
        hl=W.QHBoxLayout(holder)
        hl.setContentsMargins(0,0,0,0)
        hl.addWidget(self.path_field)
        hl.addWidget(button("Browse",self.browse_cad))
        form.addRow("CAD directory",holder)
        unit=W.QLabel("mm — measured from STEP; no automatic rescale")
        form.addRow("Unit",unit)
        self.setting_fields={}
        for key,label,value,maxi,mini,suffix in (("travel_mm","Travel limit",self.settings.travel_mm,350,1," mm"),
             ("velocity_mm_s","Default speed",self.settings.velocity_mm_s,1000,1," mm/s"),
             ("acceleration_mm_s2","Default acceleration",self.settings.acceleration_mm_s2,5000,1," mm/s²"),
             ("sensor_tolerance_mm","Sensor threshold",self.settings.sensor_tolerance_mm,1,0.001," mm"),
             ("timeout_s","State timeout",self.settings.timeout_s,120,1," s"),
             ("linear_deflection_mm","Tessellation deflection",self.settings.linear_deflection_mm,2,0.02," mm"),
             ("angular_deflection_rad","Tessellation angle",self.settings.angular_deflection_rad,1,0.03," rad")):
            field=spin(value,maxi,mini,suffix,3 if key=="sensor_tolerance_mm" else 2)
            self.setting_fields[key]=field
            form.addRow(label,field)
        for key,label,value,maximum,minimum,suffix in (("qc_camera_fov_deg","DEMO camera vertical FOV",self.settings.qc_camera_fov_deg,110,45," °"),
            ("approach_trigger_mm","Approach zone outer X",self.settings.approach_trigger_mm,850,650," mm"),
            ("inspection_move_s","QC face rotation time",self.settings.inspection_move_s,1.5,0.2," s"),
            ("inspection_hold_s","QC face capture dwell",self.settings.inspection_hold_s,1.5,0.2," s")):
            field=spin(value,maximum,minimum,suffix,2)
            self.setting_fields[key]=field
            form.addRow(label,field)
        self.qc_combo=W.QComboBox()
        self.qc_combo.addItems(["PASS","FAIL"])
        self.qc_combo.setCurrentText(self.settings.qc_result)
        form.addRow("Simulated QC result",self.qc_combo)
        form.addRow("Theme",W.QLabel("Dark Industrial • Neon Blue"))
        vl.addLayout(form)
        row(vl,button("Apply settings",self.apply_settings,"Primary"),button("Save configuration",self.save_config),button("Load configuration",self.load_config))
        desc=W.QLabel("Motion settings can change only with doors CLOSED and robots withdrawn. Rendering-quality changes require Reload CAD. QC FAIL is a simulated inspection result; it does not create an operating FAULT.")
        desc.setWordWrap(True)
        vl.addWidget(desc)
        vl.addStretch()
        self.tabs.addTab(tab,"SETTINGS")

    def _export_tab(self):
        tab=W.QWidget()
        vl=W.QVBoxLayout(tab)
        box,bl=card("VIDEO EXPORT · FIXED SIMULATION TIME")
        self.video_width=W.QSpinBox()
        self.video_width.setRange(320,3840)
        self.video_width.setValue(self.settings.video_width)
        self.video_height=W.QSpinBox()
        self.video_height.setRange(240,2160)
        self.video_height.setValue(self.settings.video_height)
        self.video_fps=W.QComboBox()
        self.video_fps.addItems(["30","60","24"])
        self.video_cycles=W.QSpinBox()
        self.video_cycles.setRange(1,100)
        self.video_cycles.setValue(self.settings.video_cycles)
        row(bl,W.QLabel("Resolution"),self.video_width,W.QLabel("×"),self.video_height,W.QLabel("FPS"),self.video_fps,
            W.QLabel("Cycles"),self.video_cycles)
        self.video_orbit=W.QCheckBox("Orbit Camera")
        self.video_overlay=W.QCheckBox("Show Motion Overlay")
        self.video_overlay.setChecked(self.settings.video_overlay)
        self.video_hide_ui=W.QCheckBox("Hide UI — clean 3D viewport")
        self.video_hide_ui.setChecked(self.settings.video_hide_ui)
        row(bl,self.video_orbit,self.video_overlay,self.video_hide_ui)
        row(bl,button("Export MP4 / H.264",self.export_video,"Primary"),button("Cancel Export",self.cancel_video,"Stop"),button("Capture 3D PNG",self.screenshot))
        self.video_status=W.QLabel("Export runs a fresh deterministic sequence using the same engine and CAD scope. A frame trace accompanies the MP4.")
        self.video_status.setWordWrap(True)
        bl.addWidget(self.video_status)
        vl.addWidget(box)
        row(vl,button("Logs CSV",lambda:self.export_logs("csv")),button("Logs JSON",lambda:self.export_logs("json")),
            button("Save simulation state",self.save_state),button("Load simulation state",self.load_state),button("Open export folder",self.open_exports))
        self.log_table=W.QTableWidget(0,4)
        self.log_table.setHorizontalHeaderLabels(["Timestamp +07:00","Simulation s","Kind","Event"])
        self.log_table.horizontalHeader().setSectionResizeMode(3,W.QHeaderView.Stretch)
        self.log_table.setEditTriggers(W.QAbstractItemView.NoEditTriggers)
        self.log_table.setAlternatingRowColors(True)
        vl.addWidget(self.log_table,1)
        self.tabs.addTab(tab,"LOG & EXPORT")

    def load_cad(self,force=False):
        if self._qc_export_busy:
            return self.error("Finish QC capture export before Reload CAD")
        if self.worker and self.worker.isRunning():
            return
        if self.engine and (any(not d.fully_closed for d in self.engine.doors.values()) or any(not r.withdrawn for r in self.engine.robots.values())):
            self.error("Return doors to CLOSED and withdraw DEMO bodies before Reload CAD")
            return
        self.banner.setText("Reading STEP and validating cache…")
        self.tabs.setEnabled(False)
        if self.engine:
            self.engine.pause()
        self.worker=CADWorker(self.settings,force)
        self.worker.progress.connect(self.banner.setText)
        self.worker.error.connect(self.cad_error)
        self.worker.result.connect(self.cad_loaded)
        self.worker.start()

    def cad_loaded(self,manifest):
        self.tabs.setEnabled(True)
        self.manifest=manifest
        for plotter in self.detail_plotters.values():
            plotter.close();plotter.interactor.setParent(None)
        self.detail_plotters.clear();self.detail_views.clear()
        source_hash=sha256(self.settings.cad_directory/self.settings.main_assembly)
        if self.settings.confirmed_source_sha256!=source_hash:
            self.settings.kinematics_confirmed=False
        self.engine=Simulation(self.settings,manifest,EventLog(ROOT/"logs"/"session.jsonl"))
        if self.camera_preview:
            self.camera_preview.close()
            self.camera_preview=None
        self._capture_serial=-1
        self.viewport.clear()
        self.scene=Scene(self.viewport,manifest,self.select_component)
        self.scene.demo_enabled=self.demo_check.isChecked()
        self.scene.sensors_visible=self.zone_check.isChecked()
        self.scene.hide_panels=self.hide_panels.isChecked()
        self.camera_lock(self.lock_camera.isChecked())
        self.populate_tree()
        n=len(manifest["preflight"]["source_envelope_overlaps"])
        envelope=" × ".join(f"{v:g}" for v in manifest["assembly_dimensions_mm"])
        bom_status="BOM matched" if all(x["matched"] for x in manifest["bom"]) else "WARNING: BOM mismatch / missing parts"
        self.cad_summary.setText(f"{len(manifest['components'])} STEP/XDE instances • {bom_status} • {manifest['unit']} • envelope {envelope} mm\n"
                                 f"CLOSED is the only geometry source. OPEN references verify +350 mm. {n} source envelope overlaps; P09/P11 excluded in the approved analysis scope.\n"
                                 "Rod: measured Ø12, lower Z=363; length 75 → 425 mm. Parametric display, not a vendor-validated actuator.")
        self.last_log_count=0
        self.log_table.setRowCount(0)
        self.scene.update(self.engine)
        self.statusBar().showMessage("CAD ready — original STEP untouched")
        self.last_wall=time.perf_counter()
        self.accumulator=0
        self.refresh()

    def cad_error(self,message):
        self.tabs.setEnabled(True)
        if self.engine:
            self.engine.resume()
        self.error(message)

    def populate_tree(self):
        self.component_tree.blockSignals(True)
        self.component_tree.clear()
        self.component_items={}
        groups={}
        for rec in self.manifest["components"]:
            g=rec["group"]
            if g not in groups:
                item=W.QTreeWidgetItem([g])
                self.component_tree.addTopLevelItem(item)
                groups[g]=item
            item=W.QTreeWidgetItem([rec["name"]+" / "+rec["part_id"],rec["source"],rec["id"],g,
                                   " / ".join(f"{v:.1f}" for v in rec["dimensions_mm"]),"",rec["confidence"]])
            item.setData(0,QtCore.Qt.UserRole,rec["id"])
            item.setFlags(item.flags()|QtCore.Qt.ItemIsUserCheckable)
            item.setCheckState(5,QtCore.Qt.Checked if rec["visible"] else QtCore.Qt.Unchecked)
            if rec["part_id"] in ("P09","P11"):
                item.setForeground(0,QtGui.QColor("#FACC15"))
                item.setToolTip(0,"Source CAD interference: excluded from approved motion analysis.")
            groups[g].addChild(item)
            self.component_items[rec["id"]]=item
        self.component_tree.expandAll()
        for column in (0,1,2,3,4):
            self.component_tree.resizeColumnToContents(column)
        self.component_tree.blockSignals(False)

    def tick(self):
        now=time.perf_counter()
        elapsed=min(now-self.last_wall,0.25)
        self.last_wall=now
        if not self.engine:
            return
        self.accumulator+=elapsed*self.settings.simulation_speed
        steps=0
        while self.accumulator>=self.engine.fixed_dt and steps<240:
            self.engine.advance(self.engine.fixed_dt)
            self.accumulator-=self.engine.fixed_dt
            steps+=1
        if self.scene and self.tabs.currentIndex()==0:
            self.scene.update(self.engine)
        elif self.scene and self.tabs.currentIndex()==7:
            self.refresh_door_detail()
        self.ui_ticks+=1
        if self.ui_ticks%6==0:
            self.refresh()

    def refresh(self):
        e=self.engine
        if not e:
            return
        for side,controls in self.door_controls.items():
            d=e.doors[side]
            controls["status"].setText(f"{d.status}  ·  {d.position:.1f} / {d.limit:.1f} mm")
            controls["extra"].setText(f"V {d.velocity:.1f} mm/s  |  A {d.accel:.1f} mm/s²\n{d.direction}  ·  remaining {abs(d.target-d.position):.1f} mm  ·  target {d.target:.1f}")
            if not controls["slider"].isSliderDown():
                controls["slider"].setValue(round(d.position*10))
            if self.engine.sequence.running and not controls["target"].hasFocus():
                controls["target"].setValue(d.target)
        seq=e.sequence
        parts=[]
        for side in ("L","R"):
            p=prefix(side);value=e.sensors.values[p+"_APPROACH_SENSOR"];measurement=e.sensors.measurements.get(side,{})
            gap=measurement.get("door_gap_mm",0);threshold=self.settings.approach_trigger_mm-407
            if p+"_APPROACH_SENSOR" in e.sensors.overrides:
                state="TEST INPUT "+str(value)
            elif value is True:
                state="ĐÃ PHÁT HIỆN TAY/GIÀY → YÊU CẦU MỞ"
            elif value is None:
                state="TÍN HIỆU KHÔNG XÁC ĐỊNH"
            else:
                state="ĐANG QUÉT / NGOÀI VÙNG"
            opening=" • ĐANG MỞ CỬA" if e.doors[side].status=="OPENING" else " • CHỜ LIÊN ĐỘNG" if side in e.queue and e.owner!=side else ""
            text=f"{side}: {state}{opening} • dX {gap:.0f} / ngưỡng {threshold:.0f} mm"
            self.proximity_labels[side].setText(text);parts.append(text)
        self.sensor_notice.setText("LASER DEMO | "+"  |  ".join(parts))
        mode="PAUSED" if seq.paused else "RUNNING" if seq.running else "MANUAL / IDLE"
        self.cycle_label.setText(seq.state+"\n"+mode+f"  ·  completed {seq.completed}  ·  QC {seq.last_result}")
        self.cycle_progress.setValue(round(seq.progress*100))
        for name,label in self.sensor_labels.items():
            value=e.sensors.values[name]
            if name not in self._sensor_display or self._sensor_display[name]!=value:
                label.setText(("●  " if value else "○  " if value is False else "?  ")+name)
                label.setStyleSheet("font-size: 10px; color: "+("#4ADE80" if value else "#94A3B8" if value is False else "#EF4444")+";")
                self._sensor_display[name]=value
        self.monitor.setText(f"Active robot / lease: {e.owner or 'NONE'}\nQueue: {list(e.queue)}\nChamber: {e.sensors.values['CHAMBER_OCCUPIED']}\n"
                             f"Cycle time: {seq.last_cycle_s:.2f} s\nScope: {self.settings.mechanism_scope}\nInterlock: {e.last_rejection or 'READY'}\nFault: {e.fault or 'NONE'}")
        proximity=" / ".join(f"{s}: {e.sensors.measurements.get(s,{}).get('nearest_x_mm',0):.0f} mm" for s in ("L","R"))
        self.qc_sidebar.setText(f"Face: {e.qc.face} • captured {len(e.qc.captured)}/6\nFRONT {e.qc.ready['FRONT']} / TOP {e.qc.ready['TOP']}\nNearest payload X: {proximity}\nApproach opens only after detection; CLEAR checks entire arm.")
        if e.fault:
            text="FAULT · "+e.fault
            style="Fault"
        elif not self.settings.kinematics_confirmed:
            text="Confirm measured kinematics in CAD & Components before motion. Geometry is available for inspection."
            style="Banner"
        else:
            text="CAD Rev A · approved plate / block / parametric rod analysis · P09/P11 source clashes excluded · DEMO robot & sensors · "+(e.last_rejection or mode)
            style="Banner"
        self.banner.setText(text)
        if self.banner.objectName()!=style:
            self.banner.setObjectName(style)
            self.banner.style().unpolish(self.banner)
            self.banner.style().polish(self.banner)
        self.clock_label.setText(f"{e.time:7.2f} s  •  {self.settings.simulation_speed:.1f}×  •  {mode}")
        self.sequence_status.setText(f"{seq.state} · {mode} · elapsed {seq.elapsed:.2f} / timeout {self.settings.timeout_s:.1f} s · lease {e.owner} · queue {list(e.queue)}")
        if self.tabs.currentIndex()==3:
            for (side,index),rect in self.graph_nodes.items():
                rect.setBrush(QtGui.QBrush(QtGui.QColor("#007D92" if side==seq.side and index==seq.index else "#111827")))
            self.graph_view.fitInView(self.graph_scene.itemsBoundingRect(),QtCore.Qt.KeepAspectRatio)
            if seq.index>=0:
                self.conditions.selectRow(seq.index)
        if self.tabs.currentIndex()==1 and e.history:
            data=list(e.history)[::4]
            t=[x["time_s"] for x in data]
            for key,curve in self.curves.items():
                curve.setData(t,[x[key] for x in data])
        if self.tabs.currentIndex()==5:
            events=list(e.log.events)
            if len(events)!=self.last_log_count:
                selected=events[-1500:]
                self.log_table.setRowCount(len(selected))
                for i,record in enumerate(selected):
                    for j,key in enumerate(("timestamp","simulation_s","kind","message")):
                        self.log_table.setItem(i,j,W.QTableWidgetItem(str(record[key])))
                self.log_table.scrollToBottom()
                self.last_log_count=len(events)
        if self.tabs.currentIndex()==6:
            self.refresh_camera()
        if self.tabs.currentIndex()==7:
            self.refresh_door_detail()

    def door_command(self,side,action):
        if not self.engine:
            return
        ctl=self.door_controls[side]
        d=self.engine.doors[side]
        if d.profile is None:
            d.speed,d.acceleration=ctl["speed"].value(),ctl["accel"].value()
        if self.engine.command(side,action,ctl["target"].value()):
            ctl["target"].setValue(d.target)
        self.refresh()

    def call_engine(self,name):
        if self.engine:
            getattr(self.engine,name)()
            self.refresh()

    def stop(self):
        self.call_engine("stop")

    def auto_start(self,mode=None):
        if not self.engine:
            return
        if not isinstance(mode,str):
            mode=self.cycle_mode.currentText()
        self.cycle_mode.setCurrentText(mode)
        self.engine.start(mode)
        self.refresh()

    def approach(self,side):
        if self.engine:
            self.engine.begin_approach(side)
            self.refresh()

    def refresh_camera(self,force=False,record=None):
        if not self.scene:
            return
        e=self.engine
        if self._capture_serial!=e.qc.serial:
            self.capture_table.blockSignals(True)
            rows=list(e.qc.records)
            self.capture_table.setRowCount(len(rows))
            for i,rec in enumerate(rows):
                views=" / ".join("IN FRAME" if rec["views"][name]["shoe_in_frame"] else "CLIPPED" for name in ("FRONT","TOP"))
                values=(rec["id"],rec["cycle_id"],rec["face"],f"{rec['time_s']:.3f}",f"{rec['alignment_cos']:.3f}",views,rec["result"])
                for j,value in enumerate(values):
                    self.capture_table.setItem(i,j,W.QTableWidgetItem(str(value)))
            self.capture_table.blockSignals(False)
            self._capture_serial=e.qc.serial
        now=time.perf_counter()
        if not force and (not self.live_preview.isChecked() or now-self._preview_wall<0.2):
            return
        self._preview_wall=now
        try:
            from qc.preview import CameraPreview
            if self.camera_preview is None:
                self.camera_preview=CameraPreview(self.scene)
            for camera,label in self.camera_labels.items():
                rgb=self.camera_preview.render(e,camera,record)
                qimage=QtGui.QImage(rgb.data,rgb.shape[1],rgb.shape[0],rgb.strides[0],QtGui.QImage.Format_RGB888).copy()
                pixmap=QtGui.QPixmap.fromImage(qimage)
                label.setPixmap(pixmap.scaled(label.size(),QtCore.Qt.KeepAspectRatio,QtCore.Qt.SmoothTransformation))
            self.qc_status.setText((f"Stored capture {record['id']} • {record['side']} / {record['face']} • t {record['time_s']:.3f} s" if record else f"LIVE • {e.qc.face} • t {e.time:.2f} s")+"\nDEMO camera renders; gripper contact may occlude a patch. PASS/FAIL is simulated.")
        except Exception as exc:
            self.error("Camera renderer: "+str(exc))

    def select_qc_capture(self):
        index=self.capture_table.currentRow()
        if self.engine and 0<=index<len(self.engine.qc.records):
            self.live_preview.setChecked(False)
            self.refresh_camera(True,list(self.engine.qc.records)[index])

    def save_qc_capture(self,all_records=False):
        if not self.engine or not self.engine.qc.records:
            return self.error("Run a QC inspection to create capture poses first")
        if self._qc_export_busy:
            return self.error("QC capture export is already running")
        from qc.preview import CameraPreview
        if self.camera_preview is None:
            self.camera_preview=CameraPreview(self.scene)
        records=list(self.engine.qc.records)
        index=self.capture_table.currentRow()
        selected=records if all_records is True else [records[index] if index>=0 else records[-1]]
        directory=ROOT/"exports"/"qc_captures"
        self._qc_export_busy=True
        exporter=self.camera_preview
        engine=self.engine
        def save_next(index=0):
            try:
                exporter.save_record(engine,selected[index],directory)
                self.statusBar().showMessage(f"QC capture export {index+1} / {len(selected)}")
                if index+1<len(selected):
                    QtCore.QTimer.singleShot(0,lambda:save_next(index+1))
                else:
                    self._qc_export_busy=False
                    self.statusBar().showMessage(f"Saved {len(selected)*2} actual camera PNGs and pose JSON in {directory}",10000)
            except Exception as exc:
                self._qc_export_busy=False
                self.error("QC capture export: "+str(exc))
        save_next()

    def withdraw(self,side):
        if self.engine:
            seq=self.engine.sequence
            if seq.side==side and seq.index==6:
                seq.transition(7)
                self.engine.resume()
            else:
                self.engine.reject("Withdrawal demo is available during SHOE_INSPECTION; it cannot force a CLEAR signal")
            self.refresh()

    def override(self,name,value):
        if self.engine:
            self.engine.sensors.set(name,value)
            self.engine.log.add(self.engine.time,"SENSOR_TEST",name,value=value)

    def sensor_test(self):
        self.override(self.sensor_pick.currentText(),[True,False,None][self.sensor_value.currentIndex()])

    def set_sensor_mode(self,value):
        self.settings.auto_sensors=value
        if self.engine:
            self.engine.sensors.auto=value

    def clear_fault_sources(self):
        self.call_engine("clear_fault_source")

    def inject_fault(self):
        if self.engine:
            self.engine.inject(self.fault_pick.currentText(),self.engine.owner or "L")

    def view(self,name):
        if self.scene:
            self.scene.camera(name)

    def camera_lock(self,value):
        self.settings.camera_locked=value
        self.viewport.interactor.setEnabled(not value)

    def scene_set(self,name,value):
        if self.scene:
            setattr(self.scene,name,value)
            if name=="demo_enabled":
                self.settings.demo_enabled=value
            self.scene.update(self.engine)

    def restore_view(self):
        if self.scene:
            self.hide_panels.setChecked(False)
            self.explosion.setValue(0)
            self.transparency.setValue(1)
            self.scene.restore()
            self.populate_tree()
            self.scene.update(self.engine)

    def select_component(self,key):
        if key in self.component_items:
            self.component_tree.setCurrentItem(self.component_items[key])

    def component_selected(self,item,previous=None):
        if not item or not self.scene:
            return
        key=item.data(0,QtCore.Qt.UserRole)
        if key:
            self.scene.select(key)
            self.component_detail.setPlainText(json.dumps(self.scene.rows[key],indent=2,ensure_ascii=False))

    def component_visibility(self,item,column):
        if self.scene and column==5:
            key=item.data(0,QtCore.Qt.UserRole)
            if key:
                self.scene.rows[key]["visible"]=item.checkState(5)==QtCore.Qt.Checked
                self.scene.update(self.engine)

    def idle_configuration(self):
        return self.engine and all(d.fully_closed for d in self.engine.doors.values()) and all(r.withdrawn for r in self.engine.robots.values()) and self.engine.sequence.side is None

    def apply_scope(self):
        if not self.idle_configuration():
            return self.error("Change scope only at CLOSED / withdrawn / IDLE")
        self.settings.mechanism_scope=self.scope_combo.currentText()
        self.scene.update(self.engine)
        self.refresh()

    def confirm_kinematics(self):
        if not self.manifest or not self.idle_configuration():
            return self.error("Confirm only at CLOSED / withdrawn / IDLE")
        rows=self.manifest["components"]
        for name,group in (("SHUTTER_L","LEFT_DOOR_MOVING"),("SHUTTER_R","RIGHT_DOOR_MOVING")):
            item=next((x for x in rows if x["name"]==name),None)
            if not item or item["group"]!=group:
                return self.error("Shutter mapping does not match opposite X end walls")
        for rec in rows:
            if rec["part_id"]=="P08":
                expected="LEFT_DOOR_MOVING" if rec["name"].startswith("BLOCK_L") else "RIGHT_DOOR_MOVING"
                if rec["group"]!=expected:
                    return self.error("Measured guide blocks must follow their matching shutter")
        if self.settings.travel_mm<340:
            return self.error("Configured lift cannot fully clear the measured aperture; minimum 340 mm includes 5 mm clearance")
        if self.manifest["unit"]!="mm" or self.manifest["preflight"]["critical_shutter_collisions"]:
            return self.error("Unconfirmed units or shutter-vs-fixed collision")
        self.settings.kinematics_confirmed=True
        self.settings.confirmed_source_sha256=sha256(self.settings.cad_directory/self.settings.main_assembly)
        self.settings.save(ROOT/"config"/"user.json")
        (ROOT/"config"/"cad_manifest.json").write_text(json.dumps(self.manifest,indent=2,ensure_ascii=False),encoding="utf-8")
        self.engine.log.add(self.engine.time,"CONFIG","Measured kinematics confirmed",scope=self.settings.mechanism_scope)
        self.refresh()

    def assign_group(self):
        if not self.idle_configuration():
            return self.error("Group assignments require CLOSED / withdrawn / IDLE")
        item=self.component_tree.currentItem()
        key=item.data(0,QtCore.Qt.UserRole) if item else None
        if not key:
            return
        rec=self.scene.rows[key]
        group=self.assign_combo.currentText()
        if rec["part_id"] in ("P01","P02","P03","P04","P06","P07","P10","P12","P13") and group!="STATIC_FRAME":
            return self.error("This measured fixed part cannot move with the door")
        if rec["part_id"]!="P10R" and group.endswith("ACTUATOR_ROD_PARAMETRIC"):
            return self.error("Parametric extension is reserved for measured P10R rods")
        rec["group"]=group
        self.settings.kinematics_confirmed=False
        self.populate_tree()
        self.refresh()

    def browse_cad(self):
        path=W.QFileDialog.getExistingDirectory(self,"STEP directory",str(self.settings.cad_directory))
        if path:
            self.path_field.setText(path)

    def apply_settings(self):
        if not self.idle_configuration():
            return self.error("Apply settings only at CLOSED / withdrawn / IDLE")
        try:
            values={key:field.value() for key,field in self.setting_fields.items()}
            candidate=Settings(**{**self.settings.__dict__,**values,"cad_path":self.path_field.text(),"qc_result":self.qc_combo.currentText()}).validate()
            changed_geometry=any(getattr(candidate,k)!=getattr(self.settings,k) for k in ("cad_path","linear_deflection_mm","angular_deflection_rad"))
            changed_travel=candidate.travel_mm!=self.settings.travel_mm
            self.settings.__dict__.update(candidate.__dict__)
            if changed_geometry or changed_travel:
                self.settings.kinematics_confirmed=False
            for side,d in self.engine.doors.items():
                d.limit,d.speed,d.acceleration,d.tolerance=self.settings.travel_mm,self.settings.velocity_mm_s,self.settings.acceleration_mm_s2,self.settings.sensor_tolerance_mm
                ctl=self.door_controls[side]
                ctl["target"].setMaximum(d.limit)
                ctl["slider"].setMaximum(round(d.limit*10))
                ctl["speed"].setValue(d.speed)
                ctl["accel"].setValue(d.acceleration)
            self.trigger_gap.blockSignals(True);self.trigger_gap.setValue(self.settings.approach_trigger_mm-407);self.trigger_gap.blockSignals(False)
            if changed_geometry:
                self.load_cad(True)
            self.refresh()
        except Exception as exc:
            self.error(str(exc))

    def path_dialog(self,title,extension,save=True):
        directory=ROOT/"exports"
        directory.mkdir(exist_ok=True)
        function=W.QFileDialog.getSaveFileName if save else W.QFileDialog.getOpenFileName
        path,_=function(self,title,str(directory),f"{extension.upper()} (*.{extension})")
        if path and save and not path.lower().endswith("."+extension):
            path+="."+extension
        return path

    def save_config(self):
        path=self.path_dialog("Save configuration","json")
        if path:
            self.settings.save(path)

    def load_config(self):
        if not self.idle_configuration():
            return self.error("Load configuration only at CLOSED / withdrawn / IDLE")
        path=self.path_dialog("Load configuration","json",False)
        if path:
            try:
                loaded=Settings.load(path)
                self.settings.__dict__.update(loaded.__dict__)
                self.path_field.setText(loaded.cad_path)
                for key,field in self.setting_fields.items():
                    field.setValue(getattr(loaded,key))
                self.scope_combo.setCurrentText(loaded.mechanism_scope)
                self.auto_sensor.setChecked(loaded.auto_sensors)
                self.sim_speed.setValue(loaded.simulation_speed)
                self.loop_check.setChecked(loaded.loop)
                self.demo_check.setChecked(loaded.demo_enabled)
                self.load_cad()
            except Exception as exc:
                self.error(str(exc))

    def export_manifest(self):
        if self.manifest:
            path=self.path_dialog("Export measured manifest","json")
            if path:
                Path(path).write_text(json.dumps(self.manifest,indent=2,ensure_ascii=False),encoding="utf-8")

    def export_logs(self,kind):
        if self.engine:
            path=self.path_dialog("Export logs",kind)
            if path:
                getattr(self.engine.log,"export_"+kind)(path)

    def export_motion(self):
        if self.engine:
            import csv
            path=self.path_dialog("Export motion history","csv")
            if path and self.engine.history:
                with open(path,"w",encoding="utf-8-sig",newline="") as f:
                    writer=csv.DictWriter(f,fieldnames=list(self.engine.history[0]))
                    writer.writeheader()
                    writer.writerows(self.engine.history)

    def save_state(self):
        if self.engine:
            path=self.path_dialog("Save simulation state","json")
            if path:
                self.engine.save_state(path)

    def load_state(self):
        if self.engine:
            path=self.path_dialog("Load simulation state","json",False)
            if path:
                try:
                    self.engine.load_state(path)
                    self.scene.update(self.engine)
                    self.refresh()
                except Exception as exc:
                    self.error(str(exc))

    def screenshot(self):
        if self.scene:
            path=self.path_dialog("Capture real 3D viewport","png")
            if path:
                self.scene.update(self.engine)
                self.viewport.screenshot(path)

    def profile_preview(self):
        dialog=W.QDialog(self)
        dialog.setWindowTitle("Analytical trapezoid profile")
        dialog.resize(800,650)
        vl=W.QVBoxLayout(dialog)
        controls=self.door_controls["L"]
        profile=Trapezoid(0,self.settings.travel_mm,controls["speed"].value(),controls["accel"].value())
        t=np.linspace(0,profile.duration,300)
        samples=np.array([profile.sample(float(v)) for v in t])
        for i,unit in enumerate(("mm","mm/s","mm/s²")):
            plot=pg.PlotWidget()
            plot.setLabel("left",unit)
            plot.setLabel("bottom","s")
            plot.plot(t,samples[:,i],pen=pg.mkPen("#00D9FF",width=2))
            vl.addWidget(plot)
        vl.addWidget(W.QLabel(f"Travel {self.settings.travel_mm:.1f} mm • duration {profile.duration:.3f} s • peak {profile.peak:.1f} mm/s"))
        dialog.exec()

    def export_video(self):
        if not self.engine or not self.settings.kinematics_confirmed:
            return self.error("Confirm CAD kinematics before video export")
        if self.video_process and self.video_process.state()!=QtCore.QProcess.NotRunning:
            return self.error("Video export already running")
        path=self.path_dialog("Export deterministic MP4","mp4")
        if not path:
            return
        self.settings.video_width=self.video_width.value()
        self.settings.video_height=self.video_height.value()
        self.settings.video_fps=int(self.video_fps.currentText())
        self.settings.video_cycles=self.video_cycles.value()
        self.settings.video_orbit=self.video_orbit.isChecked()
        self.settings.video_overlay=self.video_overlay.isChecked()
        self.settings.video_hide_ui=self.video_hide_ui.isChecked()
        cfg=ROOT/"exports"/"video_job.json"
        self.settings.save(cfg)
        import sys
        self.video_process=QtCore.QProcess(self)
        self.video_process.setProcessChannelMode(QtCore.QProcess.MergedChannels)
        self.video_process.readyReadStandardOutput.connect(self.video_output)
        self.video_process.finished.connect(lambda code,status:self.video_status.setText("Export completed: "+path if code==0 else "Export failed / cancelled; see output. Partial files are not labeled complete."))
        self.video_process.start(sys.executable,["-u",str(ROOT/"main.py"),"--config",str(cfg),"--export-video",path])
        self.video_status.setText("Exporting with fixed simulation steps in a separate process…")

    def video_output(self):
        if self.video_process:
            output=bytes(self.video_process.readAllStandardOutput()).decode("utf-8",errors="replace")
            if output.strip():
                self.video_status.setText(output.strip()[-800:])

    def cancel_video(self):
        if self.video_process:
            self.video_process.terminate()
            QtCore.QTimer.singleShot(2000,lambda:self.video_process.kill() if self.video_process and self.video_process.state()!=QtCore.QProcess.NotRunning else None)

    def open_exports(self):
        path=ROOT/"exports"
        path.mkdir(exist_ok=True)
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(path)))

    def error(self,message):
        self.banner.setText("ERROR · "+message)
        self.statusBar().showMessage(message,12000)
        if self.engine:
            self.engine.log.add(self.engine.time,"ERROR",message)

    def closeEvent(self,event):
        if self.worker and self.worker.isRunning():
            self.error("CAD worker still reading; close after import finishes")
            event.ignore()
            return
        self.timer.stop()
        self.cancel_video()
        if self.engine:
            self.engine.save_state(ROOT/"logs"/"last_state.json")
        self.viewport.close()
        for plotter in self.detail_plotters.values():
            plotter.close()
        if self.camera_preview:
            self.camera_preview.close()
        event.accept()
