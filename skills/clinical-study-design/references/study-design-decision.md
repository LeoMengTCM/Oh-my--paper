# Study-design decision guide

Pick the design from the question and what is ethical/feasible. There is no single
"best" design — only the best fit for the question and constraints.

## By question type

| Clinical question | Usual design(s) | Reporting guideline |
|---|---|---|
| Does a treatment/prevention work? | **RCT** (parallel / crossover / cluster / factorial) | CONSORT |
| Treatment works, but RCT is unethical/impractical | Prospective **cohort**; quasi-experimental | STROBE / TREND |
| What causes harm? (exposure → outcome) | **Cohort** (common outcome) or **case-control** (rare outcome) | STROBE |
| How common is it / what is associated? | **Cross-sectional** | STROBE |
| How good is a diagnostic test? | **Diagnostic-accuracy** vs reference standard | STARD |
| Does a prediction model work? | Development + external validation | TRIPOD |
| Synthesize existing studies | **Systematic review / meta-analysis** → use `systematic-review` | PRISMA |
| One patient, structured | **N-of-1** / case report | CARE |

## RCT flavors
- **Parallel**: simplest; groups run concurrently.
- **Crossover**: each participant is their own control; only for stable, chronic, reversible conditions (watch carryover — include washout).
- **Cluster**: randomize groups (clinics, wards) — needed when the intervention is delivered at group level; pay the design-effect tax on sample size.
- **Factorial**: test ≥2 interventions at once; assumes no strong interaction.
- **Pragmatic vs explanatory**: real-world effectiveness in usual care vs efficacy under ideal conditions — pick the point on the spectrum that matches your question.

## Observational pitfalls to pre-empt
- **Cohort**: loss to follow-up, time-varying confounding.
- **Case-control**: selection of controls, recall bias; define cases and the source population first.
- **Cross-sectional**: cannot establish temporality — association ≠ causation.
- All observational designs: pre-specify confounders and the adjustment strategy; consider a directed acyclic graph (DAG).

## Hierarchy of evidence (for therapy questions, roughly)
Systematic review of RCTs > single RCT > cohort > case-control > cross-sectional >
case series > expert opinion. Design as high as ethics and feasibility allow — but a
well-run cohort beats a poorly powered, biased RCT.
