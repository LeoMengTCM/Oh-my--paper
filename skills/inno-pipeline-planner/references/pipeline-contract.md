# Pipeline Contract Index

Use this index to load only the minimum required context.

## Read order

1. Read `generation-rules.md` for shared logic and constraints.
2. Read `track-profiles.md` to resolve `pipeline.track` (stage meaning, hard gates, figure timeline, quality gates, analysisMode).
3. Read `brief-schema.md` when creating/updating `.pipeline/docs/research_brief.json`.
4. Read `tasks-schema.md` when creating/updating `.pipeline/tasks/tasks.json`.

## Files

- `generation-rules.md`: directory layout, `.pipeline/config.json`, mode selection, task generation logic, `nextActionPrompt`
- `track-profiles.md`: per-track (ml / clinical / systematic-review / bioinformatics) stage interpretation, hard gates, figure timeline, confirmatory-vs-exploratory analysisMode
- `brief-schema.md`: canonical `research_brief.json` structure
- `tasks-schema.md`: canonical `tasks.json` structure
