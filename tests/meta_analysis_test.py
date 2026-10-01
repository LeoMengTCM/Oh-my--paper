"""使用合成提取记录，通过真实 CLI 验证统计前置条件与计算。"""
import copy
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from systematic_review_test import review_fixture, row, STAMP, LATER

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "skills/systematic-review/scripts/meta_analysis.py"
SCOPE = {"comparison_id": "treatment-control", "outcome_id": "score", "timepoint_id": "week-12",
         "analysis_population": "ITT", "measurement_type": "final", "direction": "lower_is_better"}


def analysis_fixture(measure="MD", n_studies=3):
    review = review_fixture()
    for name in ("reports", "records", "studies", "screening_decisions"):
        review[name] = []
    review["search_runs"][0].update(identified_count=n_studies, retrieved_count=n_studies)
    unit, scale = ("risk", "binary") if measure == "RR" else ("points", "synthetic-scale")
    plan = row(analysis_id="primary-analysis", protocol_version="v1", effect_measure=measure,
               model="REML", ci_method="z", confidence_level=0.95, unit=unit, scale_id=scale,
               zero_cell_correction="none", double_zero_policy="exclude", target_effect="assignment",
               clinically_poolable=True, pooling_rationale="合成研究的人群、比较和结局一致", approved_by="alice", approved_at=STAMP,
               extraction_ids=[f"extract-{i}" for i in range(1, n_studies + 1)], **SCOPE)
    extractions, rob = [], []
    for i in range(1, n_studies + 1):
        sid, rid, eid = f"study-{i}", f"report-{i}", f"extract-{i}"
        review["studies"].append(row(study_id=sid, design="parallel-rct"))
        review["reports"].append(row(report_id=rid, title=f"Synthetic report {i}", retrieval_status="retrieved",
                                     study_link={"study_id": sid, "protocol_version": "v1", "confirmed_by": "alice",
                                                 "confirmed_at": LATER, "reason": "合成数据身份核对"}))
        review["records"].append(row(record_id=f"record-{i}", report_id=rid, search_run_id="search-1", source_record_id=str(i)))
        for stage in ("title_abstract", "full_text"):
            for reviewer in ("alice", "bob"):
                review["screening_decisions"].append(row(decision_id=f"{i}-{stage}-{reviewer}", report_id=rid,
                    protocol_version="v1", stage=stage, reviewer_id=reviewer, decided_at=LATER, role="initial", decision="include"))
        if measure == "RR":
            values = {"n_intervention": 100, "n_comparator": 100, "events_intervention": 20, "events_comparator": 40}
        else:
            values = {"n_intervention": 20, "n_comparator": 20, "mean_intervention": 10 - i,
                      "mean_comparator": 10, "sd_intervention": 1, "sd_comparator": 1}
        extractions.append(row(extraction_id=eid, study_id=sid, protocol_version="v1", effect_measure=measure,
            label=f"Study {i}", unit=unit, scale_id=scale, intervention_arm="t", comparator_arm="c",
            verified_by="alice", verified_at=LATER, data=values, original_data=dict(values), transformation="identity",
            evidence=[{"evidence_id": "table-1", "report_id": rid, "document_path": f"report-{i}.txt", "locator": "表1，第2页",
                       "quote": "合成原文数值：" + json.dumps(values)}],
            provenance={key: "table-1" for key in values}, risk_of_bias_id=f"rob-{i}", **SCOPE))
        rob.append(row(assessment_id=f"rob-{i}", study_id=sid, protocol_version="v1", target_effect="assignment",
            comparison_id=SCOPE["comparison_id"], outcome_id=SCOPE["outcome_id"], timepoint_id=SCOPE["timepoint_id"],
            analysis_population="ITT", tool="RoB2", tool_version="2019-08-22", overall_judgment="low",
            domains={key: {"judgment": "low", "rationale": "合成判断，不是真实评估"} for key in
                     ("randomization", "deviations", "missing_data", "measurement", "selection")},
            assessment_document=f"rob-{i}.md", reviewed_by="bob", reviewed_at=LATER))
    return review, plan, extractions, rob


class MetaAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="omp-meta-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.review_dir = self.root / "review"
        self.review_dir.mkdir()
        self.plan_file = self.root / "plan.json"
        self.review, self.plan, self.extractions, self.rob = analysis_fixture()

    def save(self):
        self.plan_file.write_text(json.dumps(self.plan, ensure_ascii=False), encoding="utf-8")
        (self.review_dir / "review.json").write_text(json.dumps(self.review["review"]), encoding="utf-8")
        for name, rows in {**{k: v for k, v in self.review.items() if k != "review"},
                           "extractions": self.extractions, "rob2": self.rob}.items():
            (self.review_dir / f"{name}.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
        for name in ("protocol-v1.md", "sap-v1.md"):
            (self.review_dir / name).write_text("合成方案，不是真实研究。", encoding="utf-8")
        for i in range(1, len(self.extractions) + 1):
            (self.review_dir / f"report-{i}.txt").write_text("合成原文，请勿用作真实研究证据。", encoding="utf-8")
            (self.review_dir / f"rob-{i}.md").write_text("合成 RoB 2 文件，不是真实评估。", encoding="utf-8")

    def run_cli(self, command="validate", *args):
        self.save()
        before = {p.name: p.read_bytes() for p in self.review_dir.iterdir() if p.is_file()}
        result = subprocess.run([sys.executable, str(CLI), command, str(self.review_dir), "--plan", str(self.plan_file), *args],
                                capture_output=True, text=True, timeout=120)
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.review_dir.iterdir() if p.is_file()},
                         "分析不得修改权威研究记录")
        return result

    def assert_invalid(self):
        result = self.run_cli()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertEqual(json.loads(result.stderr)["status"], "error")

    def test_plan_requires_supported_methods_and_real_human_confirmation(self):
        patches = [{"effect_measure": "HR"}, {"model": "automatic"}, {"ci_method": "best-p"},
                   {"confidence_level": True}, {"confidence_level": 1}, {"approved_by": "assistant"},
                   {"protocol_version": "old"}, {"extraction_ids": ["extract-1", "extract-1"]},
                   {"pooling_rationale": ""}]
        for patch in patches:
            with self.subTest(patch=patch):
                self.review, self.plan, self.extractions, self.rob = analysis_fixture()
                self.plan.update(patch)
                self.assert_invalid()

    def test_duplicate_study_and_mixed_scope_are_rejected(self):
        for patch in [{"study_id": "study-1"}, {"unit": "different"}, {"scale_id": "other-scale"},
                      {"outcome_id": "another"}, {"timepoint_id": "week-24"}, {"analysis_population": "PP"},
                      {"measurement_type": "change"}, {"direction": "higher_is_better"}]:
            with self.subTest(patch=patch):
                self.review, self.plan, self.extractions, self.rob = analysis_fixture()
                self.extractions[1].update(patch)
                self.assert_invalid()
        self.review, self.plan, self.extractions, self.rob = analysis_fixture()
        self.review["studies"][0]["design"] = "cluster-rct"
        self.assert_invalid()

    def test_all_numeric_values_require_sources_and_human_verification(self):
        mutations = [
            lambda e: e["provenance"].pop("n_intervention"),
            lambda e: e["evidence"][0].update(quote=""),
            lambda e: e["evidence"][0].update(document_path="missing.txt"),
            lambda e: e["evidence"][0].update(report_id="report-2"),
            lambda e: e.update(verified_by="assistant"),
            lambda e: e["original_data"].update(mean_intervention=123),
            lambda e: e.update(transformation="estimated_sd"),
        ]
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                self.review, self.plan, self.extractions, self.rob = analysis_fixture()
                mutate(self.extractions[0])
                self.assert_invalid()

    def test_invalid_numbers_and_unsupported_zero_event_rules_are_rejected(self):
        for patch in [{"n_intervention": True}, {"n_intervention": 1.5}, {"sd_intervention": -1},
                      {"mean_intervention": None}, {"sd_intervention": 0, "sd_comparator": 0}]:
            with self.subTest(patch=patch):
                self.review, self.plan, self.extractions, self.rob = analysis_fixture()
                self.extractions[0]["data"].update(patch)
                self.extractions[0]["original_data"].update(patch)
                self.assert_invalid()
        self.review, self.plan, self.extractions, self.rob = analysis_fixture("RR")
        self.extractions[0]["data"]["events_intervention"] = 101
        self.extractions[0]["original_data"]["events_intervention"] = 101
        self.assert_invalid()
        self.review, self.plan, self.extractions, self.rob = analysis_fixture("RR")
        self.plan.pop("zero_cell_correction")
        self.assert_invalid()

    def test_risk_of_bias_must_match_the_result_and_reference_a_manual_assessment(self):
        for patch in [{"outcome_id": "other"}, {"protocol_version": "old"}, {"reviewed_by": "assistant"},
                      {"assessment_document": "missing.md"}, {"overall_judgment": "score-8"}]:
            with self.subTest(patch=patch):
                self.review, self.plan, self.extractions, self.rob = analysis_fixture()
                self.rob[0].update(patch)
                self.assert_invalid()
        self.review, self.plan, self.extractions, self.rob = analysis_fixture()
        self.rob[0]["domains"]["randomization"]["judgment"] = "high"
        self.assert_invalid()

    def test_incomplete_review_or_unpoolable_question_does_not_start_analysis(self):
        self.review["screening_decisions"].pop()
        result = self.run_cli()
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(json.loads(result.stdout)["reason"], "screening_incomplete")
        self.review, self.plan, self.extractions, self.rob = analysis_fixture()
        self.plan["clinically_poolable"] = False
        result = self.run_cli()
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(json.loads(result.stdout)["reason"], "not_poolable")

    def require_statistics(self):
        try:
            probe = subprocess.run([os.environ.get("RSCRIPT", "Rscript"), "--vanilla", "-e",
                'quit(status=if (requireNamespace("metafor", quietly=TRUE) && requireNamespace("jsonlite", quietly=TRUE)) 0 else 42)'],
                capture_output=True, text=True, timeout=30)
            available = probe.returncode == 0
        except OSError:
            available = False
        if not available:
            if os.environ.get("OMP_REQUIRE_R") == "1":
                self.fail("统计验收要求 R、metafor 和 jsonlite 可用，不能以跳过代替通过")
            self.skipTest("未安装统计依赖；运行 test:sr:stats 可要求依赖必须存在")

    def run_statistics(self, output_name="analysis"):
        self.require_statistics()
        out = self.root / output_name
        result = self.run_cli("run", "--out", str(out))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        manifest = json.loads((out / "run_manifest.json").read_text())
        self.assertEqual(manifest["status"], "completed")
        self.assertIn("summary.json", manifest["artifact_sha256"])
        return out, json.loads((out / "summary.json").read_text())

    def test_real_md_reml_matches_closed_form(self):
        out, summary = self.run_statistics()
        self.assertEqual(summary["analysis_status"], "pooled")
        self.assertAlmostEqual(summary["estimate"], -2, places=7)
        self.assertAlmostEqual(summary["tau2"], 0.9, places=6)
        self.assertAlmostEqual(summary["se_analysis"], math.sqrt(1 / 3), places=6)
        self.assertAlmostEqual(summary["ci_lower"], -2 - 1.959963984540054 * math.sqrt(1 / 3), places=6)
        self.assertAlmostEqual(summary["Q"], 20, places=6)
        self.assertAlmostEqual(summary["Q_p"], math.exp(-10), places=8)
        for name in ("input.csv", "prepared.json", "source_snapshot.json", "pairwise_meta.R", "effects.csv", "forest.pdf", "forest.png", "sessionInfo.txt", "ledger_entries.md", "summary_of_findings_draft.csv"):
            self.assertTrue((out / name).is_file(), name)

    def test_real_rr_is_reported_on_ratio_scale(self):
        self.review, self.plan, self.extractions, self.rob = analysis_fixture("RR")
        out, summary = self.run_statistics()
        self.assertEqual(summary["display_scale"], "ratio")
        self.assertAlmostEqual(summary["estimate"], 0.5, places=7)
        self.assertAlmostEqual(summary["estimate_analysis"], math.log(0.5), places=7)
        expected_se = math.sqrt((1 / 20 - 1 / 100 + 1 / 40 - 1 / 100) / 3)
        self.assertAlmostEqual(summary["ci_lower"], math.exp(math.log(0.5) - 1.959963984540054 * expected_se), places=6)

    def test_real_smd_uses_hedges_correction_and_ls_variance(self):
        import csv
        self.review, self.plan, self.extractions, self.rob = analysis_fixture("SMD")
        self.extractions[1].update(unit="different-scale-points", scale_id="another-scale")
        out, summary = self.run_statistics()
        with (out / "effects.csv").open(encoding="utf-8", newline="") as handle:
            effects = list(csv.DictReader(handle))
        j = math.exp(math.lgamma(19) - 0.5 * math.log(19) - math.lgamma(18.5))
        self.assertAlmostEqual(float(effects[0]["yi"]), -j, places=7)
        self.assertAlmostEqual(float(effects[0]["vi"]), 0.1 + j * j / 80, places=7)
        self.assertEqual(summary["display_scale"], "standardized_difference")

    def test_real_zero_cell_policy_is_explicit_and_double_zero_is_retained(self):
        import csv
        self.review, self.plan, self.extractions, self.rob = analysis_fixture("RR")
        self.plan["zero_cell_correction"] = "constant_0.5"
        for index, values in [(0, {"events_intervention": 0, "events_comparator": 10}),
                              (2, {"events_intervention": 0, "events_comparator": 0})]:
            self.extractions[index]["data"].update(values)
            self.extractions[index]["original_data"].update(values)
        out, summary = self.run_statistics()
        self.assertEqual((summary["k_selected"], summary["k_analyzed"], summary["k_excluded"]), (3, 2, 1))
        self.assertEqual(summary["excluded"][0]["study_id"], "study-3")
        with (out / "effects.csv").open(encoding="utf-8", newline="") as handle:
            effects = list(csv.DictReader(handle))
        self.assertAlmostEqual(float(effects[0]["estimate"]), 1 / 21, places=7)
        self.assertEqual(effects[0]["corrected"], "TRUE")
        self.assertEqual(effects[1]["corrected"], "FALSE")

    def test_real_single_study_and_no_estimable_effect_are_not_fake_meta_analyses(self):
        self.plan["extraction_ids"] = ["extract-1"]
        out, summary = self.run_statistics("single")
        self.assertEqual(summary["analysis_status"], "single_study")
        self.assertIsNone(summary["tau2"])
        self.assertIsNone(summary["model_applied"])
        self.assertEqual(summary["ci_method_applied"], "normal_single_study")
        self.review, self.plan, self.extractions, self.rob = analysis_fixture("RR")
        for extraction in self.extractions:
            extraction["data"].update(events_intervention=0, events_comparator=0)
            extraction["original_data"].update(events_intervention=0, events_comparator=0)
        out, summary = self.run_statistics("none")
        self.assertEqual(summary["analysis_status"], "not_estimable")
        self.assertIsNone(summary["estimate"])
        self.assertEqual(summary["k_excluded"], 3)
        self.assertFalse((out / "forest.pdf").exists())

    def test_real_knha_uses_the_prespecified_interval_method(self):
        self.plan["ci_method"] = "knha"
        out, summary = self.run_statistics()
        self.assertEqual(summary["ci_method_applied"], "knha")
        self.assertAlmostEqual(summary["ci_lower"], -2 - 4.302652729911275 * math.sqrt(1 / 3), places=6)
        self.assertAlmostEqual(summary["ci_upper"], -2 + 4.302652729911275 * math.sqrt(1 / 3), places=6)

    def test_run_refuses_existing_output_and_preserves_files(self):
        out = self.root / "existing"
        out.mkdir()
        (out / "keep.txt").write_text("原文件", encoding="utf-8")
        result = self.run_cli("run", "--out", str(out))
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertEqual((out / "keep.txt").read_text(encoding="utf-8"), "原文件")

    def test_missing_r_does_not_create_a_result_directory(self):
        out = self.root / "missing-r"
        result = self.run_cli("run", "--out", str(out), "--rscript", str(self.root / "not-an-executable"))
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(json.loads(result.stdout)["reason"], "r_dependencies_missing")
        self.assertFalse(out.exists())

    @unittest.skipIf(os.name == "nt", "此故障注入使用 POSIX 包装脚本")
    def test_r_failure_and_malformed_success_are_recorded_as_failed(self):
        import shlex
        import shutil
        self.require_statistics()
        real_r = shutil.which(os.environ.get("RSCRIPT", "Rscript"))
        fake = self.root / "r-wrapper"
        for malformed in (False, True):
            with self.subTest(malformed=malformed):
                out = self.root / ("malformed" if malformed else "failed")
                suffix = ("printf '%s' '{\"analysis_id\":\"primary-analysis\",\"measure\":\"MD\",\"k_selected\":3,\"analysis_status\":\"pooled\"}' > \"$5/summary.json\"\nexit 0\n"
                          if malformed else "printf 'synthetic R failure\\n' >&2\nexit 7\n")
                fake.write_text("#!/bin/sh\nif [ \"$2\" = \"-e\" ]; then exec " + shlex.quote(real_r) + " \"$@\"; fi\n" + suffix, encoding="utf-8")
                fake.chmod(0o755)
                result = self.run_cli("run", "--out", str(out), "--rscript", str(fake))
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                manifest = json.loads((out / "run_manifest.json").read_text())
                self.assertEqual(manifest["status"], "failed")
                self.assertTrue((out / "run.stderr.txt").is_file())
                self.assertTrue(manifest["error"])

    def test_summary_of_findings_is_only_a_draft_without_invented_grade(self):
        import csv
        out, summary = self.run_statistics()
        with (out / "summary_of_findings_draft.csv").open(encoding="utf-8", newline="") as handle:
            draft = next(csv.DictReader(handle))
        self.assertEqual(draft["grade_status"], "not_assessed")
        self.assertEqual(draft["certainty"], "")
        self.assertEqual(draft["baseline_risk"], "")
        self.assertEqual(float(draft["estimate"]), summary["estimate"])
        self.assertEqual(int(draft["participants_analyzed"]), 120)

    def test_large_forest_is_paginated_without_refitting_subsets(self):
        self.review, self.plan, self.extractions, self.rob = analysis_fixture(n_studies=41)
        out, summary = self.run_statistics()
        self.assertEqual(summary["k_analyzed"], 41)
        self.assertEqual(summary["forest_pages"], 2)
        self.assertAlmostEqual(summary["estimate"], -21, places=6)
        for name in ("forest.pdf", "forest.png", "forest-page-001.png", "forest-page-002.png"):
            self.assertGreater((out / name).stat().st_size, 0)

    def test_bundled_analysis_example_validates_without_r(self):
        example = ROOT / "skills/systematic-review/examples/pairwise-analysis"
        result = subprocess.run([sys.executable, str(CLI), "validate", str(example), "--plan", str(example / "analysis_plan.json")],
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["selected_studies"], 3)

    def test_verified_extractions_prepare_a_three_study_analysis(self):
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "ready")
        self.assertEqual(payload["selected_studies"], 3)
        self.assertEqual(payload["analysis_id"], "primary-analysis")


if __name__ == "__main__":
    unittest.main()
