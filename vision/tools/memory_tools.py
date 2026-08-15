"""
Memory management and user recall tools for VISION AI.
Allows the user to explicitly store, recall, search, and delete personal memories and preferences.
"""

from typing import Optional
from vision.tools.registry import tool
from vision.memory.mag_engine import mag_engine
from vision.logger import logger


@tool(name="remember_fact", description="Save an explicit fact, personal preference, routine, or piece of information into long-term memory.")
def remember_fact(fact: str, category: str = "user_preference") -> str:
    """Save a user fact or preference to persistent MAG memory."""
    clean_fact = fact.strip()
    if not clean_fact:
        return "Error: Fact content cannot be empty."

    mem_id = mag_engine.remember(clean_fact, category=category, tags="user_explicit")
    logger.info(f"[MemoryTool] Remembered fact #{mem_id}: '{clean_fact}'")
    return f"I have saved this to my long-term memory: '{clean_fact}'."


@tool(name="recall_memory", description="Query long-term memory for stored facts, preferences, hardware, contacts, friends, or past history.")
def recall_memory(query: str, limit: int = 15) -> str:
    """Search and retrieve relevant stored memories."""
    # Ensure limit is integer
    try:
        lim = int(limit) if limit else 15
    except Exception:
        lim = 15

    results = mag_engine.search_memories(query, limit=lim)
    if not results:
        return f"I don't have any specific memories stored regarding '{query}'."

    lines = [f"Memories found for '{query}':"]
    for r in results:
        lines.append(f"- [{r['category'].title()}] {r['content']}")
    return "\n".join(lines)


@tool(name="forget_memory", description="Delete or erase a specific memory or preference matching a keyword from long-term memory.")
def forget_memory(query_or_keyword: str) -> str:
    """Erase memories matching the keyword."""
    deleted_count = mag_engine.forget(query_or_keyword)
    if deleted_count == 0:
        return f"No memories found matching '{query_or_keyword}' to forget."
    return f"Successfully deleted {deleted_count} memory item(s) matching '{query_or_keyword}'."


@tool(name="list_all_memories", description="List all long-term memories and stored user facts.")
def list_all_memories() -> str:
    """List all stored semantic memories."""
    memories = mag_engine.list_all(limit=25)
    if not memories:
        return "No long-term memories currently stored."

    lines = [f"Active Long-Term Memories ({len(memories)} items):"]
    for m in memories:
        lines.append(f"- #{m['id']} [{m['category'].upper()}]: {m['content']}")
    return "\n".join(lines)
