"""
Session and state tracking for VISION user interactions across channels.
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
import time
import uuid


@dataclass
class Message:
    role: str
    content: Optional[str] = None
    name: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_call_id: Optional[str] = None
    timestamp: float = field(default_factory=time.time)


@dataclass
class Session:
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    channel: str = "web"
    user_id: str = "default_user"
    messages: List[Message] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    last_active_at: float = field(default_factory=time.time)

    def add_message(self, role: str, content: Optional[str] = None, **kwargs) -> Message:
        msg = Message(role=role, content=content, **kwargs)
        self.messages.append(msg)
        self.last_active_at = time.time()
        return msg

    def get_messages_for_llm(self, max_history: int = 20) -> List[Dict[str, Any]]:
        recent = self.messages[-max_history:]
        formatted = []
        for m in recent:
            item: Dict[str, Any] = {"role": m.role}
            if m.content is not None:
                item["content"] = m.content
            if m.name:
                item["name"] = m.name
            if m.tool_calls:
                item["tool_calls"] = m.tool_calls
            if m.tool_call_id:
                item["tool_call_id"] = m.tool_call_id
            formatted.append(item)
        return formatted

    def clear(self):
        self.messages.clear()
        self.last_active_at = time.time()


class SessionManager:
    def __init__(self):
        self._sessions: Dict[str, Session] = {}

    def get_or_create(self, session_id: Optional[str] = None, channel: str = "web", user_id: str = "default_user") -> Session:
        s_id = session_id or str(uuid.uuid4())
        if s_id not in self._sessions:
            self._sessions[s_id] = Session(session_id=s_id, channel=channel, user_id=user_id)
        return self._sessions[s_id]

    def get(self, session_id: str) -> Optional[Session]:
        return self._sessions.get(session_id)

    def delete(self, session_id: str):
        self._sessions.pop(session_id, None)


# Global session manager singleton
session_manager = SessionManager()
