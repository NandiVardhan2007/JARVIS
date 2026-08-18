"""
Memory management and user recall tools for VISION AI.
Allows the user to explicitly store, recall, search, delete, and synchronize personal memories,
habits, procedural rules, episodic event logs, and the Entity Knowledge Graph.
"""

from typing import Optional
from pathlib import Path
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
    memories = mag_engine.list_all(limit=50)
    if not memories:
        return "No long-term memories currently stored."

    lines = [f"Active Long-Term Memories ({len(memories)} items):"]
    for m in memories:
        lines.append(f"- #{m['id']} [{m['category'].upper()}]: {m['content']}")
    return "\n".join(lines)


@tool(name="query_knowledge_graph", description="Perform multi-hop traversal on the Knowledge Graph starting from an entity (e.g. 'Nandini', 'Hyderabad Server', 'Aditya College').")
def query_knowledge_graph(entity_name: str, depth: int = 2) -> str:
    """Traverse knowledge graph relations connected to an entity."""
    relations = mag_engine.traverse_entity_graph(entity_name, depth=depth)
    if not relations:
        return f"No knowledge graph relations found for entity '{entity_name}'."

    lines = [f"Knowledge Graph Relations for '{entity_name}' (Depth {depth}):"]
    for r in relations:
        desc = f" — {r['description']}" if r.get('description') else ""
        lines.append(f"- ({r['source_name']}) --[{r['relation_type']}]--> ({r['target_name']}){desc}")
    return "\n".join(lines)


@tool(name="add_entity_relation", description="Add an entity-to-entity relationship edge to the Knowledge Graph (e.g. source='Nandini', relation='owns_device', target='MacBook').")
def add_entity_relation(source: str, relation: str, target: str, description: str = "") -> str:
    """Add a relation edge to the Knowledge Graph."""
    rel_id = mag_engine.add_relation(source, relation, target, description)
    if rel_id <= 0:
        return "Error: Source and target entity names are required."
    return f"Added knowledge graph relation #{rel_id}: ({source}) -[{relation}]-> ({target})."


@tool(name="learn_user_rule", description="Save a procedural rule, habit, or instruction (e.g. trigger='youtube,media', rule='Always use Comet browser').")
def learn_user_rule(trigger_context: str, rule: str) -> str:
    """Record a procedural habit or rule into MAG memory."""
    rule_id = mag_engine.record_procedural_rule(trigger_context, rule)
    if rule_id <= 0:
        return "Error: Could not record rule. Please provide valid trigger and rule."
    return f"Recorded procedural habit #{rule_id}: When '{trigger_context}' -> '{rule}'."


@tool(name="list_procedural_rules", description="List all learned procedural habits, execution rules, and user preferences.")
def list_procedural_rules() -> str:
    """List procedural habits and rules."""
    rules = mag_engine.list_procedural_rules(limit=20)
    if not rules:
        return "No procedural rules currently recorded."

    lines = ["Learned Procedural Habits & Rules:"]
    for r in rules:
        lines.append(f"- #{r['id']} [When: {r['trigger_context']}]: {r['rule_action']}")
    return "\n".join(lines)


@tool(name="search_past_events", description="Search past episodic timeline events, tool executions, and system actions by keyword.")
def search_past_events(query: str) -> str:
    """Search episodic timeline."""
    events = mag_engine.search_episodic_events(query, limit=10)
    if not events:
        return f"No recent timeline events found matching '{query}'."

    lines = [f"Episodic Timeline Events for '{query}':"]
    for e in events:
        lines.append(f"- [{e['created_at']}] ({e['event_type']}) {e['description']}")
    return "\n".join(lines)


@tool(name="sync_memories_file", description="Synchronize edited memories from MEMORIES.md back into the SQLite database.")
def sync_memories_file(file_path: Optional[str] = None) -> str:
    """Sync edits made in MEMORIES.md back to SQLite."""
    target = Path(file_path) if file_path else None
    res = mag_engine.import_from_markdown(target)
    if "error" in res:
        return f"Sync failed: {res['error']}"
    return f"Memory Sync Complete: {res.get('updated', 0)} memories updated, {res.get('added', 0)} new memories added."


@tool(name="export_memories_file", description="Export all active long-term memories from SQLite into MEMORIES.md.")
def export_memories_file(file_path: Optional[str] = None) -> str:
    """Export SQLite memories to MEMORIES.md."""
    target = Path(file_path) if file_path else None
    return mag_engine.export_to_markdown(target)
