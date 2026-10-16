import numpy as np
import pytest
from collision.checker import overlaps
from sensors.geometry import hardware,lens
from conftest import advance_until


@pytest.mark.parametrize("side",["L","R"])
def test_fixed_trigger_distance_is_measured_from_door_plane(engine,side):
    r=engine.robots[side]
    trigger=engine.settings.approach_trigger_mm
    r.x=r.sign*(trigger+135+0.5)
    engine.sensors.update(engine)
    values=engine.sensors.measurements[side]
    assert not values["detected"]
    assert values["door_gap_mm"]==pytest.approx(values["trigger_gap_mm"]+0.5)
    r.x=r.sign*(trigger+135-0.5)
    engine.sensors.update(engine)
    values=engine.sensors.measurements[side]
    assert values["detected"]
    assert values["door_gap_mm"]==pytest.approx(values["trigger_gap_mm"]-0.5)


def test_external_red_sensor_mounts_do_not_overlap_source_cad(manifest):
    for name,box in hardware():
        assert not any(overlaps(box,row["bbox_mm"]) for row in manifest["components"]),name
    assert abs(lens("L")[0])>409 and abs(lens("R")[0])>409


def test_detection_notice_precedes_automatic_open(engine):
    e=engine
    e.begin_approach("L")
    advance_until(e,lambda:e.doors["L"].position>0)
    notice=e.proximity_notices["L"]
    assert notice["door_gap_mm"]<notice["trigger_gap_mm"]
    assert notice["time_s"]<e.time
    events=list(e.log.events)
    seen=next(i for i,event in enumerate(events) if event["kind"]=="PROXIMITY_DETECTED")
    opened=next(i for i,event in enumerate(events) if event["kind"]=="MOTION" and event["message"]=="L OPEN")
    assert seen<opened and not e.fault


def test_proximity_notice_survives_pause_state_restore(engine,tmp_path):
    engine.begin_approach("L")
    advance_until(engine,lambda:bool(engine.proximity_notices))
    state=engine.proximity_notices.copy()
    path=tmp_path/"sensor_notice.json"
    engine.save_state(path)
    engine.load_state(path)
    assert engine.proximity_notices==state
