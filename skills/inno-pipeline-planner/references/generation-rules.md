# Generation Rules

Shared rules for generating pipeline files.

## Directory layout

```text
.pipeline/
  config.json
  docs/
    research_brief.json
  tasks/
    tasks.json
```

## `.pipeline/config.json`

Create when missing:

```json
{
  "version": "1.0",
  "provider": "dr-claw-web",
  "initializedAt": "<ISO timestamp>"
}
```

## Brief generation rules

- Fill content from user conversation and existing project files only.
- Leave unknown fields as empty string or empty array.
- Set `pipeline.mode`:
  - Use `"plan"` when user provides concrete method/architecture/training plan.
  - Use `"idea"` otherwise.
- Set `pipeline.startStage`:
  - Use `"survey"` (default) when user is starting from scratch or needs literature review first.
  - Use `"ideation"` when the user already has enough literature context and needs to shape a direction.
  - Use `"experiment"` when user already has a research idea, problem framing, and success criteria.
  - Use `"publication"` when user already has experimental results and analysis.
  - Use `"promotion"` when user already has a manuscript or publication draft and mainly needs presentation or dissemination assets.
- Set `pipeline.track` (default `"ml"`) and derive `pipeline.analysisMode` from it — see `track-profiles.md`. The track decides stage interpretation, hard gates, figure timeline, and quality-gate contents.
- Make `task_blueprints` and `quality_gate` domain-specific to the topic.
- For skipped stages (before `startStage`): still populate `sections.*` with whatever context the user provided, but `task_blueprints` in those stages will not produce tasks.

## Task generation rules

Stage order: `survey` < `ideation` < `experiment` < `publication` < `promotion`.

1. **Only generate tasks for stages >= `pipeline.startStage`**. Skip earlier stages entirely during task generation.
2. Create tasks from each active stage's `task_blueprints`.
3. Create define/refine tasks for each `required_element` in active stages:
   - Use `Define <field>` when empty.
   - Use `Refine <field>` when already populated.
4. Add one quality-gate review task at the end of each active stage with `quality_gate`.
5. Order tasks by execution flow:
   - exploration -> implementation -> analysis -> writing -> scripting/rendering/narration/delivery
6. Add dependencies when obvious (for example, implementation depends on exploration in the same stage).
7. **作图尽早**：按 `track-profiles.md` 规划适用的图，不把数据图交给图像生成模型。systematic-review 以实际研究步骤为准，不为每阶段凑图或增加未批准分析。
8. **硬闸门（clinical / systematic-review）**：保留既有 gate ID，用 `dependencies` 声明前置门。clinical 按适用的方案、注册和伦理要求执行；systematic-review 按实际 skills 目录下 `systematic-review/references/rct-pairwise-profile.md` 执行：survey 探索，ideation 批准 PICO/方案/SAP，experiment 正式检索、筛选、提取与合成，之后 publication、promotion，五阶段不变。门任务 `done` 不是审批证据，必须核验 `decision_log.md` 中的用户批准及对应方案版本。注册状态如实记录为 `planned` / `submitted` / `registered` / `not_registered` / `not_applicable`；未注册须由用户说明并确认，不绝对阻断，公开汇总数据不默认要求 IRB。
9. **analysisMode**：clinical/systematic-review 默认 `confirmatory`，按预设分析生成任务，不生成“迭代到显著”任务；允许修复错误后重跑并记录原因，计划外分析另列为探索性分析。
10. **任务契约**：新文件写顶层 `tasks` 和任务内 `dependencies`；按 `tasks-schema.md` 调用实际 skills 目录下 `inno-pipeline-planner/scripts/task-contract.mjs` 只读校验。读兼容 `master.tasks` / `dependsOn`，保留数字或字符串旧 ID、状态与元数据；双列表或依赖冲突即停止，不自动迁移或重编号。

## `nextActionPrompt` template

```text
Task: <task title>
Stage: <stage>
User inputs: <relevant extracted values from research_brief.json>
Suggested skills: <comma-separated skills>
Quality gate: <gate items if relevant>
Stage guidance: <short stage-specific instruction>
Please produce a concrete next-step plan and execution output. If user inputs are provided, polish and make them concrete, then write updates back to .pipeline/docs/research_brief.json.
```
