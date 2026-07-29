"""
Multi-agent task orchestrator.

JARVIS's tools are already organized into specialized groups (see
TOOL_CATEGORIES / AGENT_ROSTER in Tools/__init__.py) — Research, Browser,
Terminal/Coding, File Management, Communication, System, Scheduling, and so
on. This module is the orchestrator: given a plan of subtasks (each one a
call to a specific tool "belonging" to one of those agents), it dispatches
them, running genuinely independent subtasks IN PARALLEL via asyncio.gather
rather than one at a time, and only serializing subtasks that actually
depend on each other.

This replaces the old execute_multi_task, which ran every step strictly
sequentially even when steps had nothing to do with each other (e.g.
checking the weather and checking stock prices don't need to wait on one
another — under the old tool they would anyway).
"""

import asyncio
import inspect
import json
import logging

from livekit.agents import function_tool

logger = logging.getLogger(__name__)

_REGISTRY = None


def _get_registry():
    global _REGISTRY
    if _REGISTRY is None:
        from Tools import get_all_tools
        _REGISTRY = {t.info.name: t for t in get_all_tools() if t.info.name != "execute_agent_tasks"}
    return _REGISTRY


async def _run_one(i: int, task: dict, registry: dict) -> str:
    name = task.get("tool_name")
    params = task.get("params", {})

    if not name:
        return f"Task {i}: missing 'tool_name'."

    fn = registry.get(name)
    if not fn:
        return f"Task {i}: unknown tool '{name}'."

    try:
        result = fn(**params)
        if inspect.isawaitable(result):
            result = await result
        return f"Task {i} ({name}): {result}"
    except Exception as e:
        return f"Task {i} ({name}) failed: {e}"


async def run_task_list(tasks: list) -> str:
    """
    Runs a list of already-parsed task dicts (see execute_agent_tasks for the
    schema), grouping and dispatching them with the same parallel/sequential
    logic. Shared by execute_agent_tasks (parses JSON from the LLM) and
    Tools/workflow_automation.py's run_workflow (loads JSON from a saved
    file), so the dispatch logic lives in exactly one place.
    """
    if not isinstance(tasks, list) or not tasks:
        return "No tasks were provided."

    registry = _get_registry()

    # Assign each task an index, and a group (default: one-per-task = fully sequential)
    indexed = list(enumerate(tasks, 1))
    auto_group = 0
    groups: dict = {}
    for i, task in indexed:
        if "parallel_group" in task and task["parallel_group"] is not None:
            group_key = ("explicit", task["parallel_group"])
        else:
            auto_group -= 1
            group_key = ("auto", auto_group)
        groups.setdefault(group_key, []).append((i, task))

    # Preserve first-appearance order of groups so execution order matches the plan
    ordered_group_keys = sorted(groups.keys(), key=lambda k: min(i for i, _ in groups[k]))

    results_by_index = {}
    for group_key in ordered_group_keys:
        members = groups[group_key]
        if len(members) == 1:
            i, task = members[0]
            results_by_index[i] = await _run_one(i, task, registry)
        else:
            logger.info(f"Running {len(members)} tasks concurrently (group {group_key}).")
            coros = [_run_one(i, task, registry) for i, task in members]
            outcomes = await asyncio.gather(*coros)
            for (i, _task), outcome in zip(members, outcomes):
                results_by_index[i] = outcome

    ordered_results = [results_by_index[i] for i in sorted(results_by_index)]
    return "Task Results:\n" + "\n".join(ordered_results)


@function_tool
async def execute_agent_tasks(tasks_json: str) -> str:
    """
    Dispatches multiple JARVIS tool calls as an orchestrated plan, running
    independent subtasks IN PARALLEL for speed and only serializing ones
    that depend on each other's results.

    Args:
        tasks_json: A JSON array of task objects. Each object must have:
            - 'tool_name' (str): Name of the tool to invoke (from any agent's toolset).
            - 'params' (dict): Keyword arguments for that tool.
            - 'parallel_group' (int, optional): Tasks sharing the same group
              number run CONCURRENTLY. Groups execute in ascending order, so
              use this for subtasks whose result doesn't depend on any
              earlier subtask. If omitted, each task gets its own group
              (fully sequential — the safe default when unsure or when a
              later step needs an earlier step's output first).

        Example — two independent lookups running at once, then a message
        sent after both finish:
        '[
          {"tool_name": "get_weather", "params": {"city": "London"}, "parallel_group": 0},
          {"tool_name": "get_stock_price", "params": {"symbol": "AAPL"}, "parallel_group": 0},
          {"tool_name": "send_discord_message", "params": {"channel": "general", "message": "checked both"}, "parallel_group": 1}
        ]'
        Here the weather and stock lookups run at the same time (both group 0),
        and the Discord message (group 1) waits for both to finish first.

        For a task list you'll want to reuse repeatedly (a "workflow"), save
        it once with Tools/workflow_automation.py's save_workflow instead of
        re-sending the same JSON every time.
    """
    try:
        tasks = json.loads(tasks_json)
    except json.JSONDecodeError as e:
        return f"Invalid JSON in tasks_json: {e}"

    if not isinstance(tasks, list):
        return "tasks_json must be a JSON array of task objects."

    return await run_task_list(tasks)
