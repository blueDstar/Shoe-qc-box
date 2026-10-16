from conftest import advance_until
import pytest


def test_alternating_cycle_has_no_dual_open_and_safe_withdrawal(engine):
    e=engine
    assert e.start("ALTERNATING")
    states=[]
    for _ in range(4000):
        e.advance(1/60)
        states.append(e.sequence.state)
        assert not e.fault
        assert not (e.doors["L"].position>0.02 and e.doors["R"].position>0.02)
        for side,d in e.doors.items():
            if d.status=="CLOSING":
                assert all(r.withdrawn for r in e.robots.values())
                assert e.collision.doorway_clear(side,e.robots)
        if not e.sequence.running:
            break
    assert e.sequence.completed==2
    assert e.sequence.state=="IDLE"
    assert e.doors["L"].position==e.doors["R"].position==0
    assert "LEFT_SHOE_INSPECTION" in states and "RIGHT_SHOE_INSPECTION" in states
    assert len([x for x in e.log.events if x["kind"]=="QC_RESULT"])==2


def test_concurrent_requests_serialized(engine):
    engine.inject("SIMULTANEOUS_REQUESTS")
    assert list(engine.queue)==["L","R"]
    engine.start()
    advance_until(engine,lambda:not engine.sequence.running)
    results=[row["side"] for row in engine.log.events if row["kind"]=="QC_RESULT"]
    assert results==["L","R"]


def test_pause_and_stop_hold_all_poses_and_resume(engine):
    e=engine
    e.start("LEFT")
    advance_until(e,lambda:e.sequence.state=="LEFT_ROBOT_INSERT" and e.sequence.elapsed>1)
    e.pause()
    t=e.time
    robot=e.robots["L"].snapshot()
    door=e.doors["L"].position
    e.advance(5)
    assert e.time==t and e.robots["L"].snapshot()==robot and e.doors["L"].position==door
    e.resume()
    e.advance(0.5)
    assert e.robots["L"].x!=robot["x"]
    e.stop()
    robot=e.robots["L"].snapshot()
    e.advance(5)
    assert e.robots["L"].snapshot()==robot
    e.resume()
    advance_until(e,lambda:not e.sequence.running)
    assert e.sequence.completed==1


def test_step_runs_one_real_state(engine):
    e=engine
    assert e.step()
    e.advance(0.1)
    assert e.sequence.paused and e.sequence.index==0
    e.step()
    advance_until(e,lambda:e.sequence.paused)
    assert e.sequence.index==1
    assert e.robots["L"].x==-650


@pytest.mark.parametrize("fault,expected",[("DOOR_STALL","WAIT_DOOR_FULLY_OPEN"),("SENSOR_NO_OPEN","WAIT_DOOR_FULLY_OPEN"),
                                         ("DOORWAY_BLOCKED","WAIT_DOORWAY_CLEAR"),("ROBOT_NOT_WITHDRAWN","WAIT_DOORWAY_CLEAR")])
def test_fault_injections_timeout_without_skipping_interlocks(engine,fault,expected):
    e=engine
    e.settings.timeout_s=20
    e.inject(fault)
    e.start("LEFT")
    for _ in range(1200):
        e.advance(1/30)
        if e.fault:
            break
    assert expected in e.fault
    assert e.sequence.completed==0


def test_fault_recovery_extracts_from_actual_held_pose(engine):
    e=engine
    e.settings.timeout_s=20
    e.inject("ROBOT_NOT_WITHDRAWN")
    e.start("LEFT")
    for _ in range(1500):
        e.advance(1/30)
        if e.fault:
            break
    old=e.robots["L"].x
    e.clear_fault_source()
    assert e.reset_fault()
    e.resume()
    e.advance(1/120)
    assert abs(e.robots["L"].x-old)<0.1
    advance_until(e,lambda:not e.sequence.running)
    assert e.sequence.completed==1


def test_qc_fail_is_not_operating_fault(engine):
    engine.settings.qc_result="FAIL"
    engine.start("LEFT")
    advance_until(engine,lambda:not engine.sequence.running)
    assert engine.sequence.last_result=="FAIL" and not engine.fault


def test_manual_and_auto_have_same_motion_profile(engine):
    manual=engine
    assert manual.command("L","OPEN")
    manual.advance(0.9)
    expected=manual.doors["L"].position
    from config import Settings, ROOT
    from simulation import Simulation
    auto=Simulation(Settings.load(ROOT/"config"/"default.json"),manual.manifest)
    auto.start("LEFT")
    advance_until(auto,lambda:auto.sequence.index==4)
    # The polling helper can include up to a frame of motion after OPEN_DOOR.
    # Compare at equal profile time, rather than unequal wall/state polling times.
    auto.advance(0.9-auto.doors["L"].elapsed)
    assert auto.doors["L"].position==pytest.approx(expected,abs=1e-7)
