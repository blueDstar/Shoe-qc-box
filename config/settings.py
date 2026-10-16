from __future__ import annotations

from dataclasses import dataclass, asdict, fields
from pathlib import Path
import json
import math

ROOT = Path(__file__).resolve().parents[1]


@dataclass
class Settings:
    cad_path: str = "Shoe_QC_Dual_Shutter_STEP_CAD_BOM_RevA/STEP"
    main_assembly: str = "GA_ASSEMBLY_CLOSED.step"
    unit: str = "mm"
    travel_mm: float = 350.0
    velocity_mm_s: float = 180.0
    acceleration_mm_s2: float = 600.0
    sensor_tolerance_mm: float = 0.02
    timeout_s: float = 25.0
    simulation_speed: float = 1.0
    linear_deflection_mm: float = 0.15
    angular_deflection_rad: float = 0.25
    kinematics_confirmed: bool = False
    mechanism_scope: str = "PLATE_AND_BLOCKS"
    confirmed_source_sha256: str = ""
    demo_enabled: bool = True
    auto_sensors: bool = True
    loop: bool = False
    cycle_mode: str = "ALTERNATING"
    theme: str = "Dark Industrial"
    video_width: int = 1920
    video_height: int = 1080
    video_fps: int = 30
    video_cycles: int = 2
    video_orbit: bool = False
    video_overlay: bool = True
    video_hide_ui: bool = True
    camera_locked: bool = False
    qc_result: str = "PASS"
    advanced_demo: bool = True
    qc_station_enabled: bool = True
    qc_camera_fov_deg: float = 90.0
    inspection_move_s: float = 0.8
    inspection_hold_s: float = 0.5
    approach_trigger_mm: float = 750.0
    approach_auto_open: bool = True

    def validate(self):
        if self.unit != "mm":
            raise ValueError("Only measured mm geometry is supported; no implicit unit conversion.")
        for key in ("travel_mm", "velocity_mm_s", "acceleration_mm_s2", "sensor_tolerance_mm",
                    "timeout_s", "simulation_speed", "linear_deflection_mm", "angular_deflection_rad"):
            v = getattr(self, key)
            if not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0:
                raise ValueError(key + " must be finite and positive")
        if self.travel_mm > 350:
            raise ValueError("Travel exceeds the measured 350 mm Rev A reference. Revalidate CAD before extending it.")
        if self.cycle_mode not in ("LEFT", "RIGHT", "ALTERNATING"):
            raise ValueError("Unknown cycle mode")
        if self.qc_result not in ("PASS", "FAIL"):
            raise ValueError("QC result must be PASS or FAIL")
        if self.mechanism_scope not in ("PLATE_AND_BLOCKS", "FULL_ASSEMBLY"):
            raise ValueError("Unknown mechanism scope")
        if self.video_width < 64 or self.video_height < 64 or self.video_fps not in (24,30,60):
            raise ValueError("Invalid video settings")
        if not 45<=self.qc_camera_fov_deg<=110 or not 650<=self.approach_trigger_mm<=850:
            raise ValueError("Invalid DEMO camera FOV / approach zone")
        if not 0.2<=self.inspection_move_s<=1.5 or not 0.2<=self.inspection_hold_s<=1.5:
            raise ValueError("Invalid multi-face QC timing")
        if self.advanced_demo and self.inspection_duration_s>=self.timeout_s:
            raise ValueError("Inspection duration must be shorter than state timeout")
        return self

    @property
    def inspection_duration_s(self):
        return 6*(self.inspection_move_s+self.inspection_hold_s)+self.inspection_move_s if self.advanced_demo else 4.0

    def save(self, path):
        self.validate()
        Path(path).write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path):
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        allowed = {f.name for f in fields(cls)}
        return cls(**{k: v for k,v in data.items() if k in allowed}).validate()

    @property
    def cad_directory(self):
        return (ROOT / self.cad_path).resolve()
