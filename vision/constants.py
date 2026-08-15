"""
Constants, event names, and default system prompts for the VISION framework.
"""

# ── Event Bus Topics ─────────────────────────────────────────
class VisionEvents:
    # Audio / STT events
    AUDIO_STREAM_STARTED = "audio.stream.started"
    AUDIO_CHUNK_RECORDED = "audio.chunk.recorded"
    VAD_SPEECH_START = "audio.vad.speech_start"
    VAD_SPEECH_STOP = "audio.vad.speech_stop"
    STT_TRANSCRIPTION_READY = "audio.stt.ready"
    
    # Cognitive / Reasoning events
    USER_QUERY_RECEIVED = "cognition.query.received"
    INTENT_CLASSIFIED = "cognition.intent.classified"
    LLM_STREAM_CHUNK = "cognition.llm.chunk"
    LLM_RESPONSE_DONE = "cognition.llm.done"
    TOOL_CALL_DETECTED = "cognition.tool.call"
    TOOL_EXECUTION_COMPLETED = "cognition.tool.done"
    
    # Output / TTS events
    TTS_REQUESTED = "synthesis.tts.requested"
    TTS_STREAM_CHUNK = "synthesis.tts.chunk"
    TTS_PLAYBACK_STARTED = "synthesis.playback.start"
    TTS_PLAYBACK_FINISHED = "synthesis.playback.done"
    
    # Vision & Ingress events
    FRAME_CAPTURED = "perception.frame.captured"
    SCREEN_CAPTURED = "perception.screen.captured"
    GESTURE_DETECTED = "perception.gesture.detected"
    
    # Web & LiveKit Gateway events
    WEB_CLIENT_CONNECTED = "gateway.web.connected"
    WEB_CLIENT_DISCONNECTED = "gateway.web.disconnected"
    LIVEKIT_CONNECTED = "gateway.livekit.connected"
    
    # System events
    SYSTEM_STARTED = "system.started"
    SYSTEM_SHUTDOWN = "system.shutdown"
    SYSTEM_ERROR = "system.error"


# ── System Persona Prompts ───────────────────────────────────
DEFAULT_SYSTEM_PROMPT = """You are VISION, a hyper-intelligent, proactive, and witty multimodal AI assistant.
You possess deep system automation capabilities, real-time audio/visual perception, and execute tools autonomously to fulfill user requests.

Key Guidelines:
1. Be concise, direct, and conversational. Speak naturally as a voice assistant unless detailed formatting is explicitly requested.
2. Proactively use available tools (OS commands, ADB mobile control, email, browser, desktop controls) to perform actions.
3. If an action has been executed via a tool, summarize the result succinctly without echoing raw JSON payloads unless requested.
4. Maintain a sharp, capable, and loyal persona.
"""

DEFAULT_SUBAGENT_SYSTEM_PROMPT = """You are an autonomous sub-agent within the VISION system.
Your mission is to perform your specialized workflow with high precision and return structured results to the orchestrator.
"""
