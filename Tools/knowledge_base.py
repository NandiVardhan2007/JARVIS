"""
Note-saving tool for JARVIS.

IMPORTANT: this used to maintain its OWN separate ChromaDB collection
("jarvis_notes" at jarvis_memory/knowledge_base), while the actually-exposed
search_knowledge_base tool queried a completely different collection
("jarvis_knowledge" at ~/Documents/JARVIS/chromadb, see Tools/knowledge_rag.py).
That meant anything saved via save_note was permanently unsearchable — two
disconnected silos with only one side wired up as a queryable tool.

save_note now delegates straight into knowledge_rag's add_document_to_knowledge,
so notes land in the one knowledge store that search_knowledge_base actually
queries.
"""

import logging
from livekit.agents import function_tool

logger = logging.getLogger(__name__)


@function_tool
async def save_note(title: str, content: str) -> str:
    """
    Saves a detailed note, article, or document into the personal knowledge
    base for later semantic retrieval via search_knowledge_base.

    Args:
        title: Short title for the note.
        content: The full text content to save and index.
    """
    from Tools.knowledge_rag import add_document_to_knowledge
    result = await add_document_to_knowledge(title, content)
    return result.replace("Indexed", "Note saved and indexed", 1) if result.startswith("Indexed") else result
