---
id: clinical-study-design
name: clinical-study-design
description: Turn a clinical research idea into a registered protocol with a PICO question, a justified design, a sample-size and power calculation, a statistical analysis plan, and ethics and registration steps.
version: 1.0.0
stages: [ideation, experiment]
tools: [read_file, search_project, write_file, run_terminal]
domains: [clinical-medicine]
primaryIntent: research
intents: [research]
keywords: [clinical-trial, study-design, pico, finer, sample-size, power, statistical-analysis-plan, irb, spirit, randomization, registration]
status: verified
---

# clinical-study-design

Turn a clinical research idea into a **defensible, registrable study**. In a clinical
project the pipeline's "experiment" stage is a *study* — an RCT, cohort, case-control,
cross-sectional, or diagnostic-accuracy study — not a code run. This skill takes you
from a sharp question to a protocol an IRB and a journal will accept.

Use it in **ideation** to pressure-test feasibility, and in **experiment** to lock the
design before any data are collected. For evidence synthesis instead of primary data,
use `systematic-review`; for the registry search, use `clinicaltrials-gov`.

## Bundled resources

- `templates/protocol-skeleton.md` — a SPIRIT-aligned protocol outline to fill in
- `templates/sample-size-cheatsheet.md` — runnable R for the common power calculations
- `references/study-design-decision.md` — question type → appropriate design

Write all artifacts into the project workspace; never back into this skill directory.

## Workflow

### 1. Sharpen the question — PICO + FINER
Frame it as **PICO/PECO**: Population, Intervention/Exposure, Comparator, Outcome
(+ Timeframe, Setting). Then sanity-check with **FINER**: Feasible, Interesting,
Novel, Ethical, Relevant. Before committing, check whether it is already answered —
search `pubmed-search` for an existing systematic review and `clinicaltrials-gov` for
ongoing trials. A question that fails FINER is cheaper to kill now than after IRB.

### 2. Choose the design (and say why)
Match the design to the question (see `references/study-design-decision.md`):
- **Therapy / prevention** → RCT (parallel, crossover, cluster, or factorial); pragmatic vs explanatory
- **Harm / etiology** where an RCT is unethical → cohort or case-control
- **Prevalence / association at a point** → cross-sectional
- **Diagnostic test performance** → cross-sectional diagnostic-accuracy study vs a reference standard
- **Rare exposure** → cohort; **rare outcome** → case-control
State the unit of analysis and, for RCTs, the randomization and allocation-concealment scheme and the level/feasibility of blinding.

### 3. Define outcomes and the estimand
One **primary outcome** drives the sample size; list secondary and safety outcomes.
Specify how each is measured, when, and by whom. State the **estimand**: the
population-level quantity being estimated (e.g., treatment effect on all-comers
regardless of adherence — the ITT estimand) and how intercurrent events are handled.

### 4. Sample size and power
Pre-specify α (usually two-sided 0.05), power (usually 0.80–0.90), the **minimal
clinically important difference**, and expected event rates / means+SD from the
literature. Compute with `templates/sample-size-cheatsheet.md`. Account for:
- **Dropout / loss to follow-up** — inflate the enrolled n.
- **Clustering** — multiply by the design effect `1 + (m−1)·ICC`.
- **Non-inferiority / equivalence** — use the pre-agreed margin and a one-sided α; this is a different calculation from superiority.
A study powered on a guess is the most common fatal protocol flaw — anchor every input to a citation.

### 5. Anticipate bias and confounding
Name the threats and the design/analysis response:
- **Selection bias** → sampling frame, inclusion/exclusion, consecutive enrollment
- **Information/measurement bias** → blinded/standardized assessment, validated instruments
- **Confounding** → randomization (RCT) or, for observational designs, matching, restriction, stratification, multivariable adjustment, or propensity methods (pre-specify the confounders)

### 6. Statistical Analysis Plan (SAP)
Write the SAP **before** unblinding/analysis:
- **Analysis populations**: ITT, modified ITT, per-protocol, safety
- **Primary analysis model** for the primary outcome (e.g., log-binomial/Cox/mixed model), covariates, and how clustering/repeated measures are handled
- **Missing data** strategy (and sensitivity analyses around it)
- **Multiplicity** control if there are multiple primary outcomes or interim looks
- Pre-specified **subgroups** and **interim analyses / stopping rules** (DSMB)

### 7. Ethics, governance, and registration
- **IRB/IEC** submission: protocol, informed consent form, recruitment materials, data-management/privacy plan (HIPAA/GDPR).
- **Register prospectively**: interventional trials on **ClinicalTrials.gov** (or a WHO primary registry) *before* enrolling the first participant; systematic reviews on **PROSPERO**.
- Plan reporting from the start: the design fixes which guideline the paper will follow — **SPIRIT** for the protocol, then **CONSORT** (RCT) / **STROBE** (observational) / **STARD** (diagnostic) for the manuscript (handled by `scientific-writing`).

### 8. Data management
Specify capture (e.g., **REDCap** or another EDC), the CRF/case-report form, a data
dictionary, and validation/range checks. Decide data-sharing and the analysis dataset
structure now, not after collection.

## Output
A filled `templates/protocol-skeleton.md`, an explicit sample-size calculation with its
inputs and citations, a one-page SAP, and a registration checklist. Record the design
decision and its rationale in the project memory so downstream writing and review stay
aligned.

## Guardrails
- Never finalize a sample size without a cited effect size and a stated MCID.
- Do not start an interventional study description without a registration step.
- If R or a calculator is unavailable, give the formula, the inputs, and a worked manual estimate — do not omit the power calculation.
