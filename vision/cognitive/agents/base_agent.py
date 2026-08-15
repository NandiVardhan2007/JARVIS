"""
Base class for isolated autonomous sub-agents.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from vision.cognitive.providers.openai_compatible import OpenAICompatibleProvider
from vision.cognitive.load_balancer import load_balancer
from vision.constants import DEFAULT_SUBAGENT_SYSTEM_PROMPT
from vision.logger import logger


class BaseAgent(ABC):
    def __init__(self, name: str, dedicated_api_key: Optional[str] = None):
        self.name = name
        self.dedicated_client = None
        if dedicated_api_key:
            self.dedicated_client = OpenAICompatibleProvider(
                name=f"{name}-Dedicated",
                api_key=dedicated_api_key,
                base_url="https://integrate.api.nvidia.com/v1",
                model="meta/llama-3.1-8b-instruct"
            )

    async def execute_task(self, task_description: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute task using dedicated LLM or fallback load balancer."""
        messages = [
            {"role": "system", "content": self.get_system_prompt()},
            {"role": "user", "content": f"Task: {task_description}\nContext: {context or {}}"}
        ]
        if self.dedicated_client:
            try:
                return await self.dedicated_client.chat_completion(messages=messages)
            except Exception as e:
                logger.warning(f"[{self.name}] Dedicated LLM failed, using Load Balancer: {e}")

        return await load_balancer.chat_completion(messages=messages)

    @abstractmethod
    def get_system_prompt(self) -> str:
        return DEFAULT_SUBAGENT_SYSTEM_PROMPT
