"""数据校验 CLI。

    python -m insurance.validate              # 校验全部产品
    python -m insurance.validate --strict     # warning 也算失败
    python -m insurance.validate --lint       # 附带合规文案 lint

校验分两层：
  1. JSON Schema —— 结构合法性
  2. trace.check_traces —— 溯源真实性与保鲜度（schema 做不到的部分）

退出码：0 全过 / 1 有错误
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass

from jsonschema import Draft7Validator

from . import compliance
from .paths import SCHEMA_PATH, product_files
from .trace import check_traces

GREEN, RED, YELLOW, DIM, BOLD, RESET = (
    "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[1m", "\033[0m"
)


@dataclass
class FileResult:
    path: str
    ok: bool
    errors: list[str]
    warnings: list[str]
    traced: int = 0


def load_schema() -> Draft7Validator:
    return Draft7Validator(json.loads(SCHEMA_PATH.read_text(encoding="utf-8")))


def validate_one(validator: Draft7Validator, path) -> FileResult:
    errors: list[str] = []
    warnings: list[str] = []

    try:
        product = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return FileResult(path.name, False, [f"JSON 解析失败：{e}"], [])

    for err in sorted(validator.iter_errors(product), key=lambda e: list(e.path)):
        loc = ".".join(str(x) for x in err.path) or "(根)"
        errors.append(f"schema · {loc} · {err.message}")

    report = check_traces(product)
    for issue in report.errors:
        errors.append(f"溯源 · {issue.path} · {issue.message}")
    for issue in report.warnings:
        warnings.append(f"保鲜 · {issue.path} · {issue.message}")

    return FileResult(path.name, not errors, errors, warnings, report.traced_fields)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="insurance.validate", description="保险产品数据校验")
    ap.add_argument("--strict", action="store_true", help="把 warning 视为失败")
    ap.add_argument("--lint", action="store_true", help="同时运行合规文案 lint")
    ap.add_argument("--quiet", action="store_true", help="只输出结论")
    args = ap.parse_args(argv)

    files = product_files()
    validator = load_schema()

    results = [validate_one(validator, f) for f in files]

    if not args.quiet:
        for r in results:
            mark = f"{GREEN}✓{RESET}" if r.ok else f"{RED}✗{RESET}"
            print(f"{mark} {r.path} {DIM}({r.traced} 个字段已溯源){RESET}")
            for e in r.errors:
                print(f"    {RED}ERROR{RESET}   {e}")
            for w in r.warnings:
                print(f"    {YELLOW}WARNING{RESET} {w}")

    failed = [r for r in results if not r.ok]
    warned = [r for r in results if r.warnings]

    print()
    if not files:
        print(f"{YELLOW}data/products/ 为空 —— 还没有任何产品数据{RESET}")
    else:
        print(f"{BOLD}校验结果{RESET}: {len(results) - len(failed)}/{len(results)} 通过", end="")
        print(f"，{len(warned)} 个有保鲜度提示" if warned else "")
    if failed:
        print(f"{RED}✗ {len(failed)} 个文件校验未通过{RESET}")

    lint_hits: list[compliance.LintHit] = []
    if args.lint:
        lint_hits = compliance.lint()
        if not args.quiet:
            if lint_hits:
                for h in lint_hits:
                    print(f"    {RED}LINT{RESET}   {h.where} · 「{h.word}」({h.reason}) · …{h.context}…")
            else:
                print(f"{GREEN}✓{RESET} 合规文案 lint 通过")
        if lint_hits:
            print(f"{RED}✗ 合规文案命中 {len(lint_hits)} 处{RESET}")

    if args.strict and warned:
        print(f"{YELLOW}strict 模式：{len(warned)} 个文件存在 warning{RESET}")

    return 1 if (failed or lint_hits or (args.strict and warned)) else 0


if __name__ == "__main__":
    sys.exit(main())