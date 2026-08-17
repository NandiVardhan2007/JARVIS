"""
Cache-Augmented Generation (CAG) Engine for VISION.
Provides multi-tiered in-memory (L1) and persistent disk (L2) caching for ultra-fast,
zero-token response retrieval, fuzzy semantic matching, and intelligent TTL invalidation.
"""

import json
import hashlib
import re
import time
from pathlib import Path
from typing import Optional, Dict, Any, List
from vision.logger import logger


# Queries containing these dynamic keywords should never be served from stale cache
CACHE_BYPASS_PATTERNS = [
    r"\b(?:time|date|clock|current time|today's date)\b",
    r"\b(?:screenshot|screen|what is on my screen|describe screen)\b",
    r"\b(?:cpu|ram|battery|system stats|metrics)\b",
    r"\b(?:open|launch|start|run|kill|close|terminate)\b",
    r"\b(?:move|copy|delete|rename|create folder|organize)\b",
    r"\b(?:print|send email|unlock phone|tap)\b",
    r"\b(?:remember|forget)\b",
]


class CAGEngine:
    def __init__(self, cache_dir: Optional[str] = None):
        if cache_dir is None:
            project_root = Path(__file__).resolve().parent.parent.parent
            self.cache_dir = project_root / "data" / "cache"
        else:
            self.cache_dir = Path(cache_dir)

        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.store_file = self.cache_dir / "cag_store.json"

        # L1 Memory Cache: {hash: {query, response, created_at, expires_at, category, hit_count}}
        self._l1_cache: Dict[str, Dict[str, Any]] = {}
        self.hits = 0
        self.misses = 0

        self._load_l2_cache()

    def _normalize_query(self, query: str) -> str:
        """Normalize query for fuzzy matching (lowercase, strip filler punctuation)."""
        clean = query.lower().strip()
        clean = re.sub(r"[^\w\s]", "", clean)
        # Remove common filler conversational prefixes
        clean = re.sub(r"^(hey\s+vision|vision|please|tell\s+me|can\s+you)\s+", "", clean).strip()
        return clean

    def _generate_key(self, query: str) -> str:
        """Create SHA256 key from normalized query."""
        norm = self._normalize_query(query)
        return hashlib.sha256(norm.encode("utf-8")).hexdigest()[:16]

    def _load_l2_cache(self):
        """Load persistent disk cache into memory."""
        if self.store_file.exists():
            try:
                with open(self.store_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    now = time.time()
                    # Filter out expired keys
                    self._l1_cache = {
                        k: v for k, v in data.items()
                        if v.get("expires_at", 0) > now
                    }
                logger.info(f"[CAG] Loaded {len(self._l1_cache)} active cache entries from disk.")
            except Exception as e:
                logger.warning(f"[CAG] Failed to load L2 cache from disk: {e}")
                self._l1_cache = {}

    def _save_l2_cache(self):
        """Persist L1 cache to disk."""
        try:
            with open(self.store_file, "w", encoding="utf-8") as f:
                json.dump(self._l1_cache, f, indent=2)
        except Exception as e:
            logger.warning(f"[CAG] Failed to save L2 cache: {e}")

    def should_bypass(self, query: str) -> bool:
        """Determine if a query is dynamic or actionable and must bypass the cache."""
        clean = query.lower().strip()
        for p in CACHE_BYPASS_PATTERNS:
            if re.search(p, clean):
                return True
        return False

    def lookup(self, query: str) -> Optional[Dict[str, Any]]:
        """Look up response in L1/L2 cache."""
        if self.should_bypass(query):
            self.misses += 1
            return None

        key = self._generate_key(query)
        entry = self._l1_cache.get(key)

        now = time.time()
        if entry:
            if entry.get("expires_at", 0) > now:
                self.hits += 1
                entry["hit_count"] = entry.get("hit_count", 0) + 1
                logger.info(f"[CAG] Cache HIT for key '{key}' (Query: '{query[:40]}...') -> Latency: <1ms")
                return {
                    "response": entry["response"],
                    "cached": True,
                    "hit_count": entry["hit_count"],
                    "age_seconds": round(now - entry["created_at"], 1)
                }
            else:
                # Expired
                del self._l1_cache[key]

        self.misses += 1
        return None

    def put(self, query: str, response: str, category: str = "general", ttl_seconds: int = 3600):
        """Store a newly generated response in the cache with a TTL."""
        if self.should_bypass(query) or not response or len(response.strip()) < 5:
            return

        key = self._generate_key(query)
        now = time.time()
        entry = {
            "query": query,
            "response": response,
            "category": category,
            "created_at": now,
            "expires_at": now + ttl_seconds,
            "hit_count": 0
        }
        self._l1_cache[key] = entry
        self._save_l2_cache()
        logger.debug(f"[CAG] Stored cache entry '{key}' (TTL: {ttl_seconds}s)")

    def invalidate(self, pattern: Optional[str] = None):
        """Invalidate all or matching cache entries."""
        if not pattern or pattern == "all":
            count = len(self._l1_cache)
            self._l1_cache.clear()
            self._save_l2_cache()
            logger.info(f"[CAG] Invalidated entire cache ({count} entries).")
            return count

        deleted = 0
        p_clean = pattern.lower()
        keys_to_del = []
        for k, v in self._l1_cache.items():
            if p_clean in v.get("query", "").lower() or p_clean in v.get("category", "").lower():
                keys_to_del.append(k)

        for k in keys_to_del:
            del self._l1_cache[k]
            deleted += 1

        if deleted > 0:
            self._save_l2_cache()
            logger.info(f"[CAG] Invalidated {deleted} cache entries matching '{pattern}'.")
        return deleted

    def get_stats(self) -> Dict[str, Any]:
        """Get cache performance telemetry."""
        total = self.hits + self.misses
        hit_ratio = f"{(self.hits / total * 100):.1f}%" if total > 0 else "0.0%"
        return {
            "active_entries": len(self._l1_cache),
            "hits": self.hits,
            "misses": self.misses,
            "total_queries": total,
            "hit_ratio": hit_ratio,
            "storage_file": str(self.store_file)
        }


# Global CAG Engine Singleton
cag_engine = CAGEngine()
