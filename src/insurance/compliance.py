"""合规文案 lint。

《保险销售行为管理办法》第十七条禁止"通过不当评比、不当排序等方式进行宣传"。
落到工程上就是：前端展示文案和产品数据里不能出现评分、排名、推荐类词汇。

扫描范围刻意排除 docs/——合规文档本身需要引用这些禁用词来定义红线。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from .paths import DATA_DIR, WEB_DIR

# 禁用词 → 触发的法规依据
BANNED_WORDS: dict[str, str] = {
    "推荐": "销售误导",
    "首选": "不当评比",
    "最佳": "不当评比",
    "最优": "不当评比",
    "最优解": "不当评比",
    "值得买": "夸大表述",
    "闭眼入": "夸大表述",
    "性价比之王": "夸大表述",
    "排名": "不当排序",
    "排行": "不当排序",
    "榜单": "不当排序",
    "评分": "不当评比",
    "打分": "不当评比",
    "打分榜": "不当评比",
    "第一名": "不当评比",
    "碾压": "恶意诋毁竞争对手",
    "吊打": "恶意诋毁竞争对手",
    "秒杀竞品": "恶意诋毁竞争对手",
    "限时抢": "炒作停售",
    "即将下架": "炒作停售",
    "马上停售": "炒作停售",
    "保本保息": "夸大收益",
}

IGNORE_MARKER = "lint:ignore"
SCAN_SUFFIXES = (".html", ".js", ".css", ".json")


@dataclass
class LintHit:
    where: str
    word: str
    reason: str
    context: str


def _scan_text(text: str, where: str, hits: list[LintHit]) -> None:
    # 允许按行豁免：行内出现 lint:ignore 则跳过该行
    for lineno, line in enumerate(text.splitlines(), start=1):
        if IGNORE_MARKER in line:
            continue
        for word, reason in BANNED_WORDS.items():
            for m in re.finditer(re.escape(word), line):
                start = max(0, m.start() - 20)
                end = min(len(line), m.end() + 20)
                hits.append(
                    LintHit(f"{where}:{lineno}", word, reason, line[start:end].strip())
                )


def _iter_json_strings(obj, path: str = ""):
    """递归产出 JSON 中的所有字符串及其路径。"""
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _iter_json_strings(v, f"{path}.{k}" if path else k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _iter_json_strings(v, f"{path}[{i}]")
    elif isinstance(obj, str):
        yield path, obj


def lint(extra_paths: list[Path] | None = None) -> list[LintHit]:
    hits: list[LintHit] = []
    targets: list[Path] = []
    if WEB_DIR.exists():
        targets += [p for p in WEB_DIR.rglob("*") if p.suffix in SCAN_SUFFIXES and p.is_file()]
    if DATA_DIR.exists():
        targets += [p for p in DATA_DIR.rglob("*.json") if p.is_file()]
    targets += list(extra_paths or [])

    for p in targets:
        rel = p.name
        try:
            raw = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue

        if p.suffix == ".json":
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue
            for jpath, sval in _iter_json_strings(data):
                _scan_text(sval, f"{rel}{('#' + jpath) if jpath else ''}", hits)
        else:
            _scan_text(raw, rel, hits)
    return hits