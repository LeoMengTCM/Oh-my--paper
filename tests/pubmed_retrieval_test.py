"""通过公开 CLI 入口和模拟 HTTP 边界测试 PubMed；不访问真实服务。"""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import urllib.error
import urllib.parse

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills/pubmed-search/scripts"
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location("omp_pubmed_cli", SCRIPTS / "pubmed_search.py")
CLI = importlib.util.module_from_spec(spec)
spec.loader.exec_module(CLI)


class FakeNCBI:
    def __init__(self, ids=("1", "2", "3"), total=None):
        self.ids = list(ids)
        self.total = len(self.ids) if total is None else total
        self.calls = []
        self.missing_summary = set()
        self.missing_abstract = set()
        self.no_abstract = set()
        self.fail = None
        self.overrides = {}

    def __call__(self, request, timeout=None):
        body = request.data.decode() if request.data else urllib.parse.urlsplit(request.full_url).query
        params = {k: v[0] for k, v in urllib.parse.parse_qs(body).items()}
        endpoint = Path(urllib.parse.urlsplit(request.full_url).path).name
        ids = params.get("id", "").split(",") if params.get("id") else []
        call = {"endpoint": endpoint, "params": params, "ids": ids, "method": request.get_method()}
        self.calls.append(call)
        if self.fail:
            self.fail(call)
        if endpoint in self.overrides:
            value = self.overrides[endpoint]
            return io.BytesIO(value if isinstance(value, bytes) else json.dumps(value).encode())
        if endpoint == "esearch.fcgi":
            payload = {"esearchresult": {"count": str(self.total), "idlist": self.ids[:int(params["retmax"])],
                                         "querytranslation": "synthetic translated query"}}
            return io.BytesIO(json.dumps(payload).encode())
        if endpoint == "esummary.fcgi":
            result = {"uids": [pmid for pmid in ids if pmid not in self.missing_summary]}
            for pmid in result["uids"]:
                result[pmid] = {"uid": pmid, "title": f"Synthetic report {pmid}", "authors": [{"name": "Synthetic Author"}],
                                "pubdate": "2020", "fulljournalname": "Synthetic Journal", "articleids": []}
            return io.BytesIO(json.dumps({"result": result}).encode())
        if endpoint == "efetch.fcgi":
            articles = []
            for pmid in ids:
                if pmid in self.missing_abstract:
                    continue
                abstract = "" if pmid in self.no_abstract else "<Abstract><AbstractText>合成摘要</AbstractText></Abstract>"
                articles.append(f"<PubmedArticle><MedlineCitation><PMID>{pmid}</PMID><Article>{abstract}</Article></MedlineCitation></PubmedArticle>")
            return io.BytesIO(("<PubmedArticleSet>" + "".join(articles) + "</PubmedArticleSet>").encode())
        raise AssertionError(f"不应访问的端点：{endpoint}")


class PubMedRetrievalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="omp-pubmed-test-")
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.api = FakeNCBI()

    def run_cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with patch("urllib.request.urlopen", self.api), patch("time.sleep"), contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = CLI.main(["synthetic query", "--api-key", "", "--email", "", *args])
        return code, out.getvalue(), err.getvalue()

    def test_all_search_batches_metadata_and_abstracts(self):
        checkpoint = self.directory / "checkpoint"
        self.api.no_abstract.add("2")
        code, out, err = self.run_cli("--all", "--checkpoint", str(checkpoint), "--batch-size", "2", "--abstracts",
                                      "--mindate", "2020/01/01", "--maxdate", "2021/12/31")
        self.assertEqual(code, 0, err)
        payload = json.loads(out)
        self.assertTrue(payload["retrieval_complete"])
        self.assertEqual(payload["returned"], 3)
        self.assertEqual(payload["results"][1]["abstract_status"], "not_reported")
        summaries = [call for call in self.api.calls if call["endpoint"] == "esummary.fcgi"]
        self.assertEqual([call["ids"] for call in summaries], [["1", "2"], ["3"]])
        self.assertTrue(all(call["method"] == "POST" for call in summaries))
        self.assertEqual(payload["query_parameters"]["mindate"], "2020/01/01")
        self.assertTrue((checkpoint / "checkpoint.json").is_file())

    def test_resume_reuses_uid_snapshot_and_successful_metadata_after_failure(self):
        checkpoint = self.directory / "checkpoint"
        args = ("--all", "--checkpoint", str(checkpoint), "--batch-size", "2", "--abstracts", "--retries", "1")
        def fail_fetch(call):
            if call["endpoint"] == "efetch.fcgi":
                raise urllib.error.HTTPError("https://example.invalid", 503, "unavailable", {}, None)
        self.api.fail = fail_fetch
        code, out, err = self.run_cli(*args)
        self.assertEqual(code, 2, err)
        initial = json.loads(out)
        self.assertEqual(initial["returned"], 2)
        self.assertFalse((checkpoint / ".lock").exists())
        self.api.fail = None
        self.api.calls.clear()
        code, out, err = self.run_cli(*args, "--resume")
        self.assertEqual(code, 0, err)
        resumed = json.loads(out)
        self.assertEqual(resumed["run_id"], initial["run_id"])
        self.assertEqual(resumed["executed_at"], initial["executed_at"])
        self.assertTrue(resumed["retrieval_complete"])
        self.assertNotIn("esearch.fcgi", [c["endpoint"] for c in self.api.calls])
        self.assertEqual([c["ids"] for c in self.api.calls if c["endpoint"] == "esummary.fcgi"], [["3"]])
        self.api.calls.clear()
        code, out, err = self.run_cli(*args, "--resume")
        self.assertEqual(code, 0, err)
        self.assertEqual(self.api.calls, [])

    def test_resume_only_requests_missing_metadata_or_abstract_records(self):
        checkpoint = self.directory / "checkpoint"
        args = ("--all", "--checkpoint", str(checkpoint), "--abstracts")
        self.api.missing_summary.add("2")
        self.api.missing_abstract.add("3")
        code, out, err = self.run_cli(*args)
        self.assertEqual(code, 2, err)
        payload = json.loads(out)
        self.assertEqual(payload["missing_metadata_pmids"], ["2"])
        self.assertEqual(payload["missing_abstract_pmids"], ["3"])
        self.api.missing_summary.clear()
        self.api.missing_abstract.clear()
        self.api.calls.clear()
        code, out, err = self.run_cli(*args, "--resume")
        self.assertEqual(code, 0, err)
        self.assertEqual([(c["endpoint"], c["ids"]) for c in self.api.calls],
                         [("esummary.fcgi", ["2"]), ("efetch.fcgi", ["3"])])

    def test_missing_abstract_record_is_not_a_genuinely_absent_abstract(self):
        self.api.missing_abstract.add("2")
        self.api.no_abstract.add("3")
        code, out, err = self.run_cli("--abstracts")
        self.assertEqual(code, 2, err)
        payload = json.loads(out)
        self.assertEqual(payload["returned"], payload["total_count"])
        self.assertFalse(payload["retrieval_complete"])
        self.assertEqual(payload["results"][1]["abstract_status"], "missing_record")
        self.assertEqual(payload["results"][2]["abstract_status"], "not_reported")

    def test_large_query_does_not_claim_unlimited_retrieval(self):
        self.api = FakeNCBI([str(i) for i in range(1, 10001)], total=10001)
        code, out, err = self.run_cli("--all", "--checkpoint", str(self.directory / "large"))
        self.assertEqual(code, 2, err)
        payload = json.loads(out)
        self.assertEqual(payload["total_count"], 10001)
        self.assertIn("uid_limit", payload["incomplete_reasons"])
        self.assertEqual(payload["returned"], 0)
        self.assertEqual(len(self.api.calls), 1)

    def test_bad_resume_state_is_rejected_before_new_network_requests(self):
        checkpoint = self.directory / "checkpoint"
        args = ("--all", "--checkpoint", str(checkpoint))
        self.assertEqual(self.run_cli(*args)[0], 0)
        manifest = checkpoint / "checkpoint.json"
        original = json.loads(manifest.read_text())
        for field in ("raw_response", "query_translation", "pmids"):
            with self.subTest(field=field):
                bad = json.loads(json.dumps(original))
                del bad["search"][field]
                manifest.write_text(json.dumps(bad))
                self.api.calls.clear()
                code, out, err = self.run_cli(*args, "--resume")
                self.assertEqual(code, 1, out)
                self.assertEqual(json.loads(err)["status"], "error")
                self.assertEqual(self.api.calls, [])
                self.assertFalse((checkpoint / ".lock").exists())
        manifest.write_text(json.dumps(original))

    def test_changed_query_parameters_and_owned_files_are_protected(self):
        checkpoint = self.directory / "checkpoint"
        args = ("--all", "--checkpoint", str(checkpoint))
        self.assertEqual(self.run_cli(*args)[0], 0)
        before = {str(p.relative_to(checkpoint)): p.read_bytes() for p in checkpoint.rglob("*") if p.is_file()}
        for extra in [("--resume", "--sort", "pub_date"), ("--resume", "--mindate", "2020"), ()]:
            with self.subTest(extra=extra):
                self.api.calls.clear()
                code, out, err = self.run_cli(*args, *extra)
                self.assertEqual(code, 1, out)
                self.assertEqual(self.api.calls, [])
                self.assertEqual(before, {str(p.relative_to(checkpoint)): p.read_bytes() for p in checkpoint.rglob("*") if p.is_file()})
        (checkpoint / ".lock").write_text("另一个进程的锁")
        self.api.calls.clear()
        code, out, err = self.run_cli(*args, "--resume")
        self.assertEqual(code, 1, out)
        self.assertEqual((checkpoint / ".lock").read_text(), "另一个进程的锁")
        self.assertEqual(self.api.calls, [])

    def test_output_protection_runs_before_any_requests(self):
        output = self.directory / "old.json"
        output.write_text("用户已有内容")
        code, out, err = self.run_cli("--output", str(output))
        self.assertEqual(code, 1)
        self.assertEqual(self.api.calls, [])
        self.assertEqual(output.read_text(), "用户已有内容")
        code, out, err = self.run_cli("--output", str(output), "--overwrite-output")
        self.assertEqual(code, 0, err)
        self.assertEqual(json.loads(output.read_text())["returned"], 3)
        checkpoint = self.directory / "checkpoint"
        self.api.calls.clear()
        code, out, err = self.run_cli("--all", "--checkpoint", str(checkpoint), "--output", str(checkpoint / "checkpoint.json"))
        self.assertEqual(code, 1)
        self.assertEqual(self.api.calls, [])
        self.assertFalse(checkpoint.exists())

    def test_api_failures_do_not_leak_credentials_into_output_or_checkpoint(self):
        key, email = "SECRET_TEST_KEY_123", "private-test@example.invalid"
        def fail(call):
            raise urllib.error.HTTPError(f"https://example.invalid/?api_key={key}&email={email}", 429, key, {}, None)
        self.api.fail = fail
        checkpoint = self.directory / "checkpoint"
        code, out, err = self.run_cli("--all", "--checkpoint", str(checkpoint), "--api-key", key, "--email", email, "--retries", "2")
        self.assertEqual(code, 2, err)
        self.assertEqual(len(self.api.calls), 2)
        saved = "".join(p.read_text() for p in checkpoint.rglob("*") if p.is_file())
        for secret in (key, email):
            self.assertNotIn(secret, out + err + saved)
        self.api.fail = None
        code, out, err = self.run_cli("--all", "--checkpoint", str(checkpoint), "--resume")
        self.assertEqual(code, 0, err)

    def test_http_error_responses_are_closed_on_retry_and_stop(self):
        for status, headers, expected_calls in ((400, {}, 1), (429, {"Retry-After": "600"}, 1), (503, {}, 2)):
            with self.subTest(status=status):
                failures = []
                self.api.calls.clear()
                def fail(call):
                    error = urllib.error.HTTPError("https://example.invalid", status, "synthetic error", headers, io.BytesIO(b"body"))
                    failures.append(error)
                    raise error
                self.api.fail = fail
                try:
                    code, out, err = self.run_cli("--retries", "2")
                    self.assertEqual(code, 2, err)
                    self.assertEqual(len(failures), expected_calls)
                    self.assertTrue(all(error.closed for error in failures), "重试和提前退出都须关闭 HTTP 错误响应")
                finally:
                    for error in failures:
                        error.close()

    def test_http_200_error_and_invalid_uid_snapshot_are_not_zero_results(self):
        for payload in [
            {"error": "synthetic service error"},
            {"esearchresult": {"count": "0", "idlist": [], "errorlist": {"fieldsnotfound": ["bad"]}}},
            {"esearchresult": {"idlist": []}},
            {"esearchresult": {"count": "2", "idlist": ["1", "1"]}},
        ]:
            with self.subTest(payload=payload):
                self.api.overrides["esearch.fcgi"] = payload
                code, out, err = self.run_cli()
                self.assertEqual(code, 2, err)
                self.assertFalse(json.loads(out)["retrieval_complete"])
                self.assertIsNone(json.loads(out)["total_count"])
        self.api.overrides.clear()
        self.api = FakeNCBI([], total=0)
        code, out, err = self.run_cli()
        self.assertEqual(code, 0, err)
        self.assertTrue(json.loads(out)["retrieval_complete"])
        self.assertEqual(len(self.api.calls), 1)

    def test_interruption_releases_owned_lock_and_can_resume(self):
        checkpoint = self.directory / "checkpoint"
        def interrupt(call):
            if call["endpoint"] == "efetch.fcgi":
                raise KeyboardInterrupt()
        self.api.fail = interrupt
        args = ("--all", "--checkpoint", str(checkpoint), "--abstracts")
        code, out, err = self.run_cli(*args)
        self.assertEqual(code, 2, err)
        self.assertIn("interrupted", json.loads(out)["incomplete_reasons"])
        self.assertFalse((checkpoint / ".lock").exists())
        self.api.fail = None
        self.api.calls.clear()
        code, out, err = self.run_cli(*args, "--resume")
        self.assertEqual(code, 0, err)
        self.assertEqual([c["endpoint"] for c in self.api.calls], ["efetch.fcgi"])

    def test_malformed_manifest_metadata_is_a_structured_error(self):
        checkpoint = self.directory / "checkpoint"
        args = ("--all", "--checkpoint", str(checkpoint))
        self.assertEqual(self.run_cli(*args)[0], 0)
        file = checkpoint / "checkpoint.json"
        original = json.loads(file.read_text())
        for field, value in [("started_at", None), ("search_attempts", "broken")]:
            with self.subTest(field=field):
                file.write_text(json.dumps({**original, field: value}))
                self.api.calls.clear()
                code, out, err = self.run_cli(*args, "--resume")
                self.assertEqual(code, 1, out)
                self.assertEqual(self.api.calls, [])
                self.assertEqual(json.loads(err)["status"], "error")
        file.write_text(json.dumps(original))

    def test_retry_after_is_respected_without_unbounded_waits(self):
        attempts = []
        def rate_limit_once(call):
            attempts.append(call)
            if len(attempts) == 1:
                raise urllib.error.HTTPError("https://example.invalid", 429, "rate limit", {"Retry-After": "12"}, None)
        self.api.fail = rate_limit_once
        out, err = io.StringIO(), io.StringIO()
        with patch("urllib.request.urlopen", self.api), patch("time.sleep") as sleep, contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = CLI.main(["synthetic query", "--api-key", "", "--email", "", "--retries", "2"])
        self.assertEqual(code, 0, err.getvalue())
        self.assertTrue(any(call.args[0] >= 12 for call in sleep.call_args_list))
        def long_wait(call):
            raise urllib.error.HTTPError("https://example.invalid", 429, "rate limit", {"Retry-After": "600"}, None)
        self.api.fail = long_wait
        self.api.calls.clear()
        code, out, err = self.run_cli()
        self.assertEqual(code, 2, err)
        self.assertEqual(len(self.api.calls), 1)

    def test_output_created_during_retrieval_is_not_overwritten(self):
        output = self.directory / "output.json"
        def create_user_file(call):
            if call["endpoint"] == "esummary.fcgi":
                output.write_text("另一个操作创建的文件")
        self.api.fail = create_user_file
        code, out, err = self.run_cli("--output", str(output))
        self.assertEqual(code, 1, err)
        self.assertEqual(output.read_text(), "另一个操作创建的文件")

    def test_incomplete_uid_list_can_retry_without_mixing_record_batches(self):
        self.api = FakeNCBI(["1"], total=3)
        args = ("--all", "--checkpoint", str(self.directory / "checkpoint"))
        code, out, err = self.run_cli(*args)
        self.assertEqual(code, 2, err)
        self.assertIn("uid_snapshot_incomplete", json.loads(out)["incomplete_reasons"])
        self.assertEqual(len(self.api.calls), 1)
        self.api = FakeNCBI()
        code, out, err = self.run_cli(*args, "--resume")
        self.assertEqual(code, 0, err)
        self.assertEqual(json.loads(out)["returned"], 3)

    def test_corrupt_cached_record_is_not_exported_as_complete(self):
        checkpoint = self.directory / "checkpoint"
        args = ("--all", "--checkpoint", str(checkpoint), "--abstracts")
        self.assertEqual(self.run_cli(*args)[0], 0)
        file = checkpoint / "batches/00000.json"
        original = json.loads(file.read_text())
        for section, key, value in [("summaries", "authors", "not a list"), ("abstracts", "mesh_terms", [5]),
                                    ("summaries", "pmid", "99")]:
            with self.subTest(section=section, key=key):
                bad = json.loads(json.dumps(original))
                bad[section]["1"][key] = value
                file.write_text(json.dumps(bad))
                self.api.calls.clear()
                code, out, err = self.run_cli(*args, "--resume")
                self.assertEqual(code, 1, out)
                self.assertEqual(self.api.calls, [])
        file.write_text(json.dumps(original))

    def test_malformed_article_cannot_be_reported_as_having_no_abstract(self):
        self.api.overrides["efetch.fcgi"] = ("<PubmedArticleSet>" + "".join(
            f"<PubmedArticle><MedlineCitation><PMID>{pmid}</PMID></MedlineCitation></PubmedArticle>"
            for pmid in self.api.ids) + "</PubmedArticleSet>").encode()
        code, out, err = self.run_cli("--abstracts")
        self.assertEqual(code, 2, err)
        self.assertEqual(json.loads(out)["missing_abstract_pmids"], self.api.ids)

    def test_retrieved_output_flows_into_sr02_records(self):
        from systematic_review_test import review_fixture
        code, out, err = self.run_cli("--all", "--checkpoint", str(self.directory / "checkpoint"),
                                      "--abstracts", "--mindate", "2020", "--maxdate", "2025")
        self.assertEqual(code, 0, err)
        payload = json.loads(out)
        exported = self.directory / "pubmed.json"
        exported.write_text(out, encoding="utf-8")
        importer = ROOT / "skills/systematic-review/scripts/import_records.py"
        imported = subprocess.run([sys.executable, str(importer), str(exported), "--format", "pubmed-json",
                                   "--review-id", "synthetic-review", "--search-run-id", "search-1",
                                   "--source", "PubMed", "--source-type", "database", "--query", payload["query"],
                                   "--searched-at", payload["executed_at"], "--complete", "--identified-count", "3"],
                                  capture_output=True, text=True, timeout=20)
        self.assertEqual(imported.returncode, 0, imported.stderr)
        preview = json.loads(imported.stdout)
        self.assertEqual(preview["search_run"]["query_parameters"]["mindate"], "2020")
        review_dir = self.directory / "review"
        review_dir.mkdir()
        data = review_fixture()
        data.update(search_runs=[preview["search_run"]], records=preview["records"], reports=preview["reports"])
        (review_dir / "review.json").write_text(json.dumps(data.pop("review")))
        for name, rows in data.items():
            (review_dir / f"{name}.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
        for name in ["protocol-v1.md", "sap-v1.md"]:
            (review_dir / name).write_text("合成方案，非真实研究", encoding="utf-8")
        validator = ROOT / "skills/systematic-review/scripts/review_state.py"
        checked = subprocess.run([sys.executable, str(validator), "prisma", str(review_dir)], capture_output=True, text=True, timeout=20)
        self.assertEqual(checked.returncode, 2, checked.stderr)
        self.assertEqual(json.loads(checked.stdout)["counts"]["records_pending_screening"], 3)

    def test_invalid_arguments_fail_without_network_access(self):
        for args in [("--all",), ("--resume",), ("--batch-size", "0"), ("--batch-size", "201"),
                     ("--retmax", "0"), ("--retries", "0"), ("--mindate", "2025", "--maxdate", "2024"),
                     ("--mindate", "2025/02/30"), ("--all", "--retmax", "1")]:
            with self.subTest(args=args):
                self.api.calls.clear()
                code, out, err = self.run_cli(*args)
                self.assertEqual(code, 1, out)
                self.assertEqual(self.api.calls, [])
                self.assertEqual(json.loads(err)["status"], "error")

    def test_accepted_numeric_count_remains_resumable(self):
        self.api.overrides["esearch.fcgi"] = {"esearchresult": {"count": "0003", "idlist": self.api.ids}}
        args = ("--all", "--checkpoint", str(self.directory / "checkpoint"))
        self.assertEqual(self.run_cli(*args)[0], 0)
        self.api.calls.clear()
        code, out, err = self.run_cli(*args, "--resume")
        self.assertEqual(code, 0, err)
        self.assertEqual(self.api.calls, [])

    def test_unexpected_xml_encoding_is_reported_as_incomplete_retrieval(self):
        xml = '<?xml version="1.0" encoding="UTF-16"?><PubmedArticleSet></PubmedArticleSet>'
        self.api.overrides["efetch.fcgi"] = xml.encode("utf-16")
        code, out, err = self.run_cli("--abstracts")
        self.assertEqual(code, 2, err)
        self.assertFalse(json.loads(out)["retrieval_complete"])

    def test_bounded_search_keeps_legacy_fields_and_explicit_completeness(self):
        code, out, err = self.run_cli("--retmax", "2")
        self.assertEqual(code, 0, err)
        payload = json.loads(out)
        self.assertEqual((payload["total_count"], payload["returned"]), (3, 2))
        self.assertEqual([r["pmid"] for r in payload["results"]], ["1", "2"])
        self.assertEqual(payload["query"], "synthetic query")
        self.assertFalse(payload["retrieval_complete"])
        self.assertIn("bounded_search", payload["incomplete_reasons"])
        self.assertIn("executed_at", payload)
        self.assertEqual(payload["query_translation"], "synthetic translated query")


if __name__ == "__main__":
    unittest.main()
