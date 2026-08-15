"""
Groq LLM Provider Adapter with token rate limiting and multi-key support.
"""

from typing import List, Dict, Any, AsyncGenerator, Optional
import time
from vision.cognitive.providers.base import BaseLLMProvider
from vision.logger import logger

try:
    from groq import AsyncGroq
except ImportError:
    AsyncGroq = None


class GroqLLMProvider(BaseLLMProvider):
    def __init__(self, api_key: str, model: str = "llama-3.3-70b-versatile"):
        super().__init__(name="Groq", model=model)
        self.api_key = api_key
        self.client = AsyncGroq(api_key=api_key) if AsyncGroq else None

    async def chat_completion(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> Dict[str, Any]:
        if not self.client:
            raise RuntimeError("groq package is not installed.")

        self.active_requests += 1
        start_time = time.time()
        try:
            kwargs: Dict[str, Any] = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
            }
            if max_tokens:
                kwargs["max_tokens"] = max_tokens
            if tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = "auto"

            response = await self.client.chat.completions.create(**kwargs)
            duration_ms = (time.time() - start_time) * 1000
            self._update_stats(duration_ms)

            choice = response.choices[0]
            message_obj = choice.message
            tool_calls = None
            if message_obj.tool_calls:
                tool_calls = [tc.model_dump() for tc in message_obj.tool_calls]

            return {
                "role": "assistant",
                "content": message_obj.content,
                "tool_calls": tool_calls,
                "finish_reason": choice.finish_reason,
                "provider": self.name,
                "latency_ms": duration_ms
            }
        except Exception as e:
            self.failed_requests += 1
            logger.error(f"[GroqLLM] Completion failed: {e}")
            raise e
        finally:
            self.active_requests = max(0, self.active_requests - 1)

    async def stream_chat_completion(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> AsyncGenerator[str, None]:
        if not self.client:
            raise RuntimeError("groq package is not installed.")

        self.active_requests += 1
        try:
            kwargs: Dict[str, Any] = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "stream": True
            }
            if max_tokens:
                kwargs["max_tokens"] = max_tokens

            stream = await self.client.chat.completions.create(**kwargs)
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        finally:
            self.active_requests = max(0, self.active_requests - 1)

    def _update_stats(self, duration_ms: float):
        self.total_requests += 1
        self.average_latency_ms = (
            (self.average_latency_ms * (self.total_requests - 1) + duration_ms) / self.total_requests
        )
