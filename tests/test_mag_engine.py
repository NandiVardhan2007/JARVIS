"""
Test suite for Memory-Augmented Generation (MAG) Engine and Tools.
"""

import os
import tempfile
from pathlib import Path
from vision.memory.mag_engine import MAGEngine
from vision.tools.memory_tools import remember_fact, recall_memory, forget_memory, list_all_memories


def test_mag_engine_crud():
    with tempfile.TemporaryDirectory() as tmpdir:
        test_db = str(Path(tmpdir) / "test_memory.db")
        engine = MAGEngine(db_path=test_db)

        # 1. Test remember
        mem_id = engine.remember("User prefers Python over JavaScript", category="preference", tags="coding,python")
        assert mem_id > 0

        # 2. Test search
        results = engine.search_memories("What programming language do I prefer?")
        assert len(results) >= 1
        assert "Python" in results[0]["content"]

        # 3. Test prompt injection
        injection = engine.get_mag_prompt_injection("Python code helper")
        assert "[LONG-TERM USER MEMORY & PREFERENCES (MAG)]" in injection
        assert "Python" in injection

        # 4. Test episodic event logging
        engine.record_event("app_opened", "Opened VS Code", metadata="{}")
        events = engine.get_recent_events(limit=5)
        assert len(events) >= 1
        assert "VS Code" in events[0]["description"]

        # 5. Test forget
        deleted = engine.forget("Python")
        assert deleted >= 1
        assert len(engine.search_memories("Python")) == 0


def test_memory_tools():
    # Test remember_fact tool
    res_rem = remember_fact("My favorite testing framework is pytest", category="testing")
    assert "saved this to my long-term memory" in res_rem

    # Test recall_memory tool
    res_rec = recall_memory("pytest")
    assert "pytest" in res_rec

    # Test list_all_memories tool
    res_list = list_all_memories()
    assert "pytest" in res_list

    # Test forget_memory tool
    res_del = forget_memory("pytest")
    assert "Successfully deleted" in res_del
