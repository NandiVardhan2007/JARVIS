"""
Unit tests for Smart Downloads & Desktop Auto-Organizer in VISION AI OS.
"""

import pytest
import shutil
from pathlib import Path
from vision.tools.file_tools import (
    organize_directory,
    organize_downloads,
    organize_desktop,
    clean_empty_directories
)


@pytest.fixture
def temp_messy_dir(tmp_path):
    """Creates a temporary folder with mixed loose files and an empty subfolder."""
    messy = tmp_path / "messy_folder"
    messy.mkdir()

    # Create mixed files
    (messy / "document.pdf").write_text("dummy pdf", encoding="utf-8")
    (messy / "photo.png").write_text("dummy image", encoding="utf-8")
    (messy / "song.mp3").write_text("dummy audio", encoding="utf-8")
    (messy / "archive.zip").write_text("dummy zip", encoding="utf-8")
    (messy / "script.py").write_text("print(1)", encoding="utf-8")
    (messy / "installer.exe").write_text("dummy exe", encoding="utf-8")
    
    # Empty folder
    (messy / "empty_sub").mkdir()

    return messy


def test_organize_directory(temp_messy_dir):
    """Verify loose files are sorted into Documents, Images, Audio, Archives, Code, Executables."""
    res = organize_directory(str(temp_messy_dir))
    assert "Successfully organized 6 files" in res
    assert "Documents" in res
    assert "Images" in res

    # Verify folders were created
    assert (temp_messy_dir / "Documents" / "document.pdf").exists()
    assert (temp_messy_dir / "Images" / "photo.png").exists()
    assert (temp_messy_dir / "Audio" / "song.mp3").exists()
    assert (temp_messy_dir / "Archives" / "archive.zip").exists()
    assert (temp_messy_dir / "Code_and_Scripts" / "script.py").exists()
    assert (temp_messy_dir / "Executables" / "installer.exe").exists()


def test_clean_empty_directories(temp_messy_dir):
    """Verify empty folder removal."""
    assert (temp_messy_dir / "empty_sub").exists()
    res = clean_empty_directories(str(temp_messy_dir))
    assert "Cleaned up" in res
    assert not (temp_messy_dir / "empty_sub").exists()
