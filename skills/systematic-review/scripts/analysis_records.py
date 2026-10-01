"""准备经过核对的成对 Meta 输入，不修改研究记录。"""
import math
from pathlib import Path

from review_model import human, index_rows, load_review, parse_json, require, schema, text, timestamp
from screening import summarize

DATA_FIELDS = ("n_intervention", "n_comparator", "events_intervention", "events_comparator",
               "mean_intervention", "sd_intervention", "mean_comparator", "sd_comparator")
SCOPE_FIELDS = ("comparison_id", "outcome_id", "timepoint_id", "analysis_population")
DOMAINS = ("randomization", "deviations", "missing_data", "measurement", "selection")
JUDGMENTS = ("low", "some_concerns", "high")


class AnalysisBlocked(Exception):
    def __init__(self, reason, details=None):
        super().__init__(reason)
        self.reason = reason
        self.details = details or []


def load_table(directory, name, key):
    records = [parse_json(line, f"{name}:{number}") for number, line in
               enumerate((directory / name).read_text(encoding="utf-8-sig").splitlines(), 1) if line.strip()]
    return index_rows(records, key)


def number(record, key):
    value = record.get(key)
    require(type(value) in (int, float) and math.isfinite(value), f"{key} 必须是有限数值，缺失不能填 0 或布尔值")
    return value


def document(directory, record, key):
    path = directory / text(record, key)
    require(path.is_file() and path.stat().st_size > 0, f"缺少非空来源文件：{path}")
    return str(path.resolve())


def validate_plan(plan, review):
    schema(plan)
    text(plan, "analysis_id")
    require(text(plan, "protocol_version") == review["review"]["protocol_version"], "分析计划不是当前方案版本")
    require(plan.get("effect_measure") in ("RR", "MD", "SMD"), "首版只支持 RR/MD/SMD")
    require(plan.get("model") == "REML", "首版只支持预设的 REML 合并")
    require(plan.get("ci_method") in ("z", "knha"), "ci_method 必须明确为 z 或 knha")
    require(0 < number(plan, "confidence_level") < 1, "置信水平必须在 0 与 1 之间")
    require(human(review["reviewers"], plan.get("approved_by")), "分析计划须有登记人类的批准记录")
    current = next(a for a in review["approvals"] if a["protocol_version"] == plan["protocol_version"])
    require(timestamp(plan, "approved_at") >= timestamp(current, "approved_at"), "分析计划批准时间早于方案批准")
    for field in (*SCOPE_FIELDS, "unit", "scale_id"):
        text(plan, field)
    require(plan.get("measurement_type") in ("final", "change"), "measurement_type 必须为 final 或 change")
    require(plan.get("direction") in ("lower_is_better", "higher_is_better"), "必须明确效应方向，不自动反转")
    require(plan.get("target_effect") in ("assignment", "adherence"), "必须明确 RoB 2 的目标效应")
    text(plan, "pooling_rationale")
    require(type(plan.get("clinically_poolable")) is bool, "必须明确人工可合并性判断")
    if not plan["clinically_poolable"]:
        raise AnalysisBlocked("not_poolable", ["按方案做叙述性综合，不运行 Meta 分析"])
    if plan["effect_measure"] == "RR":
        require(plan.get("zero_cell_correction") in ("none", "constant_0.5"), "RR 必须预设零单元校正策略")
        require(plan.get("double_zero_policy") in ("error", "exclude"), "RR 必须预设双零事件处理")


def validate_values(extraction, plan):
    values, original = extraction.get("data"), extraction.get("original_data")
    require(isinstance(values, dict) and isinstance(original, dict), "必须保留 data 与 original_data")
    fields = DATA_FIELDS[:4] if plan["effect_measure"] == "RR" else (DATA_FIELDS[0], DATA_FIELDS[1], *DATA_FIELDS[4:])
    require(set(values) == set(fields) and set(original) == set(fields), "数值字段必须匹配该效应量，不混入其他结局")
    require(extraction.get("transformation") == "identity", "首版不自动接受未实现的单位转换或方差估算")
    for field in fields:
        require(number(values, field) == number(original, field), "identity 提取不能改变原始数值")
    nt, nc = values["n_intervention"], values["n_comparator"]
    require(nt > 0 and nc > 0 and int(nt) == nt and int(nc) == nc, "样本量必须为正整数")
    if plan["effect_measure"] == "RR":
        a, c = values["events_intervention"], values["events_comparator"]
        require(int(a) == a and int(c) == c and 0 <= a <= nt and 0 <= c <= nc, "事件数必须是 0 到样本量之间的整数")
        if a == 0 and c == 0:
            require(plan["double_zero_policy"] == "exclude", "双零事件研究需要预设处理，不自动删除")
        elif plan["zero_cell_correction"] == "none":
            require(a > 0 and c > 0, "存在零事件，none 策略无法估计 RR；先由研究者处理方案")
            require((nt - a) / (nt * a) + (nc - c) / (nc * c) > 0, "RR 方差为零，不能合并")
    else:
        require(nt >= 2 and nc >= 2, "连续结局每组至少 2 人才能使用样本 SD")
        st, sc = values["sd_intervention"], values["sd_comparator"]
        require(st >= 0 and sc >= 0 and st * st / nt + sc * sc / nc > 0, "SD 非法或效应方差为零")
    return fields


def validate_sources(directory, extraction, fields, included, review):
    require(human(review["reviewers"], extraction.get("verified_by")), "数值必须有人类核对记录，AI 不能冒充")
    verified_at = timestamp(extraction, "verified_at")
    current = next(a for a in review["approvals"] if a["protocol_version"] == extraction["protocol_version"])
    require(verified_at >= timestamp(current, "approved_at"), "提取核对早于当前方案批准")
    evidence = index_rows(extraction.get("evidence"), "evidence_id", versioned=False)
    provenance = extraction.get("provenance")
    require(isinstance(provenance, dict) and set(provenance) == set(fields), "每个数值都必须有明确的原文出处")
    for field in fields:
        evidence_id = provenance[field]
        require(isinstance(evidence_id, str) and evidence_id in evidence, f"{field} 引用未知出处")
    for source in evidence.values():
        report_id = text(source, "report_id")
        require(report_id in included and included[report_id] == extraction["study_id"], "出处报告未纳入或不属于该研究")
        text(source, "locator")
        text(source, "quote")
        document(directory, source, "document_path")


def validate_rob(directory, assessment, extraction, plan, review):
    require(assessment.get("study_id") == extraction["study_id"] and assessment.get("protocol_version") == plan["protocol_version"],
            "偏倚评价研究或方案版本不匹配")
    for field in SCOPE_FIELDS:
        require(assessment.get(field) == plan[field], "偏倚评价必须针对当前结果，不能跨结局复用")
    require(assessment.get("tool") == "RoB2" and assessment.get("target_effect") == plan["target_effect"], "RoB 2 工具或目标效应不匹配")
    text(assessment, "tool_version")
    require(human(review["reviewers"], assessment.get("reviewed_by")), "偏倚评价须由登记的人类确认")
    timestamp(assessment, "reviewed_at")
    document(directory, assessment, "assessment_document")
    domains = assessment.get("domains")
    require(isinstance(domains, dict) and set(domains) == set(DOMAINS), "RoB 2 必须记录五个域")
    judgments = []
    for name in DOMAINS:
        item = domains[name]
        require(isinstance(item, dict) and item.get("judgment") in JUDGMENTS, f"RoB 2 的 {name} 判断无效")
        text(item, "rationale")
        judgments.append(item["judgment"])
    overall = assessment.get("overall_judgment")
    require(overall in JUDGMENTS, "RoB 2 总体判断无效，不能使用自创分数")
    require("high" not in judgments or overall == "high", "高风险域与总体低风险/有疑虑矛盾")
    require(overall != "low" or all(j == "low" for j in judgments), "总体低风险要求各域低风险")
    require(not all(j == "low" for j in judgments) or overall == "low", "所有域低风险与总体判断矛盾")


def prepare_analysis(directory, plan_file):
    directory = Path(directory)
    review = load_review(directory)
    progress = summarize(review)
    if not progress["screening_complete"]:
        raise AnalysisBlocked("screening_incomplete", progress["blockers"])
    plan = parse_json(Path(plan_file).read_text(encoding="utf-8-sig"), "analysis plan")
    validate_plan(plan, review)
    extractions = load_table(directory, "extractions.jsonl", "extraction_id")
    assessments = load_table(directory, "rob2.jsonl", "assessment_id")
    selected_ids = plan.get("extraction_ids")
    require(isinstance(selected_ids, list) and selected_ids and all(isinstance(value, str) and value in extractions for value in selected_ids),
            "extraction_ids 必须引用已存在的提取记录")
    require(len(selected_ids) == len(set(selected_ids)), "不能重复选择同一提取记录")
    selected = [extractions[identifier] for identifier in selected_ids]
    included = {state["report_id"]: state["study_id"] for state in progress["report_states"] if state["full_text"]["status"] == "include"}
    rows, study_ids = [], set()
    for extraction in selected:
        study_id = text(extraction, "study_id")
        require(study_id not in study_ids, "同一分析不能重复使用同一研究的参与者")
        study_ids.add(study_id)
        study = review["indexes"]["studies"].get(study_id)
        require(study and study["design"] == "parallel-rct", "首版仅支持平行组 RCT，复杂设计须单独处理")
        require(extraction.get("protocol_version") == plan["protocol_version"], "提取记录不是当前方案版本")
        for field in (*SCOPE_FIELDS, "measurement_type", "direction", "effect_measure"):
            require(extraction.get(field) == plan[field], f"提取记录 {field} 与分析计划不匹配")
        text(extraction, "unit")
        text(extraction, "scale_id")
        if plan["effect_measure"] != "SMD":
            require(extraction["unit"] == plan["unit"] and extraction["scale_id"] == plan["scale_id"], "单位或量表不一致，不自动转换")
        require(text(extraction, "intervention_arm") != text(extraction, "comparator_arm"), "干预与对照不能是同一组")
        label = text(extraction, "label")
        fields = validate_values(extraction, plan)
        validate_sources(directory, extraction, fields, included, review)
        risk_id = text(extraction, "risk_of_bias_id")
        require(risk_id in assessments, "提取记录缺少对应的偏倚评价")
        assessment = assessments[risk_id]
        validate_rob(directory, assessment, extraction, plan, review)
        rows.append({"extraction_id": extraction["extraction_id"], "study_id": study_id, "label": label,
                     "rob_judgment": assessment["overall_judgment"], **{key: extraction["data"].get(key) for key in DATA_FIELDS}})
    return {"schema_version": 1, "analysis_id": plan["analysis_id"], "plan": plan, "rows": rows,
            "source_snapshot": {"review": review["review"], "approvals": review["approvals"],
                                "reports": review["reports"], "studies": review["studies"],
                                "extractions": selected, "rob2": [assessments[e["risk_of_bias_id"]] for e in selected]}}
