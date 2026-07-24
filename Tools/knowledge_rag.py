"""
JARVIS Knowledge Base RAG (Retrieval-Augmented Generation).

Stores and retrieves general documents (PDFs, notes, text files) in a
ChromaDB vector store. Separate from the codebase RAG collection.

Usage:
    - add_document_to_knowledge(title, content)  → index a piece of text/note
    - index_pdf_file(file_path)                  → parse and index a PDF
    - search_knowledge_base(query)               → semantic search
"""

import os
import logging
from livekit.agents import function_tool

logger = logging.getLogger(__name__)

_KB_COLLECTION_NAME = "jarvis_knowledge"
_DB_PATH = os.path.join(os.path.expanduser("~"), "Documents", "JARVIS", "chromadb")


def _get_kb_collection():
    try:
        import chromadb
        os.makedirs(_DB_PATH, exist_ok=True)
        client = chromadb.PersistentClient(path=_DB_PATH)
        return client.get_or_create_collection(name=_KB_COLLECTION_NAME)
    except ImportError:
        raise ImportError("chromadb is not installed. Run: pip install chromadb")


@function_tool
async def add_document_to_knowledge(title: str, content: str) -> str:
    """
    Adds a text document or note to JARVIS's personal knowledge base for
    future semantic retrieval.

    Args:
        title: Short descriptive title for the document.
        content: The full text content to store and index.
    """
    try:
        collection = _get_kb_collection()
        chunk_size = 800
        overlap = 150
        chunks, ids, metas = [], [], []

        if len(content) > chunk_size:
            start, idx = 0, 0
            while start < len(content):
                end = min(start + chunk_size, len(content))
                chunks.append(content[start:end])
                ids.append(f"doc::{title}::{idx}")
                metas.append({"title": title, "chunk": idx})
                start += chunk_size - overlap
                idx += 1
        else:
            chunks = [content]
            ids = [f"doc::{title}::0"]
            metas = [{"title": title, "chunk": 0}]

        collection.upsert(documents=chunks, ids=ids, metadatas=metas)
        return f"Indexed '{title}' as {len(chunks)} chunk(s) in the knowledge base."
    except Exception as e:
        logger.error(f"Failed to add document: {e}")
        return f"Error adding document: {e}"


@function_tool
async def index_pdf_file(file_path: str) -> str:
    """
    Parses a PDF file and indexes its content into the JARVIS knowledge base.

    Args:
        file_path: Absolute path to the PDF file.
    """
    try:
        import pypdf
    except ImportError:
        return "pypdf is not installed. Run: pip install pypdf"

    if not os.path.exists(file_path):
        return f"File not found: {file_path}"

    try:
        reader = pypdf.PdfReader(file_path)
        text = "\n".join(
            page.extract_text() or "" for page in reader.pages
        ).strip()
        if not text:
            return "No readable text found in the PDF."

        title = os.path.basename(file_path).replace(".pdf", "")
        return await add_document_to_knowledge(title, text)
    except Exception as e:
        logger.error(f"PDF indexing failed: {e}")
        return f"Failed to parse PDF: {e}"


@function_tool
async def search_knowledge_base(query: str, n_results: int = 4) -> str:
    """
    Semantically searches JARVIS's personal knowledge base for relevant
    information. Use this when the user asks about something that may be
    in their stored documents, notes, or PDFs.

    Args:
        query: Natural language question or search phrase.
        n_results: Number of top matches to return (default 4).
    """
    try:
        collection = _get_kb_collection()
        results = collection.query(query_texts=[query], n_results=n_results)

        if not results["documents"][0]:
            return "Nothing found in the knowledge base matching that query."

        lines = [f"Knowledge Base Results for \"{query}\":"]
        seen_titles = set()
        for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
            title = meta.get("title", "Unknown")
            if title not in seen_titles:
                lines.append(f"\n── Source: {title} ──")
                seen_titles.add(title)
            lines.append(doc.strip())

        return "\n".join(lines)
    except Exception as e:
        logger.error(f"Knowledge search failed: {e}")
        return f"Search failed: {e}"


@function_tool
async def list_knowledge_documents() -> str:
    """
    Lists all documents currently stored in JARVIS's knowledge base.
    """
    try:
        collection = _get_kb_collection()
        results = collection.get(include=["metadatas"])
        metas = results.get("metadatas", [])
        titles = sorted(set(m.get("title", "Unknown") for m in metas))
        if not titles:
            return "The knowledge base is empty. You can add documents using add_document_to_knowledge."
        return "Documents in knowledge base:\n" + "\n".join(f"  • {t}" for t in titles)
    except Exception as e:
        return f"Failed to list documents: {e}"
