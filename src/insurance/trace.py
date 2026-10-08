"""溯源交叉校验。

JSON Schema 能保证字段结构合法，但保证不了「你写的这个数字真的来自你附的那份文件」。
这里补上 schema 做不到的三件事：

  1. fieldTrace 里声明的路径，必须在产品数据里真实存在（不能编造出处）
  2. 需要溯源的字段，不能漏（不能只给一半字段配来源）
  3. 保鲜度：verifiedAt 太久则降级警告
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field
from typing import Any

# 必须逐字段溯源的路径前缀 / 精确路径。
# 只对"用户会拿去做决策依据"的字段强制要求，其余字段（元数据）免。
TRACED_PREFIXES: tuple[str, ...] = ("coverage.",)
TRACED_EXACT: frozenset[str] = frozenset(
    {
        "premium.byInsuredAge",
        "underwriting.guaranteedRenewalYears",
        "underwriting.renewalNote",
    }
)

# 费率表是一整张表，逐个年龄建 trace 没有意义。容器路径允许整体溯源，
# 不参与 flatten 的叶子展开检查（见 _resolves）。
TRACED_CONTAINERS: frozenset[str] = frozenset({"premium.byInsuredAge"})

# 保鲜度阈值（天）
FRESH_DAYS = 60
STALE_DAYS = 180


@dataclass
class TraceIssue:
    path: str
    level: str  # "error" | "warning"
    message: str


@dataclass
class TraceReport:
    issues: list[TraceIssue] = field(default_factory=list)
    traced_fields: int = 0
    required_fields: int = 0

    @property
    def errors(self) -> list[TraceIssue]:
        return [i for i in self.issues if i.level == "error"]

    @property
    def warnings(self) -> list[TraceIssue]:
        return [i for i in self.issues if i.level == "warning"]

    @property
    def ok(self) -> bool:
        return not self.errors


def flatten(obj: Any, prefix: str = "") -> dict[str, Any]:
    """把嵌套结构摊平成 {'coverage.accident.medical.limit': 50000, ...}。

    数组按 [i] 展开。None 值保留（它们常常本身就是需要溯源的"没有/不适用"）。
    """
    out: dict[str, Any] = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            child = f"{prefix}.{k}" if prefix else k
            out.update(flatten(v, child))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            child = f"{prefix}[{i}]"
            out.update(flatten(v, child))
    else:
        if prefix:
            out[prefix] = obj
    return out


def _requires_trace(path: str) -> bool:
    if path in TRACED_EXACT or path in TRACED_CONTAINERS:
        return True
    return any(path.startswith(p) for p in TRACED_PREFIXES)


def _is_meta(path: str) -> bool:
    """source.* 下的路径由 schema 自身约束，不纳入逐字段溯源。"""
    return path.startswith("source.")


def _resolves(product: dict[str, Any], path: str) -> bool:
    """路径在产品数据中真实存在。

    与 flatten 不同，这里接受容器路径（如 premium.byInsuredAge），
    因为费率表作为整体溯源比逐个年龄溯源更贴合实际。
    """
    if path in flatten(product):
        return True
    cur: Any = product
    for seg in path.split("."):
        if isinstance(cur, dict) and seg in cur:
            cur = cur[seg]
        else:
            return False
    return True


def check_traces(product: dict[str, Any], today: _dt.date | None = None) -> TraceReport:
    today = today or _dt.date.today()
    report = TraceReport()

    source = product.get("source") or {}
    field_trace: dict[str, Any] = source.get("fieldTrace") or {}
    documents: list[dict[str, Any]] = source.get("documents") or []
    flat = flatten(product)

    # --- 1. 声明的出处必须真实存在 ---------------------------------------
    for path, tr in field_trace.items():
        if not _resolves(product, path):
            report.issues.append(
                TraceIssue(path, "error", f"fieldTrace 声明的路径在产品数据中不存在：{path}")
            )
            continue
        if _is_meta(path):
            report.issues.append(
                TraceIssue(path, "error", f"source 内部字段无需也不应出现在 fieldTrace：{path}")
            )
            continue
        doc_index = tr.get("docIndex")
        if not isinstance(doc_index, int) or not (0 <= doc_index < len(documents)):
            report.issues.append(
                TraceIssue(path, "error", f"docIndex={doc_index} 越界，documents 长度为 {len(documents)}")
            )
        if len((tr.get("quote") or "").strip()) < 4:
            report.issues.append(
                TraceIssue(path, "error", "quote 过短，无法作为可核对原文")
            )

    # --- 2. 需要溯源的字段不能漏 -----------------------------------------
    for path in flat:
        if _is_meta(path) or not _requires_trace(path):
            continue
        if path in field_trace:
            report.traced_fields += 1
        else:
            report.required_fields += 1
            report.issues.append(
                TraceIssue(path, "error", f"缺少溯源：{path}")
            )

    # 容器路径不出现在 flatten 的叶子集合里，需单独检查
    for path in sorted(TRACED_CONTAINERS):
        if not _resolves(product, path):
            continue
        if path in field_trace:
            report.traced_fields += 1
        else:
            report.required_fields += 1
            report.issues.append(
                TraceIssue(path, "error", f"缺少溯源：{path}")
            )

    # --- 3. 保鲜度 --------------------------------------------------------
    verified_at = source.get("verifiedAt")
    if verified_at:
        try:
            vd = _dt.date.fromisoformat(verified_at)
        except ValueError:
            report.issues.append(TraceIssue("source.verifiedAt", "error", "日期格式非法"))
        else:
            age = (today - vd).days
            if age > STALE_DAYS:
                report.issues.append(
                    TraceIssue("source.verifiedAt", "warning", f"数据已 {age} 天未复核，过期风险高")
                )
            elif age > FRESH_DAYS:
                report.issues.append(
                    TraceIssue("source.verifiedAt", "warning", f"数据已 {age} 天未复核")
                )

    # --- 4. 停售产品必须有停售日期 ---------------------------------------
    if product.get("status") == "delisted" and not product.get("delistedOn"):
        report.issues.append(TraceIssue("delistedOn", "error", "status=delisted 时必须填写 delistedOn"))

    return report