"""
Test suite for EventBus, SessionManager, and Engine components.
"""

import pytest
import asyncio
from vision.core.event_bus import EventBus
from vision.core.session import SessionManager
from vision.cognitive.router import IntentRouter


@pytest.mark.asyncio
async def test_event_bus_pub_sub():
    bus = EventBus()
    received = []

    async def listener(data):
        received.append(data)

    bus.subscribe("test.topic", listener)
    await bus.publish("test.topic", {"msg": "hello"})

    assert len(received) == 1
    assert received[0]["msg"] == "hello"


def test_session_manager():
    sm = SessionManager()
    session = sm.get_or_create(session_id="test_sess", channel="cli")
    session.add_message(role="user", content="List my files")
    session.add_message(role="assistant", content="Here are your files...")

    msgs = session.get_messages_for_llm()
    assert len(msgs) == 2
    assert msgs[0]["content"] == "List my files"


def test_intent_router_file_keywords():
    router = IntentRouter()
    tools = [
        {"type": "function", "function": {"name": "list_files", "description": "List directory contents"}},
        {"type": "function", "function": {"name": "play_media", "description": "Play youtube video"}},
        {"type": "function", "function": {"name": "send_email", "description": "Send email message"}},
    ]
    routed = router.route_tools("Please organize my documents folder and rename files", tools)
    routed_names = [t["function"]["name"] for t in routed]
    assert "list_files" in routed_names


def test_clean_text_for_speech_tables():
    from vision.core.engine import clean_text_for_speech
    raw_markdown = (
        "Sure thing, bro! Here is the info on your sister, Nandini:\n\n"
        "| Detail | Info |\n"
        "|---|---|\n"
        "| **Name** | Nandini Kovvuri |\n"
        "| **Birthday** | 4 December 2002 |\n"
        "| **Phone** | **910\u202f021\u202f9275** |\n\n"
        "Anything else you need, Nandu? ........"
    )
    cleaned = clean_text_for_speech(raw_markdown)
    assert "|" not in cleaned
    assert "vertical bar" not in cleaned.lower()
    assert "Name: Nandini Kovvuri" in cleaned
    assert "Birthday: 4 December 2002" in cleaned
    assert "9100219275" in cleaned
    assert "........" not in cleaned
