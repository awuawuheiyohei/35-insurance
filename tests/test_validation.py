"""溯源校验与合规 lint 的行为测试。

所有 fixture 均为**虚构数据**，与任何真实保险产品无关。
真实产品数据只能从 data/products/ 进入，且必须带官方文件出处。
"""

from __future__ import annotations

import datetime as _dt
import unittest

from insurance import compliance
from insurance.trace import check_traces, flatten
from insurance.validate import load_schema

TODAY = _dt.date.today().isoformat()
SHA = "0" * 64
FIXED_DOC = {
    "type": "clause",
    "title": "虚构测试条款",
    "url": "https://example.com/fake-clause.pdf",
    "sha256": SHA,
    "fetchedAt": TODAY,
    "tier": 1,
}


def trace(doc: int = 0, page: int = 1, quote: str = "这是一段用于测试的条款原文占位内容"):
    return {"docIndex": doc, "page": page, "quote": quote, "tier": 1}


def accident_product(**overrides):
    p = {
        "id": "accident-2026-fixture",
        "name": "虚构测试少儿意外伤害保险",
        "category": "accident",
        "status": "on_sale",
        "filingNo": "FIXTURE0000001",
        "riskLevel": "P1",
        "insurer": {"name": "虚构测试保险股份有限公司", "servicePhone": "400-000-0000"},
        "audience": {"minAge": 0, "maxAge": 17, "childEligible": True},
        "premium": {"currency": "CNY", "unit": "元/人/年", "byInsuredAge": {"0": 100, "1": 100}},
        "coverage": {
            "accident": {
                "death": {"limit": 100000, "regulationCap": {"applies": True, "rule": "累计不超过20万元"}},
                "medical": {
                    "limit": 50000,
                    "deductible": 0,
                    "reimburseRatio": "100%",
                    "outOfCatalogDrug": True,
                    "outpatientCovered": True,
                    "inHospitalDaysLimit": 180,
                },
                "hospitalizationAllowance": {"perDay": 100, "maxDays": 180},
                "specialAccidents": ["猝死", "溺水"],
            }
        },
        "source": {
            "verifiedAt": TODAY,
            "verifier": "fixture",
            "documents": [FIXED_DOC],
            "fieldTrace": {},
        },
    }
    # 自动为所有需要溯源的叶子字段生成 trace
    for path in flatten(p):
        if path.startswith("coverage.") or path in ("premium.byInsuredAge", "underwriting.guaranteedRenewalYears"):
            p["source"]["fieldTrace"][path] = trace()
    # 容器路径不会出现在 flatten 结果里，需显式补充
    p["source"]["fieldTrace"]["premium.byInsuredAge"] = trace(
        doc=0, quote="0-2周岁 100元，3-6周岁 120元（虚构费率表示例）"
    )
    p.update(overrides)
    return p


def medical_product(**overrides):
    p = {
        "id": "medical-2026-fixture",
        "name": "虚构测试少儿百万医疗保险",
        "category": "medical",
        "status": "on_sale",
        "filingNo": "FIXTURE0000002",
        "insurer": {"name": "虚构测试保险股份有限公司", "servicePhone": "400-000-0000"},
        "audience": {"minAge": 0, "maxAge": 17, "childEligible": True},
        "premium": {"currency": "CNY", "unit": "元/人/年", "byInsuredAge": {"0": 300}},
        "coverage": {
            "medical": {
                "general": {"limit": 3000000, "reimburseRatio": "100%"},
                "criticalIllness": {"limit": 3000000, "deductibleOverride": None},
                "deductible": {"amount": 10000, "scope": "annual"},
                "renewal": {"type": "guaranteed_fixed", "text": "保证续保6年"},
                "outOfCatalogDrug": True,
                "specialtyDrug": True,
                "outpatientDrugPurchase": True,
                "hospitalStayAdvance": True,
                "specialWard": False,
                "waitingPeriodDays": 30,
                "hospitalScope": "二级及以上公立医院普通部",
            }
        },
        "underwriting": {"guaranteedRenewalYears": 6, "renewalNote": "停售后可续保至105岁"},
        "source": {
            "verifiedAt": TODAY,
            "verifier": "fixture",
            "documents": [FIXED_DOC],
            "fieldTrace": {},
        },
    }
    for path in flatten(p):
        if (
            path.startswith("coverage.")
            or path in ("premium.byInsuredAge", "underwriting.guaranteedRenewalYears", "underwriting.renewalNote")
        ):
            p["source"]["fieldTrace"][path] = trace()
    p["source"]["fieldTrace"]["premium.byInsuredAge"] = trace(
        doc=0, quote="0-17周岁 300元（虚构费率表示例）"
    )
    p.update(overrides)
    return p


class TestSchema(unittest.TestCase):
    def setUp(self):
        self.v = load_schema()

    def _errs(self, p):
        return list(self.v.iter_errors(p))

    def test_accident_fixture_valid(self):
        self.assertEqual([], self._errs(accident_product()))

    def test_medical_fixture_valid(self):
        self.assertEqual([], self._errs(medical_product()))

    def test_score_field_rejected(self):
        """合规约束：schema 必须无法表达评分/排名/推荐。"""
        p = accident_product()
        p["score"] = 9.5
        self.assertTrue(self._errs(p))

    def test_rank_field_rejected(self):
        p = accident_product()
        p["rank"] = 1
        self.assertTrue(self._errs(p))

    def test_recommended_field_rejected(self):
        p = accident_product()
        p["recommended"] = True
        self.assertTrue(self._errs(p))

    def test_purchase_link_rejected(self):
        p = accident_product()
        p["purchaseUrl"] = "https://example.com/buy"
        self.assertTrue(self._errs(p))

    def test_medical_requires_guaranteed_renewal_years(self):
        p = medical_product()
        del p["underwriting"]["guaranteedRenewalYears"]
        self.assertTrue(self._errs(p))

    def test_accident_coverage_cannot_carry_medical_fields(self):
        p = accident_product()
        p["coverage"]["medical"] = {"general": {"limit": 1}}
        self.assertTrue(self._errs(p))

    def test_sha256_required(self):
        p = accident_product()
        del p["source"]["documents"][0]["sha256"]
        self.assertTrue(self._errs(p))


class TestTrace(unittest.TestCase):
    def test_complete_trace_passes(self):
        self.assertTrue(check_traces(accident_product()).ok)

    def test_missing_trace_fails(self):
        p = accident_product()
        del p["source"]["fieldTrace"]["coverage.accident.medical.limit"]
        r = check_traces(p)
        self.assertFalse(r.ok)
        self.assertTrue(any("coverage.accident.medical.limit" in e.message for e in r.errors))

    def test_fabricated_path_fails(self):
        p = accident_product()
        p["source"]["fieldTrace"]["coverage.accident.nonexistent"] = trace()
        r = check_traces(p)
        self.assertFalse(r.ok)
        self.assertTrue(any("不存在" in e.message for e in r.errors))

    def test_doc_index_out_of_range_fails(self):
        p = accident_product()
        p["source"]["fieldTrace"]["coverage.accident.medical.limit"]["docIndex"] = 9
        r = check_traces(p)
        self.assertFalse(r.ok)
        self.assertTrue(any("越界" in e.message for e in r.errors))

    def test_short_quote_fails(self):
        p = accident_product()
        p["source"]["fieldTrace"]["coverage.accident.medical.limit"]["quote"] = "好"
        self.assertFalse(check_traces(p).ok)

    def test_source_fields_cannot_self_trace(self):
        p = accident_product()
        p["source"]["fieldTrace"]["source.verifier"] = trace()
        r = check_traces(p)
        self.assertFalse(r.ok)
        self.assertTrue(any("无需" in e.message for e in r.errors))

    def test_delisted_requires_date(self):
        p = accident_product(status="delisted")
        r = check_traces(p)
        self.assertFalse(r.ok)
        self.assertTrue(any("delistedOn" in e.message for e in r.errors))

    def test_stale_data_warns(self):
        old = (_dt.date.today() - _dt.timedelta(days=200)).isoformat()
        p = accident_product()
        p["source"]["verifiedAt"] = old
        r = check_traces(p)
        self.assertTrue(r.ok, "陈旧数据只是 warning，不阻断校验")
        self.assertTrue(any("未复核" in w.message for w in r.warnings))

    def test_medical_renewal_is_traced(self):
        r = check_traces(medical_product())
        self.assertTrue(r.ok)
        self.assertGreaterEqual(r.traced_fields, 12)

    def test_container_path_trace_required(self):
        """回归：premium.byInsuredAge 是字典，flatten 后只出现 .0/.1 子路径，
        若不单独处理容器路径，它会永远逃过必溯源检查。"""
        p = accident_product()
        del p["source"]["fieldTrace"]["premium.byInsuredAge"]
        r = check_traces(p)
        self.assertFalse(r.ok)
        self.assertTrue(any(i.path == "premium.byInsuredAge" for i in r.errors))

    def test_container_path_does_not_require_per_age_traces(self):
        p = accident_product()
        r = check_traces(p)
        self.assertTrue(r.ok)
        self.assertFalse(any(i.path.startswith("premium.byInsuredAge[") for i in r.issues))

    def test_fabricated_container_path_fails(self):
        p = accident_product()
        p["source"]["fieldTrace"]["premium.fakeTable"] = trace()
        r = check_traces(p)
        self.assertFalse(r.ok)
        self.assertTrue(any("premium.fakeTable" in i.message for i in r.errors))


class TestFlatten(unittest.TestCase):
    def test_arrays_indexed(self):
        self.assertEqual(
            {"a[0]": 1, "a[1]": 2, "b": None},
            flatten({"a": [1, 2], "b": None}),
        )


class TestComplianceLint(unittest.TestCase):
    def test_banned_words_defined(self):
        for w in ("推荐", "最佳", "排名", "评分", "即将下架"):
            self.assertIn(w, compliance.BANNED_WORDS)

    def test_scan_flags_banned_word(self):
        hits: list = []
        compliance._scan_text("这款产品最值得买", "test.html", hits)
        self.assertEqual(1, len(hits))
        self.assertEqual("值得买", hits[0].word)
        self.assertEqual("夸大表述", hits[0].reason)

    def test_scan_flags_every_occurrence(self):
        hits: list = []
        compliance._scan_text("排名第一，推荐第一", "test.html", hits)
        self.assertEqual({h.word for h in hits}, {"排名", "推荐"})

    def test_scan_respects_ignore_marker(self):
        hits: list = []
        compliance._scan_text("推荐 <!-- lint:ignore -->", "t.html", hits)
        self.assertEqual([], hits)

    def test_clean_text_passes(self):
        hits: list = []
        compliance._scan_text("本产品保证续保6年，条款见下方原文", "t.html", hits)
        self.assertEqual([], hits)

    def test_lint_scans_web_and_data_but_not_docs(self):
        """合规文档必须引用禁用词来定义红线，因此 docs/ 刻意排除在扫描范围外。"""
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            web = root / "web"
            docs = root / "docs"
            data = root / "data" / "products"
            for d in (web, docs, data):
                d.mkdir(parents=True)
            (web / "index.html").write_text("<p>最佳产品推荐</p>", encoding="utf-8")
            (data / "p.json").write_text('{"name": "排名榜第一"}', encoding="utf-8")
            (docs / "01.md").write_text("禁止使用 推荐/最佳/排名 这些词", encoding="utf-8")

            old_web, old_data = compliance.WEB_DIR, compliance.DATA_DIR
            compliance.WEB_DIR, compliance.DATA_DIR = web, data
            try:
                hits = compliance.lint()
            finally:
                compliance.WEB_DIR, compliance.DATA_DIR = old_web, old_data

        words = {h.word for h in hits}
        self.assertIn("推荐", words)   # 来自 web/index.html
        self.assertIn("排名", words)   # 来自 data/products/p.json
        self.assertFalse(any("01.md" in h.where for h in hits), "docs/ 不应被扫描")


if __name__ == "__main__":
    unittest.main(verbosity=2)