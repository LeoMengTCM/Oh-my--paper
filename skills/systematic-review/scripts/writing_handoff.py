#!/usr/bin/env python3
"""检查写作交接条件，或向新目录导出结果、引用与待处理事项。"""
import argparse
import csv
import json
from pathlib import Path
import shutil
import sys

sys.dont_write_bytecode = True

from analysis_runner import now, write_json
from artifact_integrity import verify_artifacts
from handoff_records import check_handoff
from review_model import require

RESULT_FIELDS = ("analysis_status", "measure", "display_scale", "k_selected", "k_analyzed", "k_excluded",
                 "estimate", "ci_lower", "ci_upper", "confidence_level", "direction", "model_applied",
                 "ci_method_applied", "tau2", "I2", "Q", "Q_p")
CONTEXT_FIELDS = ("comparison_id", "outcome_id", "timepoint_id", "analysis_population", "unit", "scale_id")
EFFECT_FIELDS = ("extraction_id", "study_id", "label", "yi", "vi", "se", "estimate", "ci_lower", "ci_upper", "weight_percent", "corrected")


def write_csv(path, fields, rows):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def markdown(result):
    def line(value):
        return str(value).replace("\r", " ").replace("\n", " ")
    lines = ["# 系统综述写作交接", "", f"状态：{result['status']}；用途：{result['purpose']}",
             f"当前方案：{line(result['protocol_version'])}",
             f"可据此起草真实研究结果：{'是' if result['ready_for_drafting'] else '否'}；投稿准备情况：未评估。", "",
             "数字来自已登记并通过检查的运行。results.csv 包含分析级结果，study_results.csv 包含研究级效应。",
             "partial 包内可用部分仅供复核；缺失或失效的分析不会导出为有效结果。", "",
             "## 方法记录", "", f"注册：{line(json.dumps(result['methods']['registration'], ensure_ascii=False))}",
             f"筛选：{result['methods']['screening_mode']}；登记人员：{line(', '.join(result['methods']['screeners']))}",
             f"综合方式：{result['synthesis_mode']}", "",
             "## 待处理事项", ""]
    lines.extend(f"- {line(item['code'])}：{line(item.get('message', json.dumps(item, ensure_ascii=False)))}" for item in result["blockers"])
    if not result["blockers"]:
        lines.append("本工具覆盖的交接检查已通过。")
    lines.extend(["", "## 写作阶段继续完成", "", *["- " + item for item in result["reporting_pending"]], "",
                  "引用检查核对本地保存的证据一致性，不代表实时在线认证或引用语境已获支持。",
                  "文件摘要用于识别运行后改动，不认证人员身份或研究真实性。"])
    return "\n".join(lines) + "\n"


def build_handoff(result, output):
    out = Path(output)
    require(not out.exists() and not out.is_symlink(), "交接目录已存在；请选择新目录，不覆盖旧文件")
    target = out.resolve()
    for analysis in result["analyses"]:
        source = Path(analysis["run_directory"]).expanduser()
        if not source.is_absolute():
            source = Path(result["review_directory"]) / source
        require(not target.is_relative_to(source.resolve()), "交接目录不能位于原统计运行目录内")
    out.mkdir(parents=True, exist_ok=False)
    result = {**result, "built_at": now(), "output_directory": str(target)}
    # 先写 building；导出被中断时不会留下可误读为完成的清单。
    write_json(out / "handoff.json", {**result, "package_status": "building", "ready_for_drafting": False})
    results, effects = [], []
    for index, analysis in enumerate(result["analyses"], 1):
        if analysis["status"] != "validated":
            continue
        identity = {key: analysis[key] for key in ("run_id", "analysis_id", "role")}
        results.append({**identity, **{key: analysis["plan"][key] for key in CONTEXT_FIELDS},
                        **{key: analysis["summary"][key] for key in RESULT_FIELDS}})
        effects.extend({**identity, **{key: row[key] for key in EFFECT_FIELDS}} for row in analysis["effects"])
        destination = out / "analyses" / f"run-{index:03d}"
        destination.mkdir(parents=True)
        for name in analysis["manifest"]["artifacts"]:
            shutil.copyfile(Path(analysis["run_directory"]) / name, destination / name)
        verify_artifacts(destination, analysis["manifest"])
        analysis["export_directory"] = str(destination.relative_to(out))
    write_csv(out / "results.csv", ("run_id", "analysis_id", "role", *CONTEXT_FIELDS, *RESULT_FIELDS), results)
    write_csv(out / "study_results.csv", ("run_id", "analysis_id", "role", *EFFECT_FIELDS), effects)
    citations = result["citations"]
    refs = out / "refs"
    refs.mkdir()
    (refs / "references.bib").write_text(citations["bibtex"], encoding="utf-8")
    write_json(refs / "metadata.json", citations["metadata"])
    write_json(out / "citations.json", citations)
    write_json(out / "review_counts.json", {"schema_version": 1, "counts": result["counts"],
               "quantitative_study_ids": result["quantitative_study_ids"], "screening": result["screening"]})
    (out / "handoff.md").write_text(markdown(result), encoding="utf-8")
    result["package_status"] = "completed"
    write_json(out / "handoff.json", result)
    return result


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError(message)


def main(argv=None):
    try:
        parser = Parser(description=__doc__)
        parser.add_argument("command", choices=("check", "build"))
        parser.add_argument("directory")
        parser.add_argument("--config", required=True)
        parser.add_argument("--out")
        args = parser.parse_args(argv)
        require((args.command == "build") == bool(args.out), "build 必须指定 --out；check 不接受 --out")
        result = check_handoff(args.directory, args.config)
        if args.command == "build":
            result = build_handoff(result, args.out)
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
        return 0 if result["ready_for_drafting"] else 2
    except (ValueError, OSError, UnicodeError, csv.Error) as error:
        print(json.dumps({"status": "error", "error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
