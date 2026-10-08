"""产品数据读取。"""

from __future__ import annotations

import json
from pathlib import Path

from .paths import product_files


def read_products() -> list[Path]:
    return product_files()


def load_one(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))