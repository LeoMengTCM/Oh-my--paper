"""基于固定 PMID 快照分批取回；不把已知缺项当作完整检索。"""
from pubmed_api import EutilsClient, RetrievalError, UID_LIMIT, now, valid_pmid
from pubmed_checkpoint import Checkpoint, require, validate_time


def request_spec(args):
    return {"query": args.query, "mindate": args.mindate, "maxdate": args.maxdate,
            "datetype": args.datetype, "sort": args.sort, "abstracts": args.abstracts,
            "all": args.all, "limit": UID_LIMIT if args.all else args.retmax, "batch_size": args.batch_size}


def validate_snapshot(search, limit):
    require(isinstance(search, dict), "搜索快照格式无效")
    total, pmids = search.get("total_count"), search.get("pmids")
    require(type(total) is int and total >= 0, "搜索快照命中数无效")
    require(isinstance(pmids, list) and all(valid_pmid(value) for value in pmids) and len(pmids) == len(set(pmids)),
            "搜索快照 PMID 无效或重复")
    require(len(pmids) <= min(total, limit), "搜索快照 PMID 数量错误")
    require(type(search.get("uid_snapshot_complete")) is bool and
            search["uid_snapshot_complete"] == (len(pmids) == min(total, limit)), "搜索快照完整性标记错误")
    validate_time(search.get("executed_at"))
    require(isinstance(search.get("query_translation"), str), "搜索快照缺少检索转换")
    raw = search.get("raw_response")
    require(isinstance(raw, dict) and isinstance(raw.get("esearchresult"), dict), "搜索快照缺少原始 ESearch 响应")
    original = raw["esearchresult"]
    raw_count = original.get("count")
    require((type(raw_count) is int and raw_count >= 0) or
            (isinstance(raw_count, str) and raw_count.isascii() and raw_count.isdigit()), "原始 ESearch 计数无效")
    require(original.get("idlist") == pmids and int(raw_count) == total, "搜索快照与原始 PMID/计数不一致")
    require(original.get("querytranslation", "") == search["query_translation"], "搜索快照与原始检索转换不一致")


def retrieve(args):
    spec = request_spec(args)
    client = EutilsClient(args)
    errors = []
    reasons = []
    summaries, abstracts = {}, {}
    with Checkpoint(args.checkpoint, spec, args.resume) as store:
        search = store.state["search"]
        if search is not None:
            validate_snapshot(search, spec["limit"])
        try:
            if search is None or not search["uid_snapshot_complete"]:
                search = client.search(spec["limit"])
                store.state["search"] = search
                store.state["search_attempts"].append({"executed_at": search["executed_at"],
                                                       "total_count": search["total_count"], "selected": len(search["pmids"])})
                store.save_state()
        except RetrievalError as error:
            errors.append({"code": error.code, "message": str(error)})
            reasons.append("search_failed")
            search = None
        except KeyboardInterrupt:
            errors.append({"code": "interrupted", "message": "检索已中断，可用相同参数恢复"})
            reasons.append("interrupted")
            search = None

        if search is not None:
            if args.all and search["total_count"] > UID_LIMIT:
                reasons.append("uid_limit")
                errors.append({"code": "uid_limit", "message": f"超过本实现支持的 {UID_LIMIT} 个 UID 上限；请使用完整导出或人工审核的拆分，不标记完整检索"})
            elif not search["uid_snapshot_complete"]:
                reasons.append("uid_snapshot_incomplete")
            else:
                batches = [(offset, store.load_batch(offset, search["pmids"][offset:offset + args.batch_size]))
                           for offset in range(0, len(search["pmids"]), args.batch_size)]
                # 先读取全部缓存；即使中途失败，也保留以前已经完成的后续批次。
                for _, batch in batches:
                    summaries.update(batch["summaries"])
                    abstracts.update(batch["abstracts"])
                for offset, batch in batches:
                    try:
                        pending = [pmid for pmid in batch["pmids"] if pmid not in batch["summaries"]]
                        if pending:
                            values, original = client.summaries(pending)
                            batch["summaries"].update(values)
                            batch["responses"].append({"kind": "summary", "requested_pmids": pending,
                                                        "received_at": now(), "records": original})
                            store.save_batch(offset, batch)
                            summaries.update(values)
                        pending = [pmid for pmid in batch["pmids"] if pmid not in batch["abstracts"]]
                        if args.abstracts and pending:
                            values, original = client.abstracts(pending)
                            batch["abstracts"].update(values)
                            batch["responses"].append({"kind": "abstracts", "requested_pmids": pending,
                                                        "received_at": now(), "xml": original})
                            store.save_batch(offset, batch)
                            abstracts.update(values)
                    except RetrievalError as error:
                        errors.append({"code": error.code, "message": str(error)})
                        reasons.append("request_failed")
                        break
                    except KeyboardInterrupt:
                        errors.append({"code": "interrupted", "message": "取回已中断，成功批次已保存"})
                        reasons.append("interrupted")
                        break

        pmids = search["pmids"] if search else []
        total = search["total_count"] if search else None
        missing_metadata = [pmid for pmid in pmids if pmid not in summaries]
        missing_abstracts = [pmid for pmid in pmids if pmid not in abstracts] if args.abstracts else []
        if missing_metadata:
            reasons.append("metadata_missing")
        if missing_abstracts:
            reasons.append("abstract_records_missing")
        if not args.all and total is not None and total > len(pmids):
            reasons.append("bounded_search")
        records = []
        for pmid in pmids:
            if pmid in summaries:
                record = dict(summaries[pmid])
                if args.abstracts:
                    record.update(abstracts.get(pmid, {"abstract_status": "missing_record"}))
                records.append(record)
        complete = search is not None and not reasons
        payload = {"schema_version": 1, "producer": "oh-my-paper/pubmed-search", "run_id": store.state["run_id"],
                   "query": args.query, "query_parameters": spec, "query_translation": search["query_translation"] if search else None,
                   "executed_at": search["executed_at"] if search else store.state["started_at"], "updated_at": now(),
                   "total_count": total, "returned": len(records), "results": records, "requested_pmids": pmids,
                   "missing_metadata_pmids": missing_metadata, "missing_abstract_pmids": missing_abstracts,
                   "retrieval_complete": complete, "status": "complete" if complete else "partial",
                   "incomplete_reasons": list(dict.fromkeys(reasons)), "errors": errors,
                   "search_warnings": search["raw_response"].get("esearchresult", {}).get("warninglist", {}) if search else {}}
        return payload, 2 if any(reason != "bounded_search" for reason in reasons) else 0
