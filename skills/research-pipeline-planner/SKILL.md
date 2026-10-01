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
5. OMP 的 ideation 使用 `omp/references/omp-ideate.md`：五方向 idea board → 用户确认评估范围 → inno-idea-eval → 用户最终选题。不得被独立 `research-idea-convergence` 的 2–4 候选流程替换；仅在用户明确选择轻量比较时使用后者。systematic-review 按 RCT profile 制定和批准 PICO/方案/SAP，不强制生成五个创新点。
6. 在 Codex 的 OMP 全流程任务中先读 `../omp/SKILL.md`，执行其只读 workflow preflight；按当前状态与产物路由，不能仅凭“选题”等词跳阶段。阶段产物须评审；已授权的流程推进不反复询问角色或阶段，只有选定方向、方案批准等实质研究决策需要用户确认。单独请求规划时尊重该范围。
7. **严格线性执行**：任务必须按顺序执行，当前任务未完成前不得跳至下一任务。调研未完成 → 不得进入构思；构思未完成 → 不得进入实验。每个阶段的所有任务 done 后才能进入下一阶段。
8. **确定 `pipeline.track`**（ml / clinical / systematic-review / bioinformatics；缺省 ml）并据此设 `pipeline.analysisMode`。clinical/systematic-review 默认 **confirmatory**：按预设计划分析、如实报告，不为显著性改方案；允许错误修复后重跑，记录原因和偏离。细节见实际 skills 目录下 `inno-pipeline-planner/references/track-profiles.md`。
9. **硬闸门（clinical / systematic-review）**：保留既有 gate ID，以 `dependencies` 声明前置门；clinical 核验适用的方案、注册与伦理要求。systematic-review 读取实际 skills 目录下 `systematic-review/references/rct-pairwise-profile.md`：survey 探索，ideation 批准 PICO/方案/SAP，experiment 正式检索筛选合成，之后 publication、promotion。`done` 不是审批证据，核验 `decision_log.md` 中的用户批准与方案版本；注册状态按 `planned` / `submitted` / `registered` / `not_registered` / `not_applicable` 如实记录，未注册需用户说明确认但不绝对阻断，公开汇总数据不默认 IRB。
10. **作图尽早**：提前规划适用的流程图与结果图；systematic-review 不为满足阶段数量强制图表或额外分析。数据图由分析代码生成，不交给图像生成模型。

## Expected Outputs

读取任务先运行 `node "<实际skills目录>/inno-pipeline-planner/scripts/task-contract.mjs" .pipeline/tasks/tasks.json`，路径从实际安装的 skills 目录解析，不依赖仓库根脚本。成功 stdout 为规范化文档，不写文件；错误 stderr、退出 1，停止更新和阶段判断。新文件写顶层 `tasks` 和任务内 `dependencies`，读兼容 `master.tasks` / `dependsOn`，旧嵌套任务不可计为零条。双列表或依赖冲突停止；保留数字或字符串旧 ID、状态和元数据，旧文件更新保留原格式，迁移或重建需用户同意。详见同目录下 `inno-pipeline-planner/references/tasks-schema.md`。

- a concise research brief with topic, goal, venue, current stage, and stage notes
- a task list with dependencies, suggested skills, and a concrete `nextActionPrompt`
- ideation：OMP 交付五方向 idea board、评估范围、idea eval 和用户选定的方向；systematic-review 交付经研究者确认的 PICO/方案/SAP，不要求 `publishable_angle.md`
