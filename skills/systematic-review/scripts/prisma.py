"""PRISMA 计数表：仅由已校验的记录和有效筛选决定派生。"""
from collections import Counter

from review_model import require


def build_counts(data, report_states):
    reports = data["indexes"]["reports"]
    screened = [s for s in report_states if s["title_abstract"]["status"] in ("include", "exclude")]
    eligible = [s for s in screened if s["title_abstract"]["status"] == "include"]
    sought = [s for s in eligible if reports[s["report_id"]]["retrieval_status"] != "not_requested"]
    retrieved = [s for s in sought if reports[s["report_id"]]["retrieval_status"] == "retrieved"]
    assessed = [s for s in retrieved if s["full_text"]["status"] in ("include", "exclude")]
    included = [s for s in assessed if s["full_text"]["status"] == "include"]
    excluded = [s for s in assessed if s["full_text"]["status"] == "exclude"]
    hits = [r["identified_count"] for r in data["search_runs"]]
    counts = {
        "search_hits_reported": sum(hits) if hits and all(n is not None for n in hits) else None,
        "records_identified": len(data["records"]),
        "duplicate_records_removed": len(data["records"]) - len(reports),
        "reports_after_dedup": len(reports),
        "records_screened": len(screened),
        "records_pending_screening": len(reports) - len(screened),
        "records_excluded": len(screened) - len(eligible),
        "reports_pending_retrieval_request": len(eligible) - len(sought),
        "reports_sought": len(sought),
        "reports_retrieval_pending": sum(reports[s["report_id"]]["retrieval_status"] == "sought" for s in sought),
        "reports_not_retrieved": sum(reports[s["report_id"]]["retrieval_status"] == "not_retrieved" for s in sought),
        "reports_assessed": len(assessed),
        "reports_pending_full_text_screening": len(retrieved) - len(assessed),
        "reports_excluded": len(excluded),
        "full_text_exclusion_reasons": dict(Counter(s["full_text"]["reason"] for s in excluded)),
        "reports_included": len(included),
        "reports_pending_study_mapping": sum(s["study_id"] is None for s in included),
        "studies_included": len({s["study_id"] for s in included if s["study_id"] is not None}),
        "studies_in_quantitative_synthesis": None,
    }
    c = counts
    require(c["records_identified"] == c["duplicate_records_removed"] + c["records_screened"] + c["records_pending_screening"],
            "题录识别、去重与筛选计数不守恒")
    require(c["records_screened"] == c["records_excluded"] + c["reports_sought"] + c["reports_pending_retrieval_request"],
            "筛选与全文获取计数不守恒")
    require(c["reports_sought"] == c["reports_not_retrieved"] + c["reports_retrieval_pending"] + c["reports_assessed"] + c["reports_pending_full_text_screening"],
            "全文获取与评估计数不守恒")
    require(c["reports_assessed"] == c["reports_excluded"] + c["reports_included"], "全文评估与纳入计数不守恒")
    sources = []
    for run in data["search_runs"]:
        sources.append({key: run[key] for key in ("search_run_id", "source", "source_type", "identified_count", "retrieved_count", "status")})
    return counts, sources


def markdown_summary(result):
    def cell(value):
        return str(value).replace("|", "\\|").replace("\r", " ").replace("\n", "<br>")

    labels = {
        "search_hits_reported": "数据源报告的总命中数",
        "records_identified": "实际导入题录数",
        "duplicate_records_removed": "重复题录移除数",
        "reports_after_dedup": "去重后报告数",
        "records_screened": "已完成题名摘要筛选",
        "records_pending_screening": "待处理：题名摘要筛选",
        "records_excluded": "题名摘要排除数",
        "reports_pending_retrieval_request": "待处理：尚未请求全文",
        "reports_sought": "已请求获取全文",
        "reports_retrieval_pending": "待处理：全文获取中",
        "reports_not_retrieved": "全文未取得（非资格排除）",
        "reports_assessed": "已完成全文资格评估",
        "reports_pending_full_text_screening": "待处理：全文资格评估",
        "reports_excluded": "全文资格排除数",
        "reports_included": "纳入报告数",
        "reports_pending_study_mapping": "待处理：纳入报告的研究归并",
        "studies_included": "已确认的纳入研究数",
        "studies_in_quantitative_synthesis": "定量合成研究数（本工具不推断）",
    }
    status = "筛选记录完整（不表示整项研究完成）" if result["screening_complete"] else "非最终计数：仍有待处理事项"
    lines = ["# PRISMA 计数与进度", "", status, "",
             f"方案版本：{cell(result['protocol_version'])}", "",
             "| 项目 | 数量 |", "|---|---:|"]
    for key, label in labels.items():
        value = result["counts"][key]
        lines.append(f"| {label} | {value if value is not None else '未知或尚未记录'} |")
    lines.extend(["", "## 全文排除理由", "", "| 理由 | 数量 |", "|---|---:|"])
    for reason, count in sorted(result["counts"]["full_text_exclusion_reasons"].items()):
        lines.append(f"| {cell(reason)} | {count} |")
    lines.extend(["", "## 检索来源", "", "| 来源 / 批次 | 类型 | 命中 | 导入 | 状态 |", "|---|---|---:|---:|---|"])
    for source in result["sources"]:
        values = [f"{source['source']} / {source['search_run_id']}", source["source_type"],
                  source["identified_count"] if source["identified_count"] is not None else "未知",
                  source["retrieved_count"], source["status"]]
        lines.append("| " + " | ".join(cell(value) for value in values) + " |")
    lines.extend(["", "## 待处理事项与限制", ""])
    for blocker in result["blockers"]:
        lines.append("- " + cell(" / ".join(str(value) for value in blocker.values())))
    for limitation in result["limitations"]:
        lines.append("- " + cell(limitation))
    lines.extend(["", "这是由登记记录生成的计数表，不是官方流程图，也不认证筛选人员身份或实际阅读行为。"])
    return "\n".join(lines)
