import pytest
import asyncio
from unittest.mock import MagicMock, patch
import sys

@pytest.fixture
def mock_dependencies():
    mocks = {
        'piper': MagicMock(),
        'piper.PiperVoice': MagicMock(),
        'piper_tts_plugin': MagicMock(),
        'Tools': MagicMock(),
        'Tools.get_all_tools': MagicMock(),
        'Tools.classify_intent': MagicMock(),
        'Tools.get_tools_for_category': MagicMock(),
        'pygetwindow': MagicMock(),
        'Tools.user_memory': MagicMock()
    }
    with patch.dict('sys.modules', mocks):
        yield mocks

@pytest.mark.asyncio
async def test_jarvis_agent_llm_node_safe_stream_exception(mock_dependencies):
    from agent import JarvisAgent
    from livekit.agents.llm import ChatContext

    agent = JarvisAgent(
        instructions="Test prompt",
        stt=MagicMock(),
        llm=MagicMock(),
        tts=MagicMock(),
        vad=MagicMock(),
        tools=[],
    )

    chat_ctx = ChatContext()
    chat_ctx._items.append(MagicMock(role="user", content="Hello"))

    tools = []
    model_settings = {}

    async def mock_stream():
        yield "first chunk"
        raise Exception("Simulated stream error")

    with patch('livekit.agents.Agent.llm_node', return_value=mock_stream()):
        with patch('livekit.agents.llm.ChatMessage') as mock_chat_message, \
             patch('livekit.agents.llm.ChatChunk') as mock_chat_chunk, \
             patch('livekit.agents.llm.ChoiceDelta') as mock_choice_delta:

            mock_fallback_chunk = MagicMock()
            mock_chat_chunk.return_value = mock_fallback_chunk

            stream = agent.llm_node(chat_ctx, tools, model_settings)

            chunks = []
            try:
                async for chunk in stream:
                    chunks.append(chunk)
            except Exception:
                pytest.fail("stream should not raise exception")

            assert chunks[0] == "first chunk"
            assert chunks[1] == mock_fallback_chunk

            # Verify that ChatMessage was called to create the fallback system message
            mock_chat_message.assert_called_once()
            args, kwargs = mock_chat_message.call_args
            assert kwargs.get("role") == "system"
            assert "Simulated stream error" in kwargs.get("content")

            # Verify that ChatChunk was yielded
            mock_chat_chunk.assert_called_once()
