# Source Strategy

Goal: get **accurate, structured** paper metadata and **legally open** full text,
then OCR only what the user actually wants to read. The bottleneck of a survey is
not searching but *filtering* — so default to a two-pass flow (see SKILL.md):
a lightweight screening table first, deep pull + download second.

## Search sources

API-first; the browser (CDP) is a fallback only for sources with no API.

| Source | Use for | Access |
|--------|---------|--------|
| **arXiv** | CS/ML/physics/math preprints, direct PDF | REST API (no key) |
| **Semantic Scholar** | citation counts, broad discovery, `openAccessPdf` | REST API (`S2_API_KEY` lifts the rate limit) |
| **OpenAlex** | cross-discipline metadata, OA status, PDF URLs | REST API (`mailto` polite) |
| **Crossref** | authoritative DOI / venue / publication-type completion | REST API (`mailto` polite) |
| **Unpaywall** | open-access judgement + legal OA PDF link (by DOI) | REST API (email required) |
| **Papers with Code** | ML papers + linked code repos (`code_url`) | ⚠️ official API offline since 2025 — kept as a `pwc` choice, not in the default set |
| **Hugging Face daily_papers** | fresh ML leads (map back to arXiv) | REST API (no key) |
| **Google Scholar** | fullest citation counts, papers other sources miss | **CDP only** (no API; optional) — see `site-patterns/scholar.google.com.md` |

CNKI / paywalled publisher scraping are intentionally out of scope here.

## Open-access fallback chain (`enrich_open_access`)

Resolve `full_text_status` + best `pdf_url`, stopping at the first hit:

1. **arXiv direct link** — when `arxiv_id` exists, build `https://arxiv.org/pdf/{id}.pdf`
   (S2's `openAccessPdf` is often null even when the arXiv PDF is available).
2. **Semantic Scholar** `openAccessPdf.url`.
3. **OpenAlex** `best_oa_location.pdf_url` (by DOI).
4. **Unpaywall** `best_oa_location.url_for_pdf` (by DOI).
5. Nothing open → `needs_institution` (landing page exists) or `unknown`.

`download_pdf` verifies the bytes really are a PDF; an HTML page → `html_not_pdf`.
See `references/metadata-schema.md` for the full `full_text_status` /
`download_status` enums.

## Failure signals → adjustment

Every result is information, not just success/failure. Don't retry the same way.

| Signal | Meaning | Adjust |
|--------|---------|--------|
| API 429 / rate exceeded | session quota spent (not a blip) | wait 15s+ or set `S2_API_KEY`; other sources still return — don't retry the same call |
| timeout | page unfriendly to static fetch | use the API via curl, or CDP |
| empty results | wording / not indexed here | change keywords, or switch source (arXiv ↔ PubMed) |
| "not found" | maybe an access issue, not truly absent | check URL params; verify on another source |
| 3 retries, no change | wrong path, not "not yet" | re-evaluate goal; switch source or access mode |

## Legal constraints

- Download only openly accessible PDFs (`full_text_status=open_pdf`).
- Never use Sci-Hub, LibGen, shadow libraries, WebVPN, CARSI, Tor, or any
  paywall-bypass / Cloudflare-bypass tool.
- For `needs_institution` / `no_open_pdf` / `anti_bot_blocked`, keep the metadata,
  record the reason, and suggest the institutional library, author email, or ILL.
- If a paper is traceable but not downloadable, preserve metadata and mark the
  status — do not fabricate a PDF.

## Metadata fields

Records follow `references/metadata-schema.md` (unified schema, dedup rules,
field-merge priority, BibTeX assembly).

## Suggested user inputs

Ask only when needed: query / topic, expanded queries, time window, paper count,
open-access-only vs metadata-only, local input directory (if the user already has PDFs).

## Environment variables

| Variable | Purpose |
|----------|---------|
| `S2_API_KEY` | Semantic Scholar API key — strongly recommended; avoids 429 on multi-query runs. |
| `UNPAYWALL_EMAIL` | Contact email Unpaywall requires (falls back to `OPENALEX_MAILTO`). |
| `OPENALEX_MAILTO` | Polite contact for OpenAlex / Crossref. |
| `PADDLEOCR_API_URL` / `PADDLEOCR_TOKEN` | OCR step (see SKILL.md). |
| `CDP_PROXY_PORT` | CDP proxy port for Google Scholar (default 3456). |
