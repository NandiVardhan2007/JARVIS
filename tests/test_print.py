import os
import subprocess
from pathlib import Path
from vision.tools.printer_tools import create_bordered_a4_document

pdf_path = Path.home() / "Documents" / "bordered_a4_print_test.pdf"
create_bordered_a4_document(margin_cm=1.5, file_name="bordered_a4_print_test.pdf")

edge_candidates = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Users\NANDU\AppData\Local\Microsoft\Edge\Application\msedge.exe",
]

edge_exe = None
for ec in edge_candidates:
    if os.path.exists(ec):
        edge_exe = ec
        break

print("Edge executable:", edge_exe)
print("PDF exists:", pdf_path.exists())

if edge_exe and pdf_path.exists():
    cmd = f'"{edge_exe}" --headless --no-pdf-header-footer --print-to-printer="Pantum P2500 Series" "{pdf_path}"'
    print("Running print command:", cmd)
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    print("Print job dispatched! Return code:", res.returncode)
