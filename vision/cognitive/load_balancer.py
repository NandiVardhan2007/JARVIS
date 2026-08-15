"""
Multi-Provider LLM Load Balancer & Dynamic Key Pool using Groq and NVIDIA NIM.
"""

from typing import List, Dict, Any, AsyncGenerator, Optional
from vision.config import config
from vision.cognitive.providers.base import BaseLLMProvider
from vision.cognitive.providers.groq_llm import GroqLLMProvider
from vision.cognitive.providers.openai_compatible import OpenAICompatibleProvider
from vision.cognitive.providers.gemini_llm import GeminiLLMProvider
from vision.logger import logger


class LLMLoadBalancer:
    def __init__(self):
        self.providers: List[BaseLLMProvider] = []
        self._round_robin_idx = 0
        self.strategy = config.VISION_LOAD_BALANCER_STRATEGY or "least_busy"
        self._initialize_providers()

    def _initialize_providers(self):
        """Register all active Groq, NVIDIA NIM, and Cloud Fallback providers."""
        # 1. Primary: Groq Keys (Llama 3.3 70B)
        groq_keys = list(set([k for k in [config.GROQ_API_KEY] + config.GROQ_API_KEYS if k]))
        for idx, key in enumerate(groq_keys):
            self.providers.append(
                GroqLLMProvider(api_key=key, model=config.VISION_LLM_MODEL)
            )

        # 2. NVIDIA NIM Keys (Llama 3.1 / 3.3)
        nvidia_keys = list(set([k for k in [config.NVIDIA_API_KEY] + config.NVIDIA_API_KEYS if k]))
        for idx, key in enumerate(nvidia_keys):
            self.providers.append(
                OpenAICompatibleProvider(
                    name=f"NVIDIA-NIM-{idx+1}",
                    api_key=key,
                    base_url="https://integrate.api.nvidia.com/v1",
                    model=config.VISION_NIM_LLM_MODEL
                )
            )

        # 3. OpenRouter Key Pool (Cloud Fallback)
        openrouter_keys = list(set([k for k in config.OPENROUTER_API_KEYS if k]))
        for idx, key in enumerate(openrouter_keys):
            self.providers.append(
                OpenAICompatibleProvider(
                    name=f"OpenRouter-{idx+1}",
                    api_key=key,
                    base_url="https://openrouter.ai/api/v1",
                    model=config.OPENROUTER_LLM_MODEL,
                    default_headers={"HTTP-Referer": "https://vision.ai", "X-Title": "VISION AI"}
                )
            )

        # 4. Google Gemini (Multimodal / Fallback)
        if config.GEMINI_API_KEY:
            self.providers.append(
                GeminiLLMProvider(api_key=config.GEMINI_API_KEY)
            )

        logger.info(f"[LoadBalancer] Initialized {len(self.providers)} endpoints with strategy '{self.strategy}'.")

    def _select_provider_order(self) -> List[BaseLLMProvider]:
        """Return a ranked list of providers according to current strategy."""
        if not self.providers:
            raise RuntimeError("No LLM providers configured.")

        if self.strategy == "least_busy":
            return sorted(self.providers, key=lambda p: (p.active_requests, p.failed_requests))
        elif self.strategy == "latency_based":
            return sorted(self.providers, key=lambda p: (p.average_latency_ms, p.failed_requests))
        elif self.strategy == "round_robin":
            n = len(self.providers)
            idx = self._round_robin_idx % n
            self._round_robin_idx += 1
            return self.providers[idx:] + self.providers[:idx]
        else: # priority_fallback (default order)
            return list(self.providers)

    async def chat_completion(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> Dict[str, Any]:
        """Execute chat completion with automatic failover across ranked providers."""
        ranked_providers = self._select_provider_order()
        last_error = None

        for provider in ranked_providers:
            try:
                logger.debug(f"[LoadBalancer] Routing to '{provider.name}' ({provider.model})")
                return await provider.chat_completion(
                    messages=messages,
                    tools=tools,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
            except Exception as e:
                logger.warning(f"[LoadBalancer] Provider '{provider.name}' failed: {e}. Failing over.")
                last_error = e

        raise RuntimeError(f"All LLM providers failed. Last error: {last_error}")

    async def stream_chat_completion(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> AsyncGenerator[str, None]:
        """Stream tokens with failover on initial connection."""
        ranked_providers = self._select_provider_order()
        for provider in ranked_providers:
            try:
                logger.debug(f"[LoadBalancer] Streaming from '{provider.name}'")
                async for chunk in provider.stream_chat_completion(
                    messages=messages,
                    tools=tools,
                    temperature=temperature,
                    max_tokens=max_tokens
                ):
                    yield chunk
                return
            except Exception as e:
                logger.warning(f"[LoadBalancer] Stream provider '{provider.name}' failed: {e}. Attempting failover.")


# Singleton Load Balancer instance
load_balancer = LLMLoadBalancer()
