import json
import pytest
from config import ROOT, Settings
from simulation import Simulation


@pytest.fixture(scope="session")
def manifest():
    return json.loads((ROOT/"config"/"cad_manifest.json").read_text(encoding="utf-8"))


@pytest.fixture
def engine(manifest):
    settings=Settings.load(ROOT/"config"/"default.json")
    return Simulation(settings,manifest)


def advance_until(engine,condition,timeout=120):
    for _ in range(int(timeout*30)):
        engine.advance(1/30)
        if condition():
            return
        if engine.fault:
            raise AssertionError(engine.fault)
    raise AssertionError("Condition timeout at "+engine.sequence.state)
