#!/usr/bin/env python3
"""生成演示数据，用于本地预览与人工走查。

    PYTHONPATH=src:tests .venv/bin/python scripts/demo_data.py      # 生成
    PYTHONPATH=src .venv/bin/python scripts/demo_data.py --clean   # 清理

**全部为虚构数据**，产品名带【示例·虚构】前缀，保险公司名为「虚构测试保险股份有限公司」，
条款 URL 指向 example.com。仅用于确认前端渲染与溯源弹层是否正常，
任何情况下都不得进入正式库 —— `insurance.validate` 之外的流程也不会主动加载它们。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO / "src"), str(REPO / "tests")]

from test_validation import accident_product, medical_product  # noqa: E402

from insurance.paths import DATA_DIR, WEB_DIR  # noqa: E402
from insurance.compliance import BANNED_WORDS  # noqa: E402


def build() -> list[Path]:
    a1 = accident_product(id="accident-2026-demo-a")
    a1["name"] = "【示例·虚构】示例少儿意外伤害保险(A款)"
    a1["source"]["verifiedAt"] = "2026-10-05"

    a2 = accident_product(id="accident-2026-demo-b")
    a2["name"] = "【示例·虚构】示例少儿意外伤害保险(B款)"
    # 演示「本产品没有住院津贴」这一 null 断言也需要溯源
    a2["coverage"]["accident"]["hospitalizationAllowance"] = None
    for k in ("perDay", "maxDays"):
        a2["source"]["fieldTrace"].pop(f"coverage.accident.hospitalizationAllowance.{k}", None)
    a2["source"]["fieldTrace"]["coverage.accident.hospitalizationAllowance"] = {
        "docIndex": 0, "page": 3,
        "quote": "本产品保险责任仅含意外身故保险金与意外医疗保险金，不含住院津贴责任（虚构示例）。",
        "tier": 1,
    }
    a2["premium"]["byInsuredAge"] = {"0": 158, "1": 158, "3": 168}
    a2["source"]["fieldTrace"]["premium.byInsuredAge"]["quote"] = "0-2周岁 158元，3-6周岁 168元（虚构示例）"
    # 演示停售 + 陈旧数据两种标记
    a2["status"] = "delisted"
    a2["delistedOn"] = "2026-06-30"
    a2["source"]["verifiedAt"] = "2026-03-01"

    m1 = medical_product(id="medical-2026-demo-a")
    m1["name"] = "【示例·虚构】示例少儿百万医疗保险"
    m1["source"]["verifiedAt"] = "2026-10-06"

    products = [a1, a2, m1]
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    written = []
    for p in products:
        path = DATA_DIR / f"{p['id']}.json"
        path.write_text(json.dumps(p, ensure_ascii=False, indent=2), encoding="utf-8")
        written.append(path)
    return written


def clean() -> list[Path]:
    """清理演示数据，以及由它构建出来的前端产物。

    两处都要清，缺一不可：

    - ``data/products/*-demo-*.json``：演示数据源文件。
    - ``web/data/``：``insurance.build`` 的输出目录。前端直接读这里的
      JSON，演示数据的产物留在这里就等于演示数据还在生效。

    之前只清前者，清完数据源后 ``web/data/products.json`` 仍带着
    【示例·虚构】的产品留在磁盘上，正是"演示数据用完必须清理"（红线 2）
    没被真正执行的样子。

    该目录全部内容都是 build 生成的可再生文件；如果里面混有真实数据的
    产物，一并清掉也无损失，重新跑 ``insurance.build`` 即可。
    """
    removed: list[Path] = []
    if DATA_DIR.exists():
        removed += sorted(DATA_DIR.glob("*-demo-*.json"))
    out_dir = WEB_DIR / "data"
    if out_dir.exists():
        for p in sorted(out_dir.iterdir()):
            if p.is_file():
                p.unlink()
                removed.append(p)
    return removed


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--clean", action="store_true")
    args = ap.parse_args()

    if args.clean:
        gone = clean()
        print(f"已清理 {len(gone)} 个演示文件" if gone else "没有演示文件需要清理")
        return 0

    files = build()
    # 演示数据同样要过一遍禁用词检查，避免脚本本身成为合规漏洞
    blob = "".join(f.read_text(encoding="utf-8") for f in files)
    hits = [w for w in BANNED_WORDS if w in blob]
    if hits:
        print(f"✗ 演示数据命中禁用词：{hits}")
        clean()
        return 1

    print(f"已生成 {len(files)} 个演示产品：")
    for f in files:
        print(f"  {f.name}")
    print("\n下一步：")
    print("  PYTHONPATH=src .venv/bin/python -m insurance.build")
    print("  python3 -m http.server 8000 -d web")
    return 0


if __name__ == "__main__":
    sys.exit(main())