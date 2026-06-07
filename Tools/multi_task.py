"""Sequential multi-task execution tool."""

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
        _REGISTRY = {t.info.name: t for t in get_all_tools() if t.info.name != "execute_multi_task"}
    return _REGISTRY

@function_tool
async def execute_multi_task(tasks_json: str) -> str:
    """
    Executes multiple JARVIS tools sequentially in a single call.

    Args:
        tasks_json: A JSON string containing a list of task objects.
            Each object must have:
            - 'tool_name' (str): Name of the tool to invoke.
            - 'params' (dict): Keyword arguments for that tool.
            Example: '[{"tool_name": "open_app", "params": {"app_name": "chrome"}}, {"tool_name": "get_weather", "params": {"city": "London"}}]'
    """
    # Parse the JSON string into a list of task dicts
    try:
        tasks = json.loads(tasks_json)
    except json.JSONDecodeError as e:
        return f"Invalid JSON in tasks_json: {e}"

    if not isinstance(tasks, list):
        return "tasks_json must be a JSON array of task objects."

    if not tasks:
        return "No tasks were provided."

    registry = _get_registry()
    results = []
    for i, task in enumerate(tasks, 1):
        name = task.get("tool_name")
        params = task.get("params", {})

        if not name:
            results.append(f"Task {i}: missing 'tool_name'.")
            continue
        
        fn = registry.get(name)
        if not fn:
            results.append(f"Task {i}: unknown tool '{name}'.")
            continue
            
        try:
            result = fn(**params)
            if inspect.isawaitable(result):
                result = await result
            results.append(f"Task {i} ({name}): {result}")
        except Exception as e:
            results.append(f"Task {i} ({name}) failed: {e}")

    return "Multi-Task Results:\n" + "\n".join(results)
