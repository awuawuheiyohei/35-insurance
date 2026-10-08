"""保额保费基准引擎的行为测试。

全部使用虚构数据，与任何真实保险产品无关。
"""

from __future__ import annotations

import datetime as _dt
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from insurance import benchmark
from insurance.benchmark import Query, compute, load_benchmarks, to_json, validator
from insurance.paths import BENCH_DIR

TODAY = _dt.date.today().isoformat()
SHA = "0" * 64


def sample(name: str, premium: float, **over) -> dict:
    s = {
        "productName": name,
        "insurerName": "虚构测试保险股份有限公司",
        "annualPremium": premium,
        "isInLibrary": False,
        "source": {
            "verifiedAt": TODAY,
            "verifier": "fixture",
            "documents": [
                {
                    "type": "rate_table", "title": "虚构费率表",
                    "url": "https://example.com/fake-rate.pdf",
                    "sha256": SHA, "fetchedAt": TODAY, "tier": 1,
                }
            ],
            "premiumQuote": f"0岁女保额50万交30年，年交 {premium} 元（虚构示例）",
        },
    }
    s.update(over)
    return s


def group(bm_id: str, premiums: list[float], **cond) -> dict:
    c = {
        "ageFrom": 0, "ageTo": 0, "gender": "female", "sumInsured": 500000,
        "coverageTerm": "lifetime", "termYears": None, "payTerm": 30,
        "productType": "consumption",
        "hasDeathBenefit": False, "hasMultipleClaim": False, "childDiseaseExtraPct": 100,
    }
    c.update(cond)
    return {
        "id": bm_id,
        "label": f"测试组 {bm_id}",
        "condition": c,
        "samples": [sample(f"虚构示例产品{i+1}", p) for i, p in enumerate(premiums)],
        "caveats": ["虚构测试数据"],
        "source": {"verifiedAt": TODAY, "verifier": "fixture", "scopeNote": "虚构测试数据，不可用于真实决策"},
    }


class TestBenchmarkSchema(unittest.TestCase):
    def setUp(self):
        self.v = validator()

    def test_valid_group(self):
        self.assertEqual([], list(self.v.iter_errors(group("bm-test-a", [2000, 2200, 2400]))))

    def test_rank_field_rejected(self):
        g = group("bm-test-a", [2000])
        g["rank"] = 1
        self.assertTrue(self.v.iter_errors(g))

    def test_recommended_field_rejected(self):
        g = group("bm-test-a", [2000])
        g["bestProduct"] = "x"
        self.assertTrue(self.v.iter_errors(g))

    def test_sample_requires_premium_quote(self):
        g = group("bm-test-a", [2000])
        del g["samples"][0]["source"]["premiumQuote"]
        self.assertTrue(self.v.iter_errors(g))

    def test_sample_requires_sha256(self):
        g = group("bm-test-a", [2000])
        del g["samples"][0]["source"]["documents"][0]["sha256"]
        self.assertTrue(self.v.iter_errors(g))

    def test_known_product_types(self):
        for t in ("consumption", "savings", "bundle"):
            self.assertEqual([], list(self.v.iter_errors(
                group("bm-test-a", [2000], productType=t))))

    def test_unknown_product_type_rejected(self):
        self.assertTrue(self.v.iter_errors(group("bm-test-a", [2000], productType="whole_life")))


class TestCompute(unittest.TestCase):
    def test_median_and_leverage(self):
        g = group("bm-test-a", [2000, 2500, 3000])
        st = compute([g], Query(), today=_dt.date.today())[0]
        self.assertEqual(2000, st.low)
        self.assertEqual(3000, st.high)
        self.assertEqual(2500, st.median)
        self.assertAlmostEqual(200.0, st.leverage)   # 50万 / 2500

    def test_small_sample_flagged_unreliable(self):
        st = compute([group("bm-test-a", [2000, 2500])], Query(), today=_dt.date.today())[0]
        self.assertFalse(st.reliable)
        self.assertTrue(any("样本仅 2 条" in w for w in st.warnings))

    def test_three_samples_is_reliable(self):
        st = compute([group("bm-test-a", [2000, 2500, 3000])], Query(), today=_dt.date.today())[0]
        self.assertTrue(st.reliable)

    def test_query_filters_by_gender(self):
        groups = [
            group("bm-f", [2000, 2500, 3000]),
            group("bm-m", [2100, 2600, 3100], gender="male"),
        ]
        st = compute(groups, Query(gender="male"), today=_dt.date.today())
        self.assertEqual(1, len(st))
        self.assertEqual("bm-m", st[0].bm["id"])

    def test_query_filters_by_age_range(self):
        groups = [
            group("bm-age0", [2000, 2500, 3000], ageFrom=0, ageTo=0),
            group("bm-age5", [3000, 3500, 4000], ageFrom=5, ageTo=5),
        ]
        self.assertEqual(1, len(compute(groups, Query(age=5), today=_dt.date.today())))
        self.assertEqual(0, len(compute(groups, Query(age=99), today=_dt.date.today())))

    def test_query_filters_by_product_type(self):
        groups = [
            group("bm-c", [2000, 2500, 3000], productType="consumption"),
            group("bm-s", [12000, 13000, 14000], productType="savings"),
        ]
        st = compute(groups, Query(ptype="savings"), today=_dt.date.today())
        self.assertEqual(1, len(st))
        self.assertEqual("bm-s", st[0].bm["id"])

    def test_stale_sample_warns(self):
        old = (_dt.date.today() - _dt.timedelta(days=400)).isoformat()
        g = group("bm-test-a", [2000, 2500, 3000])
        for s in g["samples"]:
            s["source"]["verifiedAt"] = old
        st = compute([g], Query(), today=_dt.date.today())[0]
        self.assertTrue(any("未复核" in w for w in st.warnings))

    def test_invalid_schema_still_returns_with_warning(self):
        g = group("bm-test-a", [2000, 2500, 3000])
        del g["samples"][0]["source"]["premiumQuote"]
        st = compute([g], Query(), today=_dt.date.today())[0]
        self.assertTrue(any("schema 不合法" in w for w in st.warnings))
        self.assertEqual(3, len(st.premiums))

    def test_empty_input_returns_empty(self):
        self.assertEqual([], compute([], Query()))

    def test_output_has_no_ranking_fields(self):
        st = compute([group("bm-test-a", [2000, 2500, 3000])], Query(), today=_dt.date.today())
        payload = json.dumps(to_json(st), ensure_ascii=False)
        for banned in ("rank", "score", "recommend", "best", "winner"):
            self.assertNotIn(f'"{banned}"', payload)

    def test_render_text_has_disclaimer(self):
        st = compute([group("bm-test-a", [2000, 2500, 3000])], Query(), today=_dt.date.today())
        text = benchmark.render_text(st)
        self.assertIn("不含任何产品优劣判断", text)
        self.assertIn("3 个", text)

    def test_render_text_empty_state_mentions_template(self):
        self.assertIn("_template.json", benchmark.render_text([]))


class TestLoading(unittest.TestCase):
    def test_template_file_excluded(self):
        self.assertTrue(BENCH_DIR.joinpath("_template.json").exists())
        with TemporaryDirectory() as tmp:
            import insurance.paths as paths
            old = paths.BENCH_DIR
            paths.BENCH_DIR = Path(tmp)
            try:
                self.assertEqual([], paths.benchmark_files())
                (Path(tmp) / "bm-x.json").write_text("{}", encoding="utf-8")
                self.assertEqual(1, len(paths.benchmark_files()))
            finally:
                paths.BENCH_DIR = old

    def test_load_bad_json_skips(self):
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "bm-bad.json"
            p.write_text("{not json", encoding="utf-8")
            import insurance.paths as paths
            old = paths.BENCH_DIR
            paths.BENCH_DIR = Path(tmp)
            try:
                self.assertEqual([], load_benchmarks())
            finally:
                paths.BENCH_DIR = old


if __name__ == "__main__":
    unittest.main(verbosity=2)