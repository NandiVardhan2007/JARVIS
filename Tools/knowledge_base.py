"""Knowledge Base Tool for JARVIS using ChromaDB."""

import os
import logging
from livekit.agents import function_tool

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "jarvis_memory", "knowledge_base")

def _get_collection():
    try:
        import chromadb
        # Initialize persistent client
        client = chromadb.PersistentClient(path=DB_PATH)
        collection = client.get_or_create_collection(name="jarvis_notes")
        return collection
    except ImportError:
        logger.error("ChromaDB not installed.")
        return None
    except Exception as e:
        logger.error(f"ChromaDB initialization failed: {e}")
        return None

@function_tool
async def save_note(title: str, content: str) -> str:
    """
    Saves a detailed note, article, or document into the personal knowledge base.
    
    Args:
        title: Short title for the note.
        content: The full text content to save and index.
    """
    collection = _get_collection()
    if collection is None:
        return "Knowledge base is not available. Please ensure chromadb is installed."
        
    try:
        # We use a simple hash or safe string for ID, but let's just use a timestamp-based ID or just the title.
        import time
        note_id = f"note_{int(time.time())}"
        
        collection.add(
            documents=[content],
            metadatas=[{"title": title}],
            ids=[note_id]
        )
        return f"Note saved to knowledge base: '{title}'"
    except Exception as e:
        logger.error(f"Failed to save note: {e}")
        return f"Failed to save note: {e}"

@function_tool
async def search_knowledge_base(query: str, n_results: int = 3) -> str:
    """
    Searches the personal knowledge base for relevant notes and documents.
    
    Args:
        query: The search question or keywords.
        n_results: Number of results to return (default 3).
    """
    collection = _get_collection()
    if collection is None:
        return "Knowledge base is not available. Please ensure chromadb is installed."
        
    try:
        results = collection.query(
            query_texts=[query],
            n_results=max(1, min(n_results, 5))
        )
        
        if not results["documents"] or not results["documents"][0]:
            return f"No relevant notes found for '{query}'."
            
        docs = results["documents"][0]
        metas = results["metadatas"][0]
        
        output = [f"Found {len(docs)} relevant notes:"]
        for i, doc in enumerate(docs):
            title = metas[i].get("title", "Untitled") if metas and i < len(metas) else "Untitled"
            output.append(f"\n--- Note: {title} ---\n{doc}")
            
        return "\n".join(output)
    except Exception as e:
        logger.error(f"Failed to search knowledge base: {e}")
        return f"Failed to search knowledge base: {e}"
