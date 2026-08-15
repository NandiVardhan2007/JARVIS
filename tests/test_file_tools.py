"""
Test suite for file tools and smart folder organization.
"""

import os
from pathlib import Path
import tempfile
from vision.tools.file_tools import (
    list_files, find_files, rename_file, copy_file, move_file,
    delete_file, create_folder, organize_directory, read_file_content
)


def test_file_operations_lifecycle():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)

        # 1. Create subfolder
        subfolder = str(tmp_path / "test_sub")
        res = create_folder(subfolder)
        assert "Successfully created" in res
        assert Path(subfolder).exists()

        # 2. Create sample files
        f1 = tmp_path / "sample.txt"
        f1.write_text("Hello VISION File System!")
        f2 = tmp_path / "image.png"
        f2.write_bytes(b"dummy image bytes")

        # 3. Read file content
        content_res = read_file_content(str(f1))
        assert "Hello VISION File System!" in content_res

        # 4. List files
        list_res = list_files(str(tmp_path))
        assert "sample.txt" in list_res
        assert "image.png" in list_res

        # 5. Rename file
        rename_res = rename_file(str(f1), "renamed_sample.txt")
        assert "Successfully renamed" in rename_res
        assert (tmp_path / "renamed_sample.txt").exists()

        # 6. Copy file
        copy_res = copy_file(str(tmp_path / "renamed_sample.txt"), str(tmp_path / "copy_sample.txt"))
        assert "Successfully copied" in copy_res
        assert (tmp_path / "copy_sample.txt").exists()

        # 7. Move file
        move_res = move_file(str(tmp_path / "copy_sample.txt"), subfolder)
        assert "Successfully moved" in move_res
        assert (Path(subfolder) / "copy_sample.txt").exists()

        # 8. Organize directory
        org_res = organize_directory(str(tmp_path))
        assert "Successfully organized" in org_res
        assert (tmp_path / "Images" / "image.png").exists()

        # 9. Delete file
        del_res = delete_file(str(tmp_path / "Images" / "image.png"))
        assert "Successfully deleted" in del_res
        assert not (tmp_path / "Images" / "image.png").exists()
