#!/usr/bin/env python3
"""生成虚构的保费基准演示数据，用于本地预览。

    PYTHONPATH=src .venv/bin/python scripts/demo_benchmarks.py
    PYTHONPATH=src .venv/bin/python scripts/demo_benchmarks.py --clean

与 demo_data.py 一样，全部为虚构数据，公司名为「虚构测试保险股份有限公司」，
费率表 URL 指向 example.com。仅用于确认查询与渲染是否正常。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO / "src"), str(REPO / "tests")]

from test_benchmark import group, sample  # noqa: E402,F401  (group 提供夹具构造)

from insurance.benchmark import Query, compute, load_benchmarks, to_json  # noqa: E402
from insurance.paths import BENCH_DIR, WEB_DIR  # noqa: E402


def build() -> list[Path]:
    # 一组「消费型」：价格低，样本充足
    consumption = group("bm-f0-50w-life-30p-consumption", [1900, 2225, 2480, 2600])
    consumption["label"] = "0岁女宝 / 50万 / 保终身 / 30年缴 / 消费型"
    consumption["caveats"] = [
        "仅含互联网渠道产品。个险渠道与经代渠道报价普遍更高，样本无法覆盖。",
        "样本为手工抽样，不代表全市场。",
    ]
    consumption["source"]["scopeNote"] = "虚构演示数据，样本由测试夹具构造，不对应任何真实产品。"

    # 一组「储蓄混合型」：价格高得多，用于演示「同样保额可以差多少」
    savings = group(
        "bm-f0-50w-life-20p-savings",
        [11555, 12629],
        payTerm=20,
        productType="savings",
        hasDeathBenefit=True,
    )
    savings["label"] = "0岁女宝 / 50万 / 保终身 / 20年缴 / 储蓄型（含万能账户）"
    # sample() 的默认 quote 写的是「交30年」，与本组 20 年缴不符，按实际条件改写
    for s in savings["samples"]:
        s["source"]["premiumQuote"] = (
            f"0岁女 保额50万 保障至终身 交20年，年交 {s['annualPremium']:.0f} 元（虚构演示）"
        )
    savings["caveats"] = [
        "样本仅 2 条，低于 3 条，不足以代表市场。",
        "储蓄型保费包含账户储蓄成分，不能与消费型直接比较「性价比」，只可比价格。",
    ]
    savings["source"]["scopeNote"] = "虚构演示数据，样本由测试夹具构造，不对应任何真实产品。"

    BENCH_DIR.mkdir(parents=True, exist_ok=True)
    written = []
    for bm in (consumption, savings):
        p = BENCH_DIR / f"{bm['id']}.json"
        p.write_text(json.dumps(bm, ensure_ascii=False, indent=2), encoding="utf-8")
        written.append(p)
    return written


def clean() -> list[Path]:
    removed = sorted(BENCH_DIR.glob("bm-*.json")) if BENCH_DIR.exists() else []
    for p in removed:
        p.unlink()
    out = WEB_DIR / "data" / "benchmarks.json"
    if out.exists():
        out.unlink()
    return removed


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--clean", action="store_true")
    args = ap.parse_args()

    if args.clean:
        gone = clean()
        print(f"已清理 {len(gone)} 个演示基准组")
        return 0

    files = build()
    out = WEB_DIR / "data" / "benchmarks.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(to_json(compute(load_benchmarks(), Query())), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"已生成 {len(files)} 个演示基准组：")
    for f in files:
        print(f"  {f.name}")
    print(f"\n已写出 {out}")
    print("启动预览：python3 -m http.server 8000 -d web")
    return 0


def benchmark_empty_query():
    return Query()


if __name__ == "__main__":
    sys.exit(main())