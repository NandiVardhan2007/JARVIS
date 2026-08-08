import unittest
import time
from Tools.hand_gesture_control import (
    PrecisionAdaptiveFilter,
    set_gesture_sensitivity,
    get_gesture_control_status,
    _get_screen_dimensions
)

class TestHandGestureControl(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.filter = PrecisionAdaptiveFilter(min_alpha=0.12, max_alpha=0.88, soft_deadzone_px=1.5)

    def test_filter_initialization(self):
        x, y = self.filter.update(100.0, 200.0)
        self.assertEqual(x, 100.0)
        self.assertEqual(y, 200.0)

    def test_filter_soft_damping(self):
        # Initial position
        self.filter.update(100.0, 100.0)
        # Small micro movement < soft_deadzone_px (1.5px)
        x_micro, y_micro = self.filter.update(100.5, 100.5)
        # Micro movement should be softly damped, not jumping immediately or hard frozen
        self.assertGreater(x_micro, 100.0)
        self.assertLess(x_micro, 100.5)

    def test_filter_velocity_adaptation(self):
        # Initial position
        self.filter.update(0.0, 0.0)
        time.sleep(0.01)
        # Fast movement
        x_fast, y_fast = self.filter.update(500.0, 500.0)
        # Fast movement should have higher alpha (closer to target)
        self.assertGreater(x_fast, 300.0)

    def test_filter_reset(self):
        self.filter.update(100.0, 100.0)
        self.filter.reset()
        self.assertIsNone(self.filter.prev_x)
        self.assertIsNone(self.filter.prev_y)

    def test_screen_dimensions(self):
        w, h = _get_screen_dimensions()
        self.assertGreaterEqual(w, 800)
        self.assertGreaterEqual(h, 600)

    async def test_sensitivity_and_status(self):
        msg = await set_gesture_sensitivity(1.8)
        self.assertIn("1.8", msg)

        status = await get_gesture_control_status()
        self.assertIn("Virtual Air Mouse", status)
        self.assertIn("1.8", status)

if __name__ == "__main__":
    unittest.main()
