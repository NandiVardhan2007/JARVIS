"""
Intelligent File Management.

Distinct from Tools/file_ops.py (basic create/copy/move/delete/single-folder
search): this module understands requests like "find my resume", "show
screenshots from last week", or "organize my downloads" — searching across
all the user's common folders at once, filtering by file kind and by
modified-date range, suggesting (but never silently applying) folder
reorganizations, and finding duplicate files.

Deletion policy: nothing in this module ever permanently deletes anything.
Bulk moves during organization are fully reversible (files are moved, not
deleted) and require confirm=True. Duplicate cleanup goes through send2trash
(recoverable) and also requires confirm=True plus a live voice re-check,
consistent with delete_path in file_ops.py.
"""

import hashlib
import logging
import os
import shutil
import time
from datetime import datetime, timedelta
from typing import Optional

from livekit.agents import function_tool
from Tools.voice_verification import requires_live_master_voice

logger = logging.getLogger(__name__)

HOME = os.path.expanduser("~")

SEARCH_DIRS = {
    "desktop":   os.path.join(HOME, "Desktop"),
    "documents": os.path.join(HOME, "Documents"),
    "downloads": os.path.join(HOME, "Downloads"),
    "pictures":  os.path.join(HOME, "Pictures"),
    "music":     os.path.join(HOME, "Music"),
    "videos":    os.path.join(HOME, "Videos"),
}

# Directories never worth walking into — hidden/system/dev-tooling clutter
_SKIP_DIR_NAMES = {
    ".git", ".cache", "__pycache__", "node_modules", ".venv", "venv",
    ".npm", ".local", "jarvis_memory", ".config",
}

_KIND_EXTENSIONS = {
    "image":    {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg", ".heic", ".tiff"},
    "video":    {".mp4", ".mov", ".mkv", ".avi", ".webm", ".flv", ".m4v"},
    "music":    {".mp3", ".wav", ".flac", ".m4a", ".ogg", ".aac"},
    "document": {".pdf", ".doc", ".docx", ".txt", ".odt", ".rtf", ".xlsx", ".xls", ".pptx", ".ppt", ".csv", ".md"},
    "archive":  {".zip", ".tar", ".gz", ".7z", ".rar", ".xz"},
    "installer": {".deb", ".rpm", ".appimage", ".run"},
}

MAX_FILES_SCANNED = 30000
MAX_RESULTS = 50


def _is_screenshot(filename: str) -> bool:
    f = filename.lower()
    return "screenshot" in f or "screen shot" in f or f.startswith("scrot")


def _iter_files(root_dirs, max_scanned=MAX_FILES_SCANNED):
    """Yields (path, stat) for files under root_dirs, skipping clutter directories."""
    scanned = 0
    for root_dir in root_dirs:
        if not os.path.isdir(root_dir):
            continue
        for dirpath, dirnames, filenames in os.walk(root_dir):
            dirnames[:] = [d for d in dirnames if d not in _SKIP_DIR_NAMES and not d.startswith(".")]
            for fname in filenames:
                if fname.startswith("."):
                    continue
                full = os.path.join(dirpath, fname)
                try:
                    st = os.stat(full)
                except OSError:
                    continue
                yield full, st
                scanned += 1
                if scanned >= max_scanned:
                    return


def _parse_when(when: str) -> Optional[tuple]:
    """Parses a natural-language relative date range into (start, end) datetimes, based on file modified time."""
    if not when:
        return None
    w = when.strip().lower()
    now = datetime.now()
    today_start = datetime(now.year, now.month, now.day)

    if w in ("today",):
        return today_start, now
    if w in ("yesterday",):
        return today_start - timedelta(days=1), today_start
    if w in ("this week",):
        start = today_start - timedelta(days=today_start.weekday())
        return start, now
    if w in ("last week",):
        this_week_start = today_start - timedelta(days=today_start.weekday())
        return this_week_start - timedelta(days=7), this_week_start
    if w in ("this month",):
        return datetime(now.year, now.month, 1), now
    if w in ("last month",):
        first_of_this_month = datetime(now.year, now.month, 1)
        last_month_end = first_of_this_month
        # step back one day into last month, then to its 1st
        last_day_prev = first_of_this_month - timedelta(days=1)
        return datetime(last_day_prev.year, last_day_prev.month, 1), last_month_end

    import re
    m = re.match(r"last (\d+) days?", w)
    if m:
        n = int(m.group(1))
        return now - timedelta(days=n), now

    return None


@function_tool
async def bulk_rename_files(
    folder: str,
    mode: str = "find_replace",
    find: str = "",
    replace: str = "",
    prefix: str = "",
    suffix: str = "",
    numbered_base: str = "",
    dry_run: bool = True,
    confirm: bool = False,
) -> str:
    """
    Renames multiple files in a folder at once. Always shows a preview
    (dry_run) before actually renaming, and refuses to proceed if any
    planned rename would overwrite an existing file — nothing is ever
    silently clobbered.

    Args:
        folder: Folder whose files should be renamed — "downloads",
            "pictures", "documents", etc., or an absolute path.
        mode: "find_replace" (replace `find` with `replace` in each
            filename), "add_prefix" (prepend `prefix`), "add_suffix"
            (append `suffix` before the extension), or "numbered_sequence"
            (rename to "{numbered_base} 001.ext", "{numbered_base} 002.ext", ...
            in current name order).
        find: Substring to find (find_replace mode only).
        replace: Replacement text (find_replace mode only).
        prefix: Text to prepend (add_prefix mode only).
        suffix: Text to append before the extension (add_suffix mode only).
        numbered_base: Base name for numbered_sequence mode, e.g. "Vacation Photo".
        dry_run: If True (default), only shows the rename plan — nothing is renamed.
        confirm: Must be True to actually rename (ignored if dry_run is True).
    """
    folder_lower = folder.strip().lower()
    target = SEARCH_DIRS.get(folder_lower, os.path.expanduser(folder))
    if not os.path.isdir(target):
        return f"'{target}' is not a valid directory."

    files = sorted(f for f in os.listdir(target) if os.path.isfile(os.path.join(target, f)) and not f.startswith("."))
    if not files:
        return f"'{target}' has no files to rename."

    plan = []
    if mode == "find_replace":
        if not find:
            return "find_replace mode requires a non-empty 'find' value."
        for f in files:
            new_name = f.replace(find, replace)
            if new_name != f:
                plan.append((f, new_name))
    elif mode == "add_prefix":
        if not prefix:
            return "add_prefix mode requires a non-empty 'prefix' value."
        for f in files:
            if not f.startswith(prefix):
                plan.append((f, prefix + f))
    elif mode == "add_suffix":
        if not suffix:
            return "add_suffix mode requires a non-empty 'suffix' value."
        for f in files:
            base, ext = os.path.splitext(f)
            if not base.endswith(suffix):
                plan.append((f, base + suffix + ext))
    elif mode == "numbered_sequence":
        base_name = numbered_base.strip() or "file"
        width = max(3, len(str(len(files))))
        for i, f in enumerate(files, 1):
            ext = os.path.splitext(f)[1]
            new_name = f"{base_name} {str(i).zfill(width)}{ext}"
            if new_name != f:
                plan.append((f, new_name))
    else:
        return f"Unknown mode '{mode}'. Use find_replace, add_prefix, add_suffix, or numbered_sequence."

    if not plan:
        return f"No files in '{target}' need renaming under mode '{mode}'."

    # Collision safety: check the full planned rename set before touching anything.
    existing = set(files)
    new_names_in_plan = set()
    for old, new in plan:
        if new in existing and new not in dict(plan):
            return f"Refusing to rename — '{new}' already exists and isn't part of this rename batch."
        if new in new_names_in_plan:
            return f"Refusing to rename — two files would both become '{new}'. Adjust the pattern and try again."
        new_names_in_plan.add(new)

    if dry_run or not confirm:
        lines = [f"Rename plan for '{target}' ({len(plan)} file(s)) — dry run, nothing renamed yet:"]
        for old, new in plan[:20]:
            lines.append(f"  {old}  →  {new}")
        if len(plan) > 20:
            lines.append(f"  ...and {len(plan) - 20} more.")
        lines.append("\nCall again with dry_run=False and confirm=True to actually rename these files.")
        return "\n".join(lines)

    renamed, errors = 0, []
    for old, new in plan:
        try:
            os.rename(os.path.join(target, old), os.path.join(target, new))
            renamed += 1
        except Exception as e:
            errors.append(f"{old}: {e}")

    summary = f"Renamed {renamed} file(s) in '{target}'."
    if errors:
        summary += f"\n{len(errors)} rename(s) failed:\n" + "\n".join(errors[:5])
    return summary


@function_tool
async def smart_find_files(
    query: str = "",
    kind: Optional[str] = None,
    when: Optional[str] = None,
    folder: Optional[str] = None,
) -> str:
    """
    Finds files across all common folders (Desktop, Documents, Downloads,
    Pictures, Music, Videos) using natural-language style filters — this is
    what handles requests like "find my resume", "show screenshots from
    last week", or "any PDFs I downloaded yesterday".

    Args:
        query: Filename keyword to match (e.g. "resume"). Leave empty to
            match all files of the given kind/date instead.
        kind: Optional file category to filter by: "image", "video", "music",
            "document", "archive", "installer", or "screenshot" (a special
            case of image — filenames containing "screenshot").
        when: Optional relative date range based on last-modified time:
            "today", "yesterday", "this week", "last week", "this month",
            "last month", or "last N days".
        folder: Optional single folder to restrict the search to (e.g.
            "downloads", "documents", or an absolute path). Defaults to
            searching all common folders at once.
    """
    if folder:
        folder_lower = folder.strip().lower()
        search_root = [SEARCH_DIRS.get(folder_lower, os.path.expanduser(folder))]
    else:
        search_root = list(SEARCH_DIRS.values())

    date_range = _parse_when(when) if when else None
    want_screenshot = (kind or "").strip().lower() == "screenshot"
    kind_exts = _KIND_EXTENSIONS.get((kind or "").strip().lower())

    matches = []
    for path, st in _iter_files(search_root):
        fname = os.path.basename(path)
        ext = os.path.splitext(fname)[1].lower()

        if query and query.lower() not in fname.lower():
            continue
        if want_screenshot and not _is_screenshot(fname):
            continue
        elif kind_exts and ext not in kind_exts:
            continue
        if date_range:
            mtime = datetime.fromtimestamp(st.st_mtime)
            if not (date_range[0] <= mtime <= date_range[1]):
                continue

        matches.append((path, st.st_mtime, st.st_size))
        if len(matches) >= MAX_RESULTS:
            break

    if not matches:
        desc = " matching your criteria"
        return f"No files found{desc}."

    matches.sort(key=lambda m: m[1], reverse=True)
    lines = [f"Found {len(matches)} file(s):"]
    for path, mtime, size in matches:
        size_str = f"{size / (1024*1024):.1f} MB" if size > 1024 * 1024 else f"{size / 1024:.0f} KB"
        date_str = datetime.fromtimestamp(mtime).strftime("%b %d, %Y")
        lines.append(f"• {path} ({size_str}, modified {date_str})")
    return "\n".join(lines)


@function_tool
async def organize_folder(folder: str = "downloads", dry_run: bool = True, confirm: bool = False) -> str:
    """
    Organizes a folder by moving files into subfolders by type (Images,
    Videos, Music, Documents, Archives, Installers, Other). Files are always
    MOVED, never deleted — fully reversible.

    Args:
        folder: Folder to organize — "downloads", "desktop", "documents",
            "pictures", "music", "videos", or an absolute path. Defaults to Downloads.
        dry_run: If True (default), only shows the plan without moving anything.
        confirm: Must be True to actually perform the moves (ignored if dry_run is True).
    """
    folder_lower = folder.strip().lower()
    target = SEARCH_DIRS.get(folder_lower, os.path.expanduser(folder))

    if not os.path.isdir(target):
        return f"'{target}' is not a valid directory."

    plan: dict[str, list[str]] = {}
    for fname in os.listdir(target):
        full = os.path.join(target, fname)
        if not os.path.isfile(full) or fname.startswith("."):
            continue
        ext = os.path.splitext(fname)[1].lower()
        category = "Other"
        for cat, exts in _KIND_EXTENSIONS.items():
            if ext in exts:
                category = cat.capitalize() + ("s" if not cat.endswith("s") else "")
                break
        plan.setdefault(category, []).append(fname)

    if not plan:
        return f"'{target}' has no loose files to organize."

    if dry_run or not confirm:
        lines = [f"Organization plan for '{target}' (dry run — nothing moved yet):"]
        for category, files in sorted(plan.items()):
            lines.append(f"• {category}/ ← {len(files)} file(s)")
        lines.append("\nCall again with dry_run=False and confirm=True to actually move these files.")
        return "\n".join(lines)

    moved = 0
    errors = []
    for category, files in plan.items():
        dest_dir = os.path.join(target, category)
        os.makedirs(dest_dir, exist_ok=True)
        for fname in files:
            src = os.path.join(target, fname)
            dst = os.path.join(dest_dir, fname)
            try:
                if os.path.exists(dst):
                    base, ext = os.path.splitext(fname)
                    dst = os.path.join(dest_dir, f"{base}_{int(time.time())}{ext}")
                shutil.move(src, dst)
                moved += 1
            except Exception as e:
                errors.append(f"{fname}: {e}")

    summary = f"Organized '{target}': moved {moved} file(s) into {len(plan)} categor{'y' if len(plan)==1 else 'ies'}."
    if errors:
        summary += f"\n{len(errors)} file(s) couldn't be moved:\n" + "\n".join(errors[:5])
    return summary


@function_tool
async def suggest_folder_structure(folder: str = "downloads") -> str:
    """
    Analyzes a folder's contents and suggests a better folder structure —
    purely advisory, makes no changes. Use organize_folder to actually apply
    a type-based reorganization.

    Args:
        folder: Folder to analyze — "downloads", "desktop", "documents", etc., or an absolute path.
    """
    folder_lower = folder.strip().lower()
    target = SEARCH_DIRS.get(folder_lower, os.path.expanduser(folder))
    if not os.path.isdir(target):
        return f"'{target}' is not a valid directory."

    files = [f for f in os.listdir(target) if os.path.isfile(os.path.join(target, f)) and not f.startswith(".")]
    if not files:
        return f"'{target}' has no loose files — no reorganization needed."

    by_ext: dict[str, int] = {}
    for f in files:
        ext = os.path.splitext(f)[1].lower() or "(no extension)"
        by_ext[ext] = by_ext.get(ext, 0) + 1

    total = len(files)
    top_exts = sorted(by_ext.items(), key=lambda kv: kv[1], reverse=True)[:6]

    suggestions = [f"'{target}' has {total} loose file(s). Breakdown by type:"]
    for ext, count in top_exts:
        suggestions.append(f"  {ext}: {count}")

    suggestions.append("")
    if total > 30:
        suggestions.append(
            "This folder has enough loose files that a type-based structure "
            "(Images/, Documents/, Videos/, Archives/, Installers/, Other/) would help — "
            "I can do this with organize_folder."
        )
    screenshots = sum(1 for f in files if _is_screenshot(f))
    if screenshots > 5:
        suggestions.append(f"There are {screenshots} screenshots mixed in — a dedicated Screenshots/ subfolder would help.")
    old_installers = sum(1 for f in files if os.path.splitext(f)[1].lower() in _KIND_EXTENSIONS["installer"])
    if old_installers > 0:
        suggestions.append(f"There are {old_installers} installer file(s) (.deb/.rpm/.AppImage) — these are usually safe to remove once installed.")

    return "\n".join(suggestions)


def _quick_hash(path: str, size: int, sample_bytes: int = 65536) -> str:
    """Fast pre-filter hash: file size + a small sample from start/end (not a full read)."""
    h = hashlib.sha256()
    h.update(str(size).encode())
    try:
        with open(path, "rb") as f:
            h.update(f.read(sample_bytes))
            if size > sample_bytes * 2:
                f.seek(-sample_bytes, os.SEEK_END)
                h.update(f.read(sample_bytes))
    except OSError:
        pass
    return h.hexdigest()


def _full_hash(path: str) -> str:
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
    except OSError:
        pass
    return h.hexdigest()


@function_tool
async def find_duplicate_files(folder: str = "downloads") -> str:
    """
    Finds duplicate files (identical content) within a folder. Report only —
    does not delete anything. Use delete_duplicate_files with specific paths
    to actually clean them up.

    Args:
        folder: Folder to scan — "downloads", "pictures", "documents", etc., or an absolute path.
    """
    folder_lower = folder.strip().lower()
    target = SEARCH_DIRS.get(folder_lower, os.path.expanduser(folder))
    if not os.path.isdir(target):
        return f"'{target}' is not a valid directory."

    # Pass 1: group by size (cheap) — only sizes with >1 file are candidates
    by_size: dict[int, list[str]] = {}
    for path, st in _iter_files([target]):
        if st.st_size == 0:
            continue
        by_size.setdefault(st.st_size, []).append(path)

    candidates = [paths for paths in by_size.values() if len(paths) > 1]
    if not candidates:
        return f"No duplicate files found in '{target}'."

    # Pass 2: quick hash to narrow down, Pass 3: full hash to confirm
    dup_groups: list[list[str]] = []
    for paths in candidates:
        by_quick: dict[str, list[str]] = {}
        for p in paths:
            size = os.path.getsize(p)
            by_quick.setdefault(_quick_hash(p, size), []).append(p)
        for quick_group in by_quick.values():
            if len(quick_group) < 2:
                continue
            by_full: dict[str, list[str]] = {}
            for p in quick_group:
                by_full.setdefault(_full_hash(p), []).append(p)
            for full_group in by_full.values():
                if len(full_group) > 1:
                    dup_groups.append(full_group)

    if not dup_groups:
        return f"No duplicate files found in '{target}'."

    wasted_bytes = sum(os.path.getsize(g[0]) * (len(g) - 1) for g in dup_groups)
    lines = [f"Found {len(dup_groups)} set(s) of duplicate files in '{target}' (~{wasted_bytes / (1024*1024):.1f} MB wasted):"]
    for i, group in enumerate(dup_groups[:15], 1):
        lines.append(f"\nSet {i} ({len(group)} copies):")
        for p in group:
            lines.append(f"  • {p}")
    if len(dup_groups) > 15:
        lines.append(f"\n...and {len(dup_groups) - 15} more set(s).")
    lines.append("\nTo clean these up, tell me which copies to keep and I'll send the rest to the recycle bin with delete_duplicate_files.")
    return "\n".join(lines)


@function_tool
@requires_live_master_voice()
async def delete_duplicate_files(paths_to_delete: list[str], confirm: bool = False) -> str:
    """
    Sends specific duplicate files to the recycle bin (reversible, never a
    permanent delete). Use find_duplicate_files first to identify which
    paths are safe to remove, and confirm with the user which copies to
    keep before calling this.

    Args:
        paths_to_delete: Absolute paths of the duplicate files to remove (keep at least one copy of each set!).
        confirm: Must be explicitly True — nothing is deleted until you call again with confirm=True.
    """
    if not confirm:
        return f"NOT deleted. Confirm with the user first, then call again with confirm=True for these {len(paths_to_delete)} file(s)."

    import send2trash
    removed, errors = 0, []
    for p in paths_to_delete:
        try:
            if os.path.isfile(p):
                send2trash.send2trash(p)
                removed += 1
        except Exception as e:
            errors.append(f"{p}: {e}")

    summary = f"Sent {removed} duplicate file(s) to the recycle bin."
    if errors:
        summary += f"\n{len(errors)} couldn't be removed:\n" + "\n".join(errors[:5])
    return summary
