"""
Unit tests for VISION Task Tracker database, Excel engine, and tool registry execution.
"""

import os
import pytest
from vision.memory.task_tracker_db import TaskTrackerDB
from vision.tools.excel_tracker_engine import ExcelTrackerEngine
from vision.tools.registry import tool_registry
import vision.tools.task_tracker_tools  # Ensure registered


@pytest.fixture
def temp_db(tmp_path):
    db_file = str(tmp_path / "test_tasks.sqlite")
    return TaskTrackerDB(db_path=db_file)


@pytest.fixture
def temp_excel(tmp_path):
    excel_file = str(tmp_path / "test_tracker.xlsx")
    return ExcelTrackerEngine(filepath=excel_file)


def test_task_crud(temp_db):
    # 1. Add Task
    task = temp_db.add_task(
        title="Complete Neural Vision HUD",
        day=20,
        month="August",
        year=2026,
        category="Coding",
        priority="High"
    )
    assert task is not None
    assert task["id"] == 1
    assert task["title"] == "Complete Neural Vision HUD"
    assert task["is_completed"] == 0

    # 2. Toggle Task
    updated = temp_db.toggle_task(1, completed=True)
    assert updated["is_completed"] == 1
    assert updated["completed_at"] is not None

    # 3. Query Day & Month
    day_tasks = temp_db.get_tasks_for_day(day=20, month="August", year=2026)
    assert len(day_tasks) >= 1

    month_tasks = temp_db.get_tasks_for_month(month="August", year=2026)
    assert len(month_tasks) >= 31  # 31 Daily LeetCode tasks + user tasks

    # 4. Summary metrics
    summary = temp_db.get_dashboard_summary(day=20, month="August", year=2026)
    assert summary["day_metrics"]["completed"] >= 1
    assert "Coding" in summary["month_metrics"]["category_breakdown"]
    assert "leetcode_metrics" in summary

    # 5. Delete Task
    deleted = temp_db.delete_task(1)
    assert deleted is True
    assert temp_db.get_task_by_id(1) is None


def test_excel_generation(temp_excel):
    path = temp_excel.generate_workbook(year=2026)
    assert os.path.exists(path)
    assert os.path.getsize(path) > 1000  # Non-empty rich Excel workbook


@pytest.mark.asyncio
async def test_tool_registry_execution():
    from vision.memory.task_tracker_db import task_db

    # Test add_task tool
    res_add = await tool_registry.execute("add_task", {
        "title": "Temporary Test Task Verification",
        "category": "Testing",
        "priority": "High"
    })
    assert "Successfully added task" in res_add

    # Test get_daily_tasks tool
    res_list = await tool_registry.execute("get_daily_tasks", {})
    assert "Temporary Test Task Verification" in res_list

    # Test complete_task tool
    res_complete = await tool_registry.execute("complete_task", {
        "task_name_or_id": "Temporary Test Task Verification",
        "completed": True
    })
    assert "COMPLETED" in res_complete

    # Test get_productivity_summary tool
    res_summary = await tool_registry.execute("get_productivity_summary", {})
    assert "Productivity Summary" in res_summary

    # Clean up test task immediately from database
    with task_db._get_conn() as conn:
        conn.execute("DELETE FROM tasks WHERE title = 'Temporary Test Task Verification'")
        conn.commit()
