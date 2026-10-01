"""在全新的结果目录运行已校验的分析，保留代码、输入与失败状态。"""
import csv
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import uuid

from analysis_records import AnalysisBlocked, DATA_FIELDS
from artifact_integrity import artifact_digests
from review_model import parse_json, require


def now():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, value):
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, prefix=".meta-", delete=False) as handle:
            temporary = Path(handle.name)
            json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def check_dependencies(rscript):
    code = 'quit(status=if (requireNamespace("metafor", quietly=TRUE) && requireNamespace("jsonlite", quietly=TRUE)) 0 else 42)'
    try:
        result = subprocess.run([rscript, "--vanilla", "-e", code], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise AnalysisBlocked("r_dependencies_missing", ["无法运行 Rscript；请检查 R 安装与路径"]) from error
    if result.returncode != 0:
        raise AnalysisBlocked("r_dependencies_missing", ["需要 R、metafor 和 jsonlite；本命令不自动安装"])


def ledger_entries(manifest, summary):
    def cell(value):
        return str(value).replace("|", "\\|").replace("\r", " ").replace("\n", " ")
    out = Path(manifest["output_directory"])
    lines = ["# 本次运行的登记条目", "", "以下是供负责人核查后追加的条目；程序没有修改项目记忆文件。", "",
             "## experiment_ledger.md", "",
             "| run_id | analysis_id | 状态 | 选择/分析/排除研究数 | 结果 | 路径 |", "|---|---|---|---|---|---|"]
    estimate = "不可估计" if summary["estimate"] is None else f"{summary['measure']} {summary['estimate']:.6g} [{summary['ci_lower']:.6g}, {summary['ci_upper']:.6g}]"
    values = [manifest["run_id"], manifest["analysis_id"], summary["analysis_status"],
              f"{summary['k_selected']}/{summary['k_analyzed']}/{summary['k_excluded']}", estimate, out / "summary.json"]
    lines.append("| " + " | ".join(cell(value) for value in values) + " |")
    lines.extend(["", "## figure_ledger.md", "", "| 图名 | 路径 | 数据来源(run id) | 类型 | 状态 |", "|---|---|---|---|---|"])
    if summary["k_analyzed"]:
        lines.append("| " + " | ".join(cell(value) for value in
                     ["forest", out / "forest.pdf", manifest["run_id"], "森林图", "draft（需目视复核）"]) + " |")
    else:
        lines.append("无可计算效应，未生成森林图。")
    lines.extend(["", "单研究结果不是合并效应；排除仅针对本次计算，不修改系统综述纳入记录。", "未自动执行 GRADE、小样本效应检验、亚组或敏感性分析。",
                  "summary_of_findings_draft.csv 的确定性、基线风险与绝对效应留空；须人工评估，不能当作最终 SoF 表。"])
    if summary.get("warnings"):
        lines.extend(["", "## 运行警告", *["- " + cell(warning) for warning in summary["warnings"]]])
    return "\n".join(lines) + "\n"


def validate_result(summary, prepared, out):
    require(isinstance(summary, dict) and type(summary.get("schema_version")) is int and summary["schema_version"] == 1,
            "统计结果 schema_version 无效")
    plan = prepared["plan"]
    require(summary.get("analysis_id") == prepared["analysis_id"], "结果分析 ID 不一致")
    for result_key, plan_key in (("measure", "effect_measure"), ("model_requested", "model"),
                                 ("ci_method_requested", "ci_method"), ("confidence_level", "confidence_level"), ("direction", "direction")):
        require(summary.get(result_key) == plan[plan_key], f"统计结果 {result_key} 与计划不一致")
    for key in ("k_selected", "k_analyzed", "k_excluded"):
        require(type(summary.get(key)) is int and summary[key] >= 0, f"统计结果 {key} 无效")
    k = summary["k_analyzed"]
    require(summary["k_selected"] == len(prepared["rows"]) == k + summary["k_excluded"], "统计结果的研究数不守恒")
    expected_status = "pooled" if k >= 2 else "single_study" if k == 1 else "not_estimable"
    require(summary.get("analysis_status") == expected_status, "分析状态与可计算研究数不符")
    estimates = ("estimate", "ci_lower", "ci_upper", "estimate_analysis", "ci_lower_analysis", "ci_upper_analysis", "se_analysis")
    for key in estimates:
        value = summary.get(key)
        require(key in summary and (value is None if not k else type(value) in (int, float) and math.isfinite(value)),
                f"统计结果 {key} 缺失或无效")
    if k:
        require(summary["ci_lower"] <= summary["estimate"] <= summary["ci_upper"], "统计结果置信区间顺序错误")
        require(plan["effect_measure"] != "RR" or summary["ci_lower"] > 0, "RR 展示尺度无效")
    require(summary.get("model_applied") == ("REML" if k >= 2 else None), "单研究或无效应时不能标记已拟合模型")
    require(summary.get("ci_method_applied") == (plan["ci_method"] if k >= 2 else "normal_single_study" if k else None),
            "实际区间方法与计划或单研究状态不符")
    for key in ("tau2", "I2", "Q", "Q_p"):
        value = summary.get(key)
        require(key in summary and (value is None if k < 2 else type(value) in (int, float) and math.isfinite(value)),
                f"异质性统计量 {key} 无效")
    require(isinstance(summary.get("software"), dict) and all(isinstance(summary["software"].get(key), str)
            for key in ("R", "metafor", "jsonlite")), "统计结果缺少软件版本")
    require(isinstance(summary.get("warnings"), list), "统计结果缺少警告记录")
    excluded = summary.get("excluded")
    require(isinstance(excluded, list) and len(excluded) == summary["k_excluded"], "统计排除记录数量不一致")
    chosen = {row["extraction_id"]: row["study_id"] for row in prepared["rows"]}
    excluded_ids = []
    for entry in excluded:
        require(isinstance(entry, dict) and isinstance(entry.get("extraction_id"), str) and entry["extraction_id"] in chosen and
                chosen[entry["extraction_id"]] == entry.get("study_id") and isinstance(entry.get("reason"), str),
                "统计排除记录与选择输入不一致")
        excluded_ids.append(entry["extraction_id"])
    require(len(excluded_ids) == len(set(excluded_ids)), "统计排除记录重复")
    with (out / "effects.csv").open(encoding="utf-8", newline="") as handle:
        effects = list(csv.DictReader(handle))
    require(len(effects) == k and {e.get("extraction_id") for e in effects} == set(chosen) - set(excluded_ids),
            "effects.csv 与实际纳入计算的记录不一致")
    require(all(chosen.get(e.get("extraction_id")) == e.get("study_id") for e in effects), "effects.csv 研究身份错误")


def write_sof_draft(prepared, summary, out):
    plan = prepared["plan"]
    excluded = {item["extraction_id"] for item in summary["excluded"]}
    analyzed = [row for row in prepared["rows"] if row["extraction_id"] not in excluded]
    draft = {key: plan[key] for key in ("analysis_id", "comparison_id", "outcome_id", "timepoint_id", "analysis_population")}
    draft.update(analysis_status=summary["analysis_status"], studies_selected=summary["k_selected"],
                 studies_analyzed=summary["k_analyzed"],
                 participants_selected=int(sum(row["n_intervention"] + row["n_comparator"] for row in prepared["rows"])),
                 participants_analyzed=int(sum(row["n_intervention"] + row["n_comparator"] for row in analyzed)),
                 effect_measure=summary["measure"], estimate=summary["estimate"], ci_lower=summary["ci_lower"], ci_upper=summary["ci_upper"],
                 baseline_risk="", baseline_risk_source="", absolute_effect="", certainty="", grade_rationale="", grade_status="not_assessed")
    with (out / "summary_of_findings_draft.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(draft))
        writer.writeheader()
        writer.writerow(draft)


def run_analysis(prepared, directory, output, rscript, reason):
    out = Path(output)
    require(not out.exists() and not out.is_symlink(), "结果目录已存在；请选择新的目录，不覆盖旧结果")
    executable = shutil.which(rscript)
    if executable:
        rscript = str(Path(executable).resolve())
    check_dependencies(rscript)
    out.mkdir(parents=True, exist_ok=False)
    out = out.resolve()
    manifest = {"schema_version": 1, "run_id": str(uuid.uuid4()), "analysis_id": prepared["analysis_id"],
                "protocol_version": prepared["plan"]["protocol_version"], "status": "running", "started_at": now(),
                "reason": reason, "source_directory": str(Path(directory).resolve()), "output_directory": str(out),
                "rscript": rscript, "artifacts": []}
    write_json(out / "run_manifest.json", manifest)
    try:
        write_json(out / "prepared.json", {key: prepared[key] for key in ("schema_version", "analysis_id", "plan")})
        write_json(out / "source_snapshot.json", prepared["source_snapshot"])
        with (out / "input.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["extraction_id", "study_id", "label", "rob_judgment", *DATA_FIELDS])
            writer.writeheader()
            writer.writerows(prepared["rows"])
        engine = Path(__file__).with_name("pairwise_meta.R")
        shutil.copyfile(engine, out / "pairwise_meta.R")
        command = [rscript, "--vanilla", str(out / "pairwise_meta.R"), str(out / "prepared.json"), str(out / "input.csv"), str(out)]
        with (out / "run.stdout.txt").open("w", encoding="utf-8") as stdout, (out / "run.stderr.txt").open("w", encoding="utf-8") as stderr:
            result = subprocess.run(command, stdout=stdout, stderr=stderr, timeout=600, cwd=out)
        require(result.returncode == 0, f"R 执行失败（退出码 {result.returncode}）；查看 run.stderr.txt")
        summary = parse_json((out / "summary.json").read_text(encoding="utf-8"), "summary.json")
        validate_result(summary, prepared, out)
        expected = ["effects.csv", "exclusions.csv", "sessionInfo.txt"]
        pages = summary.get("forest_pages")
        require(type(pages) is int and pages == (summary["k_analyzed"] + 39) // 40, "森林图页数与研究数不符")
        if summary["k_analyzed"]:
            expected.extend(["forest.pdf", "forest.png"])
        if pages > 1:
            expected.extend(f"forest-page-{page:03d}.png" for page in range(1, pages + 1))
        require(all((out / name).is_file() and (out / name).stat().st_size > 0 for name in expected), "R 结果缺少必要产物")
        write_sof_draft(prepared, summary, out)
        (out / "ledger_entries.md").write_text(ledger_entries(manifest, summary), encoding="utf-8")
        manifest.update(status="completed", finished_at=now(), analysis_status=summary["analysis_status"], software=summary["software"])
    except (OSError, ValueError, subprocess.TimeoutExpired, KeyboardInterrupt) as error:
        manifest.update(status="failed", finished_at=now(), error=str(error) or "运行被中断")
    manifest["artifacts"] = sorted(path.name for path in out.iterdir() if path.is_file())
    if manifest["status"] == "completed":
        manifest["artifact_sha256"] = artifact_digests(out, manifest["artifacts"])
    write_json(out / "run_manifest.json", manifest)
    return manifest
