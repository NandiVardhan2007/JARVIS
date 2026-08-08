"""
AI API Load Balancer & Multi-Provider Router for VISION.

Distributes LLM requests dynamically across multiple providers (OpenRouter, NVIDIA NIM,
Groq, Google Gemini, OpenAI, Local LM Studio/Ollama) and multiple API keys per provider.

Features:
- Dynamic Load Balancing Strategies: least_busy (concurrency-aware), round_robin, latency_based, priority_fallback.
- Circuit Breaker & Rate Limit Cooldown: Automatically detects HTTP 429 rate limits and 5xx errors,
  cooling down the specific key while failing over to another healthy key/endpoint seamlessly.
- Multi-Key Pool Support: Parses comma-separated key strings (e.g., OPENROUTER_API_KEYS, NVIDIA_API_KEYS).
- Dual Interface:
  1. LiveKit LLM Plugin (`LoadBalancedLLM`): Drop-in replacement for agent.py voice sessions.
  2. Standalone Python API (`chat_completion`, `achat_completion`): Unified caller for background tools/sub-agents.
"""

import os
import time
import logging
import threading
import asyncio
import random
from typing import List, Dict, Any, Optional, Tuple, AsyncGenerator
import requests
from dotenv import load_dotenv

# LiveKit imports (optional at import time, resolved when LiveKit adapter is used)
try:
    from livekit.agents import llm
    from livekit.plugins import openai as lk_openai
    LIVEKIT_AVAILABLE = True
except ImportError:
    LIVEKIT_AVAILABLE = False
    llm = None
    lk_openai = None

logger = logging.getLogger("VISION.AILoadBalancer")

# Default Models per Provider
DEFAULT_MODELS = {
    "openrouter": os.getenv("OPENROUTER_LLM_MODEL", "meta-llama/llama-3.3-70b-instruct"),
    "nvidia_nim": os.getenv("NIM_LLM_MODEL", os.getenv("NVIDIA_LLM_MODEL", "meta/llama-3.3-70b-instruct")),
    "groq": os.getenv("GROQ_LLM_MODEL", os.getenv("VISION_LLM_MODEL", "llama-3.3-70b-versatile")),
    "gemini": os.getenv("GEMINI_LLM_MODEL", "gemini-2.0-flash"),
    "local": os.getenv("LOCAL_LLM_MODEL", "local-model"),
    "openai": os.getenv("OPENAI_LLM_MODEL", "gpt-4o-mini"),
    "deepseek": os.getenv("DEEPSEEK_LLM_MODEL", "deepseek-chat"),
}

# Default Base URLs
DEFAULT_BASE_URLS = {
    "openrouter": "https://openrouter.ai/api/v1",
    "nvidia_nim": "https://integrate.api.nvidia.com/v1",
    "groq": "https://api.groq.com/openai/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai/",
    "local": "http://localhost:1234/v1",
    "openai": "https://api.openai.com/v1",
    "deepseek": "https://api.deepseek.com/v1",
}


class AIEndpoint:
    """Represents a single provider endpoint + API key instance."""

    def __init__(
        self,
        endpoint_id: str,
        provider: str,
        base_url: str,
        api_key: str,
        model: str,
        weight: float = 1.0,
        extra_headers: Optional[Dict[str, str]] = None,
    ):
        self.id = endpoint_id
        self.provider = provider
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.weight = weight
        self.extra_headers = extra_headers or {}

        # Runtime Stats & Health (Thread-Safe / Lock guarded)
        self.active_requests = 0
        self.total_requests = 0
        self.failed_requests = 0
        self.cooldown_until = 0.0  # Timestamp when cooldown expires
        self.latency_history: List[float] = []
        self._lk_instance = None  # Cached LiveKit LLM object

    @property
    def is_cooling_down(self) -> bool:
        return time.time() < self.cooldown_until

    @property
    def avg_latency(self) -> float:
        if not self.latency_history:
            return 0.5  # Default baseline 500ms
        return sum(self.latency_history[-10:]) / len(self.latency_history[-10:])

    def trigger_cooldown(self, seconds: float = 60.0, reason: str = ""):
        self.cooldown_until = time.time() + seconds
        logger.warning(
            f"Endpoint [{self.id}] ({self.provider}) cooling down for {seconds}s. Reason: {reason}"
        )

    def record_request_start(self):
        self.active_requests += 1
        self.total_requests += 1

    def record_request_end(self, duration_sec: Optional[float] = None, success: bool = True):
        self.active_requests = max(0, self.active_requests - 1)
        if success:
            if duration_sec is not None:
                self.latency_history.append(duration_sec)
                if len(self.latency_history) > 50:
                    self.latency_history.pop(0)
        else:
            self.failed_requests += 1

    def get_livekit_llm(self):
        """Returns or creates a cached LiveKit OpenAI LLM instance for this endpoint."""
        if not LIVEKIT_AVAILABLE:
            raise RuntimeError("livekit-agents is not installed in the python environment.")

        if self._lk_instance is None:
            if self.provider == "openrouter":
                self._lk_instance = lk_openai.LLM.with_openrouter(
                    model=self.model,
                    api_key=self.api_key,
                )
            elif self.provider == "groq":
                self._lk_instance = lk_openai.LLM(
                    model=self.model,
                    api_key=self.api_key,
                    base_url=self.base_url,
                )
            else:
                self._lk_instance = lk_openai.LLM(
                    model=self.model,
                    api_key=self.api_key,
                    base_url=self.base_url,
                )
        return self._lk_instance

    def __repr__(self):
        status = "COOLDOWN" if self.is_cooling_down else "ACTIVE"
        return f"<AIEndpoint id={self.id} provider={self.provider} active={self.active_requests} status={status}>"


class AILoadBalancer:
    """Central AI Load Balancer and Multi-Provider Key Router."""

    def __init__(self, strategy: Optional[str] = None):
        load_dotenv(override=True)
        self.strategy = strategy or os.getenv("VISION_LOAD_BALANCER_STRATEGY", "least_busy")
        self.endpoints: List[AIEndpoint] = []
        self._lock = threading.Lock()
        self._rr_index = 0
        self._init_endpoints_from_env()

    def _init_endpoints_from_env(self):
        """Discovers and parses API keys from environment variables."""
        with self._lock:
            self.endpoints.clear()

            # Helper to parse multi-key or single key variables
            def _parse_keys(multi_env: str, single_env: str) -> List[str]:
                raw_multi = os.getenv(multi_env, "").strip()
                if raw_multi:
                    return [k.strip() for k in raw_multi.split(",") if k.strip()]
                single = os.getenv(single_env, "").strip()
                return [single] if single else []

            # 1. OpenRouter
            or_keys = _parse_keys("OPENROUTER_API_KEYS", "OPENROUTER_API_KEY")
            or_model = DEFAULT_MODELS["openrouter"]
            for idx, key in enumerate(or_keys):
                self.endpoints.append(
                    AIEndpoint(
                        endpoint_id=f"openrouter_{idx+1}",
                        provider="openrouter",
                        base_url=DEFAULT_BASE_URLS["openrouter"],
                        api_key=key,
                        model=or_model,
                        extra_headers={
                            "HTTP-Referer": "https://github.com/NandiVardhan2007/JARVIS",
                            "X-Title": "VISION AI Load Balancer",
                        },
                    )
                )

            # 2. NVIDIA NIM
            nim_keys = _parse_keys("NVIDIA_API_KEYS", "NVIDIA_API_KEY")
            nim_model = DEFAULT_MODELS["nvidia_nim"]
            for idx, key in enumerate(nim_keys):
                self.endpoints.append(
                    AIEndpoint(
                        endpoint_id=f"nvidia_nim_{idx+1}",
                        provider="nvidia_nim",
                        base_url=DEFAULT_BASE_URLS["nvidia_nim"],
                        api_key=key,
                        model=nim_model,
                    )
                )

            # 3. Groq
            groq_keys = _parse_keys("GROQ_API_KEYS", "GROQ_API_KEY")
            groq_model = DEFAULT_MODELS["groq"]
            for idx, key in enumerate(groq_keys):
                self.endpoints.append(
                    AIEndpoint(
                        endpoint_id=f"groq_{idx+1}",
                        provider="groq",
                        base_url=DEFAULT_BASE_URLS["groq"],
                        api_key=key,
                        model=groq_model,
                    )
                )

            # 4. Google Gemini
            gemini_keys = _parse_keys("GEMINI_API_KEYS", "GEMINI_API_KEY")
            gemini_model = DEFAULT_MODELS["gemini"]
            for idx, key in enumerate(gemini_keys):
                self.endpoints.append(
                    AIEndpoint(
                        endpoint_id=f"gemini_{idx+1}",
                        provider="gemini",
                        base_url=DEFAULT_BASE_URLS["gemini"],
                        api_key=key,
                        model=gemini_model,
                    )
                )

            # 5. DeepSeek / OpenAI (Online Cloud Providers)
            ds_keys = _parse_keys("DEEPSEEK_API_KEYS", "DEEPSEEK_API_KEY")
            for idx, key in enumerate(ds_keys):
                self.endpoints.append(
                    AIEndpoint(
                        endpoint_id=f"deepseek_{idx+1}",
                        provider="deepseek",
                        base_url=DEFAULT_BASE_URLS["deepseek"],
                        api_key=key,
                        model=DEFAULT_MODELS["deepseek"],
                    )
                )

            oai_keys = _parse_keys("OPENAI_API_KEYS", "OPENAI_API_KEY")
            for idx, key in enumerate(oai_keys):
                self.endpoints.append(
                    AIEndpoint(
                        endpoint_id=f"openai_{idx+1}",
                        provider="openai",
                        base_url=DEFAULT_BASE_URLS["openai"],
                        api_key=key,
                        model=DEFAULT_MODELS["openai"],
                    )
                )

            logger.info(
                f"AI Load Balancer initialized with {len(self.endpoints)} endpoints across providers: "
                f"{list(set(e.provider for e in self.endpoints))} | Strategy: {self.strategy}"
            )

    def select_endpoint(
        self,
        strategy: Optional[str] = None,
        preferred_provider: Optional[str] = None,
        requested_model: Optional[str] = None,
    ) -> AIEndpoint:
        """Selects the optimal AIEndpoint based on the load balancing strategy."""
        with self._lock:
            if not self.endpoints:
                raise RuntimeError("No AI endpoints configured! Please set GROQ_API_KEY, NVIDIA_API_KEY, OPENROUTER_API_KEY, or LOCAL_LLM_URL in .env")

            # Filter candidates (exclude cooling down endpoints unless ALL are cooling down)
            strat = strategy or self.strategy
            available = [e for e in self.endpoints if not e.is_cooling_down]

            if preferred_provider:
                pref_matches = [e for e in available if e.provider == preferred_provider]
                if pref_matches:
                    available = pref_matches

            if not available:
                logger.warning("All AI endpoints are currently in rate-limit cooldown! Selecting soonest available endpoint.")
                available = sorted(self.endpoints, key=lambda e: e.cooldown_until)

            # Routing Algorithms
            if strat == "least_busy":
                # Select endpoint with minimum active in-flight requests
                selected = min(available, key=lambda e: (e.active_requests, e.avg_latency))
            elif strat == "round_robin":
                self._rr_index = (self._rr_index + 1) % len(available)
                selected = available[self._rr_index]
            elif strat == "latency_based":
                selected = min(available, key=lambda e: e.avg_latency)
            elif strat == "priority_fallback":
                selected = max(available, key=lambda e: e.weight)
            else:
                selected = random.choice(available)

            return selected

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        strategy: Optional[str] = None,
        preferred_provider: Optional[str] = None,
        max_retries: int = 3,
    ) -> str:
        """Synchronous chat completion with automatic failover and rate-limit handling."""
        last_exception = None

        for attempt in range(max_retries):
            endpoint = self.select_endpoint(strategy=strategy, preferred_provider=preferred_provider)
            target_model = model or endpoint.model

            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {endpoint.api_key}",
                **endpoint.extra_headers,
            }

            payload = {
                "model": target_model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }

            url = f"{endpoint.base_url}/chat/completions"
            endpoint.record_request_start()
            start_t = time.time()

            try:
                resp = requests.post(url, headers=headers, json=payload, timeout=60)
                dur = time.time() - start_t

                if resp.status_code == 200:
                    data = resp.json()
                    content = data["choices"][0]["message"]["content"]
                    endpoint.record_request_end(duration_sec=dur, success=True)
                    return content
                elif resp.status_code == 429:
                    endpoint.record_request_end(duration_sec=dur, success=False)
                    endpoint.trigger_cooldown(seconds=60, reason="HTTP 429 Rate Limit Exceeded")
                    logger.warning(f"Retrying request on another key (attempt {attempt+1}/{max_retries})...")
                    continue
                else:
                    endpoint.record_request_end(duration_sec=dur, success=False)
                    if resp.status_code >= 500:
                        endpoint.trigger_cooldown(seconds=30, reason=f"HTTP {resp.status_code} Server Error")
                    logger.warning(f"Endpoint {endpoint.id} returned status {resp.status_code}: {resp.text[:200]}")
                    last_exception = RuntimeError(f"HTTP {resp.status_code}: {resp.text}")

            except Exception as e:
                dur = time.time() - start_t
                endpoint.record_request_end(duration_sec=dur, success=False)
                logger.warning(f"Request error on endpoint {endpoint.id}: {e}")
                endpoint.trigger_cooldown(seconds=30, reason=str(e))
                last_exception = e

        raise RuntimeError(f"All AI Load Balancer attempts failed after {max_retries} retries. Last error: {last_exception}")

    async def achat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        strategy: Optional[str] = None,
        preferred_provider: Optional[str] = None,
        max_retries: int = 3,
    ) -> str:
        """Asynchronous non-blocking wrapper for chat completions."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.chat_completion(
                messages=messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                strategy=strategy,
                preferred_provider=preferred_provider,
                max_retries=max_retries,
            ),
        )

    def get_status(self) -> Dict[str, Any]:
        """Returns live load balancer health metrics and concurrency telemetry."""
        with self._lock:
            return {
                "total_endpoints": len(self.endpoints),
                "strategy": self.strategy,
                "endpoints": [
                    {
                        "id": e.id,
                        "provider": e.provider,
                        "model": e.model,
                        "active_requests": e.active_requests,
                        "total_requests": e.total_requests,
                        "failed_requests": e.failed_requests,
                        "cooldown": e.is_cooling_down,
                        "avg_latency_ms": round(e.avg_latency * 1000, 1),
                    }
                    for e in self.endpoints
                ],
            }


# Singleton Global Load Balancer Instance
_global_balancer: Optional[AILoadBalancer] = None

def get_global_balancer() -> AILoadBalancer:
    global _global_balancer
    if _global_balancer is None:
        _global_balancer = AILoadBalancer()
    return _global_balancer


# LiveKit Adapter Integration (if livekit is installed)
if LIVEKIT_AVAILABLE:
    class LoadBalancedLLM(llm.LLM):
        """
        LiveKit LLM Adapter that delegates voice conversation requests to the
        least-busy AI endpoint managed by AILoadBalancer.
        """

        def __init__(self, balancer: Optional[AILoadBalancer] = None):
            super().__init__()
            self.balancer = balancer or get_global_balancer()

        def chat(
            self,
            *,
            chat_ctx: llm.ChatContext,
            tools: Optional[List[Any]] = None,
            conn_options: Optional[Any] = None,
            **kwargs,
        ) -> llm.LLMStream:
            # Pick least-busy endpoint
            endpoint = self.balancer.select_endpoint(strategy="least_busy")
            lk_llm = endpoint.get_livekit_llm()

            # Record concurrency
            endpoint.record_request_start()
            start_time = time.time()

            import inspect

            def _build_kwargs(target_llm):
                sig = inspect.signature(target_llm.chat)
                call_kwargs = {}
                if "chat_ctx" in sig.parameters:
                    call_kwargs["chat_ctx"] = chat_ctx
                if tools is not None and "tools" in sig.parameters:
                    call_kwargs["tools"] = tools
                if conn_options is not None and "conn_options" in sig.parameters:
                    call_kwargs["conn_options"] = conn_options
                for k, v in kwargs.items():
                    if k in sig.parameters:
                        call_kwargs[k] = v
                return call_kwargs

            try:
                stream = lk_llm.chat(**_build_kwargs(lk_llm))
            except Exception as e:
                endpoint.record_request_end(duration_sec=time.time() - start_time, success=False)
                if "429" in str(e) or "rate" in str(e).lower():
                    endpoint.trigger_cooldown(60, "LiveKit LLM 429 Rate Limit")
                # Fallback to secondary endpoint
                fb_endpoint = self.balancer.select_endpoint(strategy="least_busy")
                fb_llm = fb_endpoint.get_livekit_llm()
                fb_endpoint.record_request_start()
                stream = fb_llm.chat(**_build_kwargs(fb_llm))
                endpoint = fb_endpoint

            # Decorate the stream object to track completion
            original_aclose = getattr(stream, "aclose", None)

            async def _tracked_aclose(*args, **kwargs_inner):
                endpoint.record_request_end(duration_sec=time.time() - start_time, success=True)
                if original_aclose:
                    await original_aclose(*args, **kwargs_inner)

            stream.aclose = _tracked_aclose
            return stream

else:
    class LoadBalancedLLM:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("LiveKit is not installed in this environment.")
