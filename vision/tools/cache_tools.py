"""
Cache management and inspection tools for VISION CAG (Cache-Augmented Generation).
"""

from typing import Optional
from vision.tools.registry import tool
from vision.memory.cag_engine import cag_engine
from vision.logger import logger


@tool(name="get_cache_stats", description="Get cache statistics, hit ratio, total hits, and active entries in the CAG engine.")
def get_cache_stats() -> str:
    """Retrieve CAG cache performance telemetry."""
    stats = cag_engine.get_stats()
    return (
        f"CAG Cache Telemetry:\n"
        f"- Active Cache Entries: {stats['active_entries']}\n"
        f"- Cache Hits: {stats['hits']}\n"
        f"- Cache Misses: {stats['misses']}\n"
        f"- Hit Efficiency Ratio: {stats['hit_ratio']}\n"
        f"- Cache Store: {stats['storage_file']}"
    )


@tool(name="clear_system_cache", description="Clear or invalidate the CAG response cache (e.g. cache_type='all' or cache_type='weather').")
def clear_system_cache(cache_type: str = "all") -> str:
    """Clear cached entries from CAG store."""
    deleted = cag_engine.invalidate(pattern=cache_type)
    logger.info(f"[CacheTool] Cleared {deleted} cache entries for type '{cache_type}'")
    return f"Successfully cleared {deleted} cache entries (Pattern: '{cache_type}')."
