"""
Advanced File System Operations & Organization Tools for VISION.
Supports searching, listing, opening, renaming, moving, copying, deleting, creating, and intelligent organizing.
"""

import os
import shutil
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional
from vision.tools.registry import tool
from vision.logger import logger


EXTENSION_CATEGORIES = {
    "Images": [".png", ".jpg", ".jpeg", ".gif", ".bmp", ".svg", ".webp", ".ico", ".tiff"],
    "Documents": [".pdf", ".docx", ".doc", ".txt", ".xlsx", ".xls", ".pptx", ".ppt", ".csv", ".md", ".rtf"],
    "Audio": [".mp3", ".wav", ".aac", ".flac", ".ogg", ".m4a", ".wma"],
    "Videos": [".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm"],
    "Archives": [".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".iso"],
    "Code_and_Scripts": [".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".css", ".json", ".yaml", ".yml", ".xml", ".sql", ".sh", ".bat", ".ps1", ".cpp", ".c", ".java", ".rs", ".go"],
    "Executables": [".exe", ".msi", ".dmg", ".pkg", ".apk", ".deb"]
}


@tool(name="list_files", description="List files and folders inside a given directory path with optional pattern filtering.")
def list_files(directory_path: str = ".", pattern: str = "*", recursive: bool = False) -> str:
    """List directory contents."""
    p = Path(directory_path).expanduser().resolve()
    if not p.exists():
        return f"Error: Directory '{directory_path}' does not exist."
    if not p.is_dir():
        return f"Error: Path '{directory_path}' is a file, not a directory."

    try:
        items = list(p.rglob(pattern) if recursive else p.glob(pattern))
        if not items:
            return f"No items found in '{p}' matching pattern '{pattern}'."

        lines = [f"Contents of '{p}' ({len(items)} items):"]
        for item in sorted(items[:100], key=lambda x: (not x.is_dir(), x.name.lower())):
            kind = "[DIR] " if item.is_dir() else "[FILE]"
            size_str = ""
            if item.is_file():
                size_kb = item.stat().st_size / 1024
                size_str = f" ({size_kb:.1f} KB)"
            lines.append(f"  {kind} {item.name}{size_str}")

        if len(items) > 100:
            lines.append(f"  ... and {len(items) - 100} more items.")
        return "\n".join(lines)
    except Exception as e:
        return f"Error listing directory: {e}"


@tool(name="find_files", description="Search for files across the system matching a keyword or name.")
def find_files(query: str, search_root: str = ".") -> str:
    """Search for files containing query string."""
    root = Path(search_root).expanduser().resolve()
    if not root.exists():
        return f"Error: Root path '{search_root}' does not exist."

    matches = []
    try:
        for p in root.rglob(f"*{query}*"):
            matches.append(str(p))
            if len(matches) >= 50:
                break
        if not matches:
            return f"No files or folders found matching '{query}' under '{root}'."
        return f"Found {len(matches)} matches for '{query}':\n" + "\n".join(f"- {m}" for m in matches)
    except Exception as e:
        return f"Error searching files: {e}"


@tool(name="open_file", description="Open any file or folder using the OS default application.")
def open_file(file_path: str) -> str:
    """Launch or open file with default handler."""
    p = Path(file_path).expanduser().resolve()
    if not p.exists():
        return f"Error: File '{file_path}' does not exist."

    try:
        if os.name == "nt":
            os.startfile(str(p))
        else:
            subprocess.Popen(["xdg-open" if os.name == "posix" else "open", str(p)])
        return f"Successfully opened '{p.name}' with default system application."
    except Exception as e:
        return f"Failed to open '{file_path}': {e}"


@tool(name="read_file_content", description="Read the text content of a file.")
def read_file_content(file_path: str, max_lines: int = 100) -> str:
    """Read file content."""
    p = Path(file_path).expanduser().resolve()
    if not p.exists():
        return f"Error: File '{file_path}' does not exist."
    if p.is_dir():
        return f"Error: '{file_path}' is a directory. Use list_files instead."

    try:
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            lines = [f.readline() for _ in range(max_lines)]
        content = "".join(lines)
        return f"Content of '{p.name}' (first {len(lines)} lines):\n\n{content}"
    except Exception as e:
        return f"Error reading file '{file_path}': {e}"


@tool(name="rename_file", description="Rename a file or directory.")
def rename_file(source_path: str, new_name: str) -> str:
    """Rename a file or folder."""
    src = Path(source_path).expanduser().resolve()
    if not src.exists():
        return f"Error: Source '{source_path}' does not exist."

    dst = src.parent / new_name if not os.path.isabs(new_name) else Path(new_name).expanduser().resolve()
    try:
        src.rename(dst)
        return f"Successfully renamed '{src.name}' to '{dst.name}'."
    except Exception as e:
        return f"Error renaming file: {e}"


@tool(name="move_file", description="Move a file or directory to a new target directory or path.")
def move_file(source_path: str, destination_dir: str) -> str:
    """Move file or folder."""
    src = Path(source_path).expanduser().resolve()
    dst = Path(destination_dir).expanduser().resolve()

    if not src.exists():
        return f"Error: Source '{source_path}' does not exist."

    try:
        dst.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        return f"Successfully moved '{src.name}' to '{dst}'."
    except Exception as e:
        return f"Error moving file: {e}"


@tool(name="copy_file", description="Copy a file or directory to a destination path.")
def copy_file(source_path: str, destination_path: str) -> str:
    """Copy file or folder."""
    src = Path(source_path).expanduser().resolve()
    dst = Path(destination_path).expanduser().resolve()

    if not src.exists():
        return f"Error: Source '{source_path}' does not exist."

    try:
        if src.is_dir():
            shutil.copytree(str(src), str(dst), dirs_exist_ok=True)
        else:
            if dst.is_dir():
                shutil.copy2(str(src), str(dst))
            else:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(src), str(dst))
        return f"Successfully copied '{src.name}' to '{dst}'."
    except Exception as e:
        return f"Error copying file: {e}"


@tool(name="delete_file", description="Delete a file or empty folder.")
def delete_file(file_path: str) -> str:
    """Delete a file or directory."""
    p = Path(file_path).expanduser().resolve()
    if not p.exists():
        return f"Error: File '{file_path}' does not exist."

    try:
        if p.is_dir():
            shutil.rmtree(str(p))
            return f"Successfully deleted directory '{p.name}' and all contents."
        else:
            p.unlink()
            return f"Successfully deleted file '{p.name}'."
    except Exception as e:
        return f"Error deleting file: {e}"


@tool(name="create_folder", description="Create a new folder / directory structure.")
def create_folder(folder_path: str) -> str:
    """Create directory."""
    p = Path(folder_path).expanduser().resolve()
    try:
        p.mkdir(parents=True, exist_ok=True)
        return f"Successfully created folder '{p}'."
    except Exception as e:
        return f"Error creating folder: {e}"


@tool(name="organize_directory", description="Intelligently sort and organize all files in a directory into category subfolders (Images, Documents, Videos, Archives, Code, etc.).")
def organize_directory(directory_path: str) -> str:
    """Auto-organize loose files in a folder into tidy category subfolders."""
    target_dir = Path(directory_path).expanduser().resolve()
    if not target_dir.exists() or not target_dir.is_dir():
        return f"Error: Directory '{directory_path}' does not exist or is not a directory."

    moved_counts: Dict[str, int] = {}
    total_moved = 0

    try:
        for item in list(target_dir.iterdir()):
            if item.is_file():
                ext = item.suffix.lower()
                target_category = "Other"

                for category, extensions in EXTENSION_CATEGORIES.items():
                    if ext in extensions:
                        target_category = category
                        break

                category_folder = target_dir / target_category
                category_folder.mkdir(exist_ok=True)

                dest_file = category_folder / item.name
                if dest_file.exists():
                    dest_file = category_folder / f"{item.stem}_copy{item.suffix}"

                shutil.move(str(item), str(dest_file))
                moved_counts[target_category] = moved_counts.get(target_category, 0) + 1
                total_moved += 1

        if total_moved == 0:
            return f"No loose files needed organizing in '{target_dir}'."

        summary = [f"Successfully organized {total_moved} files in '{target_dir.name}':"]
        for cat, count in moved_counts.items():
            summary.append(f"  - {cat}: {count} files")
        return "\n".join(summary)
    except Exception as e:
        return f"Error during organization: {e}"
