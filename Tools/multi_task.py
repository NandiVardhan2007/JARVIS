"""Sequential multi-task execution tool."""

import asyncio
import inspect
import json
import logging
from livekit.agents import function_tool

logger = logging.getLogger(__name__)


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
    from Tools import get_all_tools

    # Parse the JSON string into a list of task dicts
    try:
        tasks = json.loads(tasks_json)
    except json.JSONDecodeError as e:
        return f"Invalid JSON in tasks_json: {e}"

    if not isinstance(tasks, list):
        return "tasks_json must be a JSON array of task objects."

    # Dynamically build the registry from all loaded tools, excluding multi_task itself to prevent recursion
    all_tools = get_all_tools()
    REGISTRY = {t.info.name: t for t in all_tools if t.info.name != "execute_multi_task"}

    if not tasks:
        return "No tasks were provided."

    results = []
    for i, task in enumerate(tasks, 1):
        name = task.get("tool_name")
        params = task.get("params", {})

        if not name:
            results.append(f"Task {i}: missing 'tool_name'.")
            continue
        fn = REGISTRY.get(name)
        if not fn:
            results.append(f"Task {i}: unknown tool '{name}'.")
            continue
        try:
            # FIX: @function_tool wraps async def functions — calling fn(**params)
            # without await just created a coroutine object that was immediately
            # discarded, so every tool silently no-oped. Now we check the underlying
            # function (_func) and await when it's a coroutine.
            raw_fn = fn._func if hasattr(fn, "_func") else fn
            if inspect.iscoroutinefunction(raw_fn):
                result = await raw_fn(**params)
            else:
                result = raw_fn(**params)
            results.append(f"Task {i} ({name}): {result}")
        except Exception as e:
            results.append(f"Task {i} ({name}) failed: {e}")

    return "Multi-Task Results:\n" + "\n".join(results)

