"""
Test suite for KeyStateManager (persistent rate limit tracking).
"""

import tempfile
import time
from pathlib import Path
from vision.cognitive.key_manager import KeyStateManager


def test_key_manager_lifecycle():
    with tempfile.TemporaryDirectory() as tmpdir:
        state_file = str(Path(tmpdir) / "test_key_state.json")
        km = KeyStateManager(state_file=state_file)

        test_key = "gsk_test1234567890abcdef"
        assert km.is_available(test_key) is True

        # Mark rate limited with retry string
        err = "Rate limit reached. Please try again in 1h15m."
        km.mark_rate_limited(test_key, err)

        assert km.is_available(test_key) is False
        assert km.get_remaining_cooldown(test_key) > 3600

        # Create new instance from disk to verify persistence across restarts
        km2 = KeyStateManager(state_file=state_file)
        assert km2.is_available(test_key) is False
