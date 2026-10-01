#!/usr/bin/env python3
"""以公开 BCG 数据验证数值内核，不执行或认证临床综述流程。"""
import argparse
import csv
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from analysis_records import DATA_FIELDS
from analysis_runner import now, write_json
from review_model import parse_json, require


def run_command(command, out, label):
    with (out / f"{label}.stdout.txt").open("w") as stdout, (out / f"{label}.stderr.txt").open("w") as stderr:
        result = subprocess.run(command, cwd=out, stdout=stdout, stderr=stderr, timeout=120)
    require(result.returncode == 0, f"{label} 执行失败，查看 {label}.stderr.txt")


def benchmark(output, rscript):
    out = Path(output)
    require(not out.exists() and not out.is_symlink(), "基准输出目录已存在；请选择新目录")
    executable = shutil.which(rscript)
    require(executable, "需要 Rscript、metafor、jsonlite 和 metadat；本脚本不自动安装")
    out.mkdir(parents=True, exist_ok=False)
    out = out.resolve()
    report = {"schema_version": 1, "purpose": "public_benchmark", "status": "running", "started_at": now(),
              "ready_for_drafting": False, "submission_readiness": "not_assessed",
              "clinical_review_validation": "not_performed"}
    write_json(out / "benchmark.json", report)
    try:
        for source in (HERE / "export_bcg.R", HERE / "reference.json", SCRIPTS / "pairwise_meta.R"):
            shutil.copyfile(source, out / source.name)
        run_command([executable, "--vanilla", str(out / "export_bcg.R"), str(out)], out, "dataset")
        source = parse_json((out / "source.json").read_text())
        reference = parse_json((out / "reference.json").read_text())
        require(source["allocation_counts"] == reference["allocation_counts"], "公开数据的研究分配类型与参考不一致")
        with (out / "dataset.csv").open(newline="") as handle:
            studies = list(csv.DictReader(handle))
        fields = ("extraction_id", "study_id", "label", "rob_judgment", *DATA_FIELDS)
        with (out / "input.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for study in studies:
                writer.writerow({"extraction_id": f"bcg-row-{study['trial']}", "study_id": f"bcg-{study['trial']}",
                                 "label": f"{study['author']} ({study['year']})", "rob_judgment": "not_assessed",
                                 "n_intervention": int(study["tpos"]) + int(study["tneg"]),
                                 "n_comparator": int(study["cpos"]) + int(study["cneg"]),
                                 "events_intervention": int(study["tpos"]), "events_comparator": int(study["cpos"])})
        plan = {"effect_measure": "RR", "model": "REML", "ci_method": "z", "confidence_level": 0.95,
                "direction": "lower_is_better", "zero_cell_correction": "none", "double_zero_policy": "error",
                "plot_title": "BCG vaccination | Public numerical benchmark (mixed allocation)"}
        write_json(out / "prepared.json", {"schema_version": 1, "analysis_id": "bcg-public-benchmark", "plan": plan,
                                           "purpose": "public_benchmark"})
        run_command([executable, "--vanilla", str(out / "pairwise_meta.R"), str(out / "prepared.json"),
                     str(out / "input.csv"), str(out)], out, "analysis")
        summary = parse_json((out / "summary.json").read_text())
        comparisons = {}
        for field, expected in reference["expected"].items():
            actual = summary[field]
            require(type(actual) in (int, float) and math.isfinite(actual), f"基准结果 {field} 无效")
            difference = abs(actual - expected["value"])
            comparisons[field] = {**expected, "actual": actual, "absolute_difference": difference,
                                  "matched": difference <= expected["absolute_tolerance"]}
        report.update(status="matched" if all(item["matched"] for item in comparisons.values()) else "mismatch",
                      comparisons=comparisons, source=source, reference=reference, software=summary["software"],
                      limitations=["13 项研究中只有 7 项标为 random；此数值基准不代表纯 RCT 综述验收",
                                   "未执行检索、人工筛选、原文提取复核、RoB 2 或 GRADE"])
    except (ValueError, OSError, subprocess.TimeoutExpired) as error:
        report.update(status="failed", error=str(error))
    report["finished_at"] = now()
    write_json(out / "benchmark.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True)
    parser.add_argument("--rscript", default=os.environ.get("RSCRIPT", "Rscript"))
    args = parser.parse_args()
    try:
        report = benchmark(args.out, args.rscript)
        import json
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["status"] == "matched" else 2
    except (ValueError, OSError) as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
