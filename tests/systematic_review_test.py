"""仅使用合成数据，通过真实 CLI 验证综述记录。"""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "skills/systematic-review/scripts/review_state.py"
STAMP = "2026-01-01T10:00:00Z"
LATER = "2026-01-02T10:00:00Z"


def row(**fields):
    return {"schema_version": 1, **fields}


def review_fixture():
    return {
        "review": row(
            review_id="synthetic-review", protocol_version="v1", screening_mode="dual",
            screeners=["alice", "bob"],
            reviewers=[{"reviewer_id": "alice", "kind": "human"},
                       {"reviewer_id": "bob", "kind": "human"},
                       {"reviewer_id": "referee", "kind": "human"},
                       {"reviewer_id": "assistant", "kind": "ai"}],
            registration={"status": "not_registered", "reason": "合成测试，不是真实研究"},
        ),
        "approvals": [row(approval_id="approval-1", protocol_version="v1", reviewer_id="alice",
                          approved_at=STAMP, screening_mode="dual", registration_status="not_registered",
                          acknowledged_limitations=True, protocol_document="protocol-v1.md",
                          sap_document="sap-v1.md")],
        "search_runs": [row(search_run_id="search-1", source="PubMed", source_type="database",
                            query="synthetic fixture", searched_at=STAMP, status="complete",
                            identified_count=1, retrieved_count=1)],
        "records": [row(record_id="record-1", search_run_id="search-1", source_record_id="1", report_id="report-1")],
        "reports": [row(report_id="report-1", title="合成报告，不是真实论文", retrieval_status="not_requested")],
        "studies": [],
        "screening_decisions": [],
    }


class ReviewStateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="omp-sr-test-")
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.data = review_fixture()

    def save(self):
        (self.directory / "review.json").write_text(json.dumps(self.data["review"], ensure_ascii=False), encoding="utf-8")
        for name, records in self.data.items():
            if name != "review":
                (self.directory / f"{name}.jsonl").write_text(
                    "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records), encoding="utf-8")
        for name in ["protocol-v1.md", "sap-v1.md"]:
            (self.directory / name).write_text("合成测试方案 v1，不是真实研究。\n", encoding="utf-8")

    def run_cli(self, command="validate", *args, save=True):
        if save:
            self.save()
        before = {p.name: p.read_bytes() for p in self.directory.iterdir()}
        result = subprocess.run([sys.executable, str(CLI), command, str(self.directory), *args],
                                capture_output=True, text=True, timeout=20)
        after = {p.name: p.read_bytes() for p in self.directory.iterdir()}
        self.assertEqual(before, after, "校验与计数不得写回研究记录")
        return result

    def test_invalid_records_are_errors_not_partial_results(self):
        mutations = [
            lambda d: d["review"].update(schema_version=2),
            lambda d: d["review"].update(screeners=["alice", "assistant"]),
            lambda d: d["review"].update(screeners=["alice", "alice"]),
            lambda d: d["reports"].append(dict(d["reports"][0])),
            lambda d: d["records"][0].update(report_id="missing"),
            lambda d: d["records"][0].update(search_run_id="missing"),
            lambda d: d["search_runs"][0].update(retrieved_count=2),
            lambda d: d["search_runs"][0].update(identified_count=-1),
            lambda d: d["search_runs"][0].update(identified_count=True),
            lambda d: d["search_runs"][0].update(searched_at="yesterday"),
            lambda d: d["approvals"][0].update(reviewer_id="assistant"),
            lambda d: d["approvals"][0].update(protocol_document="missing.md"),
            lambda d: d["reports"][0].update(retrieval_status="download_clicked"),
        ]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                self.data = review_fixture()
                mutate(self.data)
                result = self.run_cli()
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertEqual(result.stdout, "")
                self.assertEqual(json.loads(result.stderr)["status"], "error")

    def decision(self, reviewer, decision="exclude", stage="title_abstract", **extra):
        item = row(decision_id=f"decision-{len(self.data['screening_decisions']) + 1}",
                   report_id="report-1", protocol_version="v1", stage=stage,
                   reviewer_id=reviewer, decision=decision, reason="合成纳排理由",
                   decided_at=LATER, role="initial")
        item.update(extra)
        self.data["screening_decisions"].append(item)
        return item

    def test_two_independent_humans_can_exclude_a_report(self):
        self.decision("alice")
        self.decision("bob")
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["screening_complete"])
        self.assertEqual(payload["report_states"][0]["title_abstract"]["status"], "exclude")

    def test_ai_judgment_does_not_supply_second_human(self):
        self.decision("alice")
        self.decision("assistant")
        result = self.run_cli()
        self.assertEqual(result.returncode, 2, result.stderr)
        state = json.loads(result.stdout)["report_states"][0]["title_abstract"]
        self.assertEqual(state["status"], "pending")
        self.assertEqual(state["human_decisions"], 1)
        self.assertEqual(state["ai_suggestions"], 1)

    def test_single_screener_is_reported_as_a_limitation(self):
        self.data["review"].update(screening_mode="single", screeners=["alice"])
        self.data["approvals"][0]["screening_mode"] = "single"
        self.decision("alice")
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("single_screener", json.loads(result.stdout)["limitations"])

    def test_current_protocol_requires_its_own_approval(self):
        self.decision("alice")
        self.decision("bob")
        self.data["review"]["protocol_version"] = "v2"
        result = self.run_cli()
        self.assertEqual(result.returncode, 2, result.stderr)
        payload = json.loads(result.stdout)
        self.assertIn("protocol_unapproved", [item["code"] for item in payload["blockers"]])
        self.assertEqual(payload["report_states"][0]["title_abstract"]["human_decisions"], 0)

    def test_approval_does_not_survive_a_silent_mode_change(self):
        self.data["review"].update(screening_mode="single", screeners=["alice"])
        self.decision("alice")
        result = self.run_cli()
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("approval_context_changed", [b["code"] for b in json.loads(result.stdout)["blockers"]])

    def test_human_screening_cannot_predate_protocol_approval(self):
        self.decision("alice")["decided_at"] = "2025-12-01T10:00:00Z"
        self.decision("bob")
        result = self.run_cli()
        self.assertEqual(result.returncode, 1)
        self.assertIn("早于", json.loads(result.stderr)["error"])

    def test_empty_project_is_not_a_completed_search(self):
        self.data["approvals"] = []
        self.data["search_runs"] = []
        self.data["records"] = []
        self.data["reports"] = []
        result = self.run_cli()
        self.assertEqual(result.returncode, 2, result.stderr)
        codes = {b["code"] for b in json.loads(result.stdout)["blockers"]}
        self.assertTrue({"protocol_unapproved", "search_missing"}.issubset(codes))

    def conflict(self):
        first = self.decision("alice", "include")
        second = self.decision("bob", "exclude")
        return [first["decision_id"], second["decision_id"]]

    def test_conflict_remains_pending_without_adjudication(self):
        self.conflict()
        result = self.run_cli()
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(json.loads(result.stdout)["report_states"][0]["title_abstract"]["status"], "conflict")

    def test_human_adjudication_resolves_only_explicit_current_decisions(self):
        ids = self.conflict()
        self.decision("referee", role="adjudication", resolves=ids, resolution_method="third_reviewer")
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["report_states"][0]["title_abstract"]["status"], "exclude")

    def test_ai_cannot_adjudicate_and_third_reviewer_must_be_independent(self):
        for reviewer in ["assistant", "alice"]:
            with self.subTest(reviewer=reviewer):
                self.data = review_fixture()
                ids = self.conflict()
                self.decision(reviewer, role="adjudication", resolves=ids, resolution_method="third_reviewer")
                result = self.run_cli()
                self.assertEqual(result.returncode, 1, result.stdout)

    def test_revised_initial_decision_invalidates_old_adjudication(self):
        ids = self.conflict()
        self.decision("referee", role="adjudication", resolves=ids, resolution_method="third_reviewer")
        self.decision("alice", "include", supersedes=ids[0])
        result = self.run_cli()
        self.assertEqual(result.returncode, 2, result.stderr)
        state = json.loads(result.stdout)["report_states"][0]["title_abstract"]
        self.assertEqual(state["status"], "conflict")
        self.assertTrue(state["stale_adjudications"])

    def test_revision_preserves_history_without_counting_reviewer_twice(self):
        original = self.decision("alice", "include")
        self.decision("alice", "exclude", supersedes=original["decision_id"])
        self.decision("bob", "exclude")
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["report_states"][0]["title_abstract"]["human_decisions"], 2)

    def test_revision_forks_and_cycles_are_rejected(self):
        for cycle in [False, True]:
            with self.subTest(cycle=cycle):
                self.data = review_fixture()
                first = self.decision("alice")
                second = self.decision("alice", supersedes=first["decision_id"])
                if cycle:
                    first["supersedes"] = second["decision_id"]
                else:
                    self.decision("alice", supersedes=first["decision_id"])
                result = self.run_cli()
                self.assertEqual(result.returncode, 1, result.stdout)

    def include_report(self, report_id="report-1", study_id="study-1"):
        report = next(r for r in self.data["reports"] if r["report_id"] == report_id)
        report["retrieval_status"] = "retrieved"
        report["study_link"] = {"study_id": study_id, "protocol_version": "v1", "confirmed_by": "alice",
                                "confirmed_at": LATER, "reason": "核对注册号后的合成归并"}
        if not any(s["study_id"] == study_id for s in self.data["studies"]):
            self.data["studies"].append(row(study_id=study_id, design="parallel-rct"))
        for stage in ["title_abstract", "full_text"]:
            for reviewer in ["alice", "bob"]:
                self.decision(reviewer, "include", stage=stage, report_id=report_id)

    def test_full_review_counts_records_reports_and_studies_separately(self):
        self.data["records"].append(row(record_id="record-2", source_record_id="2", search_run_id="search-1", report_id="report-2"))
        self.data["reports"].append(row(report_id="report-2", title="同一试验的合成随访报告", retrieval_status="not_requested"))
        self.data["search_runs"][0].update(identified_count=2, retrieved_count=2)
        self.data["search_runs"].append(row(search_run_id="search-2", source="Embase", source_type="database",
                                            query="synthetic", searched_at=STAMP, status="complete", identified_count=1, retrieved_count=1))
        self.data["records"].append(row(record_id="record-3", source_record_id="E1", search_run_id="search-2", report_id="report-1"))
        self.include_report("report-1")
        self.include_report("report-2")
        result = self.run_cli("prisma")
        self.assertEqual(result.returncode, 0, result.stderr)
        counts = json.loads(result.stdout)["counts"]
        self.assertEqual(counts["records_identified"], 3)
        self.assertEqual(counts["duplicate_records_removed"], 1)
        self.assertEqual(counts["records_screened"], 2)
        self.assertEqual(counts["reports_included"], 2)
        self.assertEqual(counts["studies_included"], 1)
        self.assertIsNone(counts["studies_in_quantitative_synthesis"])

    def test_missing_full_text_is_not_an_eligibility_exclusion(self):
        self.decision("alice", "include")
        self.decision("bob", "include")
        self.data["reports"][0]["retrieval_status"] = "not_retrieved"
        result = self.run_cli("prisma")
        self.assertEqual(result.returncode, 0, result.stderr)
        counts = json.loads(result.stdout)["counts"]
        self.assertEqual(counts["reports_not_retrieved"], 1)
        self.assertEqual(counts["reports_assessed"], 0)
        self.assertEqual(counts["reports_excluded"], 0)

    def test_full_text_decision_requires_retrieval_and_prior_screening(self):
        self.decision("alice", "exclude", stage="full_text")
        self.decision("bob", "exclude", stage="full_text")
        result = self.run_cli()
        self.assertEqual(result.returncode, 1, result.stdout)
        self.data["screening_decisions"] = []
        self.decision("alice", "include")
        self.decision("bob", "include")
        self.decision("alice", "exclude", stage="full_text")
        self.decision("bob", "exclude", stage="full_text")
        result = self.run_cli()
        self.assertEqual(result.returncode, 1, result.stdout)

    def test_included_report_without_current_human_study_link_is_partial(self):
        self.include_report()
        for patch in [{"protocol_version": "old"}, {"confirmed_by": "assistant"}, {"study_id": "missing"}]:
            with self.subTest(patch=patch):
                original = dict(self.data["reports"][0]["study_link"])
                self.data["reports"][0]["study_link"].update(patch)
                result = self.run_cli("prisma")
                self.assertNotEqual(result.returncode, 0)
                self.data["reports"][0]["study_link"] = original
        del self.data["reports"][0]["study_link"]
        result = self.run_cli("prisma")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(json.loads(result.stdout)["counts"]["reports_pending_study_mapping"], 1)

    def test_partial_search_preserves_unknown_total(self):
        self.decision("alice")
        self.decision("bob")
        self.data["search_runs"][0].update(status="partial", identified_count=None)
        result = self.run_cli("prisma")
        self.assertEqual(result.returncode, 2, result.stderr)
        counts = json.loads(result.stdout)["counts"]
        self.assertEqual(counts["records_identified"], 1)
        self.assertIsNone(counts["search_hits_reported"])

    def test_exclusion_reason_disagreement_requires_resolution(self):
        self.include_report()
        full = [d for d in self.data["screening_decisions"] if d["stage"] == "full_text"]
        full[0].update(decision="exclude", reason="错误人群")
        full[1].update(decision="exclude", reason="错误设计")
        result = self.run_cli("prisma")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(json.loads(result.stdout)["counts"]["reports_excluded"], 0)
        self.decision("alice", "exclude", stage="full_text", role="adjudication",
                      resolution_method="discussion", resolves=[d["decision_id"] for d in full], reason="错误设计")
        result = self.run_cli("prisma")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["counts"]["full_text_exclusion_reasons"], {"错误设计": 1})

    def test_later_title_revision_makes_old_full_text_decisions_stale(self):
        self.include_report()
        first = self.data["screening_decisions"][0]
        self.decision("alice", "include", supersedes=first["decision_id"], decided_at="2026-01-03T10:00:00Z")
        result = self.run_cli("prisma")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(json.loads(result.stdout)["counts"]["reports_pending_full_text_screening"], 1)

    def test_same_doi_cannot_silently_become_two_reports(self):
        self.data["reports"][0]["doi"] = "10.1000/SYNTHETIC"
        self.data["reports"].append(row(report_id="report-2", title="重复报告", doi="https://doi.org/10.1000/synthetic",
                                          retrieval_status="not_requested"))
        self.data["records"].append(row(record_id="record-2", source_record_id="2", search_run_id="search-1", report_id="report-2"))
        self.data["search_runs"][0].update(identified_count=2, retrieved_count=2)
        result = self.run_cli("prisma")
        self.assertEqual(result.returncode, 1, result.stdout)

    def test_markdown_counts_keep_pending_and_unknown_visible(self):
        self.data["search_runs"][0].update(status="partial", identified_count=None)
        result = self.run_cli("prisma", "--format", "markdown")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("非最终", result.stdout)
        self.assertIn("未知", result.stdout)
        self.assertIn("待处理", result.stdout)
        self.assertIn("定量合成", result.stdout)

    def test_malformed_enums_return_json_errors_not_tracebacks(self):
        for name in ["registration", "report", "approval"]:
            with self.subTest(name=name):
                self.data = review_fixture()
                if name == "registration":
                    self.data["review"]["registration"]["status"] = []
                elif name == "report":
                    self.data["reports"][0]["retrieval_status"] = {}
                else:
                    self.data["approvals"][0]["registration_status"] = []
                result = self.run_cli()
                self.assertEqual(result.returncode, 1)
                self.assertEqual(json.loads(result.stderr)["status"], "error")

    def test_import_preview_can_feed_the_read_only_validator(self):
        source = self.directory / "source.csv"
        source.write_text("source_record_id,title,doi,pmid\nA,合成题录,10.1000/synthetic,\n", encoding="utf-8")
        command = [sys.executable, str(CLI.with_name("import_records.py")), str(source),
                   "--format", "csv", "--review-id", "synthetic-review", "--search-run-id", "search-1",
                   "--source", "合成数据库", "--source-type", "database", "--query", "synthetic",
                   "--searched-at", STAMP, "--complete", "--identified-count", "1"]
        imported = subprocess.run(command, capture_output=True, text=True, timeout=20)
        self.assertEqual(imported.returncode, 0, imported.stderr)
        preview = json.loads(imported.stdout)
        self.data["records"] = preview["records"]
        self.data["reports"] = preview["reports"]
        self.data["search_runs"] = [preview["search_run"]]
        result = self.run_cli("prisma")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(json.loads(result.stdout)["counts"]["records_pending_screening"], 1)

    def test_known_zero_result_search_can_finish_screening_without_invented_studies(self):
        self.data["records"] = []
        self.data["reports"] = []
        self.data["search_runs"][0].update(identified_count=0, retrieved_count=0)
        result = self.run_cli("prisma")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["counts"]["studies_included"], 0)

    def test_duplicate_json_fields_do_not_silently_override_evidence(self):
        self.save()
        file = self.directory / "review.json"
        raw = file.read_text(encoding="utf-8").replace('"schema_version": 1', '"schema_version": 1, "schema_version": 1', 1)
        file.write_text(raw, encoding="utf-8")
        result = self.run_cli(save=False)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("重复", json.loads(result.stderr)["error"])

    def test_bundled_synthetic_example_stays_runnable(self):
        example = ROOT / "skills/systematic-review/examples/rct-pairwise"
        result = subprocess.run([sys.executable, str(CLI), "prisma", str(example)], capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        counts = json.loads(result.stdout)["counts"]
        self.assertEqual((counts["records_identified"], counts["duplicate_records_removed"],
                          counts["reports_included"], counts["studies_included"]), (3, 1, 2, 1))

    def test_search_cannot_be_complete_when_source_reports_missing_records(self):
        self.decision("alice")
        self.decision("bob")
        self.data["search_runs"][0].update(retrieval_complete=False, source_status="partial",
                                          incomplete_reasons=["abstract_records_missing"])
        result = self.run_cli("prisma")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.data["search_runs"][0]["status"] = "partial"
        result = self.run_cli("prisma")
        self.assertEqual(result.returncode, 2, result.stderr)

    def test_valid_but_unscreened_review_is_partial(self):
        result = self.run_cli()
        self.assertEqual(result.returncode, 2, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "partial")
        self.assertFalse(payload["screening_complete"])
        self.assertTrue(payload["blockers"])


if __name__ == "__main__":
    unittest.main()
