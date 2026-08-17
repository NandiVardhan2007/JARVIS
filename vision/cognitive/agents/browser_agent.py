"""
Autonomous Browser Sub-Agent for VISION AI OS.
Executes multi-step browser tasks, data extraction, and web workflows in a visible browser.
"""

from typing import Dict, Any, Optional
from vision.cognitive.agents.base_agent import BaseAgent
from vision.tools.browser_control_tools import browser_autonomous_task


class BrowserAgent(BaseAgent):
    def __init__(self, dedicated_api_key: Optional[str] = None):
        super().__init__(name="BrowserAgent", dedicated_api_key=dedicated_api_key)

    async def execute_task(self, task_description: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute autonomous browsing task."""
        start_url = context.get("start_url") if context else None
        max_steps = context.get("max_steps", 6) if context else 6
        result = await browser_autonomous_task(goal=task_description, start_url=start_url, max_steps=max_steps)
        return {
            "agent": self.name,
            "status": "success",
            "content": result
        }

    def get_system_prompt(self) -> str:
        return "You are an autonomous web browsing agent that controls a visible browser, navigates pages, extracts information, fills forms, and solves web tasks accurately."
