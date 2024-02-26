from __future__ import annotations

from pathlib import Path

for path in Path().rglob("*.py[co]"):
    path.unlink()

for path in Path().rglob("__pycache__"):
    path.rmdir()
