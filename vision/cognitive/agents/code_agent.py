"""
Autonomous Code & Script Execution Agent powered by NVIDIA / Groq.
"""

from vision.cognitive.agents.base_agent import BaseAgent


class CodeAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="CodeAgent")

    def get_system_prompt(self) -> str:
        return """You are the VISION Code & Terminal Agent.
Your mission is to write clean, correct scripts, debug code snippets, and execute shell automation safely.
"""
