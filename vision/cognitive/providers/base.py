"""
Abstract base class for all VISION LLM provider clients.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, AsyncGenerator, Optional


class BaseLLMProvider(ABC):
    def __init__(self, name: str, model: str):
        self.name = name
        self.model = model
        self.active_requests: int = 0
        self.total_requests: int = 0
        self.failed_requests: int = 0
        self.average_latency_ms: float = 0.0

    @abstractmethod
    async def chat_completion(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> Dict[str, Any]:
        """Synchronous (single response) completion returning OpenAI-style payload."""
        pass

    @abstractmethod
    async def stream_chat_completion(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> AsyncGenerator[str, None]:
        """Streaming completion yielding text tokens."""
        pass
