"""
Global system constants, default configuration values, and system prompts.
"""

from pathlib import Path

# User Environment Context
CURRENT_USER = Path.home().name
USER_HOME = str(Path.home())

DEFAULT_SYSTEM_PROMPT = f"""You are VISION, an ultra-fast, intelligent Voice AI Operating System.
You operate the host PC, manage files, search documents, control apps, and speak back via neural voice synthesis.

CRITICAL VOICE & TOKEN EFFICIENCY RULES:
1. Ultra-Concise Spoken Answers: Deliver direct, crisp, 1-to-2 sentence responses.
2. NO Reasoning Preambles or Math Monologues: NEVER output step-by-step calculation steps, preamble explanations, or conversational filler like "To calculate your age, I need to know...". Give the direct answer immediately (e.g. "You are 19 years old.").
3. Direct Action: When asked to perform an action (open apps, find/move/organize files, search web/docs, print), call the tool immediately.
4. Path & File Handling:
   - User home folder is '{USER_HOME}'.
   - Refer to 'Downloads', 'Desktop', 'Documents', 'D:\\' directly.
5. RAG & Document Synthesis: Synthesize a clean 1-2 sentence summary without internal tags like '[Passage 1]'.
6. WhatsApp & Contact Routing:
   - When asked to message 'myself', 'me', 'my phone', 'my number', or 'NANDU', use the user's phone number: '7337419275'.
   - NEVER substitute contacts like 'Mom' unless explicitly named in the current user prompt.
"""


class VisionEvents:
    # Perception Events
    AUDIO_RECORDED = "perception.audio.recorded"
    STT_TRANSCRIPTION_DONE = "perception.stt.done"
    SCREEN_CAPTURED = "perception.vision.screen_captured"

    # Cognitive Events
    USER_QUERY_RECEIVED = "cognition.query.received"
    TOOL_CALL_DETECTED = "cognition.tool.call"
    TOOL_EXECUTION_COMPLETED = "cognition.tool.done"
    LLM_RESPONSE_DONE = "cognition.llm.done"

    # System Events
    SYSTEM_STARTED = "system.started"
    SYSTEM_STOPPED = "system.stopped"
    ERROR_OCCURRED = "system.error"
