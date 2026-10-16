from __future__ import annotations

import json
from pathlib import Path
import cv2
import numpy as np
import pyvista as pv
import imageio_ffmpeg

from config import ROOT
from simulation import Simulation
from scene3d import Scene


def status_panel(frame,engine):
    """Optional rendered state sidebar; data is sampled from this same video frame."""
    out=frame.copy()
    width=out.shape[1]
    x=max(0,width-410)
    out[:,x:]=np.array([17,24,39],dtype=np.uint8)
    lines=["HILYKAN / QC CONTROL","FIXED TIME SIMULATION",f"TIME {engine.time:.2f} s",engine.sequence.state,
           f"LEFT {engine.doors['L'].position:.1f} mm / {engine.doors['L'].status}",
           f"RIGHT {engine.doors['R'].position:.1f} mm / {engine.doors['R'].status}",
           f"ACTIVE {engine.owner or 'NONE'}",f"CYCLES {engine.sequence.completed}",
           f"QC {engine.sequence.last_result}","SCOPE: PLATE / BLOCK / ROD","P09 / P11 EXCLUDED","DEMO: GRIPPER + SHOE PROXY"]
    for name,value in engine.sensors.values.items():
        lines.append(f"{name}: {int(value) if value is not None else '?'}")
    for i,text in enumerate(lines):
        cv2.putText(out,text,(x+14,32+i*29),cv2.FONT_HERSHEY_SIMPLEX,0.47,
                    (0,217,255) if i<2 else (203,213,225),1,cv2.LINE_AA)
    return out


def export_video(settings,manifest,path,progress=None):
    if not settings.kinematics_confirmed:
        raise ValueError("CAD kinematics must be confirmed before export")
    if settings.mechanism_scope=="FULL_ASSEMBLY" and manifest["preflight"]["source_envelope_overlaps"]:
        raise ValueError("Full mechanism video blocked by source CAD interference")
    if not settings.auto_sensors:
        raise ValueError("Deterministic auto export requires Auto Sensor Mode")
    notify=progress or (lambda data:None)
    path=Path(path).resolve()
    path.parent.mkdir(parents=True,exist_ok=True)
    partial=path.with_name(path.stem+".partial.mp4")
    trace_path=path.with_suffix(".frames.jsonl")
    engine=Simulation(settings,manifest)
    # Keep loop and wall-clock speed out of fixed-step export.
    from dataclasses import replace
    engine.settings=replace(settings,loop=False,simulation_speed=1.0)
    p=pv.Plotter(off_screen=True,window_size=[settings.video_width,settings.video_height])
    p.ren_win.SetMultiSamples(4)
    scene=Scene(p,manifest)
    scene.demo_enabled=settings.demo_enabled
    scene.overlay=settings.video_overlay
    # A modest transparent shell exposes the same real CAD during inspection.
    scene.opacity=0.35
    writer=None
    frames=0
    success=False
    try:
        scene.update(engine)
        p.show(auto_close=False,interactive=False)
        writer=imageio_ffmpeg.write_frames(str(partial),(settings.video_width,settings.video_height),
                                          fps=settings.video_fps,codec="libx264",pix_fmt_in="rgb24",pix_fmt_out="yuv420p",
                                          quality=None,macro_block_size=1,output_params=["-preset","fast","-crf","20"],
                                          ffmpeg_log_level="error")
        writer.send(None)
        if not engine.start(settings.cycle_mode,settings.video_cycles):
            raise ValueError(engine.last_rejection)
        with trace_path.open("w",encoding="utf-8") as trace:
            while frames < settings.video_fps*max(60,settings.video_cycles*60):
                if settings.video_orbit:
                    scene.orbit(45+frames/settings.video_fps*3)
                scene.update(engine)
                frame=p.screenshot(return_img=True)
                if not settings.video_hide_ui:
                    frame=status_panel(frame,engine)
                writer.send(np.ascontiguousarray(frame[:,:,:3]))
                trace.write(json.dumps({"frame":frames,"time_s":engine.time,"state":engine.sequence.state,
                                        "left_mm":engine.doors["L"].position,"right_mm":engine.doors["R"].position,
                                        "left_v":engine.doors["L"].velocity,"right_v":engine.doors["R"].velocity,
                                        "robots":{s:r.snapshot() for s,r in engine.robots.items()},"sensors":engine.sensors.values,
                                        "qc_face":engine.qc.face,"qc_captured":sorted(engine.qc.captured),
                                        "owner":engine.owner,"completed":engine.sequence.completed,"fault":engine.fault})+"\n")
                frames+=1
                if frames%30==0:
                    notify({"frames":frames,"simulation_s":round(engine.time,3),"state":engine.sequence.state,"cycles":engine.sequence.completed})
                if engine.sequence.completed>=settings.video_cycles and not engine.queue:
                    success=True
                    break
                engine.advance(1/settings.video_fps)
                if engine.fault:
                    raise RuntimeError("Export stopped at FAULT: "+engine.fault)
            if not success:
                raise RuntimeError("Video export timed out; partial video kept")
        writer.close()
        writer=None
        partial.replace(path)
        capture=cv2.VideoCapture(str(path))
        info={"path":str(path),"frames":frames,"simulation_s":engine.time,"cycles":engine.sequence.completed,
              "codec":"H.264 / libx264","fps":capture.get(cv2.CAP_PROP_FPS),
              "width":capture.get(cv2.CAP_PROP_FRAME_WIDTH),"height":capture.get(cv2.CAP_PROP_FRAME_HEIGHT),
              "decoded_frame_count":capture.get(cv2.CAP_PROP_FRAME_COUNT),
              "first_frame_readable":bool(capture.read()[0]),"scope":settings.mechanism_scope,
              "collision_scope":"shutter swept AABB; DEMO conservative swept AABB/aperture; full joints blocked by CAD preflight",
              "trace":str(trace_path),"final_left_mm":engine.doors["L"].position,"final_right_mm":engine.doors["R"].position}
        info["engine_schema"]=2
        info["simulation_settings"]={"advanced_demo":settings.advanced_demo,"qc_station_enabled":settings.qc_station_enabled,
                                     "inspection_move_s":settings.inspection_move_s,"inspection_hold_s":settings.inspection_hold_s,
                                     "qc_camera_fov_deg":settings.qc_camera_fov_deg}
        info["qc_captures"]=len(engine.qc.records)
        path.with_suffix(".qc.json").write_text(json.dumps(list(engine.qc.records),indent=2),encoding="utf-8")
        capture.release()
        if not info["first_frame_readable"] or info["decoded_frame_count"]!=frames:
            raise RuntimeError("Encoded video verification failed")
        path.with_suffix(".verification.json").write_text(json.dumps(info,indent=2),encoding="utf-8")
        engine.log.export_json(path.with_suffix(".events.json"))
        notify(info)
        return info
    finally:
        if writer:
            writer.close()
        p.close()
