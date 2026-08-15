"""
Working Memory for holding active conversational context and retrieved facts.
"""

from typing import List, Dict, Any
from vision.memory.database import db


class WorkingMemory:
    def __init__(self, max_context_items: int = 10):
        self.max_context_items = max_context_items
        self.active_context: List[str] = []

    def add_context(self, item: str):
        self.active_context.append(item)
        if len(self.active_context) > self.max_context_items:
            self.active_context.pop(0)

    def get_context_injection_prompt(self) -> str:
        memories = db.get_all_memories()
        if not memories and not self.active_context:
            return ""

        lines = ["\n[Context & User Knowledge]:"]
        for m in memories:
            lines.append(f"- {m['key']}: {m['value']}")
        for ctx in self.active_context:
            lines.append(f"- Recent fact: {ctx}")
        return "\n".join(lines)


working_memory = WorkingMemory()
