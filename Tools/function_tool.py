"""
Zero-dependency replacement for livekit.agents function_tool decorator.
Introspects Python functions (type hints + docstrings) and formats them
into standard OpenAI tool JSON schema definitions.
"""

import inspect
import functools
from typing import Callable, Any, Dict, List, Optional


def _py_type_to_json_schema(annotation: Any) -> Dict[str, Any]:
    """Map basic Python type annotations to JSON Schema types."""
    if annotation in (str, Optional[str]):
        return {"type": "string"}
    elif annotation in (int, Optional[int]):
        return {"type": "integer"}
    elif annotation in (float, Optional[float]):
        return {"type": "number"}
    elif annotation in (bool, Optional[bool]):
        return {"type": "boolean"}
    elif annotation in (list, List, Optional[list], Optional[List]):
        return {"type": "array", "items": {"type": "string"}}
    elif annotation in (dict, Dict, Optional[dict], Optional[Dict]):
        return {"type": "object"}
    return {"type": "string"}


class ToolInfo:
    """Holds metadata for a decorated function tool."""

    def __init__(self, name: str, description: str, func: Callable):
        self.name = name
        self.description = description
        self.func = func

    def to_openai_tool(self) -> Dict[str, Any]:
        """Format function metadata as an OpenAI tool schema."""
        sig = inspect.signature(self.func)
        properties = {}
        required = []

        for param_name, param in sig.parameters.items():
            if param_name in ("self", "cls"):
                continue
            
            # Param type
            param_type = _py_type_to_json_schema(param.annotation)
            
            # Param description (fallback to param name)
            param_type["description"] = f"Parameter '{param_name}'"
            properties[param_name] = param_type

            # Check if required (no default value)
            if param.default is inspect.Parameter.empty:
                required.append(param_name)

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description or f"Tool function {self.name}",
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }


def function_tool(func: Optional[Callable] = None, *, name: Optional[str] = None, description: Optional[str] = None):
    """
    Decorator for registering functions as VISION AI tools.
    Supports both @function_tool and @function_tool(name="...", description="...") syntax.
    """
    def decorator(fn: Callable) -> Callable:
        tool_name = name or fn.__name__
        tool_desc = (description or fn.__doc__ or "").strip()
        
        # Clean docstring (first paragraph)
        if tool_desc:
            lines = [line.strip() for line in tool_desc.splitlines() if line.strip()]
            tool_desc = " ".join(lines[:3]) if lines else tool_name

        tool_info = ToolInfo(name=tool_name, description=tool_desc, func=fn)

        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            if inspect.iscoroutinefunction(fn):
                return await fn(*args, **kwargs)
            return fn(*args, **kwargs)

        wrapper.info = tool_info
        wrapper._fnc = fn
        return wrapper

    if func is None:
        return decorator
    return decorator(func)
