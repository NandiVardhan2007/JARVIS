"""
Document Processor — PDF / DOCX / TXT Q&A via Groq AI.

Flow:
  1. User triggers the tool  →  file‑selection dialog opens.
  2. The document is read, split into overlapping chunks, and cached in SQLite.
  3. Relevant chunks + user query are sent to Groq for an AI answer.
"""

import asyncio
import hashlib
import logging
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import aiohttp
from livekit.agents import function_tool

logger = logging.getLogger(__name__)

# ── Defaults ──────────────────────────────────────────────────────────────────
DB_DIR = Path("jarvis_memory")
DB_PATH = DB_DIR / "document_chunks.db"
CHUNK_SIZE = 1500      # characters per chunk
CHUNK_OVERLAP = 300    # overlap between consecutive chunks
GROQ_MODEL = "llama-3.3-70b-versatile"
MAX_CONTEXT_CHARS = 8000


# ── File processor class ─────────────────────────────────────────────────────

class DocumentProcessor:
    """Read, chunk, cache, and query documents."""

    def __init__(self):
        DB_DIR.mkdir(exist_ok=True)
        self._init_db()

    # ── Database ──────────────────────────────────────────────────────────

    def _init_db(self):
        conn = sqlite3.connect(str(DB_PATH))
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS document_chunks (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                file_hash   TEXT    NOT NULL,
                file_name   TEXT    NOT NULL,
                chunk_index INTEGER NOT NULL,
                chunk_text  TEXT    NOT NULL,
                token_count INTEGER,
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(file_hash, chunk_index)
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS file_metadata (
                file_hash    TEXT PRIMARY KEY,
                file_name    TEXT NOT NULL,
                file_path    TEXT NOT NULL,
                file_size    INTEGER,
                page_count   INTEGER,
                total_chunks INTEGER,
                processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()

    # ── File selection ────────────────────────────────────────────────────

    @staticmethod
    def select_file() -> str | None:
        """Open a native file‑selection dialog and return the chosen path."""
        try:
            import tkinter as tk
            from tkinter import filedialog

            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            path = filedialog.askopenfilename(
                title="Select a document to analyse",
                filetypes=[
                    ("Supported files", "*.pdf *.txt *.docx *.doc"),
                    ("PDF", "*.pdf"),
                    ("Text", "*.txt"),
                    ("Word", "*.docx *.doc"),
                ],
            )
            root.destroy()
            return path if path else None
        except Exception as exc:
            logger.error(f"File dialog error: {exc}")
            return None

    # ── Readers ───────────────────────────────────────────────────────────

    @staticmethod
    def _read_pdf(path: str) -> tuple[str, int]:
        import PyPDF2

        text = ""
        with open(path, "rb") as fh:
            reader = PyPDF2.PdfReader(fh)
            pages = len(reader.pages)
            for i, page in enumerate(reader.pages):
                extracted = page.extract_text() or ""
                text += f"--- Page {i + 1} ---\n{extracted}\n\n"
        return text, pages

    @staticmethod
    def _read_docx(path: str) -> tuple[str, int]:
        import docx

        doc = docx.Document(path)
        text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        est_pages = max(1, len(text) // 3000)
        return text, est_pages

    @staticmethod
    def _read_txt(path: str) -> tuple[str, int]:
        # Try chardet first, fall back through common encodings
        try:
            import chardet

            with open(path, "rb") as fh:
                raw = fh.read()
            enc = chardet.detect(raw).get("encoding") or "utf-8"
        except ImportError:
            enc = "utf-8"

        for encoding in (enc, "utf-8", "latin-1", "cp1252"):
            try:
                with open(path, "r", encoding=encoding) as fh:
                    return fh.read(), 1
            except (UnicodeDecodeError, LookupError):
                continue
        raise RuntimeError(f"Could not decode {path} with any known encoding.")

    def read_file(self, path: str) -> Dict[str, Any]:
        ext = os.path.splitext(path)[1].lower()
        readers = {".pdf": self._read_pdf, ".docx": self._read_docx, ".doc": self._read_docx, ".txt": self._read_txt}
        reader = readers.get(ext)
        if not reader:
            raise ValueError(f"Unsupported file type: {ext}")
        content, pages = reader(path)
        return {"content": content, "page_count": pages, "file_size": os.path.getsize(path), "file_name": os.path.basename(path)}

    # ── Hashing / dedup ──────────────────────────────────────────────────

    @staticmethod
    def file_hash(path: str) -> str:
        # Optimize by using file path, size, and modified time instead of reading full file
        import os
        try:
            st = os.stat(path)
            meta_str = f"{os.path.abspath(path)}|{st.st_size}|{st.st_mtime}"
            return hashlib.md5(meta_str.encode("utf-8")).hexdigest()
        except OSError:
            # Fallback if stat fails
            return hashlib.md5(path.encode("utf-8")).hexdigest()

    def is_cached(self, fhash: str) -> bool:
        conn = sqlite3.connect(str(DB_PATH))
        row = conn.execute("SELECT 1 FROM file_metadata WHERE file_hash = ?", (fhash,)).fetchone()
        conn.close()
        return row is not None

    # ── Chunking ─────────────────────────────────────────────────────────

    @staticmethod
    def smart_chunk(text: str) -> List[Dict[str, Any]]:
        text = " ".join(text.split())  # normalise whitespace
        chunks: list[dict] = []
        start = 0
        idx = 0

        while start < len(text):
            end = start + CHUNK_SIZE
            if end < len(text):
                # Find a natural sentence boundary
                for sep in (". ", "\n", "? ", "! "):
                    pos = text.rfind(sep, start, end)
                    if pos > start + CHUNK_SIZE // 2:
                        end = pos + len(sep)
                        break
                else:
                    sp = text.rfind(" ", start, end)
                    if sp > start:
                        end = sp

            chunk_text = text[start:end].strip()
            if chunk_text:
                chunks.append({"index": idx, "text": chunk_text, "token_count": len(chunk_text.split())})
                idx += 1
            start = end - CHUNK_OVERLAP
            if start < 0:
                start = 0

        return chunks

    # ── Storage ──────────────────────────────────────────────────────────

    def store(self, fhash: str, fname: str, fpath: str, chunks: list, meta: dict):
        conn = sqlite3.connect(str(DB_PATH))
        c = conn.cursor()
        c.execute(
            "INSERT OR REPLACE INTO file_metadata VALUES (?,?,?,?,?,?,?)",
            (fhash, fname, fpath, meta["file_size"], meta["page_count"], len(chunks), datetime.now().isoformat()),
        )
        for ch in chunks:
            c.execute(
                "INSERT OR REPLACE INTO document_chunks (file_hash,file_name,chunk_index,chunk_text,token_count) VALUES (?,?,?,?,?)",
                (fhash, fname, ch["index"], ch["text"], ch["token_count"]),
            )
        conn.commit()
        conn.close()

    # ── Retrieval ─────────────────────────────────────────────────────────

    def get_chunks(self, fhash: str, max_chunks: int = 10) -> List[str]:
        conn = sqlite3.connect(str(DB_PATH))
        total = conn.execute("SELECT COUNT(*) FROM document_chunks WHERE file_hash=?", (fhash,)).fetchone()[0]

        if total <= max_chunks:
            rows = conn.execute("SELECT chunk_text FROM document_chunks WHERE file_hash=? ORDER BY chunk_index", (fhash,)).fetchall()
        else:
            half = max_chunks // 2
            first = conn.execute("SELECT chunk_text FROM document_chunks WHERE file_hash=? ORDER BY chunk_index LIMIT ?", (fhash, half)).fetchall()
            last = conn.execute("SELECT chunk_text FROM document_chunks WHERE file_hash=? ORDER BY chunk_index DESC LIMIT ?", (fhash, max_chunks - half)).fetchall()
            rows = first + list(reversed(last))

        conn.close()
        # deduplicate while preserving order
        seen: set[str] = set()
        result: list[str] = []
        for (txt,) in rows:
            if txt not in seen:
                seen.add(txt)
                result.append(txt)
        return result

    # ── LLM query ─────────────────────────────────────────────────────────

    async def query_llm(self, question: str, chunks: List[str]) -> str:
        api_key = os.getenv("GROQ_API_KEY", "")
        if not api_key:
            return "Error: GROQ_API_KEY is not set in .env — cannot process documents."

        context = "\n\n".join(chunks)
        if len(context) > MAX_CONTEXT_CHARS:
            context = context[:MAX_CONTEXT_CHARS] + "\n…[truncated]"

        prompt = (
            f"DOCUMENT CONTEXT:\n{context}\n\n"
            f"USER QUESTION: {question}\n\n"
            "Instructions:\n"
            "- Answer based ONLY on the document context above.\n"
            "- If the answer is not in the document, say so.\n"
            "- Be detailed yet concise. Respond in English."
        )

        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        payload = {
            "model": GROQ_MODEL,
            "messages": [
                {"role": "system", "content": (
                    "You are JARVIS, an expert document analyst. Answer the user's question "
                    "using ONLY the provided document context. Rules:\n"
                    "- Cite specific sections, page numbers, or paragraphs when possible.\n"
                    "- Quote exact figures, dates, names, and amounts from the document.\n"
                    "- If the answer is not in the provided context, say: 'This information "
                    "is not present in the document.'\n"
                    "- Be concise but thorough. Prefer structured answers for complex questions.\n"
                    "- Never fabricate information that isn't in the context."
                )},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.1,
            "max_tokens": 2000,
        }

        async with aiohttp.ClientSession() as session:
            async with session.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                if resp.status != 200:
                    err = await resp.text()
                    return f"Groq API error ({resp.status}): {err[:200]}"
                data = await resp.json()
                return data["choices"][0]["message"]["content"].strip()


# ── Singleton ─────────────────────────────────────────────────────────────────
_processor = DocumentProcessor()


# ── Tool ──────────────────────────────────────────────────────────────────────

@function_tool
async def process_document_query(user_query: str) -> str:
    """
    Analyse a PDF, Word, or text document and answer a question about it.

    Opens a file‑selection dialog, reads and indexes the document (cached for
    repeat queries), then uses AI to answer the user's question based on the
    document content.

    Args:
        user_query: The question to answer about the document.
    """
    try:
        # 1. File selection (runs Tkinter in main thread via to_thread)
        path = await asyncio.to_thread(_processor.select_file)
        if not path:
            return "No file was selected — operation cancelled."

        fname = os.path.basename(path)
        fhash = _processor.file_hash(path)

        # 2. Process if not cached
        if not _processor.is_cached(fhash):
            logger.info(f"Processing new document: {fname}")
            data = _processor.read_file(path)
            if not data["content"].strip():
                return f"The file '{fname}' appears to be empty or unreadable."
            chunks = _processor.smart_chunk(data["content"])
            if not chunks:
                return f"Could not extract any usable text from '{fname}'."
            _processor.store(fhash, fname, path, chunks, data)
            status = f"Processed '{fname}' — {data['page_count']} pages, {len(chunks)} chunks."
        else:
            status = f"Using cached index for '{fname}'."

        # 3. Retrieve relevant chunks
        context_chunks = _processor.get_chunks(fhash, max_chunks=8)
        if not context_chunks:
            return f"{status}\nError: no indexed content found for this document."

        # 4. Query LLM
        answer = await _processor.query_llm(user_query, context_chunks)

        return (
            f"📄 **File:** {fname}\n"
            f"❓ **Question:** {user_query}\n\n"
            f"🤖 **Answer:**\n{answer}\n\n"
            f"_({status})_"
        )

    except Exception as exc:
        logger.exception("Document processing failed")
        return f"Document processing error: {exc}"
