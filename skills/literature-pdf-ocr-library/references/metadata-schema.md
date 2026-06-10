# Metadata Schema

Unified record structure for the literature library — used to merge multi-source
results, deduplicate, judge open access, and assemble BibTeX. `literature_lib.py`
emits `metadata.json` (per paper) and `search_results.json` (the whole run)
following this schema.

> The `full_text_status` / `download_status` enums, dedup rules, and BibTeX
> assembly are adapted from the academic-search skill
> (MIT, Copyright (c) 2026 Chengmingyue):
> https://github.com/ustc-ai4science/academic-search

## Standard record (JSON)

```json
{
  "source": "semanticscholar",
  "merged_sources": ["arxiv", "semanticscholar"],
  "title": "Attention Is All You Need",
  "authors": ["Ashish Vaswani", "Noam Shazeer"],
  "year": 2017,
  "published": "2017-06-12",
  "publication_date": "2017-06-12",
  "publication_type": "conference",
  "venue": "NeurIPS 2017",
  "doi": "10.5555/3295222.3295349",
  "arxiv_id": "1706.03762",
  "abstract": "The dominant sequence transduction models...",
  "citation_count": 90000,
  "is_new": false,
  "open_access_status": "green",
  "full_text_status": "open_pdf",
  "pdf_url": "https://arxiv.org/pdf/1706.03762.pdf",
  "download_source": "arxiv",
  "code_url": null,
  "license": null,
  "landing_page": "https://arxiv.org/abs/1706.03762",
  "local_pdf_path": null,
  "download_status": "not_requested",
  "download_error": null,
  "pdf_status": "not_requested",
  "rank": 1,
  "paper_slug": "1706-03762-2017-attention-is-all-you-need"
}
```

## Field reference

| Field | Type | Notes |
|------|------|------|
| `source` | string | The source that produced this record: `arxiv` / `semanticscholar` / `openalex` / `crossref` / `pwc` / `hf_daily`. |
| `merged_sources` | string[] | All sources that contributed after dedup. |
| `title` / `authors` / `year` | — | Core bibliographic fields. `authors` may keep the source's raw format. |
| `published` / `publication_date` | string | ISO date when available (arXiv, S2, OpenAlex); used by `rank_records` for the `is_new` window. |
| `publication_type` | string | e.g. `journal-article`, `conference`, `preprint`, `review`. |
| `venue` | string | Journal / conference name. |
| `doi` / `arxiv_id` | string | Primary dedup keys. |
| `citation_count` | integer | From S2 `citationCount`, OpenAlex `cited_by_count`, Crossref `is-referenced-by-count`, or Google Scholar. On merge, the **larger** value wins. |
| `is_new` | boolean | True when published within the last ~6 months; pinned to the top in ranking. |
| `open_access_status` | string | `gold` / `green` / `hybrid` / `bronze` / `closed` / `unknown` (OpenAlex / Unpaywall). |
| `full_text_status` | string | Full-text availability — see enum below. |
| `pdf_url` | string | Best legally-open PDF link, resolved by the OA fallback chain. |
| `download_source` | string | Which step in the chain supplied `pdf_url`: `arxiv` / `semantic_scholar` / `openalex` / `unpaywall`. |
| `code_url` | string | Code repository (Papers with Code). |
| `license` | string | OA license when known (e.g. `cc-by`). |
| `local_pdf_path` | string | Set only when `download_status=downloaded`. |
| `download_status` | string | OA PDF download outcome — see enum below. |
| `download_error` | string | Reason for `skipped` / `failed` / `not_pdf`. |
| `pdf_status` | string | **Legacy** field mapped from `download_status`, kept for `build_library_index.py` compatibility. |
| `citation_key` | string | Stable BibTeX key (lastname+year+title-word), written back by `build_bibliography.py`; survey and write share the same key. |
| `rank` / `paper_slug` | — | Position in the ranked set; folder slug under `papers/`. |

### Discipline extension fields (filled by the prompt layer on demand)

For clinical / systematic-review work, agents may add: `pubmed_id`, `pmcid`,
`mesh_terms[]`, `study_type` (RCT / cohort / case-control …), `sample_size`,
`population`. These are not produced by the search scripts.

## `full_text_status` (full-text availability)

| Status | Meaning |
|------|------|
| `open_pdf` | A legally open PDF was found (`pdf_url` set). |
| `needs_institution` | Landing page reachable, but full text needs institutional access. |
| `no_open_pdf` | No legal open full text (`is_oa=false` confirmed). |
| `anti_bot_blocked` | Blocked by Cloudflare / CAPTCHA / anti-scraping. |
| `html_not_pdf` | The PDF route returned HTML, not a PDF binary. |
| `unknown` | Not enough evidence to decide. |

## `download_status` (OA PDF download)

| Status | Meaning |
|------|------|
| `not_requested` | Metadata / OA judgement only (e.g. `--summary-only`). |
| `eligible` | `full_text_status=open_pdf` with a usable `pdf_url`. |
| `downloaded` | Saved locally; `local_pdf_path` set. |
| `skipped` | Not eligible (needs institution / no open PDF / missing URL). |
| `failed` | Network / HTTP / write error. |
| `not_pdf` | URL returned non-PDF content. |

## Deduplication

Primary-key priority when merging records across sources / queries:

1. **DOI** (globally unique) → 2. **arXiv ID** → 3. **PubMed ID** (if present)
→ 4. fuzzy **title + year (+ first-author initial)**.

`dedupe_records` keeps the record from the highest-priority source
(`arxiv > semanticscholar > openalex > crossref > hf_daily > pwc`) and fills
missing fields from duplicates.

## Field-merge priority

| Field | Preferred source |
|------|------|
| `citation_count` | Google Scholar > Semantic Scholar > OpenAlex > Crossref |
| `open_access_status` | Unpaywall > OpenAlex |
| `full_text_status` | actual download/access verification > Unpaywall > OpenAlex |
| `pdf_url` | arXiv > S2 openAccessPdf > OpenAlex > Unpaywall |
| `abstract` | Semantic Scholar > arXiv > Papers with Code |
| `venue` / `doi` | Crossref > Semantic Scholar > OpenAlex > arXiv |
| `code_url` | Papers with Code |

## BibTeX assembly (when no platform export is available)

`citation_key` = `{first-author-lastname-lower}{year}{first-significant-title-word-lower}`
(e.g. `vaswani2017attention`).

```bibtex
@inproceedings{<key>, title={<title>}, author={<authors joined by " and ">},
  booktitle={<venue>}, year={<year>}, doi={<doi>}, url={<pdf_url>} }

@article{<key>, title={<title>}, author={<authors>}, journal={<venue>},
  year={<year>}, doi={<doi>}, url={<pdf_url>} }

@misc{<key>, title={<title>}, author={<authors>}, year={<year>},
  eprint={<arxiv_id>}, archivePrefix={arXiv},
  url={https://arxiv.org/abs/<arxiv_id>} }
```

## Per-source field mapping

| Standard | arXiv XML | Semantic Scholar | OpenAlex | Crossref | Papers with Code |
|---------|-----------|------------------|----------|----------|------------------|
| title | `<title>` | `title` | `display_name` | `title[0]` | `title` |
| year | `<published>`[:4] | `year` | `publication_year` | `issued.date-parts[0][0]` | `published`[:4] |
| doi | `<arxiv:doi>` | `externalIds.DOI` | `doi` | `DOI` | `doi` |
| arxiv_id | `<id>` last seg | `externalIds.ArXiv` | — | — | `arxiv_id` |
| citation_count | — | `citationCount` | `cited_by_count` | `is-referenced-by-count` | — |
| pdf_url | constructed | `openAccessPdf.url` | `primary_location.pdf_url` | — | `url_pdf` |
| code_url | — | — | — | — | `url_abs` |
