"""
Comprehensive Unit and Integration Tests for Autonomous Multi-Agent & Execution Engine.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from vision.cognitive.agents.models import TaskStatus, AgentTask, ExecutionPlan
from vision.cognitive.agents.base_agent import BaseAgent
from vision.cognitive.agents.planner_agent import PlannerAgent
from vision.cognitive.agents.research_agent import ResearchAgent
from vision.cognitive.agents.code_agent import CodeAgent
from vision.cognitive.agents.file_agent import FileAgent
from vision.cognitive.agents.communication_agent import CommunicationAgent
from vision.cognitive.agents.browser_agent import BrowserAgent
from vision.cognitive.agents.orchestrator import MultiAgentOrchestrator
from vision.tools.registry import tool_registry
from vision.tools.agent_execution_tools import execute_autonomous_multi_agent_goal, get_autonomous_goal_status


def test_models_dag_readiness():
    """Test that ExecutionPlan accurately calculates ready tasks based on dependencies."""
    t1 = AgentTask(id="task_1", title="Search Web", agent_type="research", description="Search AI news")
    t2 = AgentTask(id="task_2", title="Write File", agent_type="file", description="Write summary", dependencies=["task_1"])
    t3 = AgentTask(id="task_3", title="Send Email", agent_type="communication", description="Send report", dependencies=["task_2"])

    plan = ExecutionPlan(goal="Research and email", tasks=[t1, t2, t3])

    # Initially only task_1 is ready
    ready = plan.get_ready_tasks()
    assert len(ready) == 1
    assert ready[0].id == "task_1"

    # Complete task_1
    t1.status = TaskStatus.COMPLETED
    t1.output = "AI news summary"

    # Now task_2 is ready
    ready = plan.get_ready_tasks()
    assert len(ready) == 1
    assert ready[0].id == "task_2"

    # Complete task_2
    t2.status = TaskStatus.COMPLETED
    t2.output = "Saved to file.md"

    # Now task_3 is ready
    ready = plan.get_ready_tasks()
    assert len(ready) == 1
    assert ready[0].id == "task_3"

    assert not plan.is_finished()
    t3.status = TaskStatus.COMPLETED
    assert plan.is_finished()


def test_orchestrator_variable_substitution():
    """Test ${task_id.output} variable replacement in string, dict, and list parameters."""
    orch = MultiAgentOrchestrator()
    completed_outputs = {
        "task_1": "Python 3.12 Released",
        "task_2": "C:\\Docs\\report.md"
    }

    # Test string substitution
    desc = "Send email containing ${task_1.output} with attachment ${task_2.output}"
    resolved = orch._substitute_variables(desc, completed_outputs)
    assert resolved == "Send email containing Python 3.12 Released with attachment C:\\Docs\\report.md"

    # Test dict substitution
    params = {
        "body": "${task_1.output}",
        "file": "${task_2.output}",
        "static": 123
    }
    resolved_params = orch._substitute_variables(params, completed_outputs)
    assert resolved_params["body"] == "Python 3.12 Released"
    assert resolved_params["file"] == "C:\\Docs\\report.md"
    assert resolved_params["static"] == 123


@pytest.mark.asyncio
async def test_planner_agent_json_parsing():
    """Test PlannerAgent decomposes goal and parses structured JSON plans."""
    planner = PlannerAgent()
    
    mock_json_response = """
    ```json
    {
      "goal": "Research Python 3.13 and write a report",
      "summary": "2-step research and write workflow",
      "tasks": [
        {
          "id": "t1",
          "title": "Search Python 3.13 features",
          "agent_type": "research",
          "description": "Find top Python 3.13 features",
          "dependencies": [],
          "input_params": {}
        },
        {
          "id": "t2",
          "title": "Save to markdown",
          "agent_type": "file",
          "description": "Write report with ${t1.output}",
          "dependencies": ["t1"],
          "input_params": {"path": "python_313.md"}
        }
      ]
    }
    ```
    """

    with patch.object(planner, "_call_llm", new=AsyncMock(return_value={"content": mock_json_response, "provider": "mock"})):
        plan = await planner.create_plan("Research Python 3.13 and write a report")
        assert len(plan.tasks) == 2
        assert plan.tasks[0].id == "t1"
        assert plan.tasks[0].agent_type == "research"
        assert plan.tasks[1].id == "t2"
        assert plan.tasks[1].dependencies == ["t1"]


@pytest.mark.asyncio
async def test_specialized_agents_tool_scoping():
    """Test that specialized sub-agents have properly scoped tool schemas."""
    research_agent = ResearchAgent()
    code_agent = CodeAgent()
    file_agent = FileAgent()
    comm_agent = CommunicationAgent()

    assert "search_web" in research_agent.allowed_tools
    assert "run_python_code" in code_agent.allowed_tools
    assert "create_or_write_file" in file_agent.allowed_tools
    assert "send_email" in comm_agent.allowed_tools


@pytest.mark.asyncio
async def test_orchestrator_end_to_end_execution():
    """Test full multi-agent orchestrator execution with simulated agent outputs."""
    orch = MultiAgentOrchestrator()

    mock_plan = ExecutionPlan(
        goal="Test compound workflow",
        tasks=[
            AgentTask(id="task_1", title="Gather Data", agent_type="research", description="Search info"),
            AgentTask(id="task_2", title="Save Document", agent_type="file", description="Save ${task_1.output}", dependencies=["task_1"])
        ]
    )

    with patch.object(orch.planner, "create_plan", new=AsyncMock(return_value=mock_plan)):
        with patch.object(orch.agents["research"], "execute_task", new=AsyncMock(return_value={"status": "success", "content": "Research findings verified."})):
            with patch.object(orch.agents["file"], "execute_task", new=AsyncMock(return_value={"status": "success", "content": "File saved at D:\\output.md"})):
                with patch.object(orch, "_synthesize_final_output", new=AsyncMock(return_value="Goal accomplished successfully!")):
                    result = await orch.execute_goal("Test compound workflow")

                    assert result["status"] == "completed"
                    assert len(result["tasks"]) == 2
                    assert result["tasks"][0]["status"] == "completed"
                    assert result["tasks"][0]["output"] == "Research findings verified."
                    assert result["tasks"][1]["status"] == "completed"
                    assert result["tasks"][1]["output"] == "File saved at D:\\output.md"
                    assert "accomplished" in result["final_output"]


@pytest.mark.asyncio
async def test_tool_registry_registration_and_status():
    """Test that execute_autonomous_multi_agent_goal is registered in tool_registry and queries status."""
    schema = tool_registry._schemas.get("execute_autonomous_multi_agent_goal")
    assert schema is not None
    assert schema["function"]["name"] == "execute_autonomous_multi_agent_goal"

    status_schema = tool_registry._schemas.get("get_autonomous_goal_status")
    assert status_schema is not None

    # Test status lookup for nonexistent ID
    res = get_autonomous_goal_status("nonexistent_id")
    assert "No active or historical plan" in res
