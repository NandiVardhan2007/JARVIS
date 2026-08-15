"""
Central VISION Autonomous Engine orchestrating perception, cognition, tools, memory, and TTS synthesis.
"""

import json
from typing import Optional, Dict, Any, AsyncGenerator
from vision.constants import DEFAULT_SYSTEM_PROMPT, VisionEvents
from vision.core.event_bus import event_bus
from vision.core.session import session_manager, Session
from vision.cognitive.load_balancer import load_balancer
from vision.cognitive.router import router
from vision.tools.registry import tool_registry
from vision.memory.working_memory import working_memory
from vision.synthesis.cartesia_tts import CartesiaTTS
from vision.synthesis.player import audio_player
from vision.config import config
from vision.logger import logger


class VisionEngine:
    def __init__(self):
        self.tts = CartesiaTTS() if config.CARTESIA_API_KEY else None
        self.is_running = False

    async def initialize(self):
        """Initialize engine components and background listeners."""
        self.is_running = True
        logger.info("[VisionEngine] Initialized successfully.")
        await event_bus.publish(VisionEvents.SYSTEM_STARTED)

    async def process_user_input(
        self,
        user_text: str,
        session_id: str = "default_session",
        channel: str = "web",
        synthesize_voice: bool = False
    ) -> Dict[str, Any]:
        """Core multi-turn conversational loop with dynamic function calling."""
        session: Session = session_manager.get_or_create(session_id=session_id, channel=channel)
        
        # 1. Record user message
        session.add_message(role="user", content=user_text)
        await event_bus.publish(VisionEvents.USER_QUERY_RECEIVED, {"text": user_text, "session_id": session_id})

        # 2. Prepare LLM messages with system prompt & memory injection
        system_content = DEFAULT_SYSTEM_PROMPT + working_memory.get_context_injection_prompt()
        llm_messages = [{"role": "system", "content": system_content}] + session.get_messages_for_llm(max_history=15)

        # 3. Dynamic Tool Routing
        all_tool_schemas = tool_registry.get_all_schemas()
        relevant_tools = router.route_tools(user_text, all_tool_schemas)

        # 4. LLM Load Balancer Call
        response = await load_balancer.chat_completion(
            messages=llm_messages,
            tools=relevant_tools if relevant_tools else None,
            temperature=0.7
        )

        # 5. Handle Function/Tool Calls
        tool_calls = response.get("tool_calls")
        if tool_calls:
            session.add_message(
                role="assistant",
                content=response.get("content"),
                tool_calls=tool_calls
            )

            for tc in tool_calls:
                func_name = tc.get("function", {}).get("name")
                raw_args = tc.get("function", {}).get("arguments", "{}")
                try:
                    args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                except Exception:
                    args = {}

                await event_bus.publish(VisionEvents.TOOL_CALL_DETECTED, {"tool": func_name, "args": args})
                tool_result = await tool_registry.execute(func_name, args)
                await event_bus.publish(VisionEvents.TOOL_EXECUTION_COMPLETED, {"tool": func_name, "result": tool_result})

                # Append tool response
                session.add_message(
                    role="tool",
                    name=func_name,
                    tool_call_id=tc.get("id"),
                    content=str(tool_result)
                )

            # Re-prompt LLM with tool execution result for final response
            updated_messages = [{"role": "system", "content": system_content}] + session.get_messages_for_llm(max_history=15)
            response = await load_balancer.chat_completion(
                messages=updated_messages,
                tools=None,
                temperature=0.7
            )

        final_text = response.get("content", "")
        session.add_message(role="assistant", content=final_text)
        await event_bus.publish(VisionEvents.LLM_RESPONSE_DONE, {"text": final_text, "session_id": session_id})

        # 6. Optional Speech Synthesis
        if synthesize_voice and final_text and self.tts:
            try:
                audio_bytes = await self.tts.synthesize(final_text)
                audio_player.play_wav_bytes(audio_bytes)
            except Exception as e:
                logger.error(f"[VisionEngine] Voice synthesis failed: {e}")

        return {
            "session_id": session_id,
            "response": final_text,
            "provider": response.get("provider"),
            "latency_ms": response.get("latency_ms")
        }


# Global Vision engine singleton
vision_engine = VisionEngine()
