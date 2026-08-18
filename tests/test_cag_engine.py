"""
Test suite for Cache-Augmented Generation (CAG) Engine and Tools.
"""

import os
import tempfile
import time
from pathlib import Path
from vision.memory.cag_engine import CAGEngine
from vision.tools.cache_tools import get_cache_stats, clear_system_cache


def test_cag_engine_lifecycle():
    with tempfile.TemporaryDirectory() as tmpdir:
        engine = CAGEngine(cache_dir=tmpdir, max_entries=5)

        # 1. Test miss on new query
        q = "What is the capital of France?"
        assert engine.lookup(q) is None
        assert engine.misses == 1

        # 2. Test put and exact hit
        engine.put(q, "The capital of France is Paris.", category="qa_general", ttl_seconds=10)
        hit = engine.lookup(q)
        assert hit is not None
        assert hit["response"] == "The capital of France is Paris."
        assert hit["match_type"] == "exact"
        assert engine.exact_hits == 1

        # 3. Test fuzzy semantic match (slight variation)
        fuzzy_q = "What is capital of France country?"
        fuzzy_hit = engine.lookup(fuzzy_q)
        assert fuzzy_hit is not None
        assert fuzzy_hit["response"] == "The capital of France is Paris."
        assert engine.fuzzy_hits == 1

        # 4. Test bypass for dynamic queries (time, screen, file actions)
        assert engine.should_bypass("What is the time right now?") is True
        assert engine.lookup("What is the time right now?") is None

        # 5. Test LRU capacity eviction
        for i in range(10):
            engine.put(f"query test item {i}", f"response test item {i}")
        assert len(engine._l1_cache) <= 5

        # 6. Test invalidation
        cleared = engine.invalidate("all")
        assert cleared >= 1
        assert engine.lookup(q) is None


def test_cache_tools():
    # Test get_cache_stats
    stats_res = get_cache_stats()
    assert "CAG Cache Telemetry" in stats_res

    # Test clear_system_cache
    clear_res = clear_system_cache("all")
    assert "Successfully cleared" in clear_res
