"""加载并校验系统综述权威记录；不写回文件。"""
from collections import Counter
from datetime import datetime
import json
from pathlib import Path

from identifiers import identifiers

TABLE_IDS = {
    "approvals": "approval_id", "search_runs": "search_run_id", "records": "record_id",
    "reports": "report_id", "studies": "study_id", "screening_decisions": "decision_id",
}
REGISTRATION_STATUSES = {"planned", "submitted", "registered", "not_registered", "not_applicable"}
RETRIEVAL_STATUSES = {"not_requested", "sought", "retrieved", "not_retrieved"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def text(record, key):
    value = record.get(key)
    require(isinstance(value, str) and bool(value.strip()), f"{key} 必须是非空字符串")
    return value


def timestamp(record, key):
    value = text(record, key)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"{key} 必须是含时区的 ISO 日期时间") from error
    require(parsed.tzinfo is not None, f"{key} 必须包含时区")
    return parsed


def schema(record):
    require(isinstance(record, dict), "每条记录必须是对象")
    require(type(record.get("schema_version")) is int and record["schema_version"] == 1,
            "仅支持 schema_version=1")


def index_rows(records, key, versioned=True):
    require(isinstance(records, list), f"{key} 所在表必须是数组")
    result = {}
    for record in records:
        if versioned:
            schema(record)
        else:
            require(isinstance(record, dict), f"{key} 记录必须是对象")
        identifier = text(record, key)
        require(identifier not in result, f"重复的 {key}: {identifier}")
        result[identifier] = record
    return result


def human(reviewers, reviewer_id):
    return isinstance(reviewer_id, str) and reviewer_id in reviewers and reviewers[reviewer_id]["kind"] == "human"


def validate_structure(data, directory):
    config = data["review"]
    schema(config)
    text(config, "review_id")
    text(config, "protocol_version")
    mode = config.get("screening_mode")
    require(mode in ("single", "dual"), "screening_mode 必须为 single 或 dual")
    reviewers = index_rows(config.get("reviewers"), "reviewer_id", versioned=False)
    for reviewer in reviewers.values():
        require(reviewer.get("kind") in ("human", "ai"), "reviewer.kind 必须为 human 或 ai")
    screeners = config.get("screeners")
    require(isinstance(screeners, list) and all(human(reviewers, item) for item in screeners),
            "screeners 必须引用登记的人类研究者")
    require(len(screeners) == len(set(screeners)) == (2 if mode == "dual" else 1),
            "screeners 必须是与筛选模式匹配的独立人员")
    registration = config.get("registration")
    require(isinstance(registration, dict), "缺少 registration")
    require(text(registration, "status") in REGISTRATION_STATUSES, "registration.status 无效")
    text(registration, "registration_id" if registration["status"] == "registered" else "reason")

    tables = {name: index_rows(data[name], key) for name, key in TABLE_IDS.items()}
    versions = set()
    for approval in data["approvals"]:
        version = text(approval, "protocol_version")
        require(version not in versions, f"方案版本 {version} 存在多个批准记录")
        versions.add(version)
        require(human(reviewers, approval.get("reviewer_id")), "批准者必须是登记的人类研究者")
        timestamp(approval, "approved_at")
        require(approval.get("screening_mode") in ("single", "dual"), "批准记录筛选模式无效")
        require(text(approval, "registration_status") in REGISTRATION_STATUSES, "批准记录注册状态无效")
        if approval["registration_status"] != "registered" or approval["screening_mode"] == "single":
            require(approval.get("acknowledged_limitations") is True, "批准记录须确认未注册或单人流程的限制")
        for field in ("protocol_document", "sap_document"):
            document = directory / text(approval, field)
            require(document.is_file(), f"批准记录引用的文件不存在：{document}")

    for search in data["search_runs"]:
        for field in ("source", "query"):
            text(search, field)
        require(search.get("source_type") in ("database", "register", "other"), "source_type 无效")
        timestamp(search, "searched_at")
        require(search.get("status") in ("complete", "partial"), "检索状态必须为 complete 或 partial")
        require(type(search.get("retrieved_count")) is int and search["retrieved_count"] >= 0,
                "retrieved_count 必须为非负整数")
        require("identified_count" in search, "缺少 identified_count，未知时须显式填 null")
        identified = search["identified_count"]
        require((identified is None and search["status"] == "partial") or
                (type(identified) is int and identified >= 0), "identified_count 必须为非负整数，或 partial 时的 null")
        if identified is not None:
            require(search["retrieved_count"] <= identified, "取回数不能大于命中数")
        if search["status"] == "complete":
            require(search["retrieved_count"] == identified, "完整检索的命中数与取回数不符")
        if "retrieval_complete" in search:
            complete = search["retrieval_complete"]
            require(type(complete) is bool, "来源 retrieval_complete 必须为布尔值")
            require(text(search, "source_status") in ("complete", "partial") and
                    complete == (search["source_status"] == "complete"), "来源状态与完整性声明不符")
            require(search["status"] != "complete" or complete, "来源尚未完整取回，不能标记检索 complete")
            for field in ("incomplete_reasons", "missing_metadata_pmids", "missing_abstract_pmids"):
                entries = search.get(field, [])
                require(isinstance(entries, list) and (not complete or not entries), "来源完整性声明与缺项矛盾")
        if "query_parameters" in search:
            require(isinstance(search["query_parameters"], dict) and search["query_parameters"].get("query") == search["query"],
                    "检索参数与原检索式不符")

    seen_source_ids = set()
    for record in data["records"]:
        run_id = text(record, "search_run_id")
        report_id = text(record, "report_id")
        source_id = text(record, "source_record_id")
        require(run_id in tables["search_runs"], f"未知 search_run_id: {run_id}")
        require(report_id in tables["reports"], f"未知 report_id: {report_id}")
        require((run_id, source_id) not in seen_source_ids, "同一次检索的来源记录重复导入")
        seen_source_ids.add((run_id, source_id))
    record_counts = Counter(record["search_run_id"] for record in data["records"])
    for run_id, search in tables["search_runs"].items():
        require(record_counts[run_id] == search["retrieved_count"], f"检索 {run_id} 的 records 数量与 retrieved_count 不符")
    referenced_reports = {record["report_id"] for record in data["records"]}
    require(referenced_reports == set(tables["reports"]), "存在没有来源题录的报告")
    report_identifiers = set()
    for report in data["reports"]:
        text(report, "title")
        for identifier in identifiers(report).items():
            require(identifier not in report_identifiers, "同一 DOI/PMID 对应多个报告，请先核查去重")
            report_identifiers.add(identifier)
        require(text(report, "retrieval_status") in RETRIEVAL_STATUSES, "retrieval_status 无效")
        if "study_link" in report:
            link = report["study_link"]
            require(isinstance(link, dict), "study_link 必须是对象")
            require(text(link, "study_id") in tables["studies"], "study_link 引用未知研究")
            require(human(reviewers, link.get("confirmed_by")), "研究归并须由登记的人类研究者确认")
            text(link, "protocol_version")
            text(link, "reason")
            timestamp(link, "confirmed_at")
    for study in data["studies"]:
        text(study, "design")

    data["indexes"] = tables
    data["reviewers"] = reviewers
    return data


def parse_json(content, label="JSON"):
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, f"重复 JSON 字段：{key}")
            result[key] = value
        return result

    def reject_constant(value):
        raise ValueError(f"非标准 JSON 数值：{value}")

    try:
        return json.loads(content, object_pairs_hook=unique_object, parse_constant=reject_constant)
    except ValueError as error:
        raise ValueError(f"{label}: {error}") from error


def load_review(directory):
    directory = Path(directory)
    data = {"review": parse_json((directory / "review.json").read_text(encoding="utf-8-sig"), "review.json")}
    for name in TABLE_IDS:
        data[name] = [parse_json(line, f"{name}.jsonl:{number}")
                      for number, line in enumerate((directory / f"{name}.jsonl").read_text(encoding="utf-8-sig").splitlines(), 1)
                      if line.strip()]
    return validate_structure(data, directory)
