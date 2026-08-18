"""Ensure the `src` package is importable during tests.

Also exposes the project's real SQLite path so tests that must verify the
production layout can reference it without hard-coding absolute paths.
"""

from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"
PROJECT_ROOT = Path(__file__).resolve().parent.parent

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))