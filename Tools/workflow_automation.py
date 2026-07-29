"""
Named workflow automation.

Tools/multi_task.py's execute_agent_tasks can already dispatch a multi-step,
cross-app plan (with parallel execution for independent steps). What was
missing for "automate repetitive office tasks" was the ability to SAVE one
of those plans under a name and re-run it later without re-specifying the
whole task list each time — and to compose with the existing scheduler
(Tools/scheduler.py's schedule_task can already call ANY registered tool by
name at a set time, including run_workflow, so "run my morning routine at
9am every day" works with zero scheduler changes).
"""

import json
import logging
import os

from livekit.agents import function_tool

logger = logging.getLogger(__name__)

WORKFLOWS_DIR = os.path.join(os.path.expanduser("~"), "Documents", "JARVIS", "workflows")


def _safe_name(name: str) -> str:
    return "".join(c for c in name.strip() if c.isalnum() or c in " _-").strip().replace(" ", "_") or "workflow"


def _workflow_path(name: str) -> str:
    return os.path.join(WORKFLOWS_DIR, f"{_safe_name(name)}.json")


@function_tool
async def save_workflow(name: str, tasks_json: str, description: str = "") -> str:
    """
    Saves a named, reusable workflow — a multi-step task plan (same schema
    as execute_agent_tasks) that can be run later by name instead of
    re-specifying the whole plan each time. Combine with schedule_task
    (tool_name="run_workflow", tool_parameters={"name": "..."}) to run it
    automatically at a set time.

    Args:
        name: Short name for this workflow (e.g. "morning_routine").
        tasks_json: JSON array of task objects — see execute_agent_tasks for
            the exact schema (tool_name, params, optional parallel_group).
        description: Optional human-readable description of what this workflow does.
    """
    try:
        tasks = json.loads(tasks_json)
    except json.JSONDecodeError as e:
        return f"Invalid JSON in tasks_json: {e}"
    if not isinstance(tasks, list) or not tasks:
        return "tasks_json must be a non-empty JSON array of task objects."

    os.makedirs(WORKFLOWS_DIR, exist_ok=True)
    path = _workflow_path(name)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"name": name, "description": description, "tasks": tasks}, f, indent=2)
        return f"Workflow '{name}' saved with {len(tasks)} step(s). Run it any time with run_workflow, or schedule it with schedule_task."
    except Exception as e:
        return f"Could not save workflow: {e}"


@function_tool
async def list_workflows() -> str:
    """Lists all saved workflows and how many steps each has."""
    if not os.path.isdir(WORKFLOWS_DIR):
        return "No workflows saved yet."
    lines = []
    for fname in sorted(os.listdir(WORKFLOWS_DIR)):
        if not fname.endswith(".json"):
            continue
        try:
            with open(os.path.join(WORKFLOWS_DIR, fname), encoding="utf-8") as f:
                data = json.load(f)
            desc = f" — {data['description']}" if data.get("description") else ""
            lines.append(f"• {data.get('name', fname)}: {len(data.get('tasks', []))} step(s){desc}")
        except Exception:
            continue
    if not lines:
        return "No workflows saved yet."
    return f"{len(lines)} saved workflow(s):\n" + "\n".join(lines)


@function_tool
async def run_workflow(name: str) -> str:
    """
    Runs a previously-saved workflow by name — dispatches its steps the same
    way execute_agent_tasks does (parallel where the workflow specifies it,
    sequential otherwise).

    Args:
        name: Name of the saved workflow to run (see list_workflows).
    """
    path = _workflow_path(name)
    if not os.path.isfile(path):
        return f"No workflow named '{name}' found. Use list_workflows to see saved workflows."

    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        return f"Could not read workflow '{name}': {e}"

    tasks = data.get("tasks", [])
    if not tasks:
        return f"Workflow '{name}' has no steps."

    from Tools.multi_task import run_task_list
    result = await run_task_list(tasks)
    return f"Running workflow '{name}':\n{result}"


@function_tool
async def delete_workflow(name: str) -> str:
    """
    Deletes a saved workflow.

    Args:
        name: Name of the workflow to delete.
    """
    path = _workflow_path(name)
    if not os.path.isfile(path):
        return f"No workflow named '{name}' found."
    try:
        os.remove(path)
        return f"Workflow '{name}' deleted."
    except Exception as e:
        return f"Could not delete workflow '{name}': {e}"
