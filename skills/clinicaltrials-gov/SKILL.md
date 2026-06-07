---
id: clinicaltrials-gov
name: clinicaltrials-gov
description: Search the ClinicalTrials.gov registry through its public API v2 to find interventional and observational studies by condition, intervention, status, or free text.
version: 1.0.0
stages: [survey, ideation]
tools: [read_file, search_project, write_file, run_terminal]
domains: [clinical-medicine]
primaryIntent: research
intents: [research]
keywords: [clinicaltrials, trial-registry, recruiting, intervention, condition, nct, prior-art, feasibility]
status: verified
---

# clinicaltrials-gov

Search the **ClinicalTrials.gov** registry through its public **API v2**. The
registry is the canonical source for ongoing and completed clinical studies — use
it to scope prior art, gauge feasibility, find comparators, and avoid duplicating a
trial that is already running.

## When to use

- During **ideation**, to check whether the clinical question is already being tested (and at what phase / enrollment)
- To find active or completed trials of a comparator intervention or in a target population
- To pull registered primary/secondary outcomes and design details for a study you plan to mirror
- As one of the sources in a **systematic-review** search of trial registries (alongside `pubmed-search`)

## How to run

Resolve the script from this skill's directory. Standard library only — no
`pip install` and no API key required.

```bash
# by condition, only currently recruiting studies
python3 scripts/clinicaltrials_search.py --condition "heart failure" --status RECRUITING --max 50

# free-text query, write JSON to the project workspace
python3 scripts/clinicaltrials_search.py --term "semaglutide obesity" --max 100 --output trials.json

# narrow by condition AND intervention
python3 scripts/clinicaltrials_search.py --condition stroke --intervention thrombectomy
```

Output is JSON: `total_count` and `results[]` with `nct_id`, `title`, `status`,
`study_type`, `phases`, `enrollment`, `conditions`, `interventions`,
`lead_sponsor`, `start_date`, and `url`.

## Notes

- Common `--status` values: `RECRUITING`, `NOT_YET_RECRUITING`, `ACTIVE_NOT_RECRUITING`, `COMPLETED`, `TERMINATED`, `WITHDRAWN`.
- The script paginates automatically up to `--max`; raise `--max` for an exhaustive registry sweep and record the `total_count`.
- If the API or network is unavailable, report the blocker and fall back to a hand-built query for <https://clinicaltrials.gov>; do not silently skip the step.
- Save output into the active project workspace, never back into this skill directory.
