"""
VISION Knowledge Base RAG (Retrieval-Augmented Generation).

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

_KB_COLLECTION_NAME = "vision_knowledge"
_DB_PATH = os.path.join(os.path.expanduser("~"), "Documents", "VISION", "chromadb")


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
    Adds a text document or note to VISION's personal knowledge base for
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
    Parses a PDF file and indexes its content into the VISION knowledge base.

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
async def index_folder(folder_path: str, extensions: str = ".pdf,.txt,.md") -> str:
    """
    Indexes every supported document in a folder (and its subfolders) into
    the knowledge base at once — incrementally: unchanged files (by content
    hash) are skipped on repeat runs, and files that were deleted since the
    last index have their chunks cleaned up automatically.

    Args:
        folder_path: Absolute path to the folder to index (e.g. ~/Documents).
        extensions: Comma-separated list of file extensions to include (default: .pdf,.txt,.md).
    """
    import hashlib

    folder_path = os.path.expanduser(folder_path)
    if not os.path.isdir(folder_path):
        return f"'{folder_path}' is not a valid directory."

    ext_set = {e.strip().lower() for e in extensions.split(",") if e.strip()}
    skip_dirs = {".git", "__pycache__", "node_modules", ".venv", "venv", ".cache"}

    try:
        collection = _get_kb_collection()

        existing = collection.get(where={"folder": folder_path}, include=["metadatas"])
        existing_metas = existing.get("metadatas", []) or []
        existing_ids = existing.get("ids", []) or []
        existing_hash_by_file, existing_ids_by_file = {}, {}
        for _id, meta in zip(existing_ids, existing_metas):
            f = meta.get("source_path")
            existing_hash_by_file[f] = meta.get("file_hash")
            existing_ids_by_file.setdefault(f, []).append(_id)

        seen_files = set()
        indexed_count = 0
        skipped_count = 0
        failed = []

        for root, dirnames, filenames in os.walk(folder_path):
            dirnames[:] = [d for d in dirnames if d not in skip_dirs and not d.startswith(".")]
            for fname in filenames:
                ext = os.path.splitext(fname)[1].lower()
                if ext not in ext_set:
                    continue
                full_path = os.path.join(root, fname)
                seen_files.add(full_path)

                try:
                    if ext == ".pdf":
                        import pypdf
                        reader = pypdf.PdfReader(full_path)
                        text = "\n".join(page.extract_text() or "" for page in reader.pages).strip()
                    else:
                        with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                            text = f.read()
                except Exception as e:
                    failed.append(f"{fname}: {e}")
                    continue

                if not text.strip():
                    continue

                file_hash = hashlib.sha256(text.encode("utf-8", "ignore")).hexdigest()
                if existing_hash_by_file.get(full_path) == file_hash:
                    skipped_count += 1
                    continue

                stale_ids = existing_ids_by_file.get(full_path)
                if stale_ids:
                    collection.delete(ids=stale_ids)

                title = os.path.splitext(fname)[0]
                chunk_size, overlap = 800, 150
                chunks, ids, metas = [], [], []
                if len(text) > chunk_size:
                    start, idx = 0, 0
                    while start < len(text):
                        end = min(start + chunk_size, len(text))
                        chunks.append(text[start:end])
                        ids.append(f"folder::{full_path}::{idx}")
                        metas.append({"title": title, "chunk": idx, "folder": folder_path, "source_path": full_path, "file_hash": file_hash})
                        start += chunk_size - overlap
                        idx += 1
                else:
                    chunks = [text]
                    ids = [f"folder::{full_path}::0"]
                    metas = [{"title": title, "chunk": 0, "folder": folder_path, "source_path": full_path, "file_hash": file_hash}]

                collection.upsert(documents=chunks, ids=ids, metadatas=metas)
                indexed_count += 1

        deleted_files = set(existing_ids_by_file) - seen_files
        pruned = 0
        for f in deleted_files:
            collection.delete(ids=existing_ids_by_file[f])
            pruned += len(existing_ids_by_file[f])

        summary = f"Indexed {indexed_count} new/changed file(s) from '{folder_path}'."
        if skipped_count:
            summary += f" Skipped {skipped_count} unchanged file(s)."
        if pruned:
            summary += f" Removed chunks for {len(deleted_files)} deleted file(s)."
        if failed:
            summary += f" Failed to read {len(failed)} file(s): " + ", ".join(failed[:3])
        return summary

    except Exception as e:
        logger.error(f"Folder indexing failed: {e}")
        return f"Failed to index folder: {e}"


@function_tool
async def search_knowledge_base(query: str, n_results: int = 4) -> str:
    """
    Semantically searches VISION's personal knowledge base for relevant
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
    Lists all documents currently stored in VISION's knowledge base.
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
