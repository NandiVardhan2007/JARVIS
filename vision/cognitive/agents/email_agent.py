"""
Autonomous Email Sub-Agent for reading, drafting, categorizing, and summarizing emails.
"""

from vision.cognitive.agents.base_agent import BaseAgent
from vision.config import config


class EmailAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="EmailAgent", dedicated_api_key=config.EMAIL_AGENT_LLM_API)

    def get_system_prompt(self) -> str:
        return """You are the VISION Autonomous Email Agent.
Your tasks include analyzing incoming emails, extracting action items, drafting polite and professional responses, and classifying priority.
Output structured JSON or clean summaries.
"""
