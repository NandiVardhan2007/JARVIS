"""
Unit tests for College Outlook Email Intelligence & Review Workflow.
"""

import pytest
from vision.tools.outlook_tools import (
    check_college_outlook_emails,
    confirm_move_emails_to_bin,
    get_pending_email_review,
    _classify_email
)
from vision.tools.registry import tool_registry


def test_email_classification():
    useful_mail = _classify_email("exams@aec.edu.in", "Mid-1 Exam Schedule and Timetable")
    assert useful_mail["category"] == "useful"
    assert useful_mail["priority"] == "High"

    placement_mail = _classify_email("placements@technicalhub.io", "THUB Placement Drive Announcement")
    assert placement_mail["category"] == "useful"

    junk_mail = _classify_email("promotions@e.udemy.com", "Flash Sale 80% Off Coupon Code")
    assert junk_mail["category"] == "junk"


def test_outlook_workflow():
    # 1. Scan college emails
    res = check_college_outlook_emails(account_type="college")
    assert "Google Chrome" in res or "Outlook" in res
    assert "Important College" in res or "Promotional" in res

    # 2. Get pending review state
    review = get_pending_email_review()
    assert "Current Outlook Review State" in review

    # 3. Confirm move to bin
    bin_res = confirm_move_emails_to_bin(confirmed=True)
    assert "Recycle Bin" in bin_res or "Successfully moved" in bin_res


def test_tool_registry_registration():
    all_tools = list(tool_registry._tools.keys())
    assert "check_college_outlook_emails" in all_tools
    assert "confirm_move_emails_to_bin" in all_tools
    assert "get_pending_email_review" in all_tools
