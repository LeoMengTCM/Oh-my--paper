"""通过公开 API 与真实临时文件检查引用核验边界。"""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/systematic-review/scripts"))
from citation_records import check_citations


class CitationRecordsTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.key = "smith2024trial"
        self.metadata = {
            "citation_key": self.key, "title": "A clinical trial", "authors": ["Jane Smith", "John Doe"],
            "year": 2024, "venue": "Clinical Journal", "doi": "10.1234/trial", "arxiv_id": None,
            "pmid": "12345", "source": "crossref", "merged_sources": ["crossref", "pubmed"],
        }
        self.entry = {
            field: self.metadata[field]
            for field in ("citation_key", "title", "authors", "year", "venue", "doi", "arxiv_id")
        }
        self.entry["bibtex"] = (
            "@article{smith2024trial,\n"
            "  title = {A clinical trial},\n"
            "  author = {Jane Smith and John Doe},\n"
            "  journal = {Clinical Journal},\n"
            "  year = {2024},\n"
            "  doi = {10.1234/trial}\n}\n"
        )
        self.entry["provenance"] = {
            "origin": "survey", "source_platforms": ["crossref", "pubmed"],
            "metadata_path": str(self.root / "metadata.json"),
        }
        self.bibliography = {
            "count": 1, "skipped_count": 0, "entries": {self.key: self.entry},
            "skipped": [], "bib_out": str(self.root / "references.bib"), "generated_from": [str(self.root)],
        }
        self.evidence = {"message": {
            "DOI": "10.1234/TRIAL", "title": ["A clinical trial."],
            "author": [{"given": "Jane", "family": "Smith"}, {"given": "John", "family": "Doe"}],
            "issued": {"date-parts": [[2024]]}, "container-title": ["Clinical Journal"],
            "private_unused_field": "不得复制到 checks",
        }}
        self.verification = {
            "schema_version": 1, "verification_id": "verify-1", "citation_key": self.key,
            "source_type": "crossref", "source_url": "https://api.crossref.org/works/10.1234%2Ftrial",
            "evidence_path": "crossref.json", "checked_at": "2026-09-30T10:00:00+08:00", "checked_by": "robot",
        }
        self.config = {
            "bibliography": "bibliography.json", "report_citations": {"report-1": self.key},
            "method_citations": [], "verification_records": "verifications.jsonl",
        }
        self.reports = [{"report_id": "report-1", "title": "A clinical trial", "doi": "https://doi.org/10.1234/trial", "pmid": "12345"}]
        self.reviewers = {"robot": {"kind": "ai"}, "researcher": {"kind": "human"}}
        self.write_json("metadata.json", self.metadata)
        self.write_json("crossref.json", self.evidence)
        self.write_bibliography()
        self.write_verifications([self.verification])

    def write_json(self, name, value):
        (self.root / name).write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")

    def write_bibliography(self):
        self.write_json("bibliography.json", self.bibliography)
        (self.root / "references.bib").write_text(
            "".join(self.bibliography["entries"][key]["bibtex"] for key in sorted(self.bibliography["entries"])),
            encoding="utf-8",
        )

    def write_verifications(self, records):
        (self.root / "verifications.jsonl").write_text(
            "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records), encoding="utf-8",
        )

    def check(self):
        return check_citations(self.root, self.config, self.reports, self.reviewers)

    def assert_blocked(self, code, status="invalid"):
        result = self.check()
        self.assertIn(code, {item["code"] for item in result["blockers"]})
        self.assertEqual(result["checks"][0]["status"], status)
        return result

    def test_crossref_snapshot_matches_and_preserves_originals(self):
        before = copy.deepcopy((self.config, self.reports, self.reviewers))
        result = self.check()
        self.assertEqual(result["blockers"], [])
        self.assertEqual(result["entries"], {self.key: self.entry})
        self.assertEqual(result["metadata"], {self.key: self.metadata})
        self.assertEqual(result["bibtex"], self.entry["bibtex"])
        self.assertEqual(result["used_keys"], [self.key])
        self.assertEqual(result["report_citations"], {"report-1": self.key})
        check = result["checks"][0]
        self.assertEqual(check["status"], "matched")
        self.assertEqual(check["verification_level"], "crossref_snapshot_checked")
        self.assertEqual(check["source_url"], self.verification["source_url"])
        self.assertNotIn("private_unused_field", json.dumps(check))
        self.assertNotIn("message", check)
        self.assertEqual(before, (self.config, self.reports, self.reviewers))

    def test_missing_metadata_blocks_but_keeps_partial_preview(self):
        (self.root / "metadata.json").unlink()
        result = self.assert_blocked("citation_metadata_invalid")
        self.assertEqual(result["bibtex"], self.entry["bibtex"])
        self.assertEqual(result["metadata"], {})

    def test_bib_file_tampering_blocks(self):
        (self.root / "references.bib").write_text(self.entry["bibtex"].replace("clinical", "changed"), encoding="utf-8")
        self.assert_blocked("citation_bibtex_mismatch")

    def test_entry_key_and_bib_key_tampering_block(self):
        for target in ("citation_key", "bibtex"):
            with self.subTest(target=target):
                original = self.entry[target]
                self.entry[target] = original.replace(self.key, "changed-key")
                self.write_bibliography()
                result = self.assert_blocked("citation_entry_invalid")
                self.assertEqual(result["bibtex"], "")
                self.entry[target] = original

    def test_joint_bib_tampering_does_not_bypass_metadata(self):
        self.entry["bibtex"] = self.entry["bibtex"].replace("clinical", "changed")
        self.write_bibliography()
        self.assert_blocked("citation_entry_invalid")

    def test_metadata_source_marker_is_not_verification(self):
        self.config["verification_records"] = None
        result = self.assert_blocked("citation_unverified", "unverified")
        self.assertEqual(result["checks"][0]["verification_level"], "none")
        self.assertEqual(result["bibtex"], self.entry["bibtex"])

    def test_empty_verification_file_is_unverified(self):
        self.write_verifications([])
        self.assert_blocked("citation_unverified", "unverified")

    def test_duplicate_report_mapping_blocks_but_methods_may_overlap(self):
        self.config["method_citations"] = [self.key, self.key]
        self.assertEqual(self.check()["blockers"], [])
        self.reports.append(dict(self.reports[0], report_id="report-2"))
        self.config["report_citations"]["report-2"] = self.key
        self.assert_blocked("citation_report_duplicate")

    def test_unmapped_and_missing_keys_are_reported(self):
        self.config["report_citations"] = {}
        result = self.check()
        self.assertEqual(result["used_keys"], [])
        self.assertEqual(result["blockers"][0]["code"], "citation_report_missing")
        self.config["report_citations"] = {"report-1": "missing-key"}
        self.assert_blocked("citation_entry_missing")

    def test_report_title_doi_and_pmid_must_match(self):
        for field, value in (("title", "Another report"), ("doi", "10.1234/other"), ("pmid", "7777")):
            with self.subTest(field=field):
                original = self.reports[0][field]
                self.reports[0][field] = value
                self.assert_blocked("citation_report_mismatch")
                self.reports[0][field] = original

    def test_metadata_key_fields_and_provenance_must_match(self):
        changes = {"citation_key": "other", "title": "Another trial", "authors": ["J. Smith"], "year": 2025,
                   "doi": "10.1234/other", "arxiv_id": "2401.12345", "merged_sources": ["pubmed"]}
        for field, value in changes.items():
            with self.subTest(field=field):
                modified = dict(self.metadata, **{field: value})
                self.write_json("metadata.json", modified)
                self.assert_blocked("citation_metadata_invalid")
        self.write_json("metadata.json", self.metadata)

    def test_only_used_metadata_files_are_loaded(self):
        unused = copy.deepcopy(self.entry)
        unused["citation_key"] = "unused"
        unused["bibtex"] = unused["bibtex"].replace(self.key, "unused")
        unused["provenance"]["metadata_path"] = str(self.root / "does-not-exist.json")
        self.bibliography["entries"]["unused"] = unused
        self.bibliography["count"] = 2
        self.write_bibliography()
        result = self.check()
        self.assertEqual(result["blockers"], [])
        self.assertEqual(set(result["entries"]), {self.key})
        self.assertEqual(set(result["metadata"]), {self.key})
        self.assertNotIn("unused", result["bibtex"])

    def test_manual_requires_registered_human(self):
        self.verification["source_type"] = "manual"
        self.verification["source_url"] = "https://example.org/paper"
        self.verification["evidence_path"] = "manual.json"
        manual = dict(self.metadata, source_url=self.verification["source_url"])
        self.write_json("manual.json", manual)
        for reviewer_id in ("robot", "unregistered"):
            self.verification["checked_by"] = reviewer_id
            self.write_verifications([self.verification])
            self.assert_blocked("citation_verification_invalid")
        self.verification["checked_by"] = "researcher"
        self.write_verifications([self.verification])
        result = self.check()
        self.assertEqual(result["blockers"], [])
        self.assertEqual(result["checks"][0]["verification_level"], "manual_record_checked")
        manual["source_url"] = "https://example.org/another-paper"
        self.write_json("manual.json", manual)
        self.assert_blocked("citation_verification_invalid")

    def test_crossref_identity_url_and_timezone_are_strict(self):
        changes = [
            ("source_url", "https://api.crossref.org.evil.example/works/10.1234/trial"),
            ("source_url", "https://api.crossref.org/works/10.1234/other"),
            ("source_url", "https://api.crossref.org/works/10.1234/trial?token=private"),
            ("checked_at", "2026-09-30T10:00:00"),
            ("checked_by", "unregistered"),
            ("schema_version", True),
            ("evidence_path", "missing.json"),
        ]
        for field, value in changes:
            with self.subTest(field=field, value=value):
                self.write_verifications([dict(self.verification, **{field: value})])
                self.assert_blocked("citation_verification_invalid")
        self.write_verifications([self.verification])
        for field, value in (("DOI", "10.1234/other"), ("title", ["Different title"]),
                             ("author", [{"given": "J.", "family": "Smith"}]),
                             ("issued", {"date-parts": [[2025]]})):
            with self.subTest(field=field):
                evidence = copy.deepcopy(self.evidence)
                evidence["message"][field] = value
                self.write_json("crossref.json", evidence)
                self.assert_blocked("citation_verification_invalid")

    def test_conflicting_verifications_do_not_pick_latest(self):
        another = dict(self.verification, verification_id="verify-2", checked_at="2026-10-01T10:00:00Z")
        self.write_verifications([self.verification, another])
        self.assert_blocked("citation_verification_ambiguous")

    def test_allowed_text_normalization_and_line_endings(self):
        self.metadata["title"] = "  A <b>clinical</b> trial. "
        self.write_json("metadata.json", self.metadata)
        (self.root / "references.bib").write_bytes(self.entry["bibtex"].replace("\n", "\r\n").encode())
        self.assertEqual(self.check()["blockers"], [])

    def test_safe_keys_only(self):
        self.config["report_citations"]["report-1"] = "unsafe}\\input{secret}"
        self.assert_blocked("citation_key_invalid")

    def test_top_level_format_and_counts_raise_value_error(self):
        self.bibliography["count"] = 2
        self.write_json("bibliography.json", self.bibliography)
        with self.assertRaises(ValueError):
            self.check()
        self.bibliography["count"] = 1
        self.write_bibliography()
        self.config["report_citations"] = []
        with self.assertRaises(ValueError):
            self.check()

    def test_duplicate_json_fields_are_rejected(self):
        (self.root / "bibliography.json").write_text('{"entries":{},"entries":{}}', encoding="utf-8")
        with self.assertRaises(ValueError):
            self.check()


if __name__ == "__main__":
    unittest.main()
