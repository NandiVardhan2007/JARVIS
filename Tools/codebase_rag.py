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
    Scans a project directory and indexes all code files into a semantic vector database.
    This allows JARVIS to search across the entire project for context later.

    Args:
        project_path: Absolute path to the root of the project directory.
    """
    logger.info(f"Indexing codebase at: {project_path}")
    
    if not os.path.isdir(project_path):
        return f"Error: '{project_path}' is not a valid directory."
        
    try:
        collection = _get_chroma_collection()
        
        supported_extensions = {".py", ".js", ".ts", ".html", ".css", ".java", ".cpp", ".c", ".h", ".go", ".rs", ".md", ".txt"}
        
        documents = []
        metadatas = []
        ids = []
        
        chunk_size = 1000
        overlap = 200
        
        for root, _, files in os.walk(project_path):
            # Skip hidden directories and virtual environments
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
                        
                    # Basic chunking
                    if len(text) > chunk_size:
                        start = 0
                        chunk_index = 0
                        while start < len(text):
                            end = min(start + chunk_size, len(text))
                            chunk = text[start:end]
                            
                            documents.append(chunk)
                            metadatas.append({"file": file_path, "chunk": chunk_index})
                            ids.append(f"{file_path}_{chunk_index}")
                            
                            start += chunk_size - overlap
                            chunk_index += 1
                    else:
                        documents.append(text)
                        metadatas.append({"file": file_path, "chunk": 0})
                        ids.append(f"{file_path}_0")
                        
                except Exception as e:
                    logger.debug(f"Skipping {file_path}: {e}")
                    
        if not documents:
            return "No readable code files found to index."
            
        # Batch insert to avoid overloading Chroma
        batch_size = 100
        for i in range(0, len(documents), batch_size):
            collection.add(
                documents=documents[i:i+batch_size],
                metadatas=metadatas[i:i+batch_size],
                ids=ids[i:i+batch_size]
            )
            
        return f"Successfully indexed {len(documents)} code chunks from {project_path}."
        
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
