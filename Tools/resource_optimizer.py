"""
Resource optimizer — visibility into and control over VISION's OWN resource
footprint (as opposed to Tools/system_control.py's get_system_info, which
reports the whole machine).

This is deliberately scoped to VISION's own process tree: the main agent
process plus any child processes it spawns (the Playwright/Chromium browser
from web_automation.py shows up here automatically, since Playwright launches
it as a real child process of this one).
"""

import gc
import logging
import os

from livekit.agents import function_tool

logger = logging.getLogger(__name__)


def _bytes_to_mb(n: int) -> float:
    return round(n / (1024 * 1024), 1)


def _collect_process_tree_stats() -> dict:
    """Returns RSS memory + CPU% for this process and all its children."""
    import psutil

    root = psutil.Process(os.getpid())
    procs = [root] + root.children(recursive=True)

    total_rss = 0
    entries = []
    for p in procs:
        try:
            with p.oneshot():
                rss = p.memory_info().rss
                cpu = p.cpu_percent(interval=None)  # non-blocking; first call may read 0.0
                name = p.name()
            total_rss += rss
            entries.append({"pid": p.pid, "name": name, "rss_mb": _bytes_to_mb(rss), "cpu_pct": cpu})
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    entries.sort(key=lambda e: e["rss_mb"], reverse=True)
    return {"total_rss_mb": _bytes_to_mb(total_rss), "processes": entries}


@function_tool
async def get_vision_resource_usage() -> str:
    """
    Reports how much RAM and CPU VISION itself is currently using — the main
    process plus any child processes it has spawned (e.g. the browser
    automation Chromium instance, if one is open). Use this to answer
    "how much memory are you using" style questions, distinct from
    get_system_info which reports the whole machine.
    """
    try:
        stats = _collect_process_tree_stats()
        lines = [f"VISION is currently using {stats['total_rss_mb']} MB of RAM across {len(stats['processes'])} process(es):"]
        for e in stats["processes"][:8]:
            lines.append(f"• {e['name']} (pid {e['pid']}): {e['rss_mb']} MB, {e['cpu_pct']}% CPU")
        if len(stats["processes"]) > 8:
            lines.append(f"...and {len(stats['processes']) - 8} more minor process(es).")
        return "\n".join(lines)
    except Exception as e:
        return f"Couldn't read resource usage: {e}"


@function_tool
async def release_idle_resources() -> str:
    """
    Proactively frees up memory: closes the browser automation session if
    it's just sitting open idle, forces Python garbage collection, and
    reports how much memory was freed. Use this when asked to "free up
    memory" or "optimize performance" right now, rather than waiting for
    the automatic idle timeouts.
    """
    try:
        before = _collect_process_tree_stats()["total_rss_mb"]
    except Exception:
        before = None

    actions = []

    # Close the browser automation session if one is open (regardless of
    # its own idle timer — this is an explicit, immediate request).
    try:
        from Tools import web_automation
        if web_automation._browser is not None:
            await web_automation.close_browser()
            actions.append("closed the open browser automation session")
    except Exception as e:
        logger.warning(f"Could not check/close browser during release_idle_resources: {e}")

    # Stop gesture-control camera capture if it's running — it's a
    # continuous CPU/GPU cost that's only needed while actively gesturing.
    try:
        from Tools import webcam_guard
        if webcam_guard._camera_active:
            await webcam_guard.stop_webcam_guard()
            actions.append("stopped the gesture-control camera")
    except Exception as e:
        logger.warning(f"Could not check/stop webcam guard during release_idle_resources: {e}")

    gc.collect()
    actions.append("ran garbage collection")

    try:
        after = _collect_process_tree_stats()["total_rss_mb"]
    except Exception:
        after = None

    summary = "Freed up resources: " + ", ".join(actions) + "."
    if before is not None and after is not None:
        delta = round(before - after, 1)
        if delta > 0:
            summary += f" RAM usage dropped from {before} MB to {after} MB (freed about {delta} MB)."
        else:
            summary += f" RAM usage is now {after} MB (no significant change — nothing idle to release)."
    return summary
