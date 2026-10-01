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
| `systematic-review` | confirmatory | formal search → screen → extract → synthesize | PRISMA 2020 | 具体方案版本获研究者批准，注册状态如实记录；见 RCT profile |

## Two cross-cutting process rules (all tracks)

### A. analysisMode: confirmatory vs exploratory
- **exploratory** (ml/bioinformatics default): iterate freely — adjust, re-run, compare, optimize toward a target. The existing `/omp:experiment` loop applies.
- **confirmatory**（clinical/SR 默认）：按已批准的 SAP 如实报告，不为追求显著性更换方案。允许有记录的错误修复后重跑、确定性复现与预设敏感性分析。方法变更须先获研究者批准，再记入 `.pipeline/memory/protocol_deviations.md`；计划外分析标为 exploratory / hypothesis-generating，不混入预设结果。

### B. Figures early and often — never defer to publication
**systematic-review 例外**：按 RCT profile 规划适用图表，不强制每阶段一图或不适用的分析；数据图使用真实数据和分析代码。其他 track 沿用下述图表规划规则。
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
- **HARD GATE (in the experiment stage).** The planner inserts one gate task and makes every conduct/analysis task reference it in `dependencies`:
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
- **analysisMode**：缺省 confirmatory；exploratory-search 与分析模式是不同概念。
- **共享规则**：读取实际 skills 目录下 `systematic-review/references/rct-pairwise-profile.md`。它是 RCT 干预疗效综述的入口、批准、注册与分析边界的共同来源；其他综述类型先确认方法学方案。
- **阶段**：survey = 探索；ideation = PICO、检索策略、SAP 与具体版本的研究者批准；experiment = 正式检索/导入 → 筛选 → 研究归并 → 提取 → RoB 2 → 合成；publication = GRADE 与 PRISMA 写作。
- **前置任务**：保留既有 `survey_register_protocol` 等 ID，不自动重编号。新项目可在 ideation 生成如下任务，正式检索/筛选任务的 `dependencies` 指向它：
  ```json
  { "id": "survey_register_protocol",
    "stage": "ideation",
    "title": "批准具体版本的 PICO、检索策略与 SAP，如实登记注册状态",
    "status": "pending",
    "taskType": "gate",
    "dependencies": [],
    "suggestedSkills": ["systematic-review"] }
  ```
- **证据检查**：done 不等于批准；必须核对 `protocol.md`、`sap.md` 和 `decision_log.md` 中的版本、批准者与时间。注册状态可为 planned/submitted/registered/not_registered/not_applicable；未注册需说明并由用户确认，不编造 PROSPERO 号。公开汇总数据不默认要求 IRB。
- **图与报告**：PRISMA 计数来自实际 records/reports/studies；只做适用分析和图，不能强制漏斗图。RoB 2 按具体结果，GRADE 按结局。没有可合并证据时允许叙述性综合。

## How the planner uses this
1. Read `pipeline.track` (default `ml`) and set `pipeline.analysisMode`.
2. When building each active stage's `task_blueprints` and `quality_gate`, layer in this track's items — including the **figure** blueprint and, for clinical/SR, the **gate** task with the dependency wiring.
3. Keep titles topic-specific; keep the gate and figure tasks verbatim in intent.
