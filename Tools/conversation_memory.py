"""
Conversation memory — the one RAG gap flagged in the roadmap as genuinely
missing: past conversation transcripts weren't indexed anywhere.

Design:
  - Every turn (user + assistant) is appended to a daily JSONL log
    (~/Documents/VISION/conversations/YYYY-MM-DD.jsonl) the moment it
    happens — cheap, synchronous-safe, no embedding calls in that hot path
    (embedding on every utterance would add latency to live conversation).
  - A separate, periodic background pass (every few minutes, not every
    turn) incrementally embeds only the NEW lines since last time into a
    "vision_conversations" ChromaDB collection — same db file as
    Tools/knowledge_rag.py, different collection, so document search
    results aren't flooded with one-word utterances by default.
  - search_past_conversations() is the retrieval side.

This keeps "fast retrieval with minimal latency" honest on both ends: the
live conversation is never blocked on an embedding call, and search queries
only ever hit an already-built index.
"""

import asyncio
import json
import logging
import os
import time
from datetime import datetime
from typing import Optional

from livekit.agents import function_tool

logger = logging.getLogger(__name__)

CONV_DIR = os.path.join(os.path.expanduser("~"), "Documents", "VISION", "conversations")
_INDEX_STATE_PATH = os.path.join(CONV_DIR, ".index_state.json")
_COLLECTION_NAME = "vision_conversations"
_DB_PATH = os.path.join(os.path.expanduser("~"), "Documents", "VISION", "chromadb")

INDEX_INTERVAL_SEC = float(os.getenv("VISION_CONVERSATION_INDEX_INTERVAL_SEC", "300"))

_indexer_task = None
_indexer_active = False


def _get_conv_collection():
    import chromadb
    os.makedirs(_DB_PATH, exist_ok=True)
    client = chromadb.PersistentClient(path=_DB_PATH)
    return client.get_or_create_collection(name=_COLLECTION_NAME)


def _today_path() -> str:
    os.makedirs(CONV_DIR, exist_ok=True)
    return os.path.join(CONV_DIR, datetime.now().strftime("%Y-%m-%d.jsonl"))


def log_conversation_turn(role: str, text: str):
    """
    Appends one conversation turn to today's log. Called directly from
    agent.py's event handlers — NOT a function_tool, this isn't something
    the LLM calls itself, it's plumbing.
    """
    if not text or not text.strip():
        return
    try:
        entry = {"ts": time.time(), "role": role, "text": text.strip()}
        with open(_today_path(), "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception as e:
        logger.debug(f"Could not log conversation turn: {e}")


def _load_index_state() -> dict:
    try:
        if os.path.isfile(_INDEX_STATE_PATH):
            with open(_INDEX_STATE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        logger.warning(f"Could not load conversation index state: {e}")
    return {}


def _save_index_state(state: dict):
    try:
        os.makedirs(CONV_DIR, exist_ok=True)
        with open(_INDEX_STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f)
    except Exception as e:
        logger.debug(f"Could not save conversation index state: {e}")


async def _index_new_turns() -> str:
    """Incrementally indexes any conversation lines logged since the last pass."""
    if not os.path.isdir(CONV_DIR):
        return "No conversation history yet."

    state = _load_index_state()
    loop = asyncio.get_event_loop()

    try:
        collection = await loop.run_in_executor(None, _get_conv_collection)
    except ImportError:
        return "chromadb is not installed — cannot index conversation history."
    except Exception as e:
        return f"Could not open conversation index: {e}"

    total_new = 0
    for fname in sorted(os.listdir(CONV_DIR)):
        if not fname.endswith(".jsonl"):
            continue
        path = os.path.join(CONV_DIR, fname)
        already_indexed = state.get(fname, 0)

        try:
            with open(path, encoding="utf-8") as f:
                lines = f.readlines()
        except OSError:
            continue

        new_lines = lines[already_indexed:]
        if not new_lines:
            continue

        date_str = fname.replace(".jsonl", "")
        documents, metadatas, ids = [], [], []
        for i, line in enumerate(new_lines, start=already_indexed):
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            text = entry.get("text", "").strip()
            if not text:
                continue
            documents.append(text)
            metadatas.append({"date": date_str, "role": entry.get("role", "unknown"), "ts": entry.get("ts", 0)})
            ids.append(f"conv::{date_str}::{i}")

        if documents:
            await loop.run_in_executor(None, lambda: collection.upsert(documents=documents, metadatas=metadatas, ids=ids))
            total_new += len(documents)

        state[fname] = len(lines)

    _save_index_state(state)
    return f"Indexed {total_new} new conversation turn(s)." if total_new else "No new conversation turns to index."


async def _conversation_indexer_loop():
    while _indexer_active:
        await asyncio.sleep(INDEX_INTERVAL_SEC)
        try:
            result = await _index_new_turns()
            if "0 new" not in result and "No new" not in result:
                logger.info(f"Conversation indexer: {result}")
        except Exception as e:
            logger.warning(f"Conversation indexing pass failed: {e}")


def start_conversation_indexer():
    """Starts the background incremental conversation indexer. Called from agent.py, not a tool."""
    global _indexer_task, _indexer_active
    if _indexer_active:
        return
    _indexer_active = True
    _indexer_task = asyncio.create_task(_conversation_indexer_loop())


@function_tool
async def search_past_conversations(query: str, n_results: int = 5, when: Optional[str] = None) -> str:
    """
    Searches past conversation history semantically — use this for
    questions like "what did we discuss about X" or "did I mention Y before".

    Args:
        query: Natural language question or topic to search for.
        n_results: Number of matching turns to return (default 5).
        when: Optional date filter in YYYY-MM-DD format to narrow the search
            to a specific day.
    """
    try:
        collection = _get_conv_collection()
        where = {"date": when} if when else None
        results = collection.query(query_texts=[query], n_results=n_results, where=where)

        if not results["documents"][0]:
            return "Nothing found in past conversations matching that."

        lines = [f'Past conversation matches for "{query}":']
        for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
            role = meta.get("role", "?")
            date = meta.get("date", "?")
            lines.append(f"[{date}, {role}] {doc}")
        return "\n".join(lines)
    except ImportError:
        return "chromadb is not installed — cannot search conversation history."
    except Exception as e:
        return f"Conversation search failed: {e}"


@function_tool
async def index_conversation_history_now() -> str:
    """Manually triggers indexing of any new conversation turns right now, instead of waiting for the periodic background pass."""
    return await _index_new_turns()
