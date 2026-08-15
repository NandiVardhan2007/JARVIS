"""
Zip & Archive Management Tools for VISION AI OS.
Allows VISION to compress folders into ZIP archives and extract ZIP/TAR files.
"""

import os
import shutil
import zipfile
import tarfile
from pathlib import Path
from typing import Optional
from vision.tools.registry import tool
from vision.logger import logger
from vision.tools.file_tools import _resolve_user_path


@tool(name="compress_to_zip", description="Compress a folder or file into a ZIP archive in Downloads, Desktop, or a target directory.")
def compress_to_zip(source_path: str, output_zip_name: Optional[str] = None, destination_folder: str = "Downloads") -> str:
    """Creates a ZIP archive from a folder or file."""
    if not source_path:
        return "Error: Source folder/file path is required."

    src = _resolve_user_path(source_path, find_existing_file=True)
    if not src.exists():
        return f"Error: Source path '{source_path}' does not exist."

    dest_dir = _resolve_user_path(destination_folder, find_existing_file=False)
    dest_dir.mkdir(parents=True, exist_ok=True)

    zip_name = output_zip_name or f"{src.name}.zip"
    if not zip_name.endswith(".zip"):
        zip_name += ".zip"

    out_zip = dest_dir / zip_name
    logger.info(f"[ArchiveTool] Compressing '{src}' -> '{out_zip}'...")

    try:
        with zipfile.ZipFile(out_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
            if src.is_file():
                zipf.write(src, arcname=src.name)
            else:
                for root, dirs, files in os.walk(src):
                    for file in files:
                        full_p = Path(root) / file
                        arcname = full_p.relative_to(src)
                        zipf.write(full_p, arcname=arcname)

        size_kb = round(out_zip.stat().st_size / 1024, 1)
        logger.info(f"[ArchiveTool] Successfully created '{zip_name}' ({size_kb} KB)")
        return f"Successfully created ZIP archive '{zip_name}' ({size_kb} KB) in '{dest_dir}'."
    except Exception as e:
        logger.error(f"[ArchiveTool] Compression failed: {e}")
        return f"Failed to compress archive: {e}"


@tool(name="extract_zip_archive", description="Extract a ZIP, TAR, or GZ archive file into a folder.")
def extract_zip_archive(zip_path: str, extract_to_folder: Optional[str] = None) -> str:
    """Extracts a compressed archive to a destination folder."""
    if not zip_path:
        return "Error: Archive file path is required."

    arc = _resolve_user_path(zip_path, find_existing_file=True)
    if not arc.exists() or not arc.is_file():
        return f"Error: Archive file '{zip_path}' does not exist."

    # Destination folder
    if extract_to_folder:
        out_dir = _resolve_user_path(extract_to_folder, find_existing_file=False)
    else:
        out_dir = arc.parent / arc.stem

    out_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"[ArchiveTool] Extracting '{arc}' -> '{out_dir}'...")

    try:
        if zipfile.is_zipfile(arc):
            with zipfile.ZipFile(arc, 'r') as zipf:
                zipf.extractall(out_dir)
            extracted_count = len(list(out_dir.rglob("*")))
            logger.info(f"[ArchiveTool] Extracted {extracted_count} items from ZIP.")
            return f"Successfully extracted {extracted_count} items from '{arc.name}' to '{out_dir}'."
        elif tarfile.is_tarfile(arc):
            with tarfile.open(arc, 'r:*') as tarf:
                tarf.extractall(out_dir)
            extracted_count = len(list(out_dir.rglob("*")))
            return f"Successfully extracted {extracted_count} items from TAR archive to '{out_dir}'."
        else:
            return f"Error: Unsupported archive format for '{arc.name}'."
    except Exception as e:
        logger.error(f"[ArchiveTool] Extraction failed: {e}")
        return f"Failed to extract archive: {e}"
