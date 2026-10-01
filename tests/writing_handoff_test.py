"""交接包的文件级测试。研究与核验记录均为模拟数据，不是临床证据。"""
import copy
import csv
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from meta_analysis_test import analysis_fixture
import meta_analysis_test

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills/systematic-review/scripts"
sys.path.insert(0, str(SCRIPTS))
from analysis_records import prepare_analysis, DATA_FIELDS
from artifact_integrity import artifact_digests

CLI = SCRIPTS / "writing_handoff.py"
BUILDER = ROOT / "skills/literature-pdf-ocr-library/scripts/build_bibliography.py"


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


class WritingHandoffTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="omp-handoff-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.review_dir = self.root / "review"
        self.review_dir.mkdir()
        self.review, self.plan, self.extractions, self.rob = analysis_fixture()
        # 正向用例模拟 research 输入；所有数据仍只存在于测试临时目录。
        self.review["review"]["purpose"] = "research"
        self.config = {"schema_version": 1, "purpose": "research", "protocol_version": "v1", "analyses": [],
                       "synthesis_mode": "quantitative", "bibliography": "library/bibliography.json",
                       "report_citations": {}, "method_citations": [], "verification_records": "verifications.jsonl"}
        self.plan_file = self.review_dir / "analysis_plan.json"
        self.config_file = self.review_dir / "publication.json"
        self.write_review()
        self.make_citations()
        self.run_dir = self.make_run("run-1")
        self.config["analyses"] = [{"run_directory": str(self.run_dir), "plan_path": "analysis_plan.json", "role": "primary"}]

    def write_review(self):
        write_json(self.review_dir / "review.json", self.review["review"])
        write_json(self.plan_file, self.plan)
        for name, rows in {**{key: value for key, value in self.review.items() if key != "review"},
                           "extractions": self.extractions, "rob2": self.rob}.items():
            (self.review_dir / f"{name}.jsonl").write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
        for name in ("protocol-v1.md", "sap-v1.md", *[f"report-{i}.txt" for i in range(1, 4)], *[f"rob-{i}.md" for i in range(1, 4)]):
            (self.review_dir / name).write_text("合成测试文件，不是真实原文或人工审批。", encoding="utf-8")

    def make_citations(self):
        library = self.review_dir / "library"
        for i, report in enumerate(self.review["reports"], 1):
            directory = library / "papers" / str(i)
            directory.mkdir(parents=True)
            write_json(directory / "metadata.json", {"title": report["title"], "authors": [f"Alex Example{i}"],
                "year": 2020, "venue": "Synthetic Journal", "doi": f"10.1000/fixture{i}", "source": "crossref"})
        result = subprocess.run([sys.executable, str(BUILDER), "--library-root", str(library)], capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        bibliography = json.loads((library / "bibliography.json").read_text())
        records = []
        for key, entry in bibliography["entries"].items():
            report = next(item for item in self.review["reports"] if item["title"] == entry["title"])
            self.config["report_citations"][report["report_id"]] = key
            i = report["report_id"].split("-")[-1]
            evidence_path = f"crossref-{i}.json"
            write_json(self.review_dir / evidence_path, {"message": {"DOI": entry["doi"], "title": [entry["title"]],
                "author": [{"given": "Alex", "family": f"Example{i}"}], "issued": {"date-parts": [[2020]]},
                "container-title": ["Synthetic Journal"]}})
            records.append({"schema_version": 1, "verification_id": f"verify-{i}", "citation_key": key,
                "source_type": "crossref", "source_url": "https://api.crossref.org/works/" + entry["doi"],
                "evidence_path": evidence_path, "checked_by": "assistant", "checked_at": "2026-01-03T10:00:00Z"})
        (self.review_dir / "verifications.jsonl").write_text("".join(json.dumps(row) + "\n" for row in records), encoding="utf-8")

    def make_run(self, name):
        out = self.root / name
        out.mkdir()
        prepared = prepare_analysis(self.review_dir, self.plan_file)
        write_json(out / "prepared.json", {key: prepared[key] for key in ("schema_version", "analysis_id", "plan")})
        write_json(out / "source_snapshot.json", prepared["source_snapshot"])
        with (out / "input.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["extraction_id", "study_id", "label", "rob_judgment", *DATA_FIELDS])
            writer.writeheader()
            writer.writerows(prepared["rows"])
        se = math.sqrt(1 / 3)
        summary = {"schema_version": 1, "analysis_id": self.plan["analysis_id"], "analysis_status": "pooled",
            "k_selected": 3, "k_analyzed": 3, "k_excluded": 0, "measure": "MD", "model_requested": "REML", "model_applied": "REML",
            "ci_method_requested": "z", "ci_method_applied": "z", "confidence_level": 0.95, "direction": "lower_is_better",
            "display_scale": "difference", "estimate": -2, "ci_lower": -2 - 1.959963984540054 * se,
            "ci_upper": -2 + 1.959963984540054 * se, "estimate_analysis": -2,
            "ci_lower_analysis": -2 - 1.959963984540054 * se, "ci_upper_analysis": -2 + 1.959963984540054 * se,
            "se_analysis": se, "tau2": 0.9, "I2": 90, "Q": 20, "Q_p": math.exp(-10), "forest_pages": 1,
            "excluded": [], "warnings": [], "software": {"R": "fixture", "metafor": "fixture", "jsonlite": "fixture"}}
        write_json(out / "summary.json", summary)
        with (out / "effects.csv").open("w", encoding="utf-8", newline="") as handle:
            fields = ["extraction_id", "study_id", "label", "yi", "vi", "se", "estimate", "ci_lower", "ci_upper", "weight_percent", "corrected"]
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for i, item in enumerate(prepared["rows"], 1):
                writer.writerow({**{key: item[key] for key in ("extraction_id", "study_id", "label")},
                    "yi": -i, "vi": 0.1, "se": math.sqrt(0.1), "estimate": -i,
                    "ci_lower": -i - 1.959963984540054 * math.sqrt(0.1), "ci_upper": -i + 1.959963984540054 * math.sqrt(0.1),
                    "weight_percent": 100 / 3, "corrected": "FALSE"})
        (out / "exclusions.csv").write_text("extraction_id,study_id,reason\n", encoding="utf-8")
        for artifact in ("pairwise_meta.R", "sessionInfo.txt", "forest.pdf", "forest.png", "ledger_entries.md"):
            (out / artifact).write_text("synthetic artifact: not a real execution or publication figure", encoding="utf-8")
        manifest = {"schema_version": 1, "run_id": name, "analysis_id": self.plan["analysis_id"], "protocol_version": "v1",
                    "status": "completed", "analysis_status": "pooled", "software": summary["software"]}
        write_json(out / "run_manifest.json", manifest)
        manifest["artifacts"] = sorted(path.name for path in out.iterdir())
        manifest["artifact_sha256"] = artifact_digests(out, manifest["artifacts"])
        write_json(out / "run_manifest.json", manifest)
        return out

    def invoke(self, command="check", *args):
        write_json(self.config_file, self.config)
        before = {str(path.relative_to(self.root)): path.read_bytes() for path in self.root.rglob("*") if path.is_file()}
        result = subprocess.run([sys.executable, str(CLI), command, str(self.review_dir), "--config", str(self.config_file), *args],
                                capture_output=True, text=True, timeout=30)
        for name, content in before.items():
            self.assertEqual((self.root / name).read_bytes(), content, f"交接不得改写原文件：{name}")
        return result

    def test_complete_current_records_are_ready_for_drafting_not_submission(self):
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["ready_for_drafting"])
        self.assertEqual(payload["submission_readiness"], "not_assessed")
        self.assertEqual(payload["counts"]["studies_in_quantitative_synthesis"], 3)
        self.assertEqual(len(payload["analyses"]), 1)
        self.assertEqual(len(payload["citations"]["used_keys"]), 3)

    def assert_partial(self, code):
        result = self.invoke()
        self.assertEqual(result.returncode, 2, result.stderr)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["ready_for_drafting"])
        self.assertIn(code, [item["code"] for item in payload["blockers"]])
        return payload

    def refresh_digests(self):
        path = self.run_dir / "run_manifest.json"
        manifest = json.loads(path.read_text())
        manifest["artifact_sha256"] = artifact_digests(self.run_dir, manifest["artifacts"])
        write_json(path, manifest)

    def test_old_plan_and_changed_sources_do_not_reuse_results(self):
        self.plan["pooling_rationale"] = "重新确认后的不同理由"
        self.write_review()
        payload = self.assert_partial("analysis_not_current")
        self.assertIsNone(payload["counts"]["studies_in_quantitative_synthesis"])
        self.plan["pooling_rationale"] = "合成研究的人群、比较和结局一致"
        self.extractions[0]["data"]["mean_intervention"] = 1
        self.extractions[0]["original_data"]["mean_intervention"] = 1
        self.write_review()
        self.assert_partial("analysis_not_current")

    def test_modified_results_and_old_manifests_are_rejected(self):
        for name in ("summary.json", "effects.csv", "forest.pdf"):
            with self.subTest(name=name):
                path = self.run_dir / name
                original = path.read_bytes()
                path.write_bytes(original + b"changed")
                self.assert_partial("analysis_not_current")
                path.write_bytes(original)
        path = self.run_dir / "run_manifest.json"
        manifest = json.loads(path.read_text())
        manifest.pop("artifact_sha256")
        write_json(path, manifest)
        self.assert_partial("analysis_not_current")

    def test_failed_run_cannot_export_results(self):
        path = self.run_dir / "run_manifest.json"
        manifest = json.loads(path.read_text())
        manifest["status"] = "failed"
        write_json(path, manifest)
        out = self.root / "partial-handoff"
        result = self.invoke("build", "--out", str(out))
        self.assertEqual(result.returncode, 2, result.stderr)
        with (out / "results.csv").open() as handle:
            self.assertEqual(list(csv.DictReader(handle)), [])
        payload = json.loads((out / "handoff.json").read_text())
        self.assertEqual(payload["status"], "partial")
        self.assertFalse(payload["ready_for_drafting"])
        self.assertIsNone(payload["counts"]["studies_in_quantitative_synthesis"])

    def test_output_identity_is_checked_even_with_matching_digests(self):
        path = self.run_dir / "effects.csv"
        path.write_text(path.read_text().replace("study-1", "another-study"))
        self.refresh_digests()
        self.assert_partial("analysis_not_current")

    def test_input_csv_must_match_current_extractions(self):
        path = self.run_dir / "input.csv"
        path.write_text(path.read_text().replace(",9,", ",999,"))
        self.refresh_digests()
        self.assert_partial("analysis_not_current")

    def test_missing_required_digest_cannot_be_hidden_by_manifest(self):
        path = self.run_dir / "run_manifest.json"
        manifest = json.loads(path.read_text())
        manifest["artifacts"].remove("summary.json")
        del manifest["artifact_sha256"]["summary.json"]
        write_json(path, manifest)
        self.assert_partial("analysis_not_current")

    def test_multiple_analyses_count_the_union_of_studies(self):
        second = self.make_run("run-2")
        self.config["analyses"].append({"run_directory": str(second), "plan_path": "analysis_plan.json", "role": "sensitivity"})
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["counts"]["studies_in_quantitative_synthesis"], 3)
        manifest_path = second / "run_manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["status"] = "failed"
        write_json(manifest_path, manifest)
        payload = self.assert_partial("analysis_not_current")
        self.assertIsNone(payload["counts"]["studies_in_quantitative_synthesis"])

    def test_duplicate_registration_is_an_input_error(self):
        self.config["analyses"] *= 2
        result = self.invoke()
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stderr)["status"], "error")

    def test_incomplete_screening_and_stale_publication_are_partial(self):
        self.config["protocol_version"] = "old"
        self.assert_partial("publication_version_stale")
        self.config["protocol_version"] = "v1"
        self.review["screening_decisions"].pop()
        self.write_review()
        payload = self.assert_partial("analysis_not_current")
        self.assertFalse(payload["screening"]["screening_complete"])

    def test_missing_citation_or_verification_remains_partial(self):
        key = self.config["report_citations"].pop("report-1")
        self.assert_partial("citation_report_missing")
        self.config["report_citations"]["report-1"] = key
        (self.review_dir / "verifications.jsonl").write_text("")
        self.assert_partial("citation_unverified")

    def test_software_and_benchmark_material_cannot_be_relabelled_research(self):
        for purpose in ("software_validation", "public_benchmark"):
            with self.subTest(purpose=purpose):
                self.review["review"]["purpose"] = purpose
                self.config["purpose"] = purpose
                self.write_review()
                self.assert_partial("validation_material")
                self.config["purpose"] = "research"
                self.assert_partial("purpose_mismatch")

    def test_missing_runs_and_unconfirmed_narrative_are_partial(self):
        self.config["analyses"] = []
        self.assert_partial("analysis_missing")
        self.config["synthesis_mode"] = "narrative"
        self.assert_partial("narrative_unconfirmed")
        self.config.update(narrative_reason="预设临床判断认为研究不可合并", narrative_approved_by="alice",
                           narrative_approved_at="2026-01-03T10:00:00Z")
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["counts"]["studies_in_quantitative_synthesis"], 0)

    def test_build_preserves_source_numbers_and_refuses_overwrite(self):
        out = self.root / "handoff"
        result = self.invoke("build", "--out", str(out))
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads((out / "handoff.json").read_text())
        self.assertEqual(payload["package_status"], "completed")
        with (out / "results.csv").open() as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(float(rows[0]["estimate"]), -2)
        with (out / "study_results.csv").open() as handle:
            effects = list(csv.DictReader(handle))
        self.assertEqual(len(effects), 3)
        self.assertEqual(effects[0]["vi"], "0.1")
        self.assertEqual((out / "analyses/run-001/summary.json").read_bytes(), (self.run_dir / "summary.json").read_bytes())
        self.assertEqual((out / "refs/references.bib").read_text(), payload["citations"]["bibtex"])
        result = self.invoke("build", "--out", str(out))
        self.assertEqual(result.returncode, 1)
        self.assertIn("已存在", result.stderr)

    def test_build_cannot_write_inside_an_original_run(self):
        result = self.invoke("build", "--out", str(self.run_dir / "handoff"))
        self.assertEqual(result.returncode, 1)
        self.assertFalse((self.run_dir / "handoff").exists())

    def test_real_r_run_exports_and_single_study_is_not_counted_as_meta(self):
        meta_analysis_test.MetaAnalysisTests.require_statistics(self)
        for k, expected_status in ((3, "pooled"), (1, "single_study")):
            with self.subTest(k=k):
                self.plan["extraction_ids"] = [f"extract-{i}" for i in range(1, k + 1)]
                self.write_review()
                out = self.root / f"real-run-{k}"
                result = subprocess.run([sys.executable, str(SCRIPTS / "meta_analysis.py"), "run", str(self.review_dir),
                                         "--plan", str(self.plan_file), "--out", str(out)], capture_output=True, text=True, timeout=120)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.config["analyses"][0]["run_directory"] = str(out)
                result = self.invoke("build", "--out", str(self.root / f"real-handoff-{k}"))
                self.assertEqual(result.returncode, 0, result.stderr)
                payload = json.loads(result.stdout)
                self.assertEqual(payload["counts"]["studies_in_quantitative_synthesis"], k if k > 1 else 0)
                self.assertEqual(payload["analyses"][0]["summary"]["analysis_status"], expected_status)


if __name__ == "__main__":
    unittest.main()
