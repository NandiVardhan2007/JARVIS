"""
Autonomous Browser Sub-Agent for VISION AI OS.
Executes multi-step browser tasks, data extraction, and web workflows in a visible browser.
"""

from typing import Dict, Any, Optional
from vision.cognitive.agents.base_agent import BaseAgent
from vision.tools.browser_control_tools import browser_autonomous_task


BROWSER_AGENT_SYSTEM_PROMPT = """You are an autonomous web browsing agent for VISION that controls a visible browser, navigates pages, extracts information, fills forms, and solves web tasks accurately.
"""


class BrowserAgent(BaseAgent):
    def __init__(self, dedicated_api_key: Optional[str] = None):
        super().__init__(
            name="BrowserAgent",
            agent_type="browser",
            dedicated_api_key=dedicated_api_key,
            allowed_tools=[
                "browser_autonomous_task", "browser_fill_form_and_login", "browser_open",
                "browser_navigate", "browser_click", "browser_type", "browser_hover",
                "browser_select_option", "browser_press_key", "browser_scroll",
                "browser_get_page_content", "browser_get_interactive_elements",
                "browser_take_screenshot", "browser_list_tabs", "browser_switch_tab",
                "browser_back", "browser_forward", "browser_close",
                "open_website", "download_file_from_url"
            ]
        )

    async def execute_task(self, task_description: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute autonomous browsing task using dedicated browser loop or ReAct."""
        start_url = context.get("start_url") if context else None
        max_steps = context.get("max_steps", 6) if context else 6
        
        # If explicitly high-level browsing goal, invoke browser_autonomous_task
        if start_url or "navigate" in task_description.lower() or "browse" in task_description.lower() or "website" in task_description.lower():
            try:
                result = await browser_autonomous_task(goal=task_description, start_url=start_url, max_steps=max_steps)
                return {
                    "agent": self.name,
                    "agent_type": self.agent_type,
                    "status": "success",
                    "content": result
                }
            except Exception as e:
                # Fallback to standard ReAct loop
                pass

        return await super().execute_task(task_description=task_description, context=context)

    def get_system_prompt(self) -> str:
        return BROWSER_AGENT_SYSTEM_PROMPT
