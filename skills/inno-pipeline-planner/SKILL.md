---
id: inno-pipeline-planner
name: inno-pipeline-planner
version: 1.0.0
description: |-
  Guides the user through an interactive conversation to define their research project, then generates research_brief.json and tasks.json.
stages: ["ideation"]
tools: ["read_file", "search_project", "write_file"]
summary: |-
  Guides the user through an interactive conversation to define their research project, then generates research_brief.json and tasks.json. Use when starting a new project, when no research_brief.json exists, when the user wants to start from...
primaryIntent: research
intents: ["research", "experiment"]
capabilities: ["research-planning", "agent-workflow"]
domains: ["general"]
keywords: ["inno-pipeline-planner", "research-planning", "agent-workflow", "inno", "pipeline", "planner", "guides", "user", "through", "interactive", "conversation", "define"]
source: builtin
status: verified
upstream:
  repo: dr-claw
  path: skills/inno-pipeline-planner
  revision: 8322dc4ef575affaa374aa7922c0a0971c6db7d7
resourceFlags:
  hasReferences: true
  hasScripts: true
  hasTemplates: false
  hasAssets: false
  referenceCount: 4
  scriptCount: 1
  templateCount: 0
  assetCount: 0
  optionalScripts: false
---

# inno-pipeline-planner

## Canonical Summary

Guides the user through an interactive conversation to define their research project, then generates research_brief.json and tasks.json. Use when starting a new project, when no research_brief.json exists, when the user wants to start from...

## Trigger Rules

Use this skill when the user request matches its research workflow scope. Prefer the bundled resources instead of recreating templates or reference material. Keep outputs traceable to project files, citations, scripts, or upstream evidence.

## Resource Use Rules

- Read from `references/` only when the current task needs the extra detail.

## Execution Contract

- Resolve every relative path from this skill directory first.
- Prefer inspection before mutation when invoking bundled scripts.
- If a required runtime, CLI, credential, or API is unavailable, explain the blocker and continue with the best manual fallback instead of silently skipping the step.
- Do not write generated artifacts back into the skill directory; save them inside the active project workspace.

## Upstream Instructions

# Inno Pipeline Planner

Run an interactive planning flow that turns user conversation into:
- `.pipeline/docs/research_brief.json`
- `.pipeline/tasks/tasks.json`

Keep this file short. Load full schemas and field-level rules from:
- `references/pipeline-contract.md` (index)

Read only what you need:
- `references/generation-rules.md`: generation logic, ordering, dependencies, `nextActionPrompt`
- `references/track-profiles.md`: per-track stage meaning, hard gates, figure timeline, analysisMode
- `references/brief-schema.md`: `.pipeline/docs/research_brief.json` contract
- `references/tasks-schema.md`: `.pipeline/tasks/tasks.json` contract

## Non-negotiables

- Work only inside the current project directory.
- Do not fabricate papers, datasets, metrics, or results.
- Ask follow-up questions when information is vague; do not guess.
- Ask in small batches (2-3 questions), not a long static form.

## Workflow

## 1) Inspect existing pipeline state

先按 `references/tasks-schema.md` 运行 `node "<实际skills目录>/inno-pipeline-planner/scripts/task-contract.mjs" .pipeline/tasks/tasks.json`（仅在任务文件存在时）。本技能内脚本相对路径是 `scripts/task-contract.mjs`，不依赖仓库根脚本。成功 stdout 为规范化文档且不写文件；错误 stderr、退出 1，此时停止任务更新与阶段判断。新建写顶层 `tasks` / `dependencies`；读兼容 `master.tasks` / `dependsOn`，不得当作零条。双列表或依赖冲突停止；保留数字或字符串旧 ID、状态和元数据，不自动迁移用户文件。

Check:
- `.pipeline/docs/research_brief.json`
- `.pipeline/tasks/tasks.json`
- `instance.json` (legacy source)
- Content in `Survey/`, `Ideation/`, `Experiment/`, `Publication/`, and `Promotion/` directories (to detect pre-existing artifacts)

If brief exists, summarize title, goal, current `startStage`, and completion status, then ask:
- Refine existing brief/tasks
- Regenerate from scratch
- Change the starting stage

## 2) Collect project context via conversation

Capture at least:
- Topic/problem
- Goal or hypothesis
- Success criteria or evaluation signal
- Current survey depth or known reference set

**Determine the starting stage** early in the conversation:
- Ask what the user already has: "Do you already have a research idea, experimental results, or are you starting from scratch?"
- If the user mainly needs literature review, gap analysis, or reference collection -> `startStage = "survey"`
- If the user has a concrete idea with problem framing and success criteria -> `startStage = "experiment"`
- If the user has experimental results and analysis -> `startStage = "publication"`
- If the user already has a paper/manuscript and mainly needs a homepage, slide deck, narration, or demo assets -> `startStage = "promotion"`
- If the user is starting from scratch or only has a vague direction -> `startStage = "survey"` (default)
- Detect automatically from conversation context (e.g., "I already ran all experiments" implies publication; "I need slides for my paper" implies promotion).

**Determine the track** (`pipeline.track`, default `ml`): is this machine-learning/CS, **clinical** (human studies), a **systematic-review / meta-analysis**, or **bioinformatics**? It sets `analysisMode`, hard gates, the figure timeline, and quality gates — see `references/track-profiles.md`. When the topic is biomedical and the track is ambiguous, ask one question rather than guessing.

Typical question buckets:
- Project identity: topic, prior paper/method/dataset, target venue (optional)
- Scope and method: core question, approach, expected outcome
- Evaluation: data source, metrics/protocol, baseline expectations

Adapt to context:
- Skip already-provided details.
- **Skip questions for stages before `startStage`**: If starting from experiment, do not ask survey or ideation questions in detail — just capture a brief summary of the existing context in those sections.
- If exploratory, keep experiment/publication/promotion sections lightweight.
- If user provides concrete plan, prepare for `pipeline.mode = "plan"`; otherwise use `"idea"`.

## 3) Write pipeline files

Create if missing:
- `.pipeline/config.json`
- `.pipeline/docs/research_brief.json`
- `.pipeline/tasks/tasks.json`

Use the exact JSON contracts and generation rules in:
- `references/pipeline-contract.md` and linked reference files

Rules:
- Set `pipeline.startStage` to the determined starting stage (default: `"survey"`).
- **Generate tasks only for stages >= `startStage`** in the stage order (survey < ideation < experiment < publication < promotion).
- For skipped stages: still populate their `sections.*` fields in the brief with whatever context the user provided, but do not create task blueprints or tasks for them.
- Tailor blueprint titles/descriptions to the user topic (never generic filler).
- Keep quality gates domain-appropriate.
- Resolve recommended skills from local available skills (`.agents/skills/` or `skills/`), optionally using `stage-skill-map.json` if present.

## 4) Summarize and confirm next action

After writing files, present:
- Brief summary (title, goal, starting stage, filled vs missing sections)
- Task overview (count by stage + first 2-3 task titles per stage) — only for active stages
- Recommended first task and why

## 5) Handle iteration requests

If user asks for updates:
- Update brief content directly when only text/content changes.
- 用户同意后才按结构/蓝图/阶段变化重新生成任务；保留旧任务 ID（含 gate ID）、状态和元数据，不自动迁移旧格式。
- 修改起始阶段不等于已经通过前置审批；systematic-review 按实际 skills 目录下 `systematic-review/references/rct-pairwise-profile.md` 核验批准记录，再规划活跃阶段。
- 只添加一个任务时追加未占用的 ID，兼容旧数字或字符串 ID，不重编号已有任务。
