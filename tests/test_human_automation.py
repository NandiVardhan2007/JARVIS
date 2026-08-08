import unittest
import json
import asyncio
from agent import rank_tools_for_user_query
from Tools.desktop_control import click_coordinates, smart_click_and_type, fill_form_fields, press_key
from Tools.open_app import open_app, APP_MAP

class MockToolInfo:
    def __init__(self, name, description=""):
        self.name = name
        self.description = description

class MockTool:
    def __init__(self, name, description=""):
        self.info = MockToolInfo(name, description)

class TestHumanAutomation(unittest.IsolatedAsyncioTestCase):
    def test_tool_relevance_ranking(self):
        tools = [
            MockTool("search_web", "Search the web"),
            MockTool("get_weather", "Get weather information"),
            MockTool("get_time_info", "Get current time"),
            MockTool("open_app", "Launch a Windows application"),
            MockTool("click_on_text", "Click visible screen text using OCR"),
            MockTool("type_user_message_auto", "Type or paste text into active window"),
            MockTool("fill_form_fields", "Fill out multi-field desktop or web forms"),
            MockTool("take_screenshot", "Capture desktop screenshot"),
            MockTool("process_document", "Analyze document content"),
            MockTool("list_directory", "List files in directory"),
            MockTool("delete_file", "Delete a file"),
            MockTool("create_folder", "Create new folder"),
            MockTool("check_system_health", "System health report"),
        ]

        # Query 1: Opening app & typing text
        ranked = rank_tools_for_user_query(tools, "Open notepad and type hello world", max_tools=5)
        names = [t.info.name for t in ranked]
        self.assertIn("open_app", names)
        self.assertIn("type_user_message_auto", names)

        # Query 2: Clicking text & form filling
        ranked_click = rank_tools_for_user_query(tools, "Click on submit button and fill out form", max_tools=5)
        click_names = [t.info.name for t in ranked_click]
        self.assertIn("click_on_text", click_names)
        self.assertIn("fill_form_fields", click_names)

    async def test_fill_form_fields_json_validation(self):
        # Invalid JSON
        res_invalid = await fill_form_fields("not a json string", submit=False)
        self.assertIn("failed", res_invalid.lower())

        # Non-dict JSON
        res_list = await fill_form_fields('["a", "b"]', submit=False)
        self.assertIn("must be a json object", res_list.lower())

    async def test_app_map_coverage(self):
        self.assertIn("notepad", APP_MAP)
        self.assertIn("chrome", APP_MAP)
        self.assertIn("cmd", APP_MAP)

if __name__ == "__main__":
    unittest.main()
