"""保额保费基准引擎。

回答的问题是「同样条件下，市场上这个价格大概是多少」，不是「哪款更好」。

这是刻意区分的两件事：
  - 基准  = 一个价格区间 + 每个样本的出处。客观。
  - 排序  = 告诉用户买哪个。主观，且触及《保险销售行为管理办法》第十七条。

为什么这个模块存在：同样 50 万保额、0 岁女宝，消费型年交 400-2000 元，
带万能账户的储蓄混合型可以到 12000 元，差 5 倍以上。如果用户手上拿着
一份报价单，没有基准就无从判断它处在什么位置。

用法：
    python -m insurance.benchmark                       # 列出全部基准组
    python -m insurance.benchmark --age 0 --gender female \
        --sum-insured 500000 --term lifetime --pay 30 --type consumption
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from jsonschema import Draft7Validator

from .paths import BENCHMARK_SCHEMA_PATH, benchmark_files

TERM_LABEL = {"term_N_years": "保N年", "to_age_70": "保至70岁", "lifetime": "保终身"}
TYPE_LABEL = {"consumption": "消费型", "savings": "储蓄型", "bundle": "全能险"}
GENDER_LABEL = {"male": "男", "female": "女"}

# 样本量低于此值，区间不可信，必须显式提示
MIN_SAMPLES = 3
STALE_DAYS = 180


@dataclass
class Query:
    age: int | None = None
    gender: str | None = None
    sum_insured: int | None = None
    term: str | None = None
    term_years: int | None = None
    pay: int | None = None
    ptype: str | None = None

    def matches(self, bm: dict) -> bool:
        c = bm["condition"]
        if self.age is not None and not (c["ageFrom"] <= self.age <= c["ageTo"]):
            return False
        if self.gender and c["gender"] != self.gender:
            return False
        if self.sum_insured is not None and c["sumInsured"] != self.sum_insured:
            return False
        if self.term and c["coverageTerm"] != self.term:
            return False
        if self.term_years is not None and c.get("termYears") != self.term_years:
            return False
        if self.pay is not None and c["payTerm"] != self.pay:
            return False
        if self.ptype and c["productType"] != self.ptype:
            return False
        return True


@dataclass
class Stat:
    bm: dict
    premiums: list[float] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def label(self) -> str:
        return self.bm.get("label") or _auto_label(self.bm["condition"])

    @property
    def low(self) -> float:
        return min(self.premiums)

    @property
    def high(self) -> float:
        return max(self.premiums)

    @property
    def median(self) -> float:
        return statistics.median(self.premiums)

    @property
    def mean(self) -> float:
        return statistics.fmean(self.premiums)

    @property
    def leverage(self) -> float:
        """杠杆比 = 保额 / 年保费。衡量花一块钱换多少保障。"""
        return self.bm["condition"]["sumInsured"] / self.median

    @property
    def reliable(self) -> bool:
        return len(self.premiums) >= MIN_SAMPLES


def _auto_label(c: dict) -> str:
    term = TERM_LABEL.get(c["coverageTerm"], c["coverageTerm"])
    if c["coverageTerm"] == "term_N_years" and c.get("termYears"):
        term = f"保{c['termYears']}年"
    age = str(c["ageFrom"]) if c["ageFrom"] == c["ageTo"] else f"{c['ageFrom']}-{c['ageTo']}"
    return (
        f"{age}岁{GENDER_LABEL[c['gender']]} / "
        f"{c['sumInsured'] / 10000:g}万 / {term} / "
        f"{c['payTerm']}年缴 / {TYPE_LABEL[c['productType']]}"
    )


def load_benchmarks() -> list[dict]:
    out: list[dict] = []
    for p in benchmark_files():
        try:
            out.append(json.loads(p.read_text(encoding="utf-8")))
        except json.JSONDecodeError as e:
            print(f"跳过 {p.name}：JSON 解析失败 {e}", file=sys.stderr)
    return out


def validator() -> Draft7Validator:
    return Draft7Validator(json.loads(BENCHMARK_SCHEMA_PATH.read_text(encoding="utf-8")))


def compute(bms: list[dict], q: Query, today: date | None = None) -> list[Stat]:
    today = today or date.today()
    stats: list[Stat] = []
    v = validator()
    for bm in bms:
        if not q.matches(bm):
            continue
        errors = list(v.iter_errors(bm))
        if errors:
            stat = Stat(bm=bm, premiums=[s["annualPremium"] for s in bm.get("samples", [])])
            loc = ".".join(str(x) for x in errors[0].path) or "(根)"
            stat.warnings.append(f"schema 不合法 · {loc} · {errors[0].message}")
        else:
            stat = Stat(bm=bm, premiums=[s["annualPremium"] for s in bm["samples"]])

        if not stat.premiums:
            continue
        if not stat.reliable:
            stat.warnings.append(f"样本仅 {len(stat.premiums)} 条，低于 {MIN_SAMPLES} 条，区间不可代表市场")
        for s in bm["samples"]:
            try:
                age = (today - date.fromisoformat(s["source"]["verifiedAt"])).days
            except ValueError:
                stat.warnings.append(f"{s['productName']} · 核验日期格式非法")
                continue
            if age > STALE_DAYS:
                stat.warnings.append(f"{s['productName']} · 数据已 {age} 天未复核")
        stats.append(stat)

    # 按标签排序，保证输出稳定；刻意不按价格或任何优劣指标排序
    stats.sort(key=lambda s: s.label)
    return stats


def render_text(stats: list[Stat]) -> str:
    if not stats:
        return (
            "没有匹配的基准组。\n\n"
            "data/benchmarks/ 目前是空的 —— 这是刻意的：\n"
            "  本项目不填入任何未经官方费率表核对的数据。\n"
            "  填写模板见 data/benchmarks/_template.json"
        )

    lines: list[str] = []
    for s in stats:
        c = s.bm["condition"]
        lines.append("─" * 68)
        lines.append(s.label)
        lines.append(
            f"  样本 {len(s.premiums)} 个"
            + ("" if s.reliable else f"  ⚠ 少于 {MIN_SAMPLES} 个")
            + f"   核验 {s.bm['source']['verifiedAt']} by {s.bm['source']['verifier']}"
        )
        lines.append(
            f"  年保费区间   {s.low:,.0f} – {s.high:,.0f} 元"
            f"   中位数 {s.median:,.0f}   均值 {s.mean:,.0f}"
        )
        lines.append(
            f"  每 1 元年保费换 {s.leverage:,.0f} 元保障"
            f"（{c['sumInsured'] / 10000:g} 万 ÷ 中位年保费 {s.median:,.0f}）"
        )
        lines.append(f"  {c['sumInsured'] / 10000:g} 万保额 / {c['payTerm']} 年缴")
        lines.append("  样本明细：")
        for smp in sorted(s.bm["samples"], key=lambda x: x["annualPremium"]):
            flag = " [已收录进产品库]" if smp.get("isInLibrary") else ""
            lines.append(
                f"    {smp['annualPremium']:>9,.0f} 元  {smp['insurerName']} · {smp['productName']}{flag}"
            )
            lines.append(f"              出处：{smp['source']['premiumQuote'][:60]}")
        for cv in s.bm.get("caveats") or []:
            lines.append(f"  注意：{cv}")
        for w in s.warnings:
            lines.append(f"  ! {w}")
    lines.append("─" * 68)
    lines.append("以上为价格区间与样本出处，不含任何产品优劣判断，也不提供投保入口。")
    return "\n".join(lines)


def to_json(stats: list[Stat]) -> dict:
    return {
        "count": len(stats),
        "disclaimer": (
            "本模块只做同条件下的保费区间对照，不评价产品优劣、不提供投保服务。"
            "投保前请咨询持牌保险机构。"
        ),
        "groups": [
            {
                "label": s.label,
                "condition": s.bm["condition"],
                "conditionLabel": s.label,
                "sampleCount": len(s.premiums),
                "reliable": s.reliable,
                "low": s.low,
                "high": s.high,
                "median": s.median,
                "mean": s.mean,
                "leverage": s.leverage,
                "verifiedAt": s.bm["source"]["verifiedAt"],
                "verifier": s.bm["source"]["verifier"],
                "scopeNote": s.bm["source"]["scopeNote"],
                "caveats": s.bm.get("caveats") or [],
                "warnings": s.warnings,
                "samples": sorted(
                    s.bm["samples"], key=lambda x: x["annualPremium"]
                ),
            }
            for s in stats
        ],
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="insurance.benchmark", description="保额保费基准查询（只出区间，不做优劣判断）"
    )
    ap.add_argument("--age", type=int)
    ap.add_argument("--gender", choices=["male", "female"])
    ap.add_argument("--sum-insured", type=int, help="保额，单位元")
    ap.add_argument("--term", choices=["term_N_years", "to_age_70", "lifetime"])
    ap.add_argument("--term-years", type=int)
    ap.add_argument("--pay", type=int, help="缴费年期")
    ap.add_argument("--type", choices=["consumption", "savings", "bundle"], dest="ptype")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    ap.add_argument("--out", type=Path, help="写入 JSON 文件（供前端消费）")
    args = ap.parse_args(argv)

    q = Query(
        age=args.age, gender=args.gender, sum_insured=args.sum_insured,
        term=args.term, term_years=args.term_years, pay=args.pay, ptype=args.ptype,
    )
    stats = compute(load_benchmarks(), q)

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps(to_json(stats), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"✓ 已写出 {args.out}")
    if args.json:
        print(json.dumps(to_json(stats), ensure_ascii=False, indent=2))
    elif not args.out:
        print(render_text(stats))
    return 0


if __name__ == "__main__":
    sys.exit(main())