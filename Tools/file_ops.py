"""Smart file and folder opener — understands natural language commands."""

import logging
import os
import subprocess
import shutil
import send2trash
from pathlib import Path
from livekit.agents import function_tool

logger = logging.getLogger(__name__)

FOLDER_SHORTCUTS = {
    "desktop":   os.path.expanduser("~/Desktop"),
    "documents": os.path.expanduser("~/Documents"),
    "downloads": os.path.expanduser("~/Downloads"),
    "pictures":  os.path.expanduser("~/Pictures"),
    "music":     os.path.expanduser("~/Music"),
    "videos":    os.path.expanduser("~/Videos"),
}


def _open(path: str) -> bool:
    try:
        if os.name == "nt":
            os.startfile(path)
        else:
            subprocess.Popen(["xdg-open", path])
        return True
    except Exception:
        return False

def _resolve_path(p: str) -> str:
    if not p:
        return p
    p_lower = p.lower().strip()
    if p_lower in FOLDER_SHORTCUTS:
        return FOLDER_SHORTCUTS[p_lower]
    # expand user dir (~/)
    return os.path.expanduser(p)


@function_tool
async def open_file_command(user_command: str) -> str:
    """
    Opens a file or folder using a natural language command.

    Args:
        user_command: Natural language instruction such as:
            - "Open report.pdf"
            - "Open data.xlsx from documents"
            - "Open Downloads folder"
            - "Show me my Desktop"
    """
    logger.info(f"File command: {user_command}")
    cmd = user_command.lower().strip()

    if not cmd:
        return (
            "Please tell me which file or folder to open. For example:\n"
            "• 'Open report.pdf'\n"
            "• 'Open data.xlsx from Documents'\n"
            "• 'Open Desktop folder'"
        )

    # Detect location keyword
    location = next((FOLDER_SHORTCUTS[k] for k in FOLDER_SHORTCUTS if k in cmd), None)

    # If just a location is requested with no specific file
    location_only = any(
        f"open {k}" in cmd or f"show {k}" in cmd or f"go to {k}" in cmd
        for k in FOLDER_SHORTCUTS
    )
    if location_only and location:
        if _open(location):
            return f"Opened {location}."
        return f"Could not open {location}."

    # Strip command words to isolate the filename
    filename = user_command
    for word in ["open", "show me", "show", "launch", "find", "from", "on",
                 "in", "the", "file", "folder", "me"]:
        filename = filename.lower().replace(word, "")
    for k in FOLDER_SHORTCUTS:
        filename = filename.replace(k, "")
    filename = filename.strip(" .,/\\")

    if not filename:
        if location and _open(location):
            return f"Opened {location}."
        return "I could not determine which file to open. Please be more specific."

    # Search for the file/folder
    search_dirs = [location] if location else list(FOLDER_SHORTCUTS.values())
    search_dirs.append(os.path.expanduser("~"))

    for search_dir in search_dirs:
        if not os.path.isdir(search_dir):
            continue
        for root, dirs, files in os.walk(search_dir):
            for f in files:
                if filename.lower() in f.lower():
                    full = os.path.join(root, f)
                    if _open(full):
                        return f"Opened '{f}' from {root}."
            for d in dirs:
                if filename.lower() in d.lower():
                    full = os.path.join(root, d)
                    if _open(full):
                        return f"Opened folder '{d}'."

    # Direct path attempt
    if os.path.exists(filename) and _open(filename):
        return f"Opened '{filename}'."
    return f"Could not find '{filename}'. Please check the name or location and try again."


@function_tool
async def list_directory(path: str) -> str:
    """Lists all files and folders in a given directory path."""
    try:
        path = _resolve_path(path)
        if not os.path.isdir(path):
            return f"Error: '{path}' is not a valid directory."
        
        entries = os.listdir(path)
        if not entries:
            return f"The directory '{path}' is empty."
            
        result = [f"Contents of {path}:"]
        for entry in sorted(entries):
            full_path = os.path.join(path, entry)
            if os.path.isdir(full_path):
                result.append(f"📁 {entry}/")
            else:
                size = os.path.getsize(full_path)
                result.append(f"📄 {entry} ({size} bytes)")
        return "\n".join(result)
    except Exception as e:
        return f"Failed to list directory: {str(e)}"


@function_tool
async def search_files(query: str, path: str = None) -> str:
    """Searches for files matching a keyword recursively in a directory. If path is None, defaults to Documents."""
    if not path:
        path = FOLDER_SHORTCUTS.get("documents", os.path.expanduser("~"))
    else:
        path = _resolve_path(path)
        
    try:
        if not os.path.isdir(path):
            return f"Error: '{path}' is not a valid directory."
            
        matches = []
        for root, dirs, files in os.walk(path):
            for filename in files:
                if query.lower() in filename.lower():
                    matches.append(os.path.join(root, filename))
            # Limit search results to avoid massive context
            if len(matches) > 50:
                matches.append("... (more than 50 results found, truncating)")
                break
                
        if not matches:
            return f"No files found matching '{query}' in '{path}'."
        return f"Found {len(matches)} files matching '{query}':\n" + "\n".join(matches)
    except Exception as e:
        return f"Failed to search files: {str(e)}"


@function_tool
async def create_file(path: str, content: str = "") -> str:
    """Creates a new text file at the given path with optional content."""
    try:
        path = _resolve_path(path)
        # Create directories if they don't exist
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        return f"Successfully created file at '{path}'."
    except Exception as e:
        return f"Failed to create file: {str(e)}"


@function_tool
async def create_folder(path: str) -> str:
    """Creates a new folder/directory."""
    try:
        path = _resolve_path(path)
        os.makedirs(path, exist_ok=True)
        return f"Successfully created folder at '{path}'."
    except Exception as e:
        return f"Failed to create folder: {str(e)}"


@function_tool
async def copy_file_or_folder(source: str, destination: str) -> str:
    """Copies a file or directory to a new location."""
    try:
        source = _resolve_path(source)
        destination = _resolve_path(destination)
        if not os.path.exists(source):
            return f"Error: Source '{source}' does not exist."
            
        if os.path.isdir(source):
            shutil.copytree(source, destination, dirs_exist_ok=True)
            return f"Successfully copied folder to '{destination}'."
        else:
            os.makedirs(os.path.dirname(os.path.abspath(destination)), exist_ok=True)
            shutil.copy2(source, destination)
            return f"Successfully copied file to '{destination}'."
    except Exception as e:
        return f"Failed to copy: {str(e)}"


@function_tool
async def move_or_rename_path(source: str, destination: str) -> str:
    """Moves or renames a file or directory."""
    try:
        source = _resolve_path(source)
        destination = _resolve_path(destination)
        if not os.path.exists(source):
            return f"Error: Source '{source}' does not exist."
            
        os.makedirs(os.path.dirname(os.path.abspath(destination)), exist_ok=True)
        shutil.move(source, destination)
        return f"Successfully moved/renamed to '{destination}'."
    except Exception as e:
        return f"Failed to move/rename: {str(e)}"


@function_tool
async def delete_path(path: str) -> str:
    """Deletes a file or directory permanently."""
    try:
        path = _resolve_path(path)
        if not os.path.exists(path):
            return f"Error: '{path}' does not exist."
            
        send2trash.send2trash(path)
        
        if os.path.isdir(path):
            return f"Successfully sent folder '{path}' to the recycle bin."
        else:
            return f"Successfully sent file '{path}' to the recycle bin."
    except Exception as e:
        return f"Failed to delete: {str(e)}"


@function_tool
async def read_text_file(path: str) -> str:
    """Reads and returns the contents of a text file."""
    try:
        path = _resolve_path(path)
        if not os.path.isfile(path):
            return f"Error: '{path}' is not a valid file."
            
        # Check size to prevent huge outputs
        size = os.path.getsize(path)
        if size > 1024 * 1024: # 1MB limit
            return f"Error: File is too large to read ({size} bytes). Max is 1MB."
            
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        return f"Contents of {path}:\n\n{content}"
    except UnicodeDecodeError:
        return f"Error: '{path}' appears to be a binary file and cannot be read as text."
    except Exception as e:
        return f"Failed to read file: {str(e)}"

@function_tool
async def edit_file_diff(file_path: str, target_content: str, replacement_content: str) -> str:
    """
    Edits a file by replacing a specific block of text (target_content) with new text (replacement_content).
    This is highly preferred over rewriting entire files for minor changes.
    
    Args:
        file_path: Absolute or relative path to the file to edit.
        target_content: The EXACT string in the file to be replaced (including exact indentation).
        replacement_content: The new text that will replace target_content.
    """
    try:
        path = _resolve_path(file_path)
        if not os.path.isfile(path):
            return f"Error: '{path}' does not exist or is not a file."
            
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        if target_content not in content:
            return (
                f"Error: The target_content was not found exactly as provided in '{path}'. "
                "Ensure your indentation and line breaks perfectly match the source file."
            )
            
        if content.count(target_content) > 1:
            return (
                f"Error: The target_content appears {content.count(target_content)} times in '{path}'. "
                "Please provide a larger, more unique target_content block to ensure the correct code is replaced."
            )
            
        new_content = content.replace(target_content, replacement_content)
        
        with open(path, 'w', encoding='utf-8') as f:
            f.write(new_content)
            
        return f"Successfully updated '{path}'. The code block was replaced."
    except Exception as e:
        return f"Failed to edit file: {str(e)}"
