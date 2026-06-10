---
name: literature-pdf-ocr-library
description: Search traceable academic papers across arXiv, Semantic Scholar, OpenAlex, Crossref (and optionally Google Scholar via CDP), judge open-access availability, rank by recency + citations into a screening table, download only legally accessible PDFs, convert them to Markdown with a PaddleOCR layout-parsing API (or local pdfminer fallback), and organize the results into an AI-readable literature library. Use when Claude Code needs to survey literature, build a paper corpus, judge open access, batch OCR PDFs to Markdown, ingest real papers into a knowledge base, or turn a directory of papers into structured Markdown plus metadata.
triggers:
  - /literature-library
  - /paper-library
  - build paper corpus
  - build literature library
  - ingest papers
  - batch ocr papers
  - download arxiv papers
  - search and download papers
  - paper corpus
  - literature corpus
---

# Literature PDF OCR Library

## Overview

Build a real, traceable literature corpus instead of fabricating references or
scraping arbitrary publisher pages. The bottleneck of a survey is not searching
but **filtering** — so the workflow is two passes:

1. **Screen first** — search several sources with expanded queries, judge
   open-access availability, rank by recency + citations, and emit a lightweight
   screening table (`survey_screening.md`). **No download yet.**
2. **Dig second** — once the user picks the core papers, download only those
   (legally open PDFs only), OCR them to Markdown, and index the corpus.

This keeps the expensive OCR step for the papers that will actually be read.

## Query expansion

A user's phrasing is one entry point, not the whole query. Before searching,
expand the topic into 2–3 complementary queries and pass them via `--queries`
(the script merges + dedups them):

- synonyms: `agent` → `agentic` / `multi-agent` / `autonomous`
- sub-concepts: `time series agent` → `time series LLM agent` + `temporal foundation model`
- abbreviation/full-name pairs: `LLM` / `large language model`
- controlled vocabularies by discipline: MeSH (medicine), JEL (economics),
  MSC (math), ACM CCS (CS)

## Canonical Directory Layout

In **Oh My Paper projects**, the corpus always lives under **`.pipeline/literature/<corpus-name>/`**.
In standalone projects, use `research/literature/<corpus-name>/`.
Never dump papers into the root or a flat directory without a corpus name.

```text
.pipeline/
  literature/
    <corpus-name>/              ← one folder per topic/session, e.g. "humanoid-locomotion"
      survey_screening.md       ← lightweight screening table (pass 1, --summary-only)
      search_results.json       ← raw search/ID-lookup results (full metadata)
      library_index.json        ← consolidated index for the whole corpus
      library_index.jsonl
      papers/
        <arxiv-id>-<title-slug>/   ← one folder per paper
          metadata.json
          paper.pdf
          ocr/                  ← OCR output lives here, next to the PDF
            paper/
              doc_0.md          ← main OCR markdown (PaddleOCR: multiple pages)
              manifest.json
            doc_0.md            ← pdfminer fallback: single flat file
```

**Rules:**
- `--out-dir` always points to `.pipeline/literature/<corpus-name>/` — never to `.pipeline/literature/` directly.
- OCR output lives inside the paper's own folder (`papers/<slug>/ocr/`), not in a top-level `ocr/` directory.
- After OCR, record each paper's `ocr/` path **and** `full_text_status` in `literature_bank.md`.

## Commands

```bash
# --- Pass 1: screen (search + open-access judgement + ranking, NO download) ---
# The prompt layer expands the topic into a few complementary queries.
python .claude/skills/literature-pdf-ocr-library/scripts/search_and_download_papers.py \
  --queries "humanoid locomotion reinforcement learning" "legged robot RL control" "bipedal locomotion policy" \
  --summary-only --limit 30 \
  --sources arxiv semanticscholar openalex crossref \
  --out-dir .pipeline/literature/<corpus-name>
# → writes survey_screening.md (title/year/venue/citations/[new]/full_text_status/code).
#   Present it to the user and let them pick the core papers before downloading.

# (optional) Google Scholar for the fullest citation counts / papers other sources miss.
# Needs Chrome remote debugging; degrades gracefully if absent.
bash .claude/skills/literature-pdf-ocr-library/scripts/check-deps.sh

# --- Pass 2: deep pull (download only the picked papers; open-access PDFs only) ---
python .claude/skills/literature-pdf-ocr-library/scripts/search_and_download_papers.py \
  --arxiv-ids 2502.13817 2501.14459 \
  --download-pdfs \
  --out-dir .pipeline/literature/<corpus-name>
# Only records with full_text_status=open_pdf are downloaded; others are kept as metadata.

# OCR: PaddleOCR-VL async API (best quality). Submits a job, polls, downloads Markdown.
# Default endpoint: https://paddleocr.aistudio-app.com/api/v2/ocr/jobs  (override with PADDLEOCR_API_URL)
export PADDLEOCR_TOKEN="<token>"  # ask user, never hardcode
python .claude/skills/literature-pdf-ocr-library/scripts/paddleocr_layout_to_markdown.py \
  .pipeline/literature/<corpus-name>/papers/*/paper.pdf \
  --output-dir .pipeline/literature/<corpus-name>/papers \
  --skip-existing

# OCR: pdfminer fallback (text-only, no layout — confirm with user first)
python .claude/skills/literature-pdf-ocr-library/scripts/paddleocr_layout_to_markdown.py \
  .pipeline/literature/<corpus-name>/papers/*/paper.pdf \
  --output-dir .pipeline/literature/<corpus-name>/papers \
  --fallback-pdfminer

# Build index
python .claude/skills/literature-pdf-ocr-library/scripts/build_library_index.py \
  --library-root .pipeline/literature/<corpus-name>
```

Single-call full-text query when an arXiv ID list is already known: pass
`--arxiv-ids … --summary-only` first to confirm metadata, then `--download-pdfs`.

## Sources & open access

API-first across arXiv, Semantic Scholar, OpenAlex, Crossref, and Hugging Face
daily papers; Google Scholar is an optional CDP-only add-on. (Papers with Code's
official API has been offline since 2025, so `pwc` is kept as a source choice but
not in the default set.) Open
access is resolved by a fallback chain (arXiv → S2 → OpenAlex → Unpaywall) into a
six-state `full_text_status`. Only legally open PDFs are downloaded — never
Sci-Hub / LibGen / WebVPN / CARSI / paywall bypass. Details:
[source-strategy.md](./references/source-strategy.md) and
[metadata-schema.md](./references/metadata-schema.md).

## Environment variables

- `S2_API_KEY` — Semantic Scholar key; strongly recommended, avoids 429 on multi-query runs.
- `UNPAYWALL_EMAIL` — contact email Unpaywall requires (falls back to `OPENALEX_MAILTO`).
- `OPENALEX_MAILTO` — polite contact for OpenAlex / Crossref.
- `PADDLEOCR_API_URL` / `PADDLEOCR_TOKEN` — OCR step.
- `CDP_PROXY_PORT` — Google Scholar CDP proxy port (default 3456).

## Resources

- [source-strategy.md](./references/source-strategy.md) — sources, OA fallback chain, failure signals, legal constraints, env vars.
- [metadata-schema.md](./references/metadata-schema.md) — unified record schema, `full_text_status` / `download_status` enums, dedup + field-merge rules, BibTeX assembly.
- [site-patterns/scholar.google.com.md](./references/site-patterns/scholar.google.com.md) — Google Scholar CDP selectors, pacing, pitfalls.
- `scripts/search_and_download_papers.py` — multi-source search + OA judgement + ranking + download (`--query` / `--queries` / `--arxiv-ids`, `--summary-only`).
- `scripts/paddleocr_layout_to_markdown.py` — single-file or batch OCR (`--fallback-pdfminer`).
- `scripts/build_library_index.py` — generate `library_index.json` / `.jsonl`.
- `scripts/ingest_literature_library.py` — one-shot search → download → OCR → index (full-download shortcut).
- `scripts/build_bibliography.py` — turn verified `metadata.json` into `references.bib` + stable cite keys (written back to metadata) + `bibliography.json` provenance map. The survey→write bridge: never hand-write bib entries.
- `scripts/audit_citations.py` — check every `\cite` in `sections/*.tex` resolves to a real, sourced bib entry (flags dangling / unsourced / unused).
- `scripts/check-deps.sh` + `scripts/cdp-proxy.mjs` — optional Google Scholar via CDP (Chrome remote debugging; zero npm deps).
