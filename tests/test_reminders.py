"""
Unit tests for Autonomous Spoken Reminders & Alarms in VISION AI OS.
"""

import pytest
import time
from vision.core.reminder_daemon import ReminderManager, reminder_manager
from vision.tools.reminder_tools import set_voice_reminder, set_timer, list_active_reminders, cancel_reminder


@pytest.fixture(autouse=True)
def clean_test_reminders(tmp_path, monkeypatch):
    """Isolate reminder DB for tests to prevent test timers from polluting live database."""
    test_db = tmp_path / "test_reminders.db"
    test_manager = ReminderManager(db_path=test_db)
    monkeypatch.setattr("vision.tools.reminder_tools.reminder_manager", test_manager)
    monkeypatch.setattr("vision.core.reminder_daemon.reminder_manager", test_manager)
    yield test_manager


def test_set_timer_and_list():
    """Verify timer scheduling and listing."""
    res = set_timer(duration_seconds=120, timer_label="Test Unit Timer")
    assert "Timer for 'Test Unit Timer' started!" in res
    assert ("2m 0s" in res or "1m 59s" in res)

    pending = list_active_reminders()
    assert "Test Unit Timer" in pending
    assert "TIMER" in pending


def test_set_voice_reminder_and_cancel():
    """Verify natural time reminder scheduling and cancellation."""
    res = set_voice_reminder(reminder_text="Submit college assignment", delay_minutes=30)
    assert "Reminder scheduled successfully!" in res
    assert "Submit college assignment" in res

    # Cancel by keyword
    cancel_res = cancel_reminder(keyword="assignment")
    assert "Cancelled reminder(s)" in cancel_res
    assert "Submit college assignment" in cancel_res


def test_daemon_check_and_trigger(clean_test_reminders):
    """Verify overdue reminders are automatically identified and marked completed."""
    # Add a reminder that triggers in 1 second
    clean_test_reminders.add_reminder(message="Quick Alert Test", delay_seconds=1, reminder_type="timer")
    
    time.sleep(1.2)
    due = clean_test_reminders.check_and_get_due_reminders()
    assert len(due) >= 1
    assert any(d["message"] == "Quick Alert Test" for d in due)
