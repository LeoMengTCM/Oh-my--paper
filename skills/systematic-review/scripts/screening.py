"""从记录推导筛选进度；不替研究者作判断。"""
from collections import defaultdict

from review_model import human, require, text, timestamp
from prisma import build_counts


def subject(decision):
    return tuple(decision[key] for key in ("report_id", "protocol_version", "stage"))


def validate_decisions(data):
    decisions = data["indexes"]["screening_decisions"]
    for decision in decisions.values():
        require(text(decision, "report_id") in data["indexes"]["reports"], "筛选引用未知报告")
        text(decision, "protocol_version")
        require(text(decision, "reviewer_id") in data["reviewers"], "筛选引用未登记人员")
        require(decision.get("stage") in ("title_abstract", "full_text"), "筛选阶段无效")
        require(decision.get("decision") in ("include", "exclude"), "筛选决定无效")
        require(decision.get("role") in ("initial", "adjudication"), "筛选角色无效")
        timestamp(decision, "decided_at")
        if decision["stage"] == "full_text" and decision["decision"] == "exclude":
            text(decision, "reason")

    superseded = set()
    for decision in decisions.values():
        if "supersedes" in decision:
            previous_id = text(decision, "supersedes")
            require(previous_id in decisions, "supersedes 引用未知决定")
            previous = decisions[previous_id]
            require(subject(previous) == subject(decision) and
                    previous["reviewer_id"] == decision["reviewer_id"] and previous["role"] == decision["role"],
                    "supersedes 只能修订同一人员、报告、阶段、版本和角色的决定")
            require(previous_id not in superseded, "修订链存在分叉，不能按最新时间猜测有效决定")
            require(timestamp(previous, "decided_at") <= timestamp(decision, "decided_at"), "修订时间早于原决定")
            superseded.add(previous_id)
        if decision["role"] == "adjudication":
            require(human(data["reviewers"], decision["reviewer_id"]), "AI 不能作人工裁决")
            text(decision, "reason")
            refs = decision.get("resolves")
            require(isinstance(refs, list) and all(isinstance(ref, str) and ref in decisions for ref in refs),
                    "resolves 必须引用已有独立判断")
            require(len(refs) == len(set(refs)) and len(refs) >= 2, "裁决须引用至少两个不同的独立判断")
            originals = [decisions[ref] for ref in refs]
            require(all(subject(d) == subject(decision) and d["role"] == "initial" and
                        human(data["reviewers"], d["reviewer_id"]) for d in originals), "裁决引用的对象不是同一事项的人工初始判断")
            require(len({d["reviewer_id"] for d in originals}) == len(originals), "裁决的初始判断必须来自不同人员")
            disagreements = {(d["decision"], d.get("reason") if d["stage"] == "full_text" and d["decision"] == "exclude" else None) for d in originals}
            require(len(disagreements) > 1, "裁决必须针对决定或全文排除理由有分歧的判断")
            require(all(timestamp(d, "decided_at") <= timestamp(decision, "decided_at") for d in originals),
                    "裁决时间早于引用的判断")
            require(decision.get("resolution_method") in ("discussion", "third_reviewer"), "裁决方法无效")
            if decision["resolution_method"] == "third_reviewer":
                require(decision["reviewer_id"] not in {d["reviewer_id"] for d in originals}, "第三位裁决者不能是原筛选者")
    for identifier in decisions:
        seen = set()
        cursor = identifier
        while cursor:
            require(cursor not in seen, "supersedes 存在循环")
            seen.add(cursor)
            cursor = decisions[cursor].get("supersedes")
    return superseded


def resolve_decisions(decisions, config, reviewers):
    initial = [d for d in decisions if d["role"] == "initial"]
    humans = [d for d in initial if human(reviewers, d["reviewer_id"]) and d["reviewer_id"] in config["screeners"]]
    by_reviewer = defaultdict(list)
    for decision in humans:
        by_reviewer[decision["reviewer_id"]].append(decision)
    require(all(len(items) == 1 for items in by_reviewer.values()), "同一筛选者存在多条未明确替代的判断")
    status = "pending"
    if len(humans) == len(config["screeners"]):
        choices = {(d["decision"], d.get("reason") if d["stage"] == "full_text" and d["decision"] == "exclude" else None) for d in humans}
        status = next(iter(choices))[0] if len(choices) == 1 else "conflict"
    human_ids = {d["decision_id"] for d in humans}
    adjudications = [d for d in decisions if d["role"] == "adjudication"]
    applicable = [d for d in adjudications if set(d["resolves"]) == human_ids]
    if status == "conflict" and len(applicable) == 1:
        status = applicable[0]["decision"]
    effective = applicable if len(applicable) == 1 and status in ("include", "exclude") else humans
    return {"status": status, "human_decisions": len(humans),
            "ai_suggestions": sum(not human(reviewers, d["reviewer_id"]) for d in initial),
            "decision_ids": [d["decision_id"] for d in effective],
            "reason": effective[0].get("reason") if status == "exclude" else None,
            "stale_adjudications": [d["decision_id"] for d in adjudications if d not in applicable]}


def summarize(data):
    superseded = validate_decisions(data)
    config = data["review"]
    blockers = []
    approval = next((a for a in data["approvals"] if a["protocol_version"] == config["protocol_version"]), None)
    if approval is None:
        blockers.append({"code": "protocol_unapproved", "protocol_version": config["protocol_version"]})
    elif (approval["screening_mode"] != config["screening_mode"] or
          approval["registration_status"] != config["registration"]["status"]):
        blockers.append({"code": "approval_context_changed"})
        approval = None
    current = [d for d in data["screening_decisions"]
               if d["protocol_version"] == config["protocol_version"] and d["decision_id"] not in superseded] if approval else []
    if approval:
        for decision in current:
            if human(data["reviewers"], decision["reviewer_id"]):
                require(timestamp(decision, "decided_at") >= timestamp(approval, "approved_at"),
                        "人工筛选时间早于当前方案批准时间")
    if not data["search_runs"]:
        blockers.append({"code": "search_missing"})
    for search in data["search_runs"]:
        if search["status"] == "partial":
            blockers.append({"code": "search_partial", "search_run_id": search["search_run_id"]})
    groups = defaultdict(list)
    for decision in current:
        groups[(decision["report_id"], decision["stage"])].append(decision)
    report_states = []
    for report in data["reports"]:
        title = resolve_decisions(groups[(report["report_id"], "title_abstract")], config, data["reviewers"])
        full = {"status": "not_required"}
        study_id = None
        full_decisions = groups[(report["report_id"], "full_text")]
        if full_decisions:
            require(title["status"] == "include" and report["retrieval_status"] == "retrieved",
                    "全文判断需要先完成题名摘要纳入并实际取得全文")
        if title["status"] in ("pending", "conflict"):
            blockers.append({"code": f"title_abstract_{title['status']}", "report_id": report["report_id"]})
        if title["status"] == "include":
            retrieval = report["retrieval_status"]
            if retrieval == "not_retrieved":
                full = {"status": "not_retrieved"}
            elif retrieval in ("not_requested", "sought"):
                full = {"status": "retrieval_pending"}
                blockers.append({"code": "retrieval_pending", "report_id": report["report_id"]})
            else:
                title_time = max(timestamp(data["indexes"]["screening_decisions"][identifier], "decided_at")
                                 for identifier in title["decision_ids"])
                stale_full = [d["decision_id"] for d in full_decisions if timestamp(d, "decided_at") < title_time]
                fresh_full = [d for d in full_decisions if d["decision_id"] not in stale_full]
                full = resolve_decisions(fresh_full, config, data["reviewers"])
                full["stale_decisions"] = stale_full
                if full["status"] in ("pending", "conflict"):
                    blockers.append({"code": f"full_text_{full['status']}", "report_id": report["report_id"]})
                if full["status"] == "include":
                    link = report.get("study_link")
                    if link and link["protocol_version"] == config["protocol_version"]:
                        study_id = link["study_id"]
                    else:
                        blockers.append({"code": "study_mapping_pending", "report_id": report["report_id"]})
        report_states.append({"report_id": report["report_id"], "title_abstract": title,
                              "full_text": full, "study_id": study_id})
    counts, sources = build_counts(data, report_states)
    limitations = ["single_screener"] if config["screening_mode"] == "single" else []
    if config["registration"]["status"] == "not_applicable":
        limitations.append("registration_not_applicable")
    elif config["registration"]["status"] != "registered":
        limitations.append("registration_not_completed")
    return {"schema_version": 1, "status": "partial" if blockers else "complete",
            "screening_complete": not blockers, "blockers": blockers,
            "limitations": limitations, "report_states": report_states,
            "counts": counts, "sources": sources, "review_id": config["review_id"],
            "protocol_version": config["protocol_version"], "registration": config["registration"]}
