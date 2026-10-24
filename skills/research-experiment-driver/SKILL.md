---
id: research-experiment-driver
name: Research Experiment Driver
description: Use when the project is ready to translate a selected research idea into executable experiment plans, implementation tasks, metrics, and ablations.
version: 1.0.0
stages: [experiment]
tools: [read_file, write_file, run_terminal]
---

# Research Experiment Driver

Use this skill when the project is ready to translate ideas into executable experiment work.

## Goals

- turn the chosen idea into implementation tasks
- define datasets, metrics, ablations, and failure checks
- keep implementation notes aligned with the paper claims

## Working Rules

1. Read the current brief and completed survey or ideation artifacts before drafting the plan.
2. Keep experiment plans falsifiable and measurable.
3. Separate implementation tasks from analysis tasks.
4. Do not claim results before they exist in the project.
5. In a Codex OMP project, read `../omp/SKILL.md` and run its task preflight.
   在任一宿主中，`pipeline.track = narrative-review` 或旧
   `projectContext.researchType` / `articleType`、根级同名字段标为叙述综述时，
   先读 `../inno-pipeline-planner/references/narrative-review-profile.md`。
   本阶段整合论断、来源、相互矛盾的证据与局限，不执行训练、消融或自动 Meta 分析，
   不默认要求临床试验注册、IRB 或 PRISMA。
6. On completion, register artifacts and completionSummary, update result_summary
   and the handoff, then route the next authorized writing task. Missing evidence
   returns to retrieval/analysis rather than being filled by the writer.

## Expected Outputs

- experiment task decomposition
- implementation checklist
- analysis checklist tied to the target claims
