---
id: systematic-review
name: systematic-review
description: Run a PRISMA 2020 systematic review and meta-analysis end to end from protocol and search through screening, risk-of-bias, evidence synthesis, and GRADE.
version: 1.0.0
stages: [survey, publication]
tools: [read_file, search_project, write_file, run_terminal]
domains: [clinical-medicine]
primaryIntent: research
intents: [research, writing]
keywords: [systematic-review, meta-analysis, prisma, grade, risk-of-bias, rob2, robins-i, quadas, forest-plot, evidence-synthesis]
status: verified
---

# systematic-review

Run a **systematic review** — and, where appropriate, a **meta-analysis** —
following PRISMA 2020. A systematic review is itself a study with a protocol; it is
not a casual literature scan. This skill carries the project from a registered
protocol through a reproducible search, dual screening, risk-of-bias assessment,
quantitative synthesis, and a GRADE certainty rating.

Pair this skill with `pubmed-search` and `clinicaltrials-gov` for the searches, and
with `clinical-study-design` when the protocol needs PICO and registration support.

## Bundled resources

- `templates/prisma-flow.md` — the PRISMA 2020 flow-diagram counts to fill in as you screen
- `templates/data-extraction.csv` — a starting data-extraction sheet (one row per included study)
- `templates/risk-of-bias.md` — which RoB tool to use and the domains to record
- `references/meta-analysis-R.md` — copy-paste R (`metafor` / `meta`) for pooling, forest/funnel plots, and heterogeneity

Resolve all paths from this skill's directory; write every artifact into the active
project workspace (e.g. `survey/systematic-review/`), never back into the skill.

## Workflow (PRISMA 2020)

### 1. Protocol first, then register
Define and **register before screening** (PROSPERO for reviews of health outcomes).
Lock down: review question as **PICO/PECO**, eligibility criteria (population, study
designs, comparators, outcomes, language/date limits), and the planned synthesis. A
registered protocol is what separates a systematic review from a narrative one.

### 2. Build and record the search strategy
- Search **at least two databases** plus a trial registry. For clinical questions that means MEDLINE (`pubmed-search`), and typically Embase and the Cochrane CENTRAL trials register; add `clinicaltrials-gov` for unpublished/ongoing studies to probe publication bias.
- Combine controlled vocabulary (MeSH/Emtree) with free-text synonyms for each PICO concept; join concepts with AND, synonyms with OR.
- **Record verbatim**: the exact query per database, the date run, and the number of hits. Save these — they populate the "Identification" box of the PRISMA flow and the reproducibility appendix.

### 3. De-duplicate and screen in two stages
- De-duplicate across databases; log the number removed.
- **Title/abstract screening**, then **full-text screening**, ideally by **two independent reviewers** with conflicts resolved by discussion or a third reviewer. Record inter-rater agreement if reported.
- For every full-text exclusion, record **one reason**. Keep a running tally in `templates/prisma-flow.md`.

### 4. Extract data
Use `templates/data-extraction.csv` — one row per study: identifiers, design, sample
sizes per arm, population, intervention/comparator, outcome definitions and
timepoints, effect estimates with variance (or the raw cell counts / means+SD needed
to compute them), and funding/conflicts. Extract in duplicate where feasible.

### 5. Assess risk of bias
Pick the tool that matches the design (see `templates/risk-of-bias.md`):
- **RoB 2** — randomized trials
- **ROBINS-I** — non-randomized studies of interventions
- **QUADAS-2** — diagnostic accuracy studies
- **Newcastle–Ottawa Scale** — cohort/case-control (a common lightweight alternative)
Assess per outcome where the tool requires it; never collapse to a single ad-hoc score.

### 6. Synthesize
- **Always** provide a structured narrative synthesis. Add a **meta-analysis only when studies are clinically and methodologically similar enough to pool** — otherwise synthesize without meta-analysis (SWiM) and say why.
- Choose the effect measure by outcome type: RR/OR/RD (binary), MD/SMD (continuous), HR (time-to-event).
- Prefer a **random-effects** model in clinical reviews (between-study heterogeneity is expected). Report the pooled estimate with 95% CI, **heterogeneity (I², τ², Cochran's Q)**, and a **forest plot**.
- Pre-specify **subgroup and sensitivity analyses**; do not data-dredge.
- Assess **publication/small-study bias** with a funnel plot and Egger's test when ≥10 studies. See `references/meta-analysis-R.md` for runnable code.

### 7. Rate certainty with GRADE
Rate certainty **per outcome** (High → Moderate → Low → Very low), downgrading for
risk of bias, inconsistency, indirectness, imprecision, and publication bias (and,
for observational evidence, upgrading for large effect / dose-response / plausible
confounding working against the effect). Summarize in a GRADE Summary-of-Findings table.

### 8. Report to PRISMA 2020
Report against the **PRISMA 2020 checklist** and include the **flow diagram**
(`templates/prisma-flow.md`). Hand the manuscript to the `scientific-writing` skill,
which already knows the PRISMA reporting guideline, and verify every citation with
`inno-reference-audit`.

## Guardrails

- Never report a pooled estimate without heterogeneity statistics and a risk-of-bias assessment of its contributing studies.
- Do not pool clinically heterogeneous studies just because the numbers allow it.
- Keep the search reproducible: a reviewer must be able to re-run your exact strings and land on the same counts.
- If a tool (R, a database) is unavailable, state the blocker and produce the manual artifact (hand-built search string, narrative synthesis) rather than skipping the step.
