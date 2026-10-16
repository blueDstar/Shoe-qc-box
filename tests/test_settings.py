import pytest
from config import Settings


@pytest.mark.parametrize("values",[{"unit":"inch"},{"travel_mm":351},{"velocity_mm_s":0},{"acceleration_mm_s2":float('nan')},
                                    {"mechanism_scope":"UNKNOWN"},{"qc_result":"FAULT"}])
def test_invalid_settings_rejected(values):
    with pytest.raises(ValueError):
        Settings(**values).validate()
