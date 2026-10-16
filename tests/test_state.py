import json
import pytest
from conftest import advance_until


def test_state_roundtrip_loads_paused_and_recovers(engine,tmp_path):
    e=engine
    e.start("LEFT")
    advance_until(e,lambda:e.sequence.state=="LEFT_SHOE_INSPECTION" and e.sequence.elapsed>1)
    saved=e.snapshot()
    path=tmp_path/"state.json"
    e.save_state(path)
    e.advance(1)
    e.load_state(path)
    assert e.time==saved["time_s"]
    assert e.sequence.paused
    assert e.robots["L"].snapshot()==saved["robots"]["L"]
    e.resume()
    advance_until(e,lambda:not e.sequence.running)
    assert e.sequence.completed==1


def test_saved_both_open_rejected_atomically(engine,tmp_path):
    data=engine.snapshot()
    data["doors"]["L"]["position"]=100
    data["doors"]["R"]["position"]=100
    path=tmp_path/"unsafe.json"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError,match="both doors"):
        engine.load_state(path)
    assert engine.doors["L"].position==engine.doors["R"].position==0


def test_saved_source_mismatch_rejected(engine,tmp_path):
    data=engine.snapshot()
    data["source_sha256"]="other"
    path=tmp_path/"other.json"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError,match="different CAD"):
        engine.load_state(path)


def test_insert_state_restore_has_no_trajectory_jump(engine,tmp_path):
    e=engine
    e.start("LEFT")
    advance_until(e,lambda:e.sequence.state=="LEFT_ROBOT_INSERT" and e.sequence.elapsed>1)
    path=tmp_path/"insert.json"
    e.save_state(path)
    e.advance(1)
    e.load_state(path)
    old=e.robots["L"].x
    e.resume()
    e.advance(1/120)
    assert abs(e.robots["L"].x-old)<4
    advance_until(e,lambda:not e.sequence.running)
    assert e.sequence.completed==1
