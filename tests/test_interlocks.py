import pytest
from conftest import advance_until


def open_left(e):
    assert e.command("L","OPEN")
    e.advance(4)
    assert e.doors["L"].fully_open


def test_one_door_only_and_independent_manual(engine):
    e=engine
    assert e.command("L","OPEN")
    assert not e.command("R","OPEN")
    e.advance(4)
    assert e.doors["L"].position==350 and e.doors["R"].position==0
    assert e.command("L","CLOSE")
    e.advance(4)
    assert e.command("R","OPEN")
    e.advance(4)
    assert e.doors["R"].position==350 and e.doors["L"].position==0


def test_blocked_sensor_rejects_close(engine):
    open_left(engine)
    engine.sensors.set("LEFT_CLEAR_SENSOR",False)
    assert not engine.command("L","CLOSE")
    assert engine.doors["L"].position==350


def test_clear_sensor_cannot_override_actual_body_occupancy(engine):
    e=engine
    open_left(e)
    assert e.robot_pose("L",-410,0,0)
    e.sensors.set("LEFT_CLEAR_SENSOR",True)
    e.sensors.set("CHAMBER_OCCUPIED",False)
    assert not e.command("L","CLOSE")
    assert e.doors["L"].position==350


def test_approach_is_not_close_clearance(engine):
    open_left(engine)
    engine.sensors.set("LEFT_APPROACH_SENSOR",False)
    engine.sensors.set("LEFT_CLEAR_SENSOR",False)
    assert not engine.command("L","CLOSE")


def test_obstacle_during_closing_faults_and_holds(engine):
    open_left(engine)
    assert engine.command("L","CLOSE")
    engine.advance(0.3)
    pos=engine.doors["L"].position
    engine.sensors.set("LEFT_CLEAR_SENSOR",False)
    engine.advance(0.01)
    assert engine.fault and engine.doors["L"].position==pos
    engine.advance(2)
    assert engine.doors["L"].position==pos


@pytest.mark.parametrize("sensor",["LEFT_CLEAR_SENSOR","RIGHT_CLEAR_SENSOR","CHAMBER_OCCUPIED"])
def test_unknown_sensor_faults(engine,sensor):
    engine.sensors.set(sensor,None)
    engine.advance(0.01)
    assert "Unknown" in engine.fault
    assert not engine.reset_fault()


def test_false_open_sensor_cannot_admit_robot(engine):
    open_left(engine)
    engine.sensors.set("LEFT_DOOR_OPEN_SENSOR",False)
    assert not engine.robot_pose("L",-410,0,0)
    assert engine.robots["L"].x==-900


def test_closed_door_blocks_robot_swept_jump(engine):
    engine.owner="L"
    assert not engine.robot_pose("L",0,0,0)
    assert engine.robots["L"].x==-900


def test_contradictory_endpoint_sensor_fault(engine):
    engine.sensors.set("LEFT_DOOR_OPEN_SENSOR",True)
    engine.advance(0.01)
    assert engine.fault


def test_full_mechanism_blocked_by_actual_source_clashes(engine):
    engine.settings.mechanism_scope="FULL_ASSEMBLY"
    assert not engine.command("L","OPEN")
    assert "source bracket" in engine.fault
    assert engine.doors["L"].position==0


def test_cad_confirmation_required(engine):
    engine.settings.kinematics_confirmed=False
    assert not engine.command("L","OPEN")
    assert not engine.start()
