from pathlib import Path
import json
from dataclasses import replace
import pytest
import cv2
from config import ROOT, Settings
from simulation import Simulation


VIDEO=ROOT/"exports"/"Hilykan_QC_Alternating_1080p.mp4"


@pytest.mark.parametrize("filename,resolution",[("Hilykan_QC_Alternating_1080p.mp4",(1920,1080)),
                                               ("Hilykan_Multiface_QC_720p.mp4",(1280,720))])
def test_actual_encoded_video_matches_engine_frame_by_frame(manifest,filename,resolution):
    path=ROOT/"exports"/filename
    if not path.exists():
        pytest.skip("Generate actual video before artifact integration test")
    verification=json.loads(path.with_suffix(".verification.json").read_text(encoding="utf-8"))
    trace=[json.loads(line) for line in path.with_suffix(".frames.jsonl").read_text(encoding="utf-8").splitlines()]
    assert (verification["width"],verification["height"])==resolution and verification["fps"]==30
    assert verification["decoded_frame_count"]==len(trace)==verification["frames"]
    flags=verification.get("simulation_settings",{"advanced_demo":False,"qc_station_enabled":False})
    engine=Simulation(replace(Settings.load(ROOT/"config"/"default.json"),loop=False,**flags),manifest)
    assert engine.start("ALTERNATING",2)
    for i,frame in enumerate(trace):
        assert frame["frame"]==i
        assert frame["time_s"]==pytest.approx(engine.time,abs=1e-9)
        assert frame["state"]==engine.sequence.state
        assert frame["left_mm"]==pytest.approx(engine.doors["L"].position,abs=1e-9)
        assert frame["right_mm"]==pytest.approx(engine.doors["R"].position,abs=1e-9)
        assert frame["sensors"]=={key:engine.sensors.values[key] for key in frame["sensors"]}
        for side,pose in frame["robots"].items():
            for key,value in pose.items():
                current=engine.robots[side].snapshot()[key]
                assert current==pytest.approx(value,abs=1e-9) if isinstance(value,(float,int)) else current==value
        assert frame["owner"]==engine.owner
        if "qc_face" in frame:
            assert frame["qc_face"]==engine.qc.face
            assert frame["qc_captured"]==sorted(engine.qc.captured)
        assert not frame["fault"]
        assert not (frame["left_mm"]>0.02 and frame["right_mm"]>0.02)
        engine.advance(1/30)
    assert trace[-1]["completed"]==2
    assert trace[-1]["left_mm"]==trace[-1]["right_mm"]==0
    video=cv2.VideoCapture(str(path))
    for index in (0,120,len(trace)//3,2*len(trace)//3,len(trace)-1):
        video.set(cv2.CAP_PROP_POS_FRAMES,index)
        okay,frame=video.read()
        assert okay and frame.shape==(resolution[1],resolution[0],3)
        assert frame.std()>10
    video.release()
