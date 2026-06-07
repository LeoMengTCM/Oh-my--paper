---
id: research-pipeline-planner
name: Research Pipeline Planner
description: Use when the user needs to define, initialize, revise, or checkpoint the project-level research pipeline and stage task plan.
version: 1.0.0
stages: [survey, ideation, experiment, publication, promotion]
tools: [read_file, write_file, update_pipeline]
---

# Research Pipeline Planner

Use this skill when the user needs to define or revise the project-level research pipeline.

## Goals

- clarify the research topic, target venue, and expected contribution
- set or revise the starting stage
- update `.pipeline/docs/research_brief.json`
- update `.pipeline/tasks/tasks.json`

## Working Rules

1. Read `instance.json`, `.pipeline/docs/research_brief.json`, and `.pipeline/tasks/tasks.json` first if they exist.
2. Keep the pipeline aligned with the five stages: survey, ideation, experiment, publication, promotion.
3. When the user already has results or a draft, move the starting stage forward instead of rebuilding earlier stages.
4. Do not invent citations, datasets, or experimental outcomes.
5. **When entering ideation stage, use the `research-idea-convergence` skill** to generate candidate directions and let the user choose. Never autonomously decide the research direction.
6. Ensure every stage transition involves a user checkpoint — do not skip stages or auto-advance without user confirmation.
7. **严格线性执行**：任务必须按顺序执行，当前任务未完成前不得跳至下一任务。调研未完成 → 不得进入构思；构思未完成 → 不得进入实验。每个阶段的所有任务 done 后才能进入下一阶段。
8. **确定 `pipeline.track`**（ml / clinical / systematic-review / bioinformatics；缺省 ml）并据此设 `pipeline.analysisMode`。clinical/systematic-review 为 **confirmatory**：按冻结计划跑一次、如实报告，不迭代到达标。细节见 `inno-pipeline-planner/references/track-profiles.md`。
9. **硬闸门（clinical / systematic-review）**：在锁定/注册门任务（方案+SAP 冻结、已注册 ClinicalTrials.gov/PROSPERO、过 IRB）`done` 之前，任何数据采集/分析（clinical）或筛选/提取（systematic-review）任务都不得开始；用任务依赖接线。
10. **作图尽早**：每个活跃阶段都要有图产出（`inno-figure-gen`）——流程图/示意图/主结果图边做边出，绝不憋到发表阶段。

## Expected Outputs

- a concise research brief with topic, goal, venue, current stage, and stage notes
- a task list with dependencies, suggested skills, and a concrete `nextActionPrompt`
- for ideation: candidate directions presented via `research-idea-convergence` before any `publishable_angle.md` is written
