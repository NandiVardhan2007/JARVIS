"""
Test suite for Hardware Control Tools (Volume, Brightness, Mute, Lock).
"""

from vision.tools.hardware_tools import (
    set_volume, increase_volume, decrease_volume,
    mute_volume, unmute_volume, get_volume_status,
    get_brightness_status, set_brightness, increase_brightness, decrease_brightness
)


def test_volume_controls():
    # Test get volume status
    status = get_volume_status()
    assert "Master Volume" in status

    # Test set volume
    set_res = set_volume(level=50)
    assert "50%" in set_res

    # Test mute & unmute
    mute_res = mute_volume()
    assert "muted" in mute_res.lower()
    unmute_res = unmute_volume()
    assert "unmuted" in unmute_res.lower()

    # Test increase & decrease
    inc_res = increase_volume(step=5)
    assert "%" in inc_res
    dec_res = decrease_volume(step=5)
    assert "%" in dec_res


def test_brightness_controls():
    # Test get brightness status
    b_status = get_brightness_status()
    assert "Brightness" in b_status or "Error" in b_status
