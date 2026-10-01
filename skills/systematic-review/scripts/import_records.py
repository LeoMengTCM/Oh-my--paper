#!/usr/bin/env python3
"""离线题录导入预览；只输出 JSON，不修改输入或综述文件。"""

import argparse
import csv
import hashlib
import json
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True

from identifiers import identifiers, normalize_pmid
from review_model import RETRIEVAL_STATUSES, index_rows, parse_json, timestamp


def stable_id(kind, *parts):
    encoded = json.dumps(parts, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return kind + "_" + hashlib.sha256(encoded).hexdigest()[:24]


class PreviewError(ValueError):
    """输入不能安全生成预览。"""


class JSONParser(argparse.ArgumentParser):
    def error(self, message):
        raise PreviewError("命令行参数无效：" + message)


def parser():
    cli = JSONParser(description=__doc__)
    cli.add_argument("input", help="本地题录文件")
    cli.add_argument("--format", required=True, choices=("pubmed-json", "ris", "csv"))
    cli.add_argument("--review-id", required=True)
    cli.add_argument("--search-run-id", required=True)
    cli.add_argument("--source", required=True)
    cli.add_argument("--source-type", required=True, choices=("database", "register", "other"))
    cli.add_argument("--query", required=True)
    cli.add_argument("--searched-at", required=True)
    cli.add_argument("--identified-count", type=int)
    cli.add_argument("--complete", action="store_true")
    cli.add_argument("--existing-reports")
    return cli


def text(value, field, required=True):
    if not isinstance(value, str) or (required and not value.strip()):
        raise PreviewError(field + " 必须是" + ("非空字符串" if required else "字符串"))
    return value.strip()


def count(value, field):
    if type(value) is not int or value < 0:
        raise PreviewError(field + " 必须是非负整数，不能使用布尔值")
    return value


def read_ris(handle):
    rows, warnings = [], []
    tags = None
    previous_tag = None
    for number, line in enumerate(handle, 1):
        if not line.strip():
            continue
        match = re.match(r"^([A-Z][A-Z0-9]{1,3})\s{2}- ?(.*)$", line.rstrip("\r\n"))
        if not match:
            if tags is not None and previous_tag and line[:1].isspace():
                tags[previous_tag][-1] += " " + line.strip()
                continue
            raise PreviewError(f"RIS 第 {number} 行格式无效")
        tag, value = match.groups()
        if tag == "TY":
            if tags is not None:
                raise PreviewError("RIS 记录缺少 ER 终止标签")
            tags = {"TY": [text(value, "TY")]}
        elif tag == "ER":
            if tags is None:
                raise PreviewError("RIS 的 ER 缺少对应 TY")
            def one(key):
                values = tags.get(key, [""])
                if len(set(values)) > 1:
                    raise PreviewError(f"RIS 的 {key} 有多个不同值，须核对")
                return values[0]
            title = text(one("TI") or one("T1"), "title")
            source_id = one("ID")
            if not source_id:
                source_id = stable_id("ris", sorted(tags.items()))
                warnings.append(f"{source_id} 缺少来源 ID，使用完整 RIS 记录生成标识；不能仅凭标题归并")
            rows.append({"source_record_id": source_id, "title": title, "doi": one("DO"), "pmid": one("PMID")})
            tags = None
        else:
            if tags is None:
                raise PreviewError("RIS 标签必须位于 TY 与 ER 之间")
            tags.setdefault(tag, []).append(value.strip())
        previous_tag = tag
    if tags is not None:
        raise PreviewError("RIS 最后一条记录缺少 ER")
    if not rows:
        raise PreviewError("RIS 没有完整记录，不能推断检索结果为零")
    return rows, None, warnings


def pubmed_provenance(payload, args, total, returned):
    provenance = {}
    modern = payload.get("producer") == "oh-my-paper/pubmed-search"
    if modern and "retrieval_complete" not in payload:
        raise PreviewError("新版 PubMed 输出缺少完整性字段")
    if "retrieval_complete" in payload:
        complete = payload["retrieval_complete"]
        if type(complete) is not bool or payload.get("status") not in ("complete", "partial"):
            raise PreviewError("PubMed 完整性字段无效")
        if complete != (payload["status"] == "complete"):
            raise PreviewError("PubMed 状态与完整性声明矛盾")
        for key in ("incomplete_reasons", "missing_metadata_pmids", "missing_abstract_pmids", "errors"):
            values = payload.get(key, [])
            if not isinstance(values, list) or (complete and values):
                raise PreviewError("PubMed 完整性声明与缺项或错误矛盾")
        if complete and total != returned:
            raise PreviewError("PubMed 声称完整，但数量不一致")
        if args.complete and not complete:
            raise PreviewError("PubMed 尚未完整取回，不能用 --complete 提升为完整来源")
        provenance.update(retrieval_complete=complete, source_status=payload["status"],
                          incomplete_reasons=payload.get("incomplete_reasons", []),
                          missing_metadata_pmids=payload.get("missing_metadata_pmids", []),
                          missing_abstract_pmids=payload.get("missing_abstract_pmids", []))
    if modern and "executed_at" not in payload:
        raise PreviewError("新版 PubMed 输出缺少真实检索时间")
    if "executed_at" in payload:
        if timestamp(payload, "executed_at") != timestamp({"searched_at": args.searched_at}, "searched_at"):
            raise PreviewError("searched-at 必须与源文件 executed_at 一致，不能改成导入日期")
    if "query_parameters" in payload:
        parameters = payload["query_parameters"]
        if not isinstance(parameters, dict) or parameters.get("query") != args.query:
            raise PreviewError("PubMed 查询参数与检索式不一致")
        allowed = ("query", "mindate", "maxdate", "datetype", "sort", "abstracts", "all", "limit", "batch_size")
        provenance["query_parameters"] = {key: parameters[key] for key in allowed if key in parameters}
    if "query_translation" in payload:
        provenance["query_translation"] = text(payload["query_translation"], "query_translation", required=False)
    if "run_id" in payload:
        provenance["source_run_id"] = text(payload["run_id"], "run_id")
    if "requested_pmids" in payload:
        requested = payload["requested_pmids"]
        if not isinstance(requested, list) or not all(isinstance(value, str) for value in requested):
            raise PreviewError("PubMed 请求 PMID 清单无效")
        requested = [normalize_pmid(value) for value in requested]
        if any(not value for value in requested) or len(set(requested)) != len(requested):
            raise PreviewError("PubMed 请求 PMID 清单无效或重复")
        returned_ids = {normalize_pmid(item.get("pmid")) for item in payload["results"] if isinstance(item, dict)}
        if not returned_ids.issubset(requested) or (payload.get("retrieval_complete") is True and returned_ids != set(requested)):
            raise PreviewError("PubMed 结果与请求 PMID 清单不一致")
    return provenance


def load_rows(args):
    with Path(args.input).open(encoding="utf-8-sig", newline="") as handle:
        if args.format == "pubmed-json":
            payload = parse_json(handle.read(), args.input)
            if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
                raise PreviewError("PubMed JSON 必须包含 results 数组")
            total = count(payload.get("total_count"), "total_count")
            returned = count(payload.get("returned"), "returned")
            if returned != len(payload["results"]) or total < returned:
                raise PreviewError("PubMed 计数不一致，可能有题录丢失")
            if text(payload.get("query"), "query") != args.query:
                raise PreviewError("PubMed query 与实际检索式不一致")
            provenance = pubmed_provenance(payload, args, total, returned)
            rows = []
            for item in payload["results"]:
                if not isinstance(item, dict):
                    raise PreviewError("PubMed 每条题录必须是对象")
                pmid = normalize_pmid(text(item.get("pmid"), "pmid"))
                rows.append({**item, "pmid": pmid, "source_record_id": pmid})
            return rows, total, [], provenance
        if args.format == "ris":
            rows, total, warnings = read_ris(handle)
            return rows, total, warnings, {}
        reader = csv.DictReader(handle)
        headers = reader.fieldnames
        if not headers or len(headers) != len(set(headers)) or not {"source_record_id", "title"}.issubset(headers):
            raise PreviewError("CSV 必须有不重复的 source_record_id、title 列")
        rows = list(reader)
        if any(None in row or any(value is None for value in row.values()) for row in rows):
            raise PreviewError("CSV 行列数量不一致")
        return rows, None, [], {}


def preview(args):
    for field in ("review_id", "search_run_id", "source", "query"):
        setattr(args, field, text(getattr(args, field), field))
    timestamp({"searched_at": args.searched_at}, "searched_at")
    rows, total, warnings, provenance = load_rows(args)
    if total is not None and args.identified_count is not None and total != args.identified_count:
        raise PreviewError("identified_count 与 PubMed total_count 不一致")
    if args.identified_count is not None and args.identified_count < len(rows):
        raise PreviewError("identified_count 不能为负数或小于实际取回数")
    if args.complete and (args.identified_count is None or args.identified_count != len(rows)):
        raise PreviewError("complete 必须提供与实际取回数相同的 identified_count")
    records, reports = [], []
    by_identifier = {}
    report_map = {}
    if args.existing_reports:
        lines = Path(args.existing_reports).read_text(encoding="utf-8-sig").splitlines()
        existing = index_rows([parse_json(line, f"existing-reports:{number}")
                               for number, line in enumerate(lines, 1) if line.strip()], "report_id")
        for report_id, saved in existing.items():
            text(saved.get("title"), "既有报告 title")
            if text(saved.get("retrieval_status"), "retrieval_status") not in RETRIEVAL_STATUSES:
                raise PreviewError("既有报告的 retrieval_status 无效")
            identity = identifiers(saved)
            report_map[report_id] = {**{k: v for k, v in saved.items() if k not in ("doi", "pmid")}, **identity}
            for key, value in identity.items():
                if (key, value) in by_identifier:
                    raise PreviewError("既有报告中同一标识对应多个 report_id，须人工核查")
                by_identifier[(key, value)] = report_id
    else:
        existing = {}
    source_ids = set()
    for row in rows:
        source_id = text(row.get("source_record_id"), "source_record_id")
        title = text(row.get("title"), "title")
        if source_id in source_ids:
            raise PreviewError("同一批次的 source_record_id 重复，不能静默丢弃")
        source_ids.add(source_id)
        identity = identifiers(row)
        matches = {by_identifier[(key, value)] for key, value in identity.items() if (key, value) in by_identifier}
        seed = sorted(identity.items())[:1] or [(args.source, source_id)]
        generated_id = stable_id("report", args.review_id, seed)
        if not identity and generated_id in report_map:
            matches.add(generated_id)
        if len(matches) > 1:
            raise PreviewError("DOI 与 PMID 指向不同报告，须人工核查")
        if matches:
            report_id = matches.pop()
            report = report_map[report_id]
            if any(report.get(key) and report[key] != value for key, value in identity.items()):
                raise PreviewError("报告标识冲突，不能自动归并")
            if report_id in existing and any(not report.get(key) for key in identity):
                warnings.append(f"既有报告 {report_id} 有新增标识，须人工核查补入；预览不会覆盖原报告")
            report.update(identity)
            if report["title"] != title:
                warnings.append(f"{source_id} 的标识相同但标题不同，请核查报告 {report_id}")
        else:
            report_id = generated_id
            report = {"schema_version": 1, "report_id": report_id, "title": title,
                      "retrieval_status": "not_requested", **identity}
            reports.append(report)
            report_map[report_id] = report
        for key, value in identity.items():
            by_identifier[(key, value)] = report_id
        records.append({"schema_version": 1, "record_id": stable_id("record", args.review_id, args.search_run_id, args.source, source_id),
                        "search_run_id": args.search_run_id, "source_record_id": source_id, "report_id": report_id})
    run = {"schema_version": 1, "search_run_id": args.search_run_id, "source": args.source,
           "source_type": args.source_type, "query": args.query, "searched_at": args.searched_at,
           "status": "complete" if args.complete else "partial",
           "identified_count": args.identified_count if args.identified_count is not None else total,
           "retrieved_count": len(rows), **provenance}
    if run["identified_count"] is None:
        warnings.append("命中总数未知；取回数不能作为完整检索的总数")
    if run["status"] == "partial":
        warnings.append("本次仅为部分检索记录预览，不能据此标记正式检索完成")
    return {"schema_version": 1, "search_run": run, "records": records, "reports": reports, "warnings": warnings}


def main():
    try:
        args = parser().parse_args()
        result = preview(args)
    except (ValueError, OSError, csv.Error) as exc:
        print(json.dumps({"schema_version": 1, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
