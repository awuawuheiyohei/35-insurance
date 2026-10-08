"""构建命令：校验 → 聚合 → 输出给前端。

    python -m insurance.build

硬约束：校验不通过就不产出。宁可没有数据，也不能让前端拿到不合规或无出处的数据。
"""

from __future__ import annotations

import json
import sys
from datetime import date

from .paths import DATA_DIR, WEB_DIR
from .validate import load_schema, validate_one
from .product_files import read_products
from .trace import check_traces

OUT_DIR = WEB_DIR / "data"


def build(strict: bool = False) -> int:
    files = read_products()
    if not files:
        print("data/products/ 为空，没有可构建的数据。")
        print("填写方法见 docs/02-数据源与溯源规范.md §5。")
        return 1

    validator = load_schema()
    results = [validate_one(validator, f) for f in files]
    failed = [r for r in results if not r.ok]
    warned = [r for r in results if r.warnings]

    for r in failed:
        print(f"✗ {r.path}")
        for e in r.errors:
            print(f"    ERROR {e}")
    for r in warned:
        print(f"! {r.path}")
        for w in r.warnings:
            print(f"    WARNING {w}")

    if failed:
        print(f"\n构建中止：{len(failed)} 个文件校验未通过。前端不会收到不合规数据。")
        return 1
    if strict and warned:
        print("\n构建中止：strict 模式下存在保鲜度警告。")
        return 1

    products = []
    for f in files:
        p = json.loads(f.read_text(encoding="utf-8"))
        tr = check_traces(p)
        products.append(
            {
                "product": p,
                "trace": {
                    "tracedFields": tr.traced_fields,
                    "freshness": _freshness(p),
                    "verifiedAt": p["source"]["verifiedAt"],
                },
            }
        )

    # 固定按备案名称字典序排列，刻意不提供任何排序/评分维度。
    products.sort(key=lambda x: x["product"]["name"])

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "snapshotDate": date.today().isoformat(),
        "disclaimer": (
            "本工具仅作保险条款信息披露与事实对比，不提供倾向性意见，"
            "不构成保险建议，亦不提供投保服务。投保前请咨询持牌保险机构。"
        ),
        "count": len(products),
        "products": products,
    }
    out = OUT_DIR / "products.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n✓ 已构建 {len(products)} 个产品 → {out.relative_to(OUT_DIR.parents[2])}")
    return 0


def _freshness(product: dict) -> str:
    from .trace import FRESH_DAYS, STALE_DAYS

    vd = date.fromisoformat(product["source"]["verifiedAt"])
    age = (date.today() - vd).days
    if age > STALE_DAYS:
        return "expired"
    if age > FRESH_DAYS:
        return "aging"
    return "fresh"


if __name__ == "__main__":
    sys.exit(build("--strict" in sys.argv))