"""仓库路径解析。所有模块统一从这里取路径，避免散落的相对路径。"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

SCHEMA_PATH = REPO_ROOT / "schema" / "product.schema.json"
DATA_DIR = REPO_ROOT / "data" / "products"
WEB_DIR = REPO_ROOT / "web"
DOCS_DIR = REPO_ROOT / "docs"
EXPORT_DIR = REPO_ROOT / "dist"


def product_files() -> list[Path]:
    """所有产品数据文件，按文件名排序（保证输出稳定）。"""
    if not DATA_DIR.exists():
        return []
    return sorted(DATA_DIR.glob("*.json"))