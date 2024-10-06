from __future__ import annotations

from pathlib import Path
from shutil import rmtree

for path in Path().rglob("__pycache__"):
    rmtree(path)
