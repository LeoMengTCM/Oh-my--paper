"""将当前综述记录与明确登记的统计运行绑定；只读取研究文件。"""
import csv
import math
from pathlib import Path

from analysis_records import AnalysisBlocked, DATA_FIELDS, prepare_analysis
from analysis_runner import validate_result
from artifact_integrity import verify_artifacts
from citation_records import check_citations
from review_model import human, load_review, parse_json, require, schema, text, timestamp
from screening import summarize

PURPOSES = ("research", "software_validation", "public_benchmark")
ROLES = ("primary", "secondary", "sensitivity", "exploratory")
REPORTING_PENDING = ["GRADE 与最终 Summary of Findings", "引用语境与论断支持核查",
                     "临床解释与方法陈述复核", "PRISMA 清单与正式流程图", "全文审稿与投稿要求检查"]


def read_json(path):
    return parse_json(Path(path).read_text(encoding="utf-8-sig"), str(path))


def resolve_path(base, record, key):
    path = Path(text(record, key)).expanduser()
    return (path if path.is_absolute() else base / path).resolve()


def read_csv(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        require(reader.fieldnames and len(reader.fieldnames) == len(set(reader.fieldnames)), f"CSV 表头无效：{path}")
        rows = list(reader)
    require(all(None not in row and None not in row.values() for row in rows), f"CSV 列数不一致：{path}")
    return rows


def check_run(directory, registration):
    out = resolve_path(directory, registration, "run_directory")
    plan_file = resolve_path(directory, registration, "plan_path")
    prepared = prepare_analysis(directory, plan_file)
    manifest = read_json(out / "run_manifest.json")
    schema(manifest)
    text(manifest, "run_id")
    require(manifest.get("status") == "completed", "运行未完成，不能交接结果")
    require(manifest.get("analysis_id") == prepared["analysis_id"] and
            manifest.get("protocol_version") == prepared["plan"]["protocol_version"], "运行与当前分析或方案版本不匹配")
    verify_artifacts(out, manifest)
    require("run_manifest.json" in manifest["artifacts"], "运行清单缺少自身文件名")
    required = {"prepared.json", "source_snapshot.json", "input.csv", "summary.json", "effects.csv",
                "exclusions.csv", "pairwise_meta.R", "sessionInfo.txt", "ledger_entries.md"}
    require(required <= set(manifest["artifact_sha256"]), "运行的必要文件未全部记录摘要")
    require(read_json(out / "prepared.json") == {key: prepared[key] for key in ("schema_version", "analysis_id", "plan")},
            "运行使用的分析计划已过时")
    require(read_json(out / "source_snapshot.json") == prepared["source_snapshot"], "运行的来源快照与当前记录不一致")
    fields = ("extraction_id", "study_id", "label", "rob_judgment", *DATA_FIELDS)
    expected_rows = [{key: "" if row[key] is None else str(row[key]) for key in fields} for row in prepared["rows"]]
    require(read_csv(out / "input.csv") == expected_rows, "运行输入表与当前选中输入不一致")
    summary = read_json(out / "summary.json")
    validate_result(summary, prepared, out)
    require(manifest.get("analysis_status") == summary["analysis_status"] and manifest.get("software") == summary["software"],
            "运行清单与统计结果的状态或软件版本不一致")
    require(summary.get("display_scale") == {"RR": "ratio", "MD": "difference", "SMD": "standardized_difference"}[summary["measure"]],
            "统计结果展示尺度错误")
    require(read_csv(out / "exclusions.csv") == summary["excluded"], "排除表与统计结果不一致")
    pages = (summary["k_analyzed"] + 39) // 40
    require(type(summary.get("forest_pages")) is int and summary["forest_pages"] == pages, "森林图页数错误")
    figures = {"forest.pdf", "forest.png"} if pages else set()
    if pages > 1:
        figures.update(f"forest-page-{page:03d}.png" for page in range(1, pages + 1))
    require(figures <= set(manifest["artifact_sha256"]), "森林图未全部记录摘要")
    effects = read_csv(out / "effects.csv")
    for effect in effects:
        for key in ("yi", "vi", "se", "estimate", "ci_lower", "ci_upper"):
            require(key in effect and math.isfinite(float(effect[key])), f"研究效应 {key} 缺失或非有限值")
        require(float(effect["vi"]) > 0 and float(effect["se"]) > 0, "研究效应方差或标准误无效")
        require(float(effect["ci_lower"]) <= float(effect["estimate"]) <= float(effect["ci_upper"]), "研究效应区间顺序错误")
        require("label" in effect and effect.get("corrected") in ("TRUE", "FALSE"), "研究效应缺少标签或校正状态")
        require("weight_percent" in effect and (effect["weight_percent"] == "" if summary["k_analyzed"] < 2 else
                math.isfinite(float(effect["weight_percent"])) and 0 <= float(effect["weight_percent"]) <= 100), "研究权重无效")
    return {"status": "validated", "run_id": manifest["run_id"], "analysis_id": prepared["analysis_id"],
            "role": registration["role"], "run_directory": str(out), "plan_path": str(plan_file),
            "plan": prepared["plan"], "summary": summary, "effects": effects,
            "study_ids": sorted(row["study_id"] for row in effects), "manifest": manifest}


def check_handoff(directory, config_file):
    directory = Path(directory).resolve()
    config = read_json(config_file)
    schema(config)
    require(config.get("purpose") in PURPOSES, "purpose 必须为 research、software_validation 或 public_benchmark")
    text(config, "protocol_version")
    require(config.get("synthesis_mode") in ("quantitative", "narrative"), "synthesis_mode 必须为 quantitative 或 narrative")
    registrations = config.get("analyses")
    require(isinstance(registrations, list), "analyses 必须是数组")
    seen_paths = set()
    for registration in registrations:
        require(isinstance(registration, dict) and registration.get("role") in ROLES, "分析 role 无效")
        out = resolve_path(directory, registration, "run_directory")
        resolve_path(directory, registration, "plan_path")
        require(out not in seen_paths, "同一个运行目录不能重复登记")
        seen_paths.add(out)
    review = load_review(directory)
    progress = summarize(review)
    blockers = list(progress["blockers"])

    def block(code, message):
        blockers.append({"code": code, "message": message})

    if config["protocol_version"] != progress["protocol_version"]:
        block("publication_version_stale", "交接配置不是当前方案版本")
    purpose = review["review"].get("purpose")
    if purpose != config["purpose"]:
        block("purpose_mismatch", "review.json 与交接配置须明确登记相同用途")
    if purpose != "research" or config["purpose"] != "research":
        block("validation_material", "软件验证与公开数值基准不能作为真实研究的写作交接")

    analyses, run_ids = [], set()
    for registration in registrations:
        try:
            analysis = check_run(directory, registration)
            require(analysis["run_id"] not in run_ids, "不同登记目录使用了重复的 run_id")
            run_ids.add(analysis["run_id"])
            analyses.append(analysis)
        except (AnalysisBlocked, ValueError, OSError, UnicodeError, csv.Error) as error:
            message = f"{error.reason}: {error.details}" if isinstance(error, AnalysisBlocked) else str(error)
            analyses.append({**registration, "status": "invalid", "error": message})
            block("analysis_not_current", f"{registration['run_directory']}: {message}")
    mode = config["synthesis_mode"]
    synthesis_confirmed = True
    if mode == "quantitative" and not registrations:
        synthesis_confirmed = False
        block("analysis_missing", "定量合成尚未登记任何运行")
    if mode == "narrative":
        require(not registrations, "narrative 不得同时登记统计运行；有运行时使用 quantitative")
        try:
            text(config, "narrative_reason")
            require(human(review["reviewers"], config.get("narrative_approved_by")), "叙述性综合须有登记人类确认")
            approved = timestamp(config, "narrative_approved_at")
            current = next((a for a in review["approvals"] if a["protocol_version"] == progress["protocol_version"]), None)
            require(current is not None and approved >= timestamp(current, "approved_at"), "叙述性综合确认须对应当前批准方案")
        except ValueError as error:
            synthesis_confirmed = False
            block("narrative_unconfirmed", str(error))
    included_ids = {state["report_id"] for state in progress["report_states"] if state["full_text"]["status"] == "include"}
    try:
        citations = check_citations(directory, config, [report for report in review["reports"] if report["report_id"] in included_ids],
                                    review["reviewers"])
    except (ValueError, OSError, UnicodeError) as error:
        citations = {"entries": {}, "metadata": {}, "checks": [], "used_keys": [], "bibtex": "",
                     "report_citations": {}, "blockers": [{"code": "citation_input_invalid", "message": str(error)}]}
    blockers.extend(citations["blockers"])
    counts = dict(progress["counts"])
    known = (progress["screening_complete"] and synthesis_confirmed and config["protocol_version"] == progress["protocol_version"]
             and all(a["status"] == "validated" for a in analyses))
    pooled_ids = sorted({study for a in analyses if a["status"] == "validated" and a["summary"]["analysis_status"] == "pooled"
                         for study in a["study_ids"]})
    counts["studies_in_quantitative_synthesis"] = len(pooled_ids) if known else None
    return {"schema_version": 1, "status": "partial" if blockers else "ready", "ready_for_drafting": not blockers,
            "submission_readiness": "not_assessed", "purpose": config["purpose"], "review_purpose": purpose,
            "review_id": progress["review_id"], "protocol_version": progress["protocol_version"],
            "review_directory": str(directory), "config_path": str(Path(config_file).resolve()),
            "synthesis_mode": mode, "narrative_reason": config.get("narrative_reason"),
            "counts": counts, "quantitative_study_ids": pooled_ids if known else None,
            "screening": progress, "analyses": analyses, "citations": citations, "blockers": blockers,
            "methods": {"registration": review["review"]["registration"], "screening_mode": review["review"]["screening_mode"],
                        "screeners": review["review"]["screeners"], "limitations": progress["limitations"]},
            "reporting_pending": REPORTING_PENDING}
