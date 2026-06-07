---
id: pubmed-search
name: pubmed-search
description: Search PubMed and MEDLINE for peer-reviewed biomedical and clinical literature through the NCBI E-utilities API with MeSH terms, date filters, and abstracts.
version: 1.0.0
stages: [survey, ideation]
tools: [read_file, search_project, write_file, run_terminal]
domains: [clinical-medicine]
primaryIntent: research
intents: [research]
keywords: [pubmed, medline, ncbi, e-utilities, mesh, clinical-literature, evidence-search, systematic-review]
status: verified
---

# pubmed-search

Search **PubMed / MEDLINE** — the primary index of peer-reviewed biomedical and
clinical literature — through the NCBI E-utilities API. Use this whenever the
question is clinical or biomedical: it reaches the evidence base that `paper-finder`
(local notes) and `biorxiv-database` (preprints only) cannot.

## When to use

- Building a literature foundation for a clinical question (diagnosis, therapy, prognosis, etiology)
- Constructing or running a **systematic-review** search string and recording per-database hit counts
- Checking whether a research idea has already been answered before committing to it
- Pulling abstracts and MeSH terms for screening, citation, or evidence tables

## How to run

Resolve the script from this skill's directory. It uses only the Python standard
library (urllib + xml) — no `pip install` needed.

```bash
# basic search (returns metadata only)
python3 scripts/pubmed_search.py "metformin AND cardiovascular outcomes" --retmax 50

# field tags + date window + abstracts and MeSH (one extra request)
python3 scripts/pubmed_search.py '"heart failure"[MeSH] AND randomized[tiab]' \
  --mindate 2020/01/01 --maxdate 2024/12/31 --abstracts --output hf.json

# faster + higher rate limit with a free NCBI API key
python3 scripts/pubmed_search.py "sepsis bundle mortality" --api-key "$NCBI_API_KEY" --abstracts
```

Output is JSON: `total_count` (all matches PubMed reports) and `results[]` with
`pmid`, `title`, `journal`, `pubdate`, `authors`, `doi`, `url`, and — with
`--abstracts` — `abstract` and `mesh_terms`.

## Query craft (the part that matters for clinical search)

- **Use MeSH for concepts, free text for the latest work.** Combine both:
  `("Heart Failure"[MeSH] OR "heart failure"[tiab]) AND ("SGLT2"[tiab])`.
- **Field tags**: `[MeSH]`, `[tiab]` (title/abstract), `[ti]`, `[au]`, `[ta]` (journal), `[pdat]` (publication date), `[la]` (language).
- **Filters as terms**: `AND randomized controlled trial[pt]`, `AND humans[mh]`, `AND english[la]`.
- For a reproducible review, **save the exact query string and the `total_count`** — that pair is what goes into the PRISMA flow diagram. Hand off to the `systematic-review` skill.

## Etiquette & limits

- Pass `--email` so NCBI can reach you; without an `--api-key` the script self-throttles to ~3 requests/second (10/s with a key).
- If the network or NCBI is unavailable, report the blocker and fall back to a manually constructed query string the user can paste into <https://pubmed.ncbi.nlm.nih.gov>; do not silently skip the search.
- Save all output into the active project workspace (e.g. `survey/`), never back into this skill directory.
