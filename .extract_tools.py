"""临时脚本：解包便携版 VS Code / Python，并开启 site-packages。"""

import os
import shutil
import zipfile

os.makedirs(".tools", exist_ok=True)

# ---------- Python 嵌入式版 ----------
py_dir = os.path.join(".tools", "python")
shutil.rmtree(py_dir, ignore_errors=True)
with zipfile.ZipFile("portable/python-embed.zip") as zf:
    zf.extractall(py_dir)

pth = os.path.join(py_dir, "python312._pth")
with open(pth, encoding="utf-8") as f:
    content = f.read()
content = content.replace("#import site", "import site")
with open(pth, "w", encoding="utf-8") as f:
    f.write(content)
print("python extracted, _pth updated")

# ---------- VS Code ----------
raw = os.path.join("portable", "vscode_raw")
shutil.rmtree(raw, ignore_errors=True)
with zipfile.ZipFile("portable/vscode.zip") as zf:
    zf.extractall(raw)

entries = [e for e in os.listdir(raw) if os.path.isdir(os.path.join(raw, e))]
src = os.path.join(raw, entries[0]) if len(entries) == 1 else raw
dst = os.path.join(".tools", "vscode")
shutil.rmtree(dst, ignore_errors=True)
shutil.move(src, dst)
print("vscode extracted")
