"""
Document RAG (Retrieval-Augmented Generation) & Semantic Content Search Engine for VISION.
Extracts, chunks, and semantically retrieves relevant passages from PDF, DOCX, TXT, MD, and Code files.
"""

import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from vision.tools.registry import tool
from vision.memory.working_memory import working_memory
from vision.logger import logger

try:
    import pypdf
except ImportError:
    pypdf = None

try:
    import docx
except ImportError:
    docx = None


class DocumentRAGEngine:
    """Document text extractor and BM25 / keyword chunk retrieval engine."""

    def extract_text_from_file(self, file_path: Path) -> str:
        """Extract plain text from PDF, DOCX, TXT, MD, Python, etc."""
        if not file_path.exists():
            return ""

        ext = file_path.suffix.lower()

        # PDF extraction
        if ext == ".pdf":
            if not pypdf:
                return "Error: pypdf not installed."
            try:
                reader = pypdf.PdfReader(str(file_path))
                text_parts = []
                for i, page in enumerate(reader.pages):
                    t = page.extract_text()
                    if t:
                        text_parts.append(f"--- Page {i+1} ---\n{t}")
                return "\n\n".join(text_parts)
            except Exception as e:
                return f"Error extracting PDF text: {e}"

        # DOCX extraction
        elif ext in [".docx", ".doc"]:
            if not docx:
                return "Error: python-docx not installed."
            try:
                doc = docx.Document(str(file_path))
                return "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
            except Exception as e:
                return f"Error extracting DOCX text: {e}"

        # Plain text & code extraction
        else:
            try:
                with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                    return f.read()
            except Exception as e:
                return f"Error reading text: {e}"

    def chunk_text(self, text: str, chunk_size: int = 600, overlap: int = 100) -> List[str]:
        """Split document text into overlapping chunks."""
        words = text.split()
        if not words:
            return []
        chunks = []
        for i in range(0, len(words), chunk_size - overlap):
            chunk = " ".join(words[i:i + chunk_size])
            chunks.append(chunk)
        return chunks

    def search_in_document(self, file_path: Path, query: str, top_k: int = 3) -> str:
        """Retrieve the most relevant passages from a document for a query."""
        raw_text = self.extract_text_from_file(file_path)
        if not raw_text or raw_text.startswith("Error"):
            return raw_text or f"No text could be extracted from '{file_path.name}'."

        chunks = self.chunk_text(raw_text)
        if not chunks:
            return f"The document '{file_path.name}' is empty."

        query_tokens = set(query.lower().split())

        # Score chunks based on term occurrence and proximity
        scored_chunks = []
        for chunk in chunks:
            chunk_lower = chunk.lower()
            score = sum(chunk_lower.count(token) * 2 for token in query_tokens)
            if any(token in chunk_lower for token in query_tokens):
                score += 1
            scored_chunks.append((score, chunk))

        scored_chunks.sort(key=lambda x: x[0], reverse=True)
        top_chunks = [c[1] for c in scored_chunks[:top_k] if c[0] > 0]

        if not top_chunks:
            # Fallback to first chunks
            top_chunks = chunks[:2]

        result = [f"RAG Document Context from '{file_path.name}':"]
        for idx, passage in enumerate(top_chunks, 1):
            result.append(f"\n[Passage {idx}]\n{passage}")

        return "\n".join(result)


rag_engine = DocumentRAGEngine()


@tool(name="search_and_read_documents", description="Extract and answer questions from the content of PDFs, Word docs, code, or text files using semantic RAG retrieval.")
def search_and_read_documents(query: str, document_name_or_path: Optional[str] = None) -> str:
    """RAG semantic search and content extraction tool."""
    from vision.tools.file_tools import _resolve_user_path

    target_path = None
    if document_name_or_path:
        target_path = _resolve_user_path(document_name_or_path, find_existing_file=True)
    elif working_memory.recent_files:
        # Pick the most recent document from working memory
        for fp in working_memory.recent_files:
            p = Path(fp)
            if p.suffix.lower() in [".pdf", ".docx", ".txt", ".md", ".py"]:
                target_path = p
                break

    if not target_path or not target_path.exists():
        return f"Error: Could not locate document '{document_name_or_path or 'recent document'}'. Please specify filename."

    working_memory.record_file(str(target_path))
    return rag_engine.search_in_document(target_path, query)
