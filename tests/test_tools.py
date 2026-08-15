"""
Test suite for tool registration and schema generation.
"""

from vision.tools.registry import tool_registry, tool


def test_tool_registration():
    @tool(name="sample_test_tool", description="Test description")
    def sample_tool(param1: str, param2: int = 10) -> str:
        return f"{param1}-{param2}"

    schemas = tool_registry.get_all_schemas()
    names = [s["function"]["name"] for s in schemas]
    assert "sample_test_tool" in names
