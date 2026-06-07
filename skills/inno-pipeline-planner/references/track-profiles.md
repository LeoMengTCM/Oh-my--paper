# Track Profiles

`pipeline.track` selects how the five fixed stages (survey < ideation < experiment <
publication < promotion) are *interpreted*, *gated*, and what *figures* and *quality
gates* each stage produces. The stage spine never changes — only its contents do.

Set `pipeline.track` in `research_brief.json` (default `"ml"`). It also sets a default
`pipeline.analysisMode`. **Consult this file whenever generating or revising
`task_blueprints`, `quality_gate`, gates, or figure deliverables.** Unknown track →
treat as `ml` (fully backward-compatible with existing projects).

## Track summary

| track | analysisMode default | "experiment" stage means | reporting guideline | hard gate before data/analysis |
|---|---|---|---|---|
| `ml` | exploratory | train / evaluate / ablate models | venue template | none |
| `bioinformatics` | exploratory | run analysis pipelines (often on HPC) | target journal | none, but pin pipeline + reference/DB versions |
| `clinical` | confirmatory | conduct a **study** (RCT / cohort / case-control / cross-sectional / diagnostic) | CONSORT / STROBE / STARD (by design) | **YES** — protocol + SAP frozen, registered (ClinicalTrials.gov), IRB-approved |
| `systematic-review` | confirmatory | screen → extract → synthesize | PRISMA 2020 | **YES** — protocol registered (PROSPERO) before screening |

## Two cross-cutting process rules (all tracks)

### A. analysisMode: confirmatory vs exploratory
- **exploratory** (ml/bioinformatics default): iterate freely — adjust, re-run, compare, optimize toward a target. The existing `/omp:experiment` loop applies.
- **confirmatory** (clinical/SR default): run the **pre-specified** analysis from the frozen SAP **once** and report whatever you get. Do **not** re-run-until-significant — that is p-hacking. Any change from the plan is logged in `.pipeline/memory/protocol_deviations.md`; any unplanned finding is explicitly labeled *exploratory / hypothesis-generating* and never reported as confirmatory.

### B. Figures early and often — never defer to publication
**Every stage has at least one figure deliverable.** A study-flow diagram, schematic, or main-result plot built late is a late discovery of missing data. Add a figure `task_blueprint` (taskType `figure`, skill `inno-figure-gen`) to each active stage and a `quality_gate` line "stage figure(s) produced and current". Per-track figure timeline below.

## Per-track detail

### `ml`
- **analysisMode**: exploratory. Standard hyperparameter/ablation loop.
- **Figures early**: experiment → training/validation curves and ablation bars *as each run lands*; publication → finalize/polish.
- **No hard gate.**

### `bioinformatics`
- **analysisMode**: exploratory, but **pin versions** (tools, reference genome/build, databases) in the brief; a pipeline that can't be re-run is not a result.
- **experiment** = pipeline runs, usually remote — see `bioinformatics-init-analysis` + `remote-experiment`.
- **Figures early**: experiment → QC report (e.g. MultiQC), PCA/UMAP, volcano/heatmap *as the pipeline progresses*; publication → finalize.
- **quality_gate (publication)**: tool + reference/DB versions reported; pipeline reproducible; raw data deposited (GEO/SRA) where applicable.

### `clinical`
- **analysisMode**: confirmatory (unless the user states the work is exploratory/pilot).
- **Stage meaning**: ideation = sharpen the question (PICO/FINER) and choose a design; experiment = run the **study** (design → conduct → analysis); use `clinical-study-design`.
- **HARD GATE (in the experiment stage).** The planner inserts one gate task and makes every conduct/analysis task `dependsOn` it:
  ```json
  { "id": "experiment_lock_and_register",
    "title": "Lock protocol + SAP, register on ClinicalTrials.gov, obtain IRB/IEC approval",
    "taskType": "gate",
    "recommended_skills": ["clinical-study-design"] }
  ```
  No data collection or analysis task may start until this gate is `done`. `/omp:experiment`, `/omp:plan`, and the Conductor must refuse to advance otherwise.
- **Figures early**: ideation/design → study-design schematic + a blank CONSORT/PRISMA/STROBE flow skeleton; experiment(conduct) → flow diagram filled with **real** screening/enrollment counts as they accrue; analysis → primary-outcome figure (Kaplan–Meier / forest / effect plot); publication → finalize.
- **quality_gate (publication)**: registration number present; the design's reporting checklist complete (CONSORT/STROBE/STARD); ethics + informed-consent statement; data-availability statement; flow diagram with real counts. Verify via `clinical-study-design` and `scientific-writing` references.

### `systematic-review`
- **analysisMode**: confirmatory. Use `systematic-review`.
- **Stage meaning**: survey = the SR search itself; experiment = screen → extract → risk-of-bias → synthesis (meta-analysis if poolable); publication = PRISMA write-up.
- **HARD GATE**: register the protocol on **PROSPERO** and lock eligibility + search strategy **before** screening:
  ```json
  { "id": "survey_register_protocol",
    "title": "Register review protocol on PROSPERO; lock PICO, eligibility, and search strategy",
    "taskType": "gate",
    "recommended_skills": ["systematic-review"] }
  ```
  Screening/extraction tasks `dependsOn` it.
- **Figures early**: survey/screening → PRISMA flow diagram whose counts accrue during screening (not drawn at the end); synthesis → forest + funnel plots; publication → finalize.
- **quality_gate (publication)**: PROSPERO id; PRISMA 2020 checklist + flow diagram; risk-of-bias completed (RoB 2 / ROBINS-I / QUADAS-2); GRADE certainty per outcome.

## How the planner uses this
1. Read `pipeline.track` (default `ml`) and set `pipeline.analysisMode`.
2. When building each active stage's `task_blueprints` and `quality_gate`, layer in this track's items — including the **figure** blueprint and, for clinical/SR, the **gate** task with the dependency wiring.
3. Keep titles topic-specific; keep the gate and figure tasks verbatim in intent.
