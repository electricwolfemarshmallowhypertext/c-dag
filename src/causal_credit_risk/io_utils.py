"""Minimal file loading utilities for robust BOM-safe ingestion."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def read_text_file(path: str | Path, *, encoding: str = "utf-8-sig") -> str:
    file_path = Path(path)
    return file_path.read_text(encoding=encoding)


def read_json_file(path: str | Path, *, encoding: str = "utf-8-sig") -> Any:
    return json.loads(read_text_file(path, encoding=encoding))
