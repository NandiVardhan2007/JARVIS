"""Codebase RAG (Retrieval-Augmented Generation) using ChromaDB."""

import os
import logging
from pathlib import Path
from livekit.agents import function_tool

logger = logging.getLogger(__name__)

def _get_chroma_collection():
    try:
        import chromadb
        
        # Store the DB in the user's documents folder
        db_path = os.path.join(os.path.expanduser("~"), "Documents", "JARVIS", "chromadb")
        os.makedirs(db_path, exist_ok=True)
        
        client = chromadb.PersistentClient(path=db_path)
        collection = client.get_or_create_collection(name="codebase_rag")
        return collection
    except ImportError:
        raise ImportError("chromadb is not installed. Please add it to requirements.txt.")

@function_tool
async def index_project_codebase(project_path: str) -> str:
    """
    Scans a project directory and indexes all code files into a semantic
    vector database, incrementally — unchanged files are skipped (by content
    hash) so re-running this after a small edit is fast, and stale chunks
    from since-shrunk or deleted files are cleaned up automatically.
    This allows JARVIS to search across the entire project for context later.

    Args:
        project_path: Absolute path to the root of the project directory.
    """
    import hashlib

    logger.info(f"Indexing codebase at: {project_path}")

    if not os.path.isdir(project_path):
        return f"Error: '{project_path}' is not a valid directory."

    try:
        collection = _get_chroma_collection()

        supported_extensions = {".py", ".js", ".ts", ".html", ".css", ".java", ".cpp", ".c", ".h", ".go", ".rs", ".md", ".txt"}

        # Existing chunk IDs for this project, so we can (a) skip unchanged
        # files by comparing a stored content hash and (b) delete chunks
        # belonging to files that shrank or were removed since last index.
        existing = collection.get(where={"project": project_path}, include=["metadatas"])
        existing_ids = existing.get("ids", []) or []
        existing_metas = existing.get("metadatas", []) or []
        existing_hash_by_file = {}
        existing_ids_by_file: dict = {}
        for _id, meta in zip(existing_ids, existing_metas):
            f = meta.get("file")
            existing_hash_by_file[f] = meta.get("file_hash")
            existing_ids_by_file.setdefault(f, []).append(_id)

        chunk_size = 1000
        overlap = 200

        documents, metadatas, ids = [], [], []
        seen_files = set()
        skipped_unchanged = 0

        for root, _, files in os.walk(project_path):
            if any(part.startswith('.') or part in ('venv', 'node_modules', '__pycache__') for part in Path(root).parts):
                continue

            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext not in supported_extensions:
                    continue

                file_path = os.path.join(root, file)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        text = f.read()
                except Exception as e:
                    logger.debug(f"Skipping {file_path}: {e}")
                    continue

                file_hash = hashlib.sha256(text.encode("utf-8", "ignore")).hexdigest()
                seen_files.add(file_path)

                if existing_hash_by_file.get(file_path) == file_hash:
                    skipped_unchanged += 1
                    continue  # content unchanged since last index — nothing to do

                # Content changed (or new file) — remove any old chunks for
                # this file first, so a shrunk file doesn't leave orphans.
                stale_ids = existing_ids_by_file.get(file_path)
                if stale_ids:
                    collection.delete(ids=stale_ids)

                if len(text) > chunk_size:
                    start, chunk_index = 0, 0
                    while start < len(text):
                        end = min(start + chunk_size, len(text))
                        documents.append(text[start:end])
                        metadatas.append({"file": file_path, "chunk": chunk_index, "project": project_path, "file_hash": file_hash})
                        ids.append(f"{file_path}_{chunk_index}")
                        start += chunk_size - overlap
                        chunk_index += 1
                else:
                    documents.append(text)
                    metadatas.append({"file": file_path, "chunk": 0, "project": project_path, "file_hash": file_hash})
                    ids.append(f"{file_path}_0")

        # Prune chunks for files that were deleted since the last index.
        deleted_files = set(existing_ids_by_file) - seen_files
        pruned = 0
        for f in deleted_files:
            stale_ids = existing_ids_by_file[f]
            collection.delete(ids=stale_ids)
            pruned += len(stale_ids)

        if not documents:
            msg = f"No changes to index — {skipped_unchanged} file(s) unchanged since last index."
            if pruned:
                msg += f" Removed {pruned} stale chunk(s) from {len(deleted_files)} deleted file(s)."
            return msg

        # Batch upsert (safe to re-run — updates existing IDs, adds new ones)
        batch_size = 100
        for i in range(0, len(documents), batch_size):
            collection.upsert(
                documents=documents[i:i+batch_size],
                metadatas=metadatas[i:i+batch_size],
                ids=ids[i:i+batch_size]
            )

        summary = f"Indexed {len(documents)} code chunk(s) from {len(seen_files) - skipped_unchanged} changed/new file(s) in {project_path}."
        if skipped_unchanged:
            summary += f" Skipped {skipped_unchanged} unchanged file(s)."
        if pruned:
            summary += f" Removed {pruned} stale chunk(s) from {len(deleted_files)} deleted file(s)."
        return summary

    except Exception as e:
        return f"Failed to index codebase: {str(e)}"

@function_tool
async def search_codebase(query: str, n_results: int = 3) -> str:
    """
    Searches the indexed codebase for semantic matches to the query.
    Use this when you need context about functions, classes, or patterns across the project.

    Args:
        query: What to search for (e.g., 'database connection string', 'auth middleware').
        n_results: Number of results to return (default 3).
    """
    logger.info(f"Searching codebase for: {query}")
    
    try:
        collection = _get_chroma_collection()
        
        results = collection.query(
            query_texts=[query],
            n_results=n_results
        )
        
        if not results['documents'][0]:
            return "No relevant code found in the index."
            
        formatted_results = [f"Search Results for '{query}':"]
        
        for i in range(len(results['documents'][0])):
            doc = results['documents'][0][i]
            meta = results['metadatas'][0][i]
            file_path = meta['file']
            
            formatted_results.append(f"\n--- File: {file_path} ---")
            formatted_results.append(doc)
            
        return "\n".join(formatted_results)
        
    except Exception as e:
        return f"Failed to search codebase: {str(e)}"
