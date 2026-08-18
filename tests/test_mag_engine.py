"""
Test suite for Memory-Augmented Generation (MAG) Engine and Tools.
"""

import os
import tempfile
from pathlib import Path
from vision.memory.mag_engine import MAGEngine
from vision.tools.memory_tools import (
    remember_fact,
    recall_memory,
    forget_memory,
    list_all_memories,
    learn_user_rule,
    list_procedural_rules,
    search_past_events,
    sync_memories_file,
    export_memories_file
)


def test_mag_engine_crud_and_sync():
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

        # 3. Test prompt injection with procedural rules
        engine.record_procedural_rule("python,coding", "Always write clean unit tests.")
        injection = engine.get_mag_prompt_injection("Python code helper")
        assert "[LONG-TERM USER MEMORY & PREFERENCES (MAG)]" in injection
        assert "Python" in injection
        assert "[PROCEDURAL HABITS & RULES]" in injection
        assert "Always write clean unit tests" in injection

        # 4. Test episodic event logging & search
        engine.record_event("app_opened", "Opened VS Code", metadata="{}")
        events = engine.get_recent_events(limit=5)
        assert len(events) >= 1
        assert "VS Code" in events[0]["description"]

        search_ev = engine.search_episodic_events("VS Code")
        assert len(search_ev) >= 1
        assert "VS Code" in search_ev[0]["description"]

        # 5. Test markdown export and import sync
        md_path = Path(tmpdir) / "TEST_MEMORIES.md"
        export_msg = engine.export_to_markdown(md_path)
        assert "Successfully exported" in export_msg
        assert md_path.exists()

        # Modify md file and sync back
        content = md_path.read_text(encoding="utf-8")
        content += f"\n| **#999** | `custom_category` | Testing Markdown Sync Fact | `sync,test` | 1.0 |"
        md_path.write_text(content, encoding="utf-8")

        sync_res = engine.import_from_markdown(md_path)
        assert sync_res["added"] >= 1

        recalled = engine.search_memories("Testing Markdown Sync Fact")
        assert len(recalled) >= 1
        assert "Testing Markdown Sync Fact" in recalled[0]["content"]

        # 6. Test forget
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

    # Test procedural rule tools
    res_rule = learn_user_rule("youtube,video", "Use Comet browser")
    assert "Recorded procedural habit" in res_rule
    res_rules = list_procedural_rules()
    assert "Use Comet browser" in res_rules

    # Test forget_memory tool
    res_del = forget_memory("pytest")
    assert "Successfully deleted" in res_del
