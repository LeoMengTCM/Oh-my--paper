---
id: research-paper-handoff
name: Research Paper Handoff
description: Use when the workflow moves into paper writing, publication delivery, LaTeX handoff, figure/reference insertion, or promotion follow-up.
version: 1.0.0
stages: [publication, promotion]
tools: [read_file, write_file]
---

# Research Paper Handoff

Use this skill when the workflow moves into writing or delivery.

## Goals

- convert validated research state into a paper-writing checklist
- map claims, figures, and references into the LaTeX workspace
- prepare follow-up deliverables such as slides or summaries

## Working Rules

1. Use the project's actual manuscript format and location as canonical; do not
   force a Markdown/Word narrative review into a LaTeX conference layout.
2. Keep handoff notes compact and directly actionable.
3. Link each writing task to the evidence or artifact it depends on.
4. Do not rewrite the whole manuscript unless the user asks.
5. In Codex, follow `../omp/SKILL.md` for task-based routing. Separate draft, integrity audit,
   scientific review, revision, re-review and submission-readiness tasks. Link review
   and revision records to the current manuscript version and preserve issue IDs.
6. A review report can be complete with unresolved manuscript issues. Add the required
   repair/evidence tasks and recheck before delivery; do not jump directly to promotion.
7. Continue already-authorized downstream work without another workflow reminder.
   Promotion and actual external submission/upload are not automatic consequences
   of completing a manuscript.

## Expected Outputs

- publication-stage checklist
- figure/reference insertion reminders
- promotion-stage follow-up tasks when requested
