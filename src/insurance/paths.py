"""仓库路径解析。所有模块统一从这里取路径，避免散落的相对路径。"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

SCHEMA_PATH = REPO_ROOT / "schema" / "product.schema.json"
BENCHMARK_SCHEMA_PATH = REPO_ROOT / "schema" / "benchmark.schema.json"
DATA_DIR = REPO_ROOT / "data" / "products"
BENCH_DIR = REPO_ROOT / "data" / "benchmarks"
WEB_DIR = REPO_ROOT / "web"
DOCS_DIR = REPO_ROOT / "docs"
EXPORT_DIR = REPO_ROOT / "dist"


def product_files() -> list[Path]:
    """所有产品数据文件，按文件名排序（保证输出稳定）。"""
    if not DATA_DIR.exists():
        return []
    return sorted(DATA_DIR.glob("*.json"))


def benchmark_files() -> list[Path]:
    """所有保费基准文件，按文件名排序。"""
    if not BENCH_DIR.exists():
        return []
    return sorted(p for p in BENCH_DIR.glob("*.json") if not p.name.startswith("_"))