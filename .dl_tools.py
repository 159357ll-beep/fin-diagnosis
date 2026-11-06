"""临时脚本：下载便携版 VS Code / Python / get-pip。"""

import os
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

OUT = "portable"
os.makedirs(OUT, exist_ok=True)

TARGETS = {
    "vscode.zip": "https://code.visualstudio.com/sha/download?build=stable&os=win32-x64-archive",
    "python-embed.zip": "https://www.python.org/ftp/python/3.12.10/python-3.12.10-embed-amd64.zip",
    "get-pip.py": "https://bootstrap.pypa.io/get-pip.py",
}
HEADERS = {"User-Agent": "Mozilla/5.0"}


def resolve(url: str) -> tuple[str, int]:
    req = urllib.request.Request(url, headers={**HEADERS, "Range": "bytes=0-0"})
    with urllib.request.urlopen(req, timeout=40) as r:
        total = int(r.headers["Content-Range"].split("/")[-1])
        return r.geturl(), total


def fetch(url: str, start: int, end: int) -> bytes:
    req = urllib.request.Request(
        url, headers={**HEADERS, "Range": "bytes=%d-%d" % (start, end)}
    )
    last = None
    for _ in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read()
        except Exception as exc:
            last = exc
            time.sleep(1)
    raise RuntimeError(f"chunk failed: {last}")


def download(name: str, url: str) -> None:
    final_url, size = resolve(url)
    path = os.path.join(OUT, name)
    if os.path.exists(path) and os.path.getsize(path) == size:
        print(f"skip {name}", flush=True)
        return

    print(f"start {name}: {size/1048576:.1f} MB", flush=True)
    chunk = 4 * 1024 * 1024
    ranges = [(i, min(i + chunk, size) - 1) for i in range(0, size, chunk)]
    with open(path, "wb") as f:
        f.truncate(size)

    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = {pool.submit(fetch, final_url, s, e): (s, e) for s, e in ranges}
        for fut in as_completed(futures):
            start, _ = futures[fut]
            with open(path, "r+b") as f:
                f.seek(start)
                f.write(fut.result())
    print(f"done {name}: {os.path.getsize(path)/1048576:.1f} MB", flush=True)


for filename, link in TARGETS.items():
    download(filename, link)

print("ALL DONE", flush=True)
