"""
Tool Registry and schema generator for OpenAI/Groq function calling.
"""

import inspect
from typing import Callable, Dict, Any, List, Optional
from vision.logger import logger


class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, Callable] = {}
        self._schemas: Dict[str, Dict[str, Any]] = {}

    def register(self, name: Optional[str] = None, description: Optional[str] = None):
        """Decorator to register a python function as an LLM tool."""
        def decorator(func: Callable):
            tool_name = name or func.__name__
            tool_doc = description or (func.__doc__ or "No description provided.").strip()

            sig = inspect.signature(func)
            properties = {}
            required = []

            for param_name, param in sig.parameters.items():
                if param_name in ["self", "cls"]:
                    continue

                param_type = "string"
                if param.annotation == int:
                    param_type = "integer"
                elif param.annotation == float:
                    param_type = "number"
                elif param.annotation == bool:
                    param_type = "boolean"
                elif param.annotation == list or getattr(param.annotation, "_name", None) == "List":
                    param_type = "array"
                elif param.annotation == dict or getattr(param.annotation, "_name", None) == "Dict":
                    param_type = "object"

                properties[param_name] = {
                    "type": param_type,
                    "description": f"Parameter: {param_name}"
                }

                if param.default == inspect.Parameter.empty:
                    required.append(param_name)

            schema = {
                "type": "function",
                "function": {
                    "name": tool_name,
                    "description": tool_doc,
                    "parameters": {
                        "type": "object",
                        "properties": properties,
                        "required": required
                    }
                }
            }

            self._tools[tool_name] = func
            self._schemas[tool_name] = schema
            logger.debug(f"[ToolRegistry] Registered tool '{tool_name}'")
            return func
        return decorator

    def get_all_schemas(self) -> List[Dict[str, Any]]:
        return list(self._schemas.values())

    async def execute(self, name: str, arguments: Optional[Dict[str, Any]] = None) -> Any:
        if name not in self._tools:
            return f"Error: Tool '{name}' is not registered."

        if not isinstance(arguments, dict):
            arguments = {}

        func = self._tools[name]
        try:
            # Auto-coerce parameter types (e.g. string "true"/"false" to bool, string digits to int)
            sig = inspect.signature(func)
            cleaned_args = {}
            for k, v in arguments.items():
                if k in sig.parameters:
                    param = sig.parameters[k]
                    if param.annotation == bool and isinstance(v, str):
                        cleaned_args[k] = v.strip().lower() in ["true", "1", "yes"]
                    elif param.annotation == int and isinstance(v, str) and v.isdigit():
                        cleaned_args[k] = int(v)
                    elif param.annotation == float and isinstance(v, str):
                        try:
                            cleaned_args[k] = float(v)
                        except ValueError:
                            cleaned_args[k] = v
                    else:
                        cleaned_args[k] = v
                else:
                    cleaned_args[k] = v

            logger.info(f"[ToolRegistry] Executing tool '{name}' with args {cleaned_args}")
            if inspect.iscoroutinefunction(func):
                return await func(**cleaned_args)
            else:
                return func(**cleaned_args)
        except Exception as e:
            logger.error(f"[ToolRegistry] Tool '{name}' execution failed: {e}")
            return f"Error executing tool '{name}': {str(e)}"


# Singleton tool registry
tool_registry = ToolRegistry()
tool = tool_registry.register
