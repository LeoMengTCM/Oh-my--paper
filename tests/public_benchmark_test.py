"""公开计数表的数值复现；不生成或模拟临床研究决定。"""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import meta_analysis_test

SCRIPT = Path(__file__).resolve().parents[1] / "skills/systematic-review/examples/bcg-benchmark/run_benchmark.py"


class PublicBenchmarkTests(unittest.TestCase):
    def test_published_reference_matches_without_fabricating_review_records(self):
        meta_analysis_test.MetaAnalysisTests.require_statistics(self)
        with tempfile.TemporaryDirectory(prefix="omp-bcg-test-") as directory:
            out = Path(directory) / "benchmark"
            command = [sys.executable, str(SCRIPT), "--out", str(out)]
            result = subprocess.run(command, capture_output=True, text=True, timeout=120)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            report = json.loads((out / "benchmark.json").read_text())
            self.assertEqual(report["status"], "matched")
            self.assertEqual(report["purpose"], "public_benchmark")
            self.assertFalse(report["ready_for_drafting"])
            self.assertEqual(report["clinical_review_validation"], "not_performed")
            self.assertEqual(report["source"]["allocation_counts"], {"random": 7, "alternate": 2, "systematic": 4})
            self.assertEqual(report["comparisons"]["k_analyzed"]["actual"], 13)
            self.assertTrue((out / "forest.pdf").is_file())
            for name in ("review.json", "approvals.jsonl", "rob2.jsonl", "run_manifest.json"):
                self.assertFalse((out / name).exists(), name)
            before = {path.name: path.read_bytes() for path in out.iterdir() if path.is_file()}
            result = subprocess.run(command, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(before, {path.name: path.read_bytes() for path in out.iterdir() if path.is_file()})


if __name__ == "__main__":
    unittest.main()
