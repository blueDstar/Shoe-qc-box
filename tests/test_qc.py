import json
import numpy as np
import pytest
from conftest import advance_until
from controllers.robot_demo import DemoRobot
from controllers.inspection import FACES,poses,interpolate
from qc.station import HARDWARE
from collision.checker import overlaps


def test_six_faces_both_robots_align_to_actual_camera_and_stay_clear(engine):
    e=engine
    e.start("ALTERNATING")
    advance_until(e,lambda:not e.sequence.running)
    assert len(e.qc.records)==12
    for side in ("L","R"):
        captures=[r for r in e.qc.records if r["side"]==side]
        assert [r["face"] for r in captures]==list(FACES)
        assert all(r["alignment_cos"]>0.9999 for r in captures)
        assert all(r["views"]["FRONT"]["shoe_in_frame"] for r in captures)
        assert all(r["doors"][side]==350 for r in captures)
    assert not e.fault and e.sequence.completed==2


@pytest.mark.parametrize("side",["L","R"])
def test_arm_links_are_rigid_through_translation_and_rotations(side):
    r=DemoRobot(side)
    for q in np.linspace(r.sign*900,0,50):
        r.x=float(q)
        a,b,c=r.joint_positions()
        assert np.linalg.norm(b-a)==pytest.approx(650,abs=1e-8)
        assert np.linalg.norm(c-b)==pytest.approx(650,abs=1e-8)
    for yaw,pitch,roll in poses(side):
        r.yaw,r.pitch,r.roll=yaw,pitch,roll
        a,b,c=r.joint_positions()
        assert np.linalg.norm(b-a)==pytest.approx(650,abs=1e-8)
        assert np.linalg.norm(c-b)==pytest.approx(650,abs=1e-8)
        assert c==pytest.approx((r.matrix()@r.wrist_anchor)[:3],abs=1e-9)


def test_toe_heel_transition_uses_reachable_half_turn():
    assert interpolate((-90,0,0),(90,0,0),0.5)[0]==pytest.approx(0)
    assert interpolate((90,0,0),(-90,0,0),0.5)[0]==pytest.approx(0)


def test_proximity_is_measured_from_geometry_not_phase(engine):
    r=engine.robots["L"]
    r.phase="APPROACH"
    engine.sensors.update(engine)
    assert not engine.sensors.values["LEFT_APPROACH_SENSOR"]
    r.x=-650
    r.phase="IDLE"
    engine.sensors.update(engine)
    assert engine.sensors.values["LEFT_APPROACH_SENSOR"]
    assert engine.sensors.measurements["L"]["nearest_x_mm"]==pytest.approx(515)


def test_measured_approach_can_start_cycle_without_auto_start(engine):
    e=engine
    assert e.begin_approach("L")
    advance_until(e,lambda:e.sequence.running)
    assert e.sensors.values["LEFT_APPROACH_SENSOR"]
    advance_until(e,lambda:e.sequence.completed==1 and not e.sequence.running)
    assert len(e.qc.records)==6 and not e.fault


def test_false_approach_input_prevents_automatic_open(engine):
    e=engine
    e.sensors.set("LEFT_APPROACH_SENSOR",False)
    e.begin_approach("L")
    e.advance(3)
    assert e.robots["L"].x==-650
    assert e.doors["L"].position==0 and not e.sequence.running and e.owner is None
    e.sensors.clear_overrides()
    advance_until(e,lambda:e.sequence.completed==1)


def test_simultaneous_physical_approaches_get_serialized(engine):
    e=engine
    e.begin_approach("L")
    e.begin_approach("R")
    advance_until(e,lambda:e.sequence.completed==2 and not e.sequence.running)
    results=[r["side"] for r in e.log.events if r["kind"]=="QC_RESULT"]
    assert results==["L","R"]
    assert not e.fault


def test_camera_hardware_is_inside_source_chamber_without_fixed_cad_collision(manifest):
    for name,box in HARDWARE:
        assert box[0]>=-397 and box[3]<=397 and box[1]>=-257 and box[4]<=257 and box[2]>=3 and box[5]<=557
        assert not any(overlaps(box,row["bbox_mm"]) for row in manifest["components"] if row["group"]=="STATIC_FRAME")


def test_shoe_gripper_arm_meshes_fit_their_collision_envelopes():
    from scene3d.demo_assets import robot_assets
    for side in ("L","R"):
        robot=DemoRobot(side)
        robot.x=0
        matrices=robot.matrices()
        parts={p["name"]:p["bbox"] for p in robot.parts()}
        tool=np.array([parts[n] for n in ("shoe","gripper","wrist")])
        tool_bounds=np.r_[tool[:,:3].min(axis=0),tool[:,3:].max(axis=0)]
        for role,mesh,_ in robot_assets(side):
            points=np.c_[mesh.points,np.ones(mesh.n_points)]@matrices[role].T
            bound=tool_bounds if role=="tool" else np.array(parts[role])
            assert np.all(points[:,:3]>=bound[:3]-1e-6),role
            assert np.all(points[:,:3]<=bound[3:]+1e-6),role


def test_camera_not_ready_fault_and_reinspection_recovery(engine):
    e=engine
    e.inject("CAMERA_NOT_READY")
    e.start("LEFT")
    for _ in range(1600):
        e.advance(1/30)
        if e.fault:
            break
    assert "SHOE_INSPECTION" in e.fault and not e.qc.records
    e.clear_fault_source()
    e.reset_fault()
    e.resume()
    advance_until(e,lambda:not e.sequence.running)
    assert len(e.qc.records)==6 and e.sequence.completed==1


def test_qc_capture_state_restores_without_duplicate_faces(engine,tmp_path):
    e=engine
    e.start("LEFT")
    advance_until(e,lambda:len(e.qc.records)==3)
    path=tmp_path/"qc.json"
    e.save_state(path)
    captured=e.qc.snapshot()
    e.advance(0.3)
    e.load_state(path)
    assert e.qc.snapshot()==captured
    e.resume()
    advance_until(e,lambda:not e.sequence.running)
    assert [r["face"] for r in e.qc.records]==list(FACES)


def test_unreachable_arm_request_restores_valid_geometry(engine):
    e=engine
    e.start("LEFT")
    advance_until(e,lambda:e.sequence.state=="LEFT_SHOE_INSPECTION")
    before=e.robots["L"].matrix().copy()
    assert not e.robot_pose("L",0,180,0)
    assert "reach" in e.fault
    assert np.array_equal(before,e.robots["L"].matrix())


def test_sensor_timeout_can_recover_without_teleport(engine):
    e=engine
    e.sensors.set("LEFT_APPROACH_SENSOR",False)
    e.begin_approach("L")
    e.advance(26)
    assert e.fault
    before=e.robots["L"].snapshot()
    e.clear_fault_source()
    assert e.reset_fault()
    e.resume()
    e.advance(1/120)
    assert abs(e.robots["L"].x-before["x"])<0.1
    advance_until(e,lambda:e.sequence.completed==1)


def test_early_withdrawal_reports_incomplete_qc(engine):
    e=engine
    e.start("LEFT")
    advance_until(e,lambda:len(e.qc.records)==1)
    e.sequence.transition(7)
    advance_until(e,lambda:not e.sequence.running)
    assert e.sequence.last_result=="INCOMPLETE" and not e.fault
