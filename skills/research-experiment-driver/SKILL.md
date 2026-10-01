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
5. In a Codex OMP project, read `../omp/SKILL.md` and run its task preflight. Respect
   `projectContext.researchType`/articleType: for narrative-review, integrate claims,
   sources, competing evidence and limitations instead of designing training runs.
6. On completion, register artifacts and completionSummary, update result_summary
   and the handoff, then route the next authorized writing task. Missing evidence
   returns to retrieval/analysis rather than being filled by the writer.

## Expected Outputs

- experiment task decomposition
- implementation checklist
- analysis checklist tied to the target claims
