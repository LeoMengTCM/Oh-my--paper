---
id: research-literature-trace
name: Research Literature Trace
description: Use for survey or ideation work that needs literature collection, screening, source tracing, canonical paper URLs, or gap summaries.
version: 1.0.0
stages: [survey, ideation]
tools: [read_file, search_project, write_file]
---

# Research Literature Trace

Use this skill for literature collection, screening, and source tracing.

## Goals

- collect traceable papers and canonical links
- identify representative baselines and gaps
- write reusable notes into the survey-stage workspace

## Working Rules

1. Prefer official publisher pages, DOI resolvers, conference proceedings, or trusted indexes.
2. Keep claims tied to an explicit source path or URL.
3. Record short screening notes rather than long prose.
4. Mark uncertainty explicitly when a source cannot be verified.
5. Each paper entry in `paper_bank.json` **MUST** include a `url` field pointing to the real paper page (prefer DOI link `https://doi.org/...`; fallback to Semantic Scholar, arXiv, or publisher page). Never leave `url` empty.
6. The `authors` field in `paper_bank.json` **MUST** be an array of strings (e.g. `["Alice", "Bob"]`), never a single string like `"TBD"`.
7. For every markdown artifact (e.g. `domain_map.md`), generate **both** a Chinese version (`domain_map.zh.md`) and an English version (`domain_map.en.md`) alongside the main file, unless the user specifies the output languages. 叙述性综述按 `../inno-pipeline-planner/references/narrative-review-profile.md` 保留稿件语言和内部记录语言，不强制双语副本。
8. 缺少研究说明或任务文件时先执行 setup。正式 `narrative-review` 及旧研究类型字段均读取上述共享规则；保留实际检索日志和资料获取状态，不把精选阅读表作为正式 PRISMA 计数。

## Expected Outputs

- literature shortlist with URLs
- screening notes
- gap summary for ideation

For a Codex OMP project, follow `../omp/SKILL.md` for stage checks and completion.
Before reporting survey complete, verify the actual source records, existing-review
overlap, representative original studies, reading scope and unresolved questions.
Register the actual artifact paths and completionSummary on the survey task.
If the user requested the full workflow, prepare and execute the authorized ideation
handoff; if only survey was requested, name the concrete next task without exceeding
that scope. Do not require another reminder to follow OMP.
