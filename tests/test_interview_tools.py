"""
Unit tests for AI Mock Interview Coach in VISION AI OS.
"""

import pytest
from vision.tools.interview_tools import (
    start_mock_interview,
    evaluate_interview_answer,
    end_mock_interview,
    interview_manager
)


def test_mock_interview_flow():
    # 1. Start Python interview
    start_res = start_mock_interview(role_or_topic="Python", interview_type="Technical", difficulty="Medium")
    assert "Mock Interview Session Started" in start_res
    assert "Python" in start_res
    assert interview_manager.is_active is True
    assert len(interview_manager.questions) == 5

    # 2. Evaluate Question 1
    eval1 = evaluate_interview_answer(
        answer_summary="Mutable types like lists can be modified in place, while immutable types like tuples cannot.",
        constructive_feedback="Great clarity on mutability and memory referencing.",
        score_out_of_10=9
    )
    assert "Answer Evaluated" in eval1
    assert "Question 2" in eval1
    assert len(interview_manager.history) == 1

    # 3. End interview and verify report generation
    end_res = end_mock_interview(write_to_notepad=False)
    assert "Mock Interview concluded" in end_res
    assert interview_manager.is_active is False

    report = interview_manager.generate_report()
    assert "CANDIDATE INTERVIEW EVALUATION REPORT" in report
    assert "Kovvuri Nandi Vardhan Reddy" in report
    assert "Score: 9 / 10" in report
