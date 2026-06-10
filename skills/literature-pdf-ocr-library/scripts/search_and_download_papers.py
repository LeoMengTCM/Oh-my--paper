#!/usr/bin/env python3
"""Search traceable papers, judge open access, and optionally download open PDFs.

Three input modes (mutually exclusive):
  --query      Full-text search across configured sources.
  --queries    Several expanded queries (synonyms / sub-concepts) merged + deduped.
               The prompt layer decides the expansions; this just runs + merges them.
  --arxiv-ids  Resolve specific arXiv IDs via the arXiv API, confirm metadata, then download.

Two passes (the "filter before you dig" strategy):
  1. --summary-only : search + open-access judgement + ranking, write a lightweight
                       screening table (survey_screening.md). No download. Let the
                       user pick the core papers first.
  2. --download-pdfs: download only the selected papers whose full_text_status is
                      open_pdf, then OCR them downstream.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Dict, List, Optional

from literature_lib import (
    discover_records,
    download_pdf,
    enrich_open_access,
    ensure_dir,
    fetch_arxiv_by_ids,
    merge_query_results,
    NotPdfError,
    rank_records,
    slugify,
    write_json,
)

SOURCE_CHOICES = ["arxiv", "semanticscholar", "openalex", "crossref", "pwc", "hf_daily"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--query", help="Free-text search query.")
    mode.add_argument("--queries", nargs="+", metavar="Q", help="Several expanded queries; merged + deduped.")
    mode.add_argument(
        "--arxiv-ids",
        nargs="+",
        metavar="ID",
        help="One or more arXiv IDs (e.g. 2502.13817) to resolve via arXiv API and download.",
    )
    parser.add_argument("--out-dir", required=True, help="Output directory.")
    parser.add_argument("--limit", type=int, default=10, help="Final number of unique records (search modes).")
    parser.add_argument("--sources", nargs="+", default=["arxiv", "semanticscholar", "openalex"], choices=SOURCE_CHOICES)
    parser.add_argument("--download-pdfs", action="store_true", help="Download open-access PDFs when available.")
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="First pass: search + OA judgement + ranking, write screening table, do NOT download.",
    )
    parser.add_argument("--openalex-mailto", default=os.environ.get("OPENALEX_MAILTO"), help="mailto for OpenAlex/Crossref.")
    parser.add_argument(
        "--unpaywall-email",
        default=os.environ.get("UNPAYWALL_EMAIL") or os.environ.get("OPENALEX_MAILTO"),
        help="Contact email for Unpaywall (required by their API).",
    )
    parser.add_argument("--sort", choices=["relevance", "recent"], default="relevance", help="Per-source sort hint.")
    parser.add_argument("--min-year", type=int, default=None, help="Keep only records with year >= min-year.")
    parser.add_argument("--no-rank", action="store_true", help="Disable recency+citation ranking.")
    parser.add_argument("--no-enrich-oa", action="store_true", help="Disable the open-access fallback chain.")
    return parser.parse_args()


def render_screening_table(records: List[Dict], *, queries: str, sources: List[str]) -> str:
    lines = [
        "# 文献筛选表（先筛后深 · 第一遍）",
        "",
        f"- 检索式：{queries}",
        f"- 数据源：{', '.join(sources)}",
        f"- 命中：{len(records)} 篇（按时效 [new] 置顶 + 引用数降序）",
        "",
        "| # | 标题 | 年 | Venue | 引用 | 新 | 全文 | 代码 | ID |",
        "|---|------|----|-------|------|----|------|------|----|",
    ]
    for index, record in enumerate(records, start=1):
        title = (record.get("title") or "").replace("|", " ").replace("\n", " ").strip()
        if len(title) > 70:
            title = title[:67] + "…"
        year = record.get("year") or ""
        venue = (record.get("venue") or "").replace("|", " ").strip()[:24]
        citations = record.get("citation_count")
        citations = str(citations) if isinstance(citations, int) else "—"
        is_new = "[new]" if record.get("is_new") else ""
        full_text = record.get("full_text_status") or "—"
        code = "✓" if record.get("code_url") else ""
        ident = record.get("arxiv_id") or record.get("doi") or ""
        lines.append(
            f"| {index} | {title} | {year} | {venue} | {citations} | {is_new} | {full_text} | {code} | {ident} |"
        )
    lines += [
        "",
        "下一步：从上表选出要深读 / 下载的核心论文（建议 5-10 篇），把它们的 arXiv ID 或 DOI 交给第二遍下载 + OCR。",
        "只有 `full_text_status=open_pdf` 的论文会被下载；其余仅保留元数据。",
        "",
    ]
    return "\n".join(lines) + "\n"


def _legacy_pdf_status(download_status: str) -> str:
    """Map the new download_status onto the legacy pdf_status field that
    build_library_index.py still reads (backward compatibility)."""
    return {
        "downloaded": "downloaded",
        "skipped": "unavailable",
        "not_pdf": "unavailable",
        "failed": "failed",
        "not_requested": "not_requested",
        "eligible": "not_requested",
    }.get(download_status, download_status)


def main() -> int:
    args = parse_args()
    out_dir = Path(args.out_dir).expanduser().resolve()
    papers_dir = out_dir / "papers"
    ensure_dir(papers_dir)

    do_enrich = not args.no_enrich_oa
    do_rank = not args.no_rank
    queries_label = args.query or (" / ".join(args.queries) if args.queries else ",".join(args.arxiv_ids or []))

    if args.arxiv_ids:
        try:
            records = fetch_arxiv_by_ids(args.arxiv_ids)
        except Exception as exc:  # noqa: BLE001 — a network/HTTP blip shouldn't traceback
            print(json.dumps({"error": f"arxiv metadata fetch failed: {exc}"}, ensure_ascii=False))
            return 1
        source_errors: Dict[str, str] = {}
        if do_enrich:
            for record in records:
                enrich_open_access(record, mailto=args.openalex_mailto, email=args.unpaywall_email)
        if do_rank:
            records = rank_records(records)
    elif args.queries:
        records, source_errors = merge_query_results(
            queries=args.queries,
            limit=args.limit,
            sources=args.sources,
            openalex_mailto=args.openalex_mailto,
            sort=args.sort,
            min_year=args.min_year,
            enrich_oa=do_enrich,
            unpaywall_email=args.unpaywall_email,
            do_rank=do_rank,
        )
    else:
        records, source_errors = discover_records(
            query=args.query,
            limit=args.limit,
            sources=args.sources,
            openalex_mailto=args.openalex_mailto,
            sort=args.sort,
            min_year=args.min_year,
            enrich_oa=do_enrich,
            unpaywall_email=args.unpaywall_email,
            do_rank=do_rank,
        )

    download_requested = args.download_pdfs and not args.summary_only

    saved = []
    for index, record in enumerate(records, start=1):
        arxiv_id = record.get("arxiv_id") or ""
        title_slug = slugify(f"{record.get('year') or 'na'}-{record.get('title') or index}")
        paper_slug = slugify(f"{arxiv_id}-{title_slug}") if arxiv_id else title_slug
        paper_dir = papers_dir / paper_slug
        ensure_dir(paper_dir)

        local_pdf_path: Optional[Path] = None
        download_status = "not_requested"
        download_error = None
        full_text_status = record.get("full_text_status")
        pdf_url = record.get("pdf_url")

        if download_requested:
            if full_text_status == "open_pdf" and pdf_url:
                local_pdf_path = paper_dir / "paper.pdf"
                try:
                    download_pdf(pdf_url, local_pdf_path)
                    download_status = "downloaded"
                except NotPdfError as exc:
                    download_status = "not_pdf"
                    download_error = str(exc)
                    full_text_status = "html_not_pdf"
                    local_pdf_path = None
                except Exception as exc:  # noqa: BLE001
                    download_status = "failed"
                    download_error = str(exc)
                    local_pdf_path = None
            else:
                download_status = "skipped"
                download_error = f"full_text_status={full_text_status or 'unknown'}"

        paper_record = {
            **record,
            "rank": index,
            "paper_slug": paper_slug,
            "full_text_status": full_text_status,
            "local_pdf_path": str(local_pdf_path) if local_pdf_path else None,
            "download_status": download_status,
            "download_error": download_error,
            "pdf_status": _legacy_pdf_status(download_status),
        }
        write_json(paper_dir / "metadata.json", paper_record)
        saved.append(paper_record)

    screening_path = out_dir / "survey_screening.md"
    screening_path.write_text(
        render_screening_table(saved, queries=queries_label, sources=args.sources),
        encoding="utf-8",
    )

    write_json(
        out_dir / "search_results.json",
        {
            "mode": "arxiv_ids" if args.arxiv_ids else ("queries" if args.queries else "query"),
            "query": args.query,
            "queries": args.queries,
            "arxiv_ids": args.arxiv_ids,
            "limit": args.limit,
            "sources": ["arxiv"] if args.arxiv_ids else args.sources,
            "sort": args.sort,
            "min_year": args.min_year,
            "summary_only": args.summary_only,
            "enriched_oa": do_enrich,
            "ranked": do_rank,
            "source_errors": source_errors,
            "records": saved,
        },
    )

    counts = {"downloaded": 0, "skipped": 0, "failed": 0, "not_pdf": 0, "not_requested": 0}
    for record in saved:
        counts[record["download_status"]] = counts.get(record["download_status"], 0) + 1
    print(
        json.dumps(
            {
                "saved_records": len(saved),
                "screening_table": str(screening_path),
                "downloads": counts,
                "out_dir": str(out_dir),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
