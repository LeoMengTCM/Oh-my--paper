"""通过真实命令行验证题录导入预览，不依赖第三方包。"""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "skills/systematic-review/scripts/import_records.py"


class ImportRecordsTest(unittest.TestCase):
    def invoke(self, content, fmt="csv", extra=(), existing=None):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "input.txt"
            source.write_text(content, encoding="utf-8")
            command = [sys.executable, str(SCRIPT), str(source), "--format", fmt,
                       "--review-id", "review-1", "--search-run-id", "search-1",
                       "--source", "PubMed", "--source-type", "database",
                       "--query", "实际检索式", "--searched-at", "2026-09-28T12:00:00+08:00"]
            if existing is not None:
                reports = root / "reports.jsonl"
                reports.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in existing), encoding="utf-8")
                command += ["--existing-reports", str(reports)]
            before = {path.name: path.read_bytes() for path in root.iterdir()}
            result = subprocess.run(command + list(extra), text=True, capture_output=True)
            self.assertEqual(before, {path.name: path.read_bytes() for path in root.iterdir()}, "命令不能修改或新增用户文件")
            return result

    def success(self, *args, **kwargs):
        result = self.invoke(*args, **kwargs)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        return json.loads(result.stdout)

    def failure(self, *args, **kwargs):
        result = self.invoke(*args, **kwargs)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(result.stdout, "")
        payload = json.loads(result.stderr)
        self.assertIsInstance(payload["error"], str)
        return payload

    def test_csv_preview_is_partial_and_does_not_invent_total(self):
        preview = self.success("source_record_id,title,doi,pmid\nA,临床研究,,\n")
        self.assertEqual(preview["schema_version"], 1)
        run = preview["search_run"]
        self.assertEqual(run["status"], "partial")
        self.assertIsNone(run["identified_count"])
        self.assertEqual(run["retrieved_count"], 1)
        self.assertEqual(run["source_type"], "database")
        self.assertEqual(run["query"], "实际检索式")
        self.assertEqual(preview["records"][0]["source_record_id"], "A")
        self.assertEqual(preview["reports"][0]["title"], "临床研究")
        self.assertEqual(preview["reports"][0]["retrieval_status"], "not_requested")
        self.assertEqual(preview["records"][0]["report_id"], preview["reports"][0]["report_id"])

    def test_complete_requires_explicit_matching_nonnegative_count(self):
        data = "source_record_id,title,doi,pmid\nA,研究,,\n"
        for extra in [("--complete",), ("--complete", "--identified-count", "2"),
                      ("--identified-count", "-1"), ("--identified-count", "0"),
                      ("--identified-count", "true")]:
            with self.subTest(extra=extra):
                self.failure(data, extra=extra)
        preview = self.success(data, extra=("--complete", "--identified-count", "1"))
        self.assertEqual(preview["search_run"]["status"], "complete")
        self.assertEqual(preview["search_run"]["identified_count"], 1)
        partial = self.success(data, extra=("--identified-count", "10"))
        self.assertEqual(partial["search_run"]["status"], "partial")

    def test_pubmed_preserves_counts_and_rejects_missing_records(self):
        payload = {"query": "实际检索式", "total_count": 10, "returned": 1,
                   "results": [{"pmid": "123", "title": "临床研究", "doi": ""}]}
        preview = self.success(json.dumps(payload), "pubmed-json")
        self.assertEqual(preview["search_run"]["identified_count"], 10)
        self.assertEqual(preview["search_run"]["status"], "partial")
        self.assertEqual(preview["records"][0]["source_record_id"], "123")
        self.failure(json.dumps(payload), "pubmed-json", extra=("--complete", "--identified-count", "1"))
        for patch in [{"returned": 2}, {"returned": True}, {"total_count": False},
                      {"total_count": 0}, {"results": {}}, {"results": [None]},
                      {"results": [{"pmid": True, "title": "研究"}]}, {"query": "不同检索式"}]:
            with self.subTest(patch=patch):
                self.failure(json.dumps({**payload, **patch}), "pubmed-json")
        payload["total_count"] = 1
        complete = self.success(json.dumps(payload), "pubmed-json", extra=("--complete", "--identified-count", "1"))
        self.assertEqual(complete["search_run"]["status"], "complete")

    def test_pubmed_partial_status_cannot_be_promoted_by_matching_counts(self):
        payload = {"producer": "oh-my-paper/pubmed-search", "query": "实际检索式", "total_count": 1, "returned": 1,
                   "results": [{"pmid": "123", "title": "合成研究", "doi": ""}],
                   "status": "partial", "retrieval_complete": False,
                   "incomplete_reasons": ["abstract_records_missing"], "missing_metadata_pmids": [], "missing_abstract_pmids": ["123"],
                   "errors": [], "requested_pmids": ["123"], "executed_at": "2026-09-28T12:00:00+08:00",
                   "run_id": "source-run", "query_translation": "synthetic translation",
                   "query_parameters": {"query": "实际检索式", "mindate": "2020", "maxdate": "2025", "abstracts": True}}
        self.failure(json.dumps(payload), "pubmed-json", extra=("--complete", "--identified-count", "1"))
        partial = self.success(json.dumps(payload), "pubmed-json")
        self.assertFalse(partial["search_run"]["retrieval_complete"])
        self.assertEqual(partial["search_run"]["query_parameters"]["mindate"], "2020")
        self.assertEqual(partial["search_run"]["source_run_id"], "source-run")
        self.failure(json.dumps(payload), "pubmed-json", extra=("--searched-at", "2026-09-29T12:00:00+08:00"))
        bad = {**payload, "retrieval_complete": True, "status": "complete"}
        self.failure(json.dumps(bad), "pubmed-json", extra=("--complete", "--identified-count", "1"))
        complete = {**bad, "incomplete_reasons": [], "missing_abstract_pmids": []}
        result = self.success(json.dumps(complete), "pubmed-json", extra=("--complete", "--identified-count", "1"))
        self.assertEqual(result["search_run"]["status"], "complete")

    def test_existing_report_ids_are_preserved_without_rewriting_reports(self):
        existing = [{"schema_version": 1, "report_id": "old-human-id", "title": "既有报告",
                     "retrieval_status": "retrieved", "doi": "10.1000/a", "pmid": "123"}]
        data = "source_record_id,title,doi,pmid\nB,既有报告,https://doi.org/10.1000/A,123\n"
        preview = self.success(data, existing=existing)
        self.assertEqual(preview["records"][0]["report_id"], "old-human-id")
        self.assertEqual(preview["reports"], [])
        existing.append({"schema_version": 1, "report_id": "other-id", "title": "另一报告",
                         "retrieval_status": "not_requested", "pmid": "456"})
        self.failure(data.replace(",123", ",456"), existing=existing)
        self.failure(data, existing=existing + [dict(existing[0])])
        self.failure(data, existing=[{**existing[0], "retrieval_status": "clicked"}])

    def test_ris_multiline_titles_and_missing_ids_are_explicit(self):
        data = "TY  - JOUR\nTI  - 合成标题\n      后续文字\nDO  - doi:10.1000/A\nID  - A1\nER  - \n"
        preview = self.success(data, "ris")
        self.assertEqual(preview["reports"][0]["title"], "合成标题 后续文字")
        self.assertEqual(preview["reports"][0]["doi"], "10.1000/a")
        self.assertEqual(preview["records"][0]["source_record_id"], "A1")
        generated = self.success("TY  - JOUR\nT1  - 无标识报告\nER  - \n", "ris")
        self.assertTrue(generated["warnings"])
        self.assertEqual(generated, self.success("TY  - JOUR\nT1  - 无标识报告\nER  - \n", "ris"))
        for invalid in ["不是RIS", "TY  - JOUR\nTI  - 未结束", "TI  - 无开始\nER  - ", "TY  - JOUR\nER  - "]:
            with self.subTest(invalid=invalid):
                self.failure(invalid, "ris")

    def test_invalid_metadata_and_cli_parameters_have_json_errors(self):
        data = "source_record_id,title,doi,pmid\nA,研究,,\n"
        for extra in [("--searched-at", "yesterday"), ("--searched-at", "2026-01-01"),
                      ("--query", " "), ("--review-id", " "), ("--source", " ")]:
            with self.subTest(extra=extra):
                self.failure(data, extra=extra)
        for invalid in ["", "wrong,header\na,b\n", "source_record_id,title\nA\n",
                        "source_record_id,title\nA,研究,多余字段\n", "source_record_id,title,title\nA,甲,乙\n",
                        "source_record_id,title,pmid\nA,研究,invalid\n"]:
            with self.subTest(invalid=invalid):
                self.failure(invalid)

    def test_exact_identifiers_reuse_reports_and_keep_source_records(self):
        data = ("source_record_id,title,doi,pmid\n"
                "A,研究,HTTPS://DOI.ORG/10.1000/ABC,PMID: 00123\n"
                "B,题目不同,doi:10.1000/abc,123\n")
        preview = self.success(data)
        self.assertEqual(len(preview["records"]), 2)
        self.assertEqual(len(preview["reports"]), 1)
        self.assertEqual(preview["reports"][0]["doi"], "10.1000/abc")
        self.assertEqual(preview["reports"][0]["pmid"], "123")
        self.assertEqual(preview["records"][0]["report_id"], preview["records"][1]["report_id"])
        self.assertEqual(preview, self.success(data))
        other = self.success(data, extra=("--review-id", "review-2"))
        self.assertNotEqual(preview["reports"][0]["report_id"], other["reports"][0]["report_id"])
        self.failure(data.replace("B,", "A,"))
        distinct = self.success("source_record_id,title,doi,pmid\nA,同一题目,,\nB,同一题目,,\n")
        self.assertEqual(len(distinct["reports"]), 2)
        self.failure("source_record_id,title,doi,pmid\nA,研究,10.1000/a,123\nB,研究,10.1000/a,456\n")


if __name__ == "__main__":
    unittest.main()
