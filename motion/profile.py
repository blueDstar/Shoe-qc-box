from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class Trapezoid:
    start: float
    target: float
    speed: float
    acceleration: float

    def __post_init__(self):
        self.distance = abs(self.target - self.start)
        self.sign = 1 if self.target >= self.start else -1
        self.peak = min(self.speed, math.sqrt(self.distance * self.acceleration))
        self.ta = self.peak / self.acceleration
        self.tc = max(0.0, (self.distance - self.peak**2 / self.acceleration) / self.peak) if self.peak else 0
        self.duration = 2 * self.ta + self.tc

    def sample(self, t):
        t = max(0.0, t)
        if t >= self.duration:
            return self.target, 0.0, 0.0
        if t < self.ta:
            d, v, a = 0.5*self.acceleration*t*t, self.acceleration*t, self.acceleration
        elif t < self.ta + self.tc:
            d = 0.5*self.acceleration*self.ta**2 + self.peak*(t-self.ta)
            v, a = self.peak, 0.0
        else:
            remain = self.duration - t
            d = self.distance - 0.5*self.acceleration*remain*remain
            v, a = self.acceleration*remain, -self.acceleration
        return self.start + self.sign*d, self.sign*v, self.sign*a


class DoorMotion:
    def __init__(self, side, limit=350, speed=180, acceleration=600, tolerance=0.02):
        self.side, self.limit, self.speed, self.acceleration = side, limit, speed, acceleration
        self.tolerance = tolerance
        self.position = self.target = self.velocity = self.accel = self.elapsed = 0.0
        self.profile = None
        self.status = "CLOSED"

    @property
    def fully_open(self):
        return abs(self.position-self.limit) <= self.tolerance and self.profile is None

    @property
    def fully_closed(self):
        return self.position <= self.tolerance and self.profile is None

    @property
    def direction(self):
        return "UP" if self.velocity > 0 else "DOWN" if self.velocity < 0 else "HOLD"

    def go(self, target):
        if not math.isfinite(target) or not 0 <= target <= self.limit:
            raise ValueError("Target outside travel limit")
        self.target = float(target)
        if abs(self.target - self.position) <= 1e-9:
            self.stop()
            return
        # A newly requested move starts from a held pose. Reversals never integrate old transforms.
        self.profile = Trapezoid(self.position, self.target, self.speed, self.acceleration)
        self.elapsed = self.velocity = self.accel = 0.0
        self.status = "OPENING" if target > self.position else "CLOSING"

    def proposal(self, dt):
        return self.profile.sample(self.elapsed + dt) if self.profile else (self.position, 0.0, 0.0)

    def advance(self, dt):
        if self.profile is None:
            return
        self.elapsed += dt
        self.position, self.velocity, self.accel = self.profile.sample(self.elapsed)
        if self.elapsed >= self.profile.duration:
            self.profile = None
            self.status = "OPEN" if self.fully_open else "CLOSED" if self.fully_closed else "HOLD"

    def stop(self):
        self.profile = None
        self.target = self.position
        self.velocity = self.accel = 0.0
        self.status = "OPEN" if self.fully_open else "CLOSED" if self.fully_closed else "STOPPED"
