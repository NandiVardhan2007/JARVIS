"""
Central VISION Autonomous Engine orchestrating perception, cognition, tools, memory (Working + MAG + CAG), and TTS synthesis.
"""

import asyncio
import json
import re
import time
from datetime import datetime
from typing import Optional, Dict, Any
from vision.constants import DEFAULT_SYSTEM_PROMPT, VisionEvents
from vision.core.event_bus import event_bus
from vision.core.session import session_manager, Session
from vision.cognitive.load_balancer import load_balancer
from vision.cognitive.router import router
from vision.tools.registry import tool_registry
from vision.memory.working_memory import working_memory
from vision.memory.mag_engine import mag_engine
from vision.memory.cag_engine import cag_engine
from vision.synthesis.cartesia_tts import CartesiaTTS
from vision.synthesis.player import audio_player
from vision.config import config
from vision.logger import logger


from vision.core.reminder_daemon import reminder_manager


def clean_text_for_speech(text: str) -> str:
    """Normalize and clean LLM response text for natural, fluid spoken voice playback."""
    if not text:
        return ""
    t = text.strip()

    # If model returned raw JSON tool call payload
    if t.startswith("{") and ("\"name\"" in t or "'name'" in t or "\"action\"" in t):
        return "Action completed successfully, Nandu!"

    # Remove thinking tags if model outputs <think>...</think>
    t = re.sub(r'<think>.*?</think>', '', t, flags=re.DOTALL)

    # Remove markdown code blocks ```...```
    t = re.sub(r'```[\s\S]*?```', '', t)

    # Remove inline code `...`
    t = re.sub(r'`([^`]+)`', r'\1', t)

    # Remove markdown links [text](url) -> text
    t = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', t)

    # Remove raw URLs
    t = re.sub(r'https?://\S+', '', t)

    # Remove markdown headers #, ##, ###
    t = re.sub(r'^\s*#+\s*', '', t, flags=re.MULTILINE)

    # Remove bold / italic markers **text**, *text*, _text_
    t = re.sub(r'\*\*([^*]+)\*\*', r'\1', t)
    t = re.sub(r'\*([^*]+)\*', r'\1', t)
    t = re.sub(r'__([^_]+)__', r'\1', t)
    t = re.sub(r'_([^_]+)_', r'\1', t)

    # Convert markdown bullet points or numbered lists into natural spoken pauses
    t = re.sub(r'^\s*[\*\-\+•]\s*', '', t, flags=re.MULTILINE)
    t = re.sub(r'^\s*\d+\.\s*', '', t, flags=re.MULTILINE)

    # Normalize smart quotes, dashes, and special typography
    t = t.replace('\u2011', '-').replace('\u2013', '-').replace('\u2014', ' - ')
    t = t.replace('\u2018', "'").replace('\u2019', "'")
    t = t.replace('\u201c', '"').replace('\u201d', '"')

    # Strip emoji and special decorative unicode symbols for clean voice synthesis
    t = re.sub(r'[\U00010000-\U0010ffff]', '', t)
    t = re.sub(r'[\u2600-\u27bf\u2300-\u23ff]', '', t)

    # Normalize multiple whitespace / line breaks
    t = re.sub(r'\n+', ' ', t)
    t = re.sub(r'\s{2,}', ' ', t)

    return t.strip()


class VisionEngine:
    def __init__(self):
        self.tts = CartesiaTTS() if config.CARTESIA_API_KEY else None
        self.is_running = False

    async def initialize(self):
        """Initialize engine components and background listeners."""
        self.is_running = True
        logger.info("[VisionEngine] Initialized successfully with MAG + CAG memory subsystems.")
        
        # Launch Autonomous Spoken Reminder Daemon
        async def _reminder_speaker(alert_text: str):
            logger.info(f"[VisionEngine] 🗣️ Speaking proactive reminder: '{alert_text}'")
            if self.tts:
                try:
                    audio_bytes = await self.tts.synthesize(alert_text)
                    audio_player.play_wav_bytes(audio_bytes)
                except Exception as e:
                    logger.error(f"[VisionEngine] Reminder voice synthesis error: {e}")

        asyncio.create_task(reminder_manager.start_daemon(speech_callback=_reminder_speaker))
        
        # Launch Autonomous Academic Timetable Watchdog Daemon
        from vision.tools.academic_tools import start_academic_daemon
        asyncio.create_task(start_academic_daemon(speech_callback=_reminder_speaker))
        
        await event_bus.publish(VisionEvents.SYSTEM_STARTED)

    async def process_user_input(
        self,
        user_text: str,
        session_id: str = "default_session",
        channel: str = "web",
        synthesize_voice: bool = True
    ) -> Dict[str, Any]:
        """Core multi-turn conversational loop with CAG caching, MAG memory, and dynamic tool calling."""
        start_time = time.time()
        session: Session = session_manager.get_or_create(session_id=session_id, channel=channel)
        
        # 1. Record user message
        session.add_message(role="user", content=user_text)
        await event_bus.publish(VisionEvents.USER_QUERY_RECEIVED, {"text": user_text, "session_id": session_id})

        # 2. Check CAG (Cache-Augmented Generation) Cache
        cached_result = cag_engine.lookup(user_text)
        if cached_result:
            final_text = cached_result["response"]
            elapsed_ms = round((time.time() - start_time) * 1000, 1)
            logger.info(f"[VisionEngine] CAG Cache HIT -> returning in {elapsed_ms}ms (Age: {cached_result['age_seconds']}s)")
            
            session.add_message(role="assistant", content=final_text)
            await event_bus.publish(VisionEvents.LLM_RESPONSE_DONE, {"text": final_text, "session_id": session_id, "cached": True})

            if synthesize_voice and final_text and self.tts:
                try:
                    audio_bytes = await self.tts.synthesize(final_text)
                    audio_player.play_wav_bytes(audio_bytes)
                except Exception as e:
                    logger.error(f"[VisionEngine] Voice synthesis failed: {e}")

            return {
                "session_id": session_id,
                "response": final_text,
                "provider": "CAG-Cache (Ultra-Low Latency)",
                "latency_ms": elapsed_ms,
                "cached": True
            }

        # 3. Dynamic temporal, MAG Long-term Memory & Working Memory injection
        live_now = datetime.now().strftime("%A, %B %d, %Y - %I:%M:%S %p")
        system_content = (
            DEFAULT_SYSTEM_PROMPT
            + f"\n[CURRENT LIVE SYSTEM TIME: {live_now}]\n"
            + mag_engine.get_mag_prompt_injection(user_text)
            + working_memory.get_context_injection_prompt()
        )
        llm_messages = [{"role": "system", "content": system_content}] + session.get_messages_for_llm(max_history=15)

        # 4. Dynamic Tool Routing
        all_tool_schemas = tool_registry.get_all_schemas()
        relevant_tools = router.route_tools(user_text, all_tool_schemas)

        # 5. LLM Load Balancer Call
        response = await load_balancer.chat_completion(
            messages=llm_messages,
            tools=relevant_tools if relevant_tools else None,
            temperature=0.6,
            max_tokens=1024
        )

        # 6. Handle Function/Tool Calls
        tool_calls = response.get("tool_calls")
        has_executed_tools = False
        if tool_calls:
            has_executed_tools = True
            session.add_message(
                role="assistant",
                content=response.get("content"),
                tool_calls=tool_calls
            )

            for tc in tool_calls:
                func_name = tc.get("function", {}).get("name")
                raw_args = tc.get("function", {}).get("arguments", {})
                
                args = {}
                if isinstance(raw_args, str):
                    try:
                        args = json.loads(raw_args) if raw_args.strip() else {}
                    except Exception:
                        args = {}
                elif isinstance(raw_args, dict):
                    args = raw_args

                await event_bus.publish(VisionEvents.TOOL_CALL_DETECTED, {"tool": func_name, "args": args})
                tool_result = await tool_registry.execute(func_name, args)
                await event_bus.publish(VisionEvents.TOOL_EXECUTION_COMPLETED, {"tool": func_name, "result": tool_result})

                # Log episodic timeline event
                mag_engine.record_event(
                    event_type="tool_execution",
                    description=f"Executed {func_name}",
                    metadata=json.dumps({"args": args, "status": "success"})
                )

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
                temperature=0.6,
                max_tokens=800
            )

        final_text = response.get("content", "")
        session.add_message(role="assistant", content=final_text)
        await event_bus.publish(VisionEvents.LLM_RESPONSE_DONE, {"text": final_text, "session_id": session_id})

        # 7. Store in CAG Cache if not a dynamic tool execution
        if not has_executed_tools and not cag_engine.should_bypass(user_text):
            cag_engine.put(user_text, final_text, category="qa_general", ttl_seconds=3600)

        # 8. Autonomous Fact & Habit Extraction
        try:
            mag_engine.auto_extract_facts(user_text, final_text)
        except Exception as e:
            logger.debug(f"[VisionEngine] Auto fact extraction skipped: {e}")


        # 9. Speech Synthesis Playback (Synthesize clean, complete spoken text)
        if synthesize_voice and final_text and self.tts:
            spoken_text = clean_text_for_speech(final_text)
            if spoken_text:
                try:
                    audio_bytes = await self.tts.synthesize(spoken_text)
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
