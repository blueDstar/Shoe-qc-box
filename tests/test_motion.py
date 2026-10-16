import math
import numpy as np
import pytest
from motion.profile import Trapezoid, DoorMotion


@pytest.mark.parametrize("distance,speed,accel",[(350,180,600),(10,180,600),(350,50,100),(0,180,600)])
def test_analytical_profile_limits_and_endpoint(distance,speed,accel):
    p=Trapezoid(0,distance,speed,accel)
    samples=np.array([p.sample(t) for t in np.linspace(0,p.duration+0.2,1000)])
    assert samples[:,0].min()>=-1e-9
    assert samples[:,0].max()<=distance+1e-9
    assert np.max(np.abs(samples[:,1]))<=speed+1e-9
    assert np.max(np.abs(samples[:,2]))<=accel+1e-9
    assert p.sample(p.duration+1)==(distance,0,0)


def test_position_derivative_agrees_with_velocity():
    p=Trapezoid(350,0,180,600)
    for t in (0.12,0.7,p.duration-0.12):
        h=1e-5
        derivative=(p.sample(t+h)[0]-p.sample(t-h)[0])/(2*h)
        assert derivative==pytest.approx(p.sample(t)[1],abs=1e-6)


def test_stop_holds_without_homing():
    d=DoorMotion("L")
    d.go(350)
    d.advance(0.7)
    position=d.position
    d.stop()
    d.advance(100)
    assert d.position==position and 0<position<350
    assert d.velocity==0


def test_repeated_motion_has_no_position_drift():
    d=DoorMotion("L")
    for _ in range(1000):
        d.go(350)
        d.advance(10)
        assert d.position==350
        d.go(0)
        d.advance(10)
        assert d.position==0


@pytest.mark.parametrize("target",[-1,351,float('nan'),float('inf')])
def test_invalid_target_rejected(target):
    d=DoorMotion("L")
    with pytest.raises(ValueError):
        d.go(target)
