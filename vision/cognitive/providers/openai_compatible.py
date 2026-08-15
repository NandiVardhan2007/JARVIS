"""
Generic OpenAI-Compatible Provider for NVIDIA NIM, OpenRouter, and custom endpoints.
"""

from typing import List, Dict, Any, AsyncGenerator, Optional
import time
from vision.cognitive.providers.base import BaseLLMProvider
from vision.logger import logger

try:
    from openai import AsyncOpenAI
except ImportError:
    AsyncOpenAI = None


def _sanitize_messages_for_nim(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    NVIDIA NIM strictness fix: Ensures that assistant tool_calls don't contain multiple
    tool calls per turn, which causes NIM 500 error 'only supports single tool-calls at once'.
    """
    sanitized = []
    for msg in messages:
        m = dict(msg)
        if m.get("role") == "assistant" and m.get("tool_calls"):
            tcs = m["tool_calls"]
            if isinstance(tcs, list) and len(tcs) > 1:
                # Keep only the first tool call for strict providers
                m["tool_calls"] = [tcs[0]]
        sanitized.append(m)
    return sanitized


class OpenAICompatibleProvider(BaseLLMProvider):
    def __init__(
        self,
        name: str,
        api_key: str,
        base_url: str,
        model: str,
        default_headers: Optional[Dict[str, str]] = None
    ):
        super().__init__(name=name, model=model)
        self.api_key = api_key
        self.base_url = base_url
        self.client = AsyncOpenAI(
            api_key=api_key or "not-needed",
            base_url=base_url,
            default_headers=default_headers
        ) if AsyncOpenAI else None

    async def chat_completion(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> Dict[str, Any]:
        if not self.client:
            raise RuntimeError("openai package is not installed.")

        self.active_requests += 1
        start_time = time.time()
        try:
            clean_messages = _sanitize_messages_for_nim(messages)
            kwargs: Dict[str, Any] = {
                "model": self.model,
                "messages": clean_messages,
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
            elif message_obj.content and "{" in message_obj.content and ("\"name\"" in message_obj.content or "'name'" in message_obj.content):
                # Fallback: Extract JSON tool call generated in text content
                raw_c = message_obj.content.strip()
                try:
                    import re, uuid, ast
                    # Strip markdown blocks
                    clean_c = re.sub(r"^```(?:json)?", "", raw_c).strip()
                    clean_c = re.sub(r"```$", "", clean_c).strip()
                    first_brace = clean_c.find("{")
                    last_brace = clean_c.rfind("}")
                    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
                        candidate = clean_c[first_brace:last_brace+1]
                        parsed = None
                        try:
                            parsed = json.loads(candidate)
                        except Exception:
                            try:
                                parsed = ast.literal_eval(candidate)
                            except Exception:
                                pass

                        if isinstance(parsed, dict) and "name" in parsed:
                            fn_name = parsed["name"]
                            fn_args = parsed.get("parameters") or parsed.get("arguments") or {}
                            tool_calls = [{
                                "id": f"call_{uuid.uuid4().hex[:8]}",
                                "type": "function",
                                "function": {
                                    "name": fn_name,
                                    "arguments": json.dumps(fn_args) if isinstance(fn_args, dict) else str(fn_args)
                                }
                            }]
                            message_obj.content = None

                    if not tool_calls and "type_text_into_application" in raw_c:
                        # Fallback for unclosed/truncated typing calls
                        t_match = re.search(r'"text":\s*"([\s\S]+)', raw_c)
                        if t_match:
                            extracted_text = t_match.group(1).replace("\\n", "\n").replace('\\"', '"').rstrip('"} \n\r')
                            tool_calls = [{
                                "id": f"call_{uuid.uuid4().hex[:8]}",
                                "type": "function",
                                "function": {
                                    "name": "type_text_into_application",
                                    "arguments": json.dumps({"text": extracted_text, "target_app": "Notepad"})
                                }
                            }]
                            message_obj.content = None
                except Exception:
                    pass

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
            logger.debug(f"[{self.name}] Provider note: {e}")
            raise e
        finally:
            self.active_requests -= 1

    async def stream_chat_completion(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> AsyncGenerator[str, None]:
        if not self.client:
            raise RuntimeError("openai package is not installed.")

        self.active_requests += 1
        try:
            clean_messages = _sanitize_messages_for_nim(messages)
            kwargs: Dict[str, Any] = {
                "model": self.model,
                "messages": clean_messages,
                "temperature": temperature,
                "stream": True
            }
            if max_tokens:
                kwargs["max_tokens"] = max_tokens
            if tools:
                kwargs["tools"] = tools

            stream = await self.client.chat.completions.create(**kwargs)
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            self.failed_requests += 1
            logger.debug(f"[{self.name}] Stream note: {e}")
            raise e
        finally:
            self.active_requests -= 1
