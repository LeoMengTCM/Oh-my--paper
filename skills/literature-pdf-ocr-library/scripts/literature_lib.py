#!/usr/bin/env python3
"""Shared helpers for the literature PDF OCR library skill.

Search traceable papers across multiple academic sources, judge open-access
(OA) availability, rank by recency + citations, and download only legally
accessible PDFs.

Sources: arXiv, Semantic Scholar, OpenAlex, Crossref, Papers with Code,
Hugging Face daily papers. Open-access fallback chain for full-text status:
arXiv direct link -> S2 openAccessPdf -> OpenAlex best_oa_location -> Unpaywall.

Google Scholar / CNKI are intentionally NOT here — they have no API and need a
browser (CDP); see scripts/cdp-proxy.mjs + references/site-patterns/.
"""

from __future__ import annotations

import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from datetime import date, datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import requests

USER_AGENT = "Codex literature-pdf-ocr-library/1.1"
TIMEOUT = 45
# A paper counts as "new" (pinned to the top of the screening table) when it
# was published within this many days — recency-first ranking, since
# cutting-edge work naturally has low citation counts.
RECENT_DAYS = 183
ARXIV_ATOM_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
}
PDF_EXTENSIONS = {".pdf"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}

# full_text_status enum (see references/metadata-schema.md):
#   open_pdf | needs_institution | no_open_pdf | anti_bot_blocked | html_not_pdf | unknown
# download_status enum:
#   not_requested | eligible | downloaded | skipped | failed | not_pdf


class NotPdfError(Exception):
    """Raised when a downloaded resource is not a PDF (e.g. an HTML full-text page)."""


def slugify(text: str, limit: int = 80) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-{2,}", "-", text).strip("-")
    return text[:limit] or "paper"


def normalize_title(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip().lower()


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, data: object) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: Iterable[Dict]) -> None:
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def safe_request(
    url: str,
    *,
    params: Optional[Dict] = None,
    headers: Optional[Dict] = None,
    timeout: int = TIMEOUT,
) -> requests.Response:
    merged_headers = {"User-Agent": USER_AGENT}
    if headers:
        merged_headers.update(headers)
    response = requests.get(url, params=params, headers=merged_headers, timeout=timeout)
    response.raise_for_status()
    return response


def choose_best_pdf_url(record: Dict) -> Optional[str]:
    candidates = [
        record.get("pdf_url"),
        record.get("open_access_pdf_url"),
        record.get("oa_url"),
        record.get("primary_pdf_url"),
    ]
    for url in candidates:
        if isinstance(url, str) and url.strip():
            return url.strip()
    return None


def _coalesce_citation(existing: Optional[int], incoming: Optional[int]) -> Optional[int]:
    values = [value for value in (existing, incoming) if isinstance(value, int)]
    return max(values) if values else (existing if existing is not None else incoming)


def dedupe_records(records: List[Dict], limit: Optional[int] = None) -> List[Dict]:
    source_priority = {
        "arxiv": 0,
        "semanticscholar": 1,
        "openalex": 2,
        "crossref": 3,
        "hf_daily": 4,
        "pwc": 5,
    }
    chosen: Dict[str, Dict] = {}

    def key_for(record: Dict) -> str:
        for field in ("doi", "arxiv_id"):
            value = record.get(field)
            if value:
                return f"{field}:{str(value).lower()}"
        return f"title:{normalize_title(record.get('title', ''))}"

    ordered = sorted(records, key=lambda row: source_priority.get(row.get("source", ""), 99))
    for record in ordered:
        key = key_for(record)
        if key not in chosen:
            chosen[key] = dict(record)
            continue
        existing = chosen[key]
        # Fill missing fields from a duplicate hit on another source.
        for field in (
            "abstract",
            "pdf_url",
            "landing_page",
            "open_access_pdf_url",
            "oa_url",
            "primary_pdf_url",
            "doi",
            "arxiv_id",
            "venue",
            "year",
            "published",
            "publication_date",
            "publication_type",
            "code_url",
            "open_access_status",
            "full_text_status",
        ):
            if not existing.get(field) and record.get(field):
                existing[field] = record[field]
        # Citation count: keep the larger of the two (sources disagree; higher
        # usually means broader coverage).
        existing["citation_count"] = _coalesce_citation(
            existing.get("citation_count"), record.get("citation_count")
        )
        merged_sources = list(
            dict.fromkeys(existing.get("merged_sources", [existing.get("source")]) + [record.get("source")])
        )
        existing["merged_sources"] = [item for item in merged_sources if item]
        existing["pdf_url"] = choose_best_pdf_url(existing)

    results = list(chosen.values())
    if limit is not None:
        return results[:limit]
    return results


def _text(node: Optional[ET.Element]) -> str:
    return node.text.strip() if node is not None and node.text else ""


def _parse_arxiv_id(entry_id: str) -> str:
    value = entry_id.rsplit("/", 1)[-1]
    return value.replace("v", "v") if value else ""


def _arxiv_pdf_url(entry_id: str) -> str:
    arxiv_id = entry_id.rsplit("/", 1)[-1]
    if arxiv_id.endswith(".pdf"):
        return f"https://arxiv.org/pdf/{arxiv_id}"
    return f"https://arxiv.org/pdf/{arxiv_id}.pdf"


def arxiv_pdf_url_from_id(arxiv_id: str) -> str:
    """Direct PDF link from a bare or versioned arXiv id (e.g. ``2502.13817``)."""
    arxiv_id = (arxiv_id or "").strip()
    if not arxiv_id:
        return ""
    if arxiv_id.endswith(".pdf"):
        return f"https://arxiv.org/pdf/{arxiv_id}"
    return f"https://arxiv.org/pdf/{arxiv_id}.pdf"


def search_arxiv(query: str, limit: int, sort: str = "relevance") -> List[Dict]:
    sort_by = "submittedDate" if sort == "recent" else "relevance"
    response = safe_request(
        "https://export.arxiv.org/api/query",
        params={
            "search_query": f"all:{query}",
            "start": 0,
            "max_results": limit,
            "sortBy": sort_by,
            "sortOrder": "descending",
        },
    )
    root = ET.fromstring(response.text)
    rows: List[Dict] = []
    for entry in root.findall("atom:entry", ARXIV_ATOM_NS):
        entry_id = _text(entry.find("atom:id", ARXIV_ATOM_NS))
        doi = _text(entry.find("arxiv:doi", ARXIV_ATOM_NS))
        published = _text(entry.find("atom:published", ARXIV_ATOM_NS))
        rows.append(
            {
                "source": "arxiv",
                "title": _text(entry.find("atom:title", ARXIV_ATOM_NS)),
                "authors": [_text(author.find("atom:name", ARXIV_ATOM_NS)) for author in entry.findall("atom:author", ARXIV_ATOM_NS)],
                "abstract": _text(entry.find("atom:summary", ARXIV_ATOM_NS)),
                "year": int(published[:4]) if published[:4].isdigit() else None,
                "published": published,
                "landing_page": entry_id.replace("http://", "https://"),
                "pdf_url": _arxiv_pdf_url(entry_id),
                "doi": doi or None,
                "arxiv_id": _parse_arxiv_id(entry_id),
                "venue": "arXiv",
            }
        )
    return rows


def fetch_arxiv_by_ids(arxiv_ids: List[str]) -> List[Dict]:
    """Fetch paper metadata from arXiv API for a specific list of arXiv IDs.

    Uses the arXiv export API with id_list to retrieve confirmed metadata (title,
    authors, abstract, year) before downloading.  IDs may be bare (``2502.13817``)
    or versioned (``2502.13817v2``).
    """
    id_list = ",".join(arxiv_ids)
    response = safe_request(
        "https://export.arxiv.org/api/query",
        params={"id_list": id_list, "max_results": len(arxiv_ids)},
    )
    root = ET.fromstring(response.text)
    rows: List[Dict] = []
    for entry in root.findall("atom:entry", ARXIV_ATOM_NS):
        entry_id = _text(entry.find("atom:id", ARXIV_ATOM_NS))
        doi = _text(entry.find("arxiv:doi", ARXIV_ATOM_NS))
        published = _text(entry.find("atom:published", ARXIV_ATOM_NS))
        rows.append(
            {
                "source": "arxiv",
                "title": _text(entry.find("atom:title", ARXIV_ATOM_NS)),
                "authors": [
                    _text(author.find("atom:name", ARXIV_ATOM_NS))
                    for author in entry.findall("atom:author", ARXIV_ATOM_NS)
                ],
                "abstract": _text(entry.find("atom:summary", ARXIV_ATOM_NS)),
                "year": int(published[:4]) if (published or "")[:4].isdigit() else None,
                "published": published,
                "landing_page": entry_id.replace("http://", "https://"),
                "pdf_url": _arxiv_pdf_url(entry_id),
                "doi": doi or None,
                "arxiv_id": _parse_arxiv_id(entry_id),
                "venue": "arXiv",
            }
        )
    return rows


def search_semanticscholar(query: str, limit: int, sort: str = "relevance") -> List[Dict]:
    # S2 search has no sort param (relevance only); honour `recent` by sorting
    # the returned rows by year locally. An API key (S2_API_KEY) lifts the very
    # low anonymous rate limit that otherwise triggers 429 within one session.
    headers: Dict[str, str] = {}
    api_key = os.environ.get("S2_API_KEY")
    if api_key:
        headers["x-api-key"] = api_key
    response = safe_request(
        "https://api.semanticscholar.org/graph/v1/paper/search",
        params={
            "query": query,
            "limit": limit,
            "fields": "title,year,authors,abstract,url,openAccessPdf,isOpenAccess,externalIds,venue,citationCount,publicationTypes,publicationDate",
        },
        headers=headers or None,
    )
    body = response.json()
    rows: List[Dict] = []
    for item in body.get("data", []):
        external_ids = item.get("externalIds") or {}
        open_pdf = item.get("openAccessPdf") or {}
        publication_types = item.get("publicationTypes") or []
        rows.append(
            {
                "source": "semanticscholar",
                "title": item.get("title"),
                "authors": [author.get("name") for author in item.get("authors", []) if author.get("name")],
                "abstract": item.get("abstract"),
                "year": item.get("year"),
                "publication_date": item.get("publicationDate"),
                "published": item.get("publicationDate"),
                "publication_type": publication_types[0].lower() if publication_types else None,
                "landing_page": item.get("url"),
                "pdf_url": open_pdf.get("url"),
                "open_access_pdf_url": open_pdf.get("url"),
                "doi": external_ids.get("DOI"),
                "arxiv_id": external_ids.get("ArXiv"),
                "venue": item.get("venue"),
                "citation_count": item.get("citationCount"),
                "is_open_access": item.get("isOpenAccess"),
            }
        )
    if sort == "recent":
        rows.sort(key=lambda row: row.get("year") or 0, reverse=True)
    return rows


def search_openalex(query: str, limit: int, mailto: Optional[str] = None, sort: str = "relevance") -> List[Dict]:
    params = {"search": query, "per-page": limit}
    if sort == "recent":
        params["sort"] = "publication_date:desc"
    headers: Dict[str, str] = {}
    if mailto:
        params["mailto"] = mailto
        headers["User-Agent"] = f"{USER_AGENT} ({mailto})"
    response = safe_request("https://api.openalex.org/works", params=params, headers=headers)
    body = response.json()
    rows: List[Dict] = []
    for item in body.get("results", []):
        primary_location = item.get("primary_location") or {}
        open_access = item.get("open_access") or {}
        ids = item.get("ids") or {}
        doi = item.get("doi") or ids.get("doi")
        if doi and doi.startswith("https://doi.org/"):
            doi = doi[len("https://doi.org/") :]
        rows.append(
            {
                "source": "openalex",
                "title": item.get("display_name") or item.get("title"),
                "authors": [author.get("author", {}).get("display_name") for author in item.get("authorships", []) if author.get("author", {}).get("display_name")],
                "abstract": None,
                "year": item.get("publication_year"),
                "publication_date": item.get("publication_date"),
                "published": item.get("publication_date"),
                "publication_type": item.get("type"),
                "landing_page": primary_location.get("landing_page_url") or item.get("id"),
                "pdf_url": primary_location.get("pdf_url") or open_access.get("oa_url"),
                "primary_pdf_url": primary_location.get("pdf_url"),
                "oa_url": open_access.get("oa_url"),
                "doi": doi,
                "arxiv_id": None,
                "venue": (primary_location.get("source") or {}).get("display_name"),
                "citation_count": item.get("cited_by_count"),
                "open_access_status": open_access.get("oa_status"),
                "is_open_access": open_access.get("is_oa"),
            }
        )
    return rows


def search_crossref(query: str, limit: int, mailto: Optional[str] = None, sort: str = "relevance") -> List[Dict]:
    """Cross-disciplinary DOI / venue / publication-type metadata.

    Crossref does not guarantee abstracts or PDFs; use it as authoritative
    bibliographic completion, not as a full-text source.
    """
    params: Dict[str, object] = {"query": query, "rows": limit}
    if mailto:
        params["mailto"] = mailto
    if sort == "recent":
        params["sort"] = "published"
        params["order"] = "desc"
    response = safe_request("https://api.crossref.org/works", params=params)
    items = (response.json().get("message") or {}).get("items", [])
    rows: List[Dict] = []
    for item in items:
        titles = item.get("title") or []
        authors = []
        for author in item.get("author", []) or []:
            name = " ".join(part for part in (author.get("given"), author.get("family")) if part)
            if name:
                authors.append(name)
        issued = (item.get("issued") or {}).get("date-parts") or [[None]]
        year = issued[0][0] if issued and issued[0] else None
        containers = item.get("container-title") or []
        rows.append(
            {
                "source": "crossref",
                "title": titles[0] if titles else None,
                "authors": authors,
                "abstract": None,
                "year": int(year) if isinstance(year, int) else None,
                "publication_type": item.get("type"),
                "landing_page": item.get("URL"),
                "pdf_url": None,
                "doi": item.get("DOI"),
                "arxiv_id": None,
                "venue": containers[0] if containers else None,
                "citation_count": item.get("is-referenced-by-count"),
                "issn": (item.get("ISSN") or [None])[0],
            }
        )
    return rows


def search_papers_with_code(query: str, limit: int, sort: str = "relevance") -> List[Dict]:
    """ML papers with linked code repositories (adds ``code_url``)."""
    del sort
    response = safe_request(
        "https://paperswithcode.com/api/v1/papers/",
        params={"q": query, "items_per_page": limit},
    )
    body = response.json()
    rows: List[Dict] = []
    for item in body.get("results", []):
        published = item.get("published")
        arxiv_id = item.get("arxiv_id")
        rows.append(
            {
                "source": "pwc",
                "title": item.get("title"),
                "authors": item.get("authors") or [],
                "abstract": item.get("abstract"),
                "year": int(str(published)[:4]) if str(published or "")[:4].isdigit() else None,
                "published": published,
                "landing_page": item.get("url_abs"),
                "pdf_url": item.get("url_pdf") or (arxiv_pdf_url_from_id(arxiv_id) if arxiv_id else None),
                "doi": item.get("doi"),
                "arxiv_id": arxiv_id,
                "venue": item.get("proceeding"),
                "code_url": item.get("url_abs"),
            }
        )
    return rows


def search_hf_daily_papers(query: str, limit: int, sort: str = "relevance") -> List[Dict]:
    del sort
    response = safe_request("https://huggingface.co/api/daily_papers")
    body = response.json()
    items = body if isinstance(body, list) else [body]
    terms = [term.lower() for term in re.findall(r"[a-zA-Z0-9_-]+", query) if term.strip()]
    rows: List[Dict] = []
    for item in items:
        paper = item.get("paper") or {}
        haystack = f"{paper.get('title', '')} {paper.get('summary', '')}".lower()
        if terms and not all(term in haystack for term in terms[:3]):
            continue
        paper_id = str(paper.get("id") or "").strip()
        pdf_url = f"https://arxiv.org/pdf/{paper_id}.pdf" if re.fullmatch(r"\d{4}\.\d{4,5}", paper_id) else None
        rows.append(
            {
                "source": "hf_daily",
                "title": paper.get("title"),
                "authors": [author.get("name") for author in paper.get("authors", []) if author.get("name")],
                "abstract": paper.get("summary"),
                "year": int(str(paper.get("publishedAt", ""))[:4]) if str(paper.get("publishedAt", ""))[:4].isdigit() else None,
                "published": paper.get("publishedAt"),
                "landing_page": f"https://huggingface.co/papers/{paper_id}" if paper_id else None,
                "pdf_url": pdf_url,
                "doi": None,
                "arxiv_id": paper_id if pdf_url else None,
                "venue": "Hugging Face daily papers",
            }
        )
        if len(rows) >= limit:
            break
    return rows


# ---------------------------------------------------------------------------
# Open-access full-text resolution
# ---------------------------------------------------------------------------


def fetch_openalex_oa_by_doi(doi: str, *, mailto: Optional[str] = None) -> Dict:
    params = {"filter": f"doi:{doi}", "select": "id,open_access,best_oa_location"}
    if mailto:
        params["mailto"] = mailto
    response = safe_request("https://api.openalex.org/works", params=params)
    results = response.json().get("results", [])
    if not results:
        return {}
    item = results[0]
    open_access = item.get("open_access") or {}
    best = item.get("best_oa_location") or {}
    return {
        "is_oa": open_access.get("is_oa"),
        "oa_status": open_access.get("oa_status"),
        "pdf_url": best.get("pdf_url"),
    }


def fetch_unpaywall(doi: str, *, email: Optional[str] = None) -> Dict:
    # Unpaywall requires a contactable email; never bypasses paywalls.
    email = email or "research@example.org"
    response = safe_request(f"https://api.unpaywall.org/v2/{doi}", params={"email": email})
    body = response.json()
    best = body.get("best_oa_location") or {}
    return {
        "is_oa": body.get("is_oa"),
        "oa_status": body.get("oa_status"),
        "pdf_url": best.get("url_for_pdf"),
        "license": best.get("license"),
    }


def enrich_open_access(
    record: Dict,
    *,
    mailto: Optional[str] = None,
    email: Optional[str] = None,
) -> Dict:
    """Resolve ``full_text_status`` + best ``pdf_url`` via the OA fallback chain.

    arXiv direct link -> S2 openAccessPdf -> OpenAlex best_oa_location ->
    Unpaywall. Network failures degrade gracefully to ``unknown`` rather than
    raising. Only flags legally open full text; never bypasses paywalls.
    """
    # 1. arXiv direct link (S2's openAccessPdf is often null even when the
    #    arXiv PDF is actually available, so prefer the constructed link).
    if record.get("arxiv_id"):
        record["pdf_url"] = arxiv_pdf_url_from_id(record["arxiv_id"])
        record["full_text_status"] = "open_pdf"
        record["download_source"] = "arxiv"
        return record
    # 2. Semantic Scholar openAccessPdf
    if record.get("open_access_pdf_url"):
        record["pdf_url"] = record["open_access_pdf_url"]
        record["full_text_status"] = "open_pdf"
        record["download_source"] = "semantic_scholar"
        return record

    doi = record.get("doi")
    if not doi:
        if record.get("pdf_url"):
            record["full_text_status"] = "open_pdf"
            record.setdefault("download_source", record.get("source"))
        else:
            record["full_text_status"] = "unknown"
        return record

    # 3. OpenAlex OA location
    try:
        openalex = fetch_openalex_oa_by_doi(doi, mailto=mailto)
        if openalex.get("oa_status") and not record.get("open_access_status"):
            record["open_access_status"] = openalex.get("oa_status")
        if openalex.get("pdf_url"):
            record["pdf_url"] = openalex["pdf_url"]
            record["full_text_status"] = "open_pdf"
            record["download_source"] = "openalex"
            return record
        if openalex.get("is_oa") is False:
            record["full_text_status"] = "no_open_pdf"
    except Exception as exc:  # noqa: BLE001 — degrade gracefully
        print(f"[warn] openalex OA lookup failed for {doi}: {exc}", file=sys.stderr)

    # 4. Unpaywall
    try:
        unpaywall = fetch_unpaywall(doi, email=email or mailto)
        if unpaywall.get("oa_status") and not record.get("open_access_status"):
            record["open_access_status"] = unpaywall.get("oa_status")
        if unpaywall.get("pdf_url"):
            record["pdf_url"] = unpaywall["pdf_url"]
            record["full_text_status"] = "open_pdf"
            record["download_source"] = "unpaywall"
            record.setdefault("license", unpaywall.get("license"))
            return record
        if unpaywall.get("is_oa") is False:
            record["full_text_status"] = "no_open_pdf"
    except Exception as exc:  # noqa: BLE001 — degrade gracefully
        print(f"[warn] unpaywall lookup failed for {doi}: {exc}", file=sys.stderr)

    # 5. Nothing open found.
    if record.get("full_text_status") != "no_open_pdf":
        record["full_text_status"] = "needs_institution" if record.get("landing_page") else "unknown"
    return record


# ---------------------------------------------------------------------------
# Ranking
# ---------------------------------------------------------------------------


def _published_date(record: Dict) -> Optional[date]:
    raw = record.get("published") or record.get("publication_date")
    if raw:
        try:
            return datetime.fromisoformat(str(raw).replace("Z", "+00:00")).date()
        except ValueError:
            if str(raw)[:4].isdigit():
                return date(int(str(raw)[:4]), 1, 1)
    year = record.get("year")
    if isinstance(year, int):
        return date(year, 1, 1)
    return None


def rank_records(records: List[Dict]) -> List[Dict]:
    """Recency-first ranking: papers from the last RECENT_DAYS pinned to the
    top (marked ``is_new``), then citation count descending within each group.
    """
    today = date.today()
    for record in records:
        published = _published_date(record)
        record["is_new"] = bool(published and 0 <= (today - published).days <= RECENT_DAYS)

    def sort_key(record: Dict) -> Tuple[int, int]:
        citations = record.get("citation_count") or 0
        return (0 if record.get("is_new") else 1, -citations)

    return sorted(records, key=sort_key)


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def discover_records(
    query: str,
    limit: int,
    sources: List[str],
    openalex_mailto: Optional[str] = None,
    sort: str = "relevance",
    min_year: Optional[int] = None,
    enrich_oa: bool = False,
    unpaywall_email: Optional[str] = None,
    do_rank: bool = False,
) -> Tuple[List[Dict], Dict[str, str]]:
    rows: List[Dict] = []
    errors: Dict[str, str] = {}
    for source in sources:
        try:
            if source == "arxiv":
                rows.extend(search_arxiv(query, limit, sort=sort))
            elif source == "semanticscholar":
                rows.extend(search_semanticscholar(query, limit, sort=sort))
            elif source == "openalex":
                rows.extend(search_openalex(query, limit, mailto=openalex_mailto, sort=sort))
            elif source == "crossref":
                rows.extend(search_crossref(query, limit, mailto=openalex_mailto, sort=sort))
            elif source == "pwc":
                rows.extend(search_papers_with_code(query, limit, sort=sort))
            elif source == "hf_daily":
                rows.extend(search_hf_daily_papers(query, limit, sort=sort))
            else:
                raise ValueError(f"Unsupported source: {source}")
        except Exception as exc:  # noqa: BLE001
            errors[source] = str(exc)
            print(f"[warn] source failed: {source}: {exc}", file=sys.stderr)

    if min_year is not None:
        rows = [row for row in rows if row.get("year") is None or int(row["year"]) >= min_year]

    deduped = dedupe_records(rows, limit=None)
    for record in deduped:
        record["pdf_url"] = choose_best_pdf_url(record)

    if do_rank:
        deduped = rank_records(deduped)
    if limit:
        deduped = deduped[:limit]

    # Enrich OA status only on the final (post-rank, truncated) set to keep the
    # number of extra network calls bounded.
    if enrich_oa:
        for record in deduped:
            enrich_open_access(record, mailto=openalex_mailto, email=unpaywall_email)

    return deduped, errors


def merge_query_results(
    queries: List[str],
    limit: int,
    sources: List[str],
    openalex_mailto: Optional[str] = None,
    sort: str = "relevance",
    min_year: Optional[int] = None,
    enrich_oa: bool = False,
    unpaywall_email: Optional[str] = None,
    do_rank: bool = False,
) -> Tuple[List[Dict], Dict[str, str]]:
    """Run several expanded queries, then dedupe + rank + enrich the union once.

    Query expansion (synonyms, sub-concepts, abbreviation/full-name pairs) is
    decided by the LLM prompt layer; this just executes the list and merges.
    """
    pooled: List[Dict] = []
    errors: Dict[str, str] = {}
    for query in queries:
        # Per-query: search + dedupe, but defer OA-enrich and ranking to the union.
        records, query_errors = discover_records(
            query=query,
            limit=limit,
            sources=sources,
            openalex_mailto=openalex_mailto,
            sort=sort,
            min_year=min_year,
            enrich_oa=False,
            do_rank=False,
        )
        pooled.extend(records)
        for source, message in query_errors.items():
            errors.setdefault(f"{source} ({query})", message)

    deduped = dedupe_records(pooled, limit=None)
    for record in deduped:
        record["pdf_url"] = choose_best_pdf_url(record)
    if do_rank:
        deduped = rank_records(deduped)
    if limit:
        deduped = deduped[:limit]
    if enrich_oa:
        for record in deduped:
            enrich_open_access(record, mailto=openalex_mailto, email=unpaywall_email)
    return deduped, errors


def download_pdf(url: str, destination: Path) -> str:
    """Download a PDF and verify it is really a PDF.

    Returns the response Content-Type. Raises :class:`NotPdfError` when the
    bytes are not a PDF (e.g. an HTML full-text landing page), after removing
    the partial file, so callers can record ``not_pdf`` / ``html_not_pdf``.
    """
    ensure_dir(destination.parent)
    first_bytes = b""
    with requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT, stream=True) as response:
        response.raise_for_status()
        content_type = (response.headers.get("Content-Type") or "").lower()
        with destination.open("wb") as fh:
            for chunk in response.iter_content(chunk_size=1024 * 64):
                if chunk:
                    if not first_bytes:
                        first_bytes = chunk[:5]
                    fh.write(chunk)
    if not first_bytes.startswith(b"%PDF") and "pdf" not in content_type:
        try:
            destination.unlink()
        except OSError:
            pass
        raise NotPdfError(f"content is not a PDF (content-type={content_type or 'unknown'})")
    return content_type


def discover_input_files(paths: Iterable[Path], recursive: bool = False) -> List[Path]:
    discovered: List[Path] = []
    for path in paths:
        if path.is_file():
            discovered.append(path)
            continue
        pattern = "**/*" if recursive else "*"
        for candidate in sorted(path.glob(pattern)):
            if not candidate.is_file():
                continue
            if candidate.suffix.lower() in PDF_EXTENSIONS | IMAGE_EXTENSIONS:
                discovered.append(candidate)
    return discovered
