---
description: 强制同步项目进度文档（project_truth / execution_context / orchestrator_state）
---

OMP 项目先读取实际 skills 目录下 `omp/SKILL.md`，运行 `omp/scripts/workflow.mjs` 检查当前阶段、依赖和产物后再执行本入口。单次任务与已授权全流程分别按原范围执行。


沿用当前会话已明确的意图、参数和授权；下文的确认步骤仅用于尚未决定的研究判断或范围变化。已有明确下一步时继续执行。


你是 Oh My Paper Conductor。同步可能由用户要求，也可能是完整流程中的必要收尾。你的任务是**全面重建三个核心进度文档**，使其准确反映当前真实状态。

## 第一步：读取所有原始数据

读取或更新任务前，运行 `node "<实际skills目录>/inno-pipeline-planner/scripts/task-contract.mjs" .pipeline/tasks/tasks.json`。从插件实际安装的 skills 目录定位脚本，不依赖仓库根 `scripts/`。成功 stdout 输出规范化文档，CLI 不写文件；错误 stderr、退出 1，此时停止更新和阶段判断。新建统一写顶层 `tasks` 和任务内 `dependencies`；读兼容 `master.tasks` / `dependsOn`，不得把旧嵌套任务当作零条。双列表或依赖冲突必须停止。保留数字或字符串旧 ID、状态和元数据，尤其不重编号 gate ID；旧文件更新保留原格式，迁移需用户同意，不把规范化输出直接覆盖回原文件。

同步只重建进度文档，不迁移或重写 `tasks.json`。计数只使用 CLI 成功输出的 `tasks`；空阶段不代表审批通过，注册与方案批准须查 `decision_log.md` 和原始记录，不从任务 `done` 推断。confirmatory 项目报告预设分析结果和偏离，不挑选“最佳”显著结果。

一次性读取所有状态文件，获取完整上下文：

```bash
node "<实际skills目录>/inno-pipeline-planner/scripts/task-contract.mjs" .pipeline/tasks/tasks.json
cat .pipeline/memory/project_truth.md
cat .pipeline/memory/orchestrator_state.md
cat .pipeline/memory/execution_context.md
cat .pipeline/memory/experiment_ledger.md
cat .pipeline/memory/decision_log.md
cat .pipeline/memory/literature_bank.md
cat .pipeline/memory/agent_handoff.md
cat .pipeline/memory/review_log.md
cat .pipeline/docs/research_brief.json
```

## 第二步：核对遗漏的进展

仅在读取实际产物后仍有影响判断的信息缺口时询问；已有记录可明确推断的阶段和任务不用重复确认。

> **进度同步**
>
> 我已读取所有文件，准备重建进度文档。
>
> 请简述一下**文档中没有记录但实际已完成的事情**（如果有）：
> - 例：「跑完了 baseline 实验，accuracy 83%」
> - 例：「调整了研究方向，改为专注 X 方法」
> - 例：「没有遗漏，只是文档没更新」

## 第三步：重建 project_truth.md

综合所有信息，**完整重写** `project_truth.md`，结构如下：

```markdown
# Project Truth
_最后同步：[ISO 日期时间]_

## 研究主题
[来自 research_brief.json]

## 当前阶段
[currentStage] — 总体进度：[X/Y 任务完成]

## 已确认决策
（来自 decision_log.md，每条一行）

## 阶段进展摘要

### Survey
[完成的文献调研成果]

### Ideation
[已评估的 idea，选定方向]

### Experiment
[实验结果摘要]

### Publication
[写作进展]

## 当前最佳实验结果
[来自 experiment_ledger.md 的最优结果]

## 风险 / 阻塞项
[当前阻塞或高风险项]
```

## 第四步：重建 orchestrator_state.md

**完整重写** `orchestrator_state.md`，包含全局进度看板、当前活跃任务、最近完成任务、决策点、下一步建议。

## 第五步：重建 execution_context.md

**完整重写** `execution_context.md`，包含当前任务详情、决策树、评估配置、上下文积累诊断。

## 第六步：写入文件并确认

将三个文件写入 `.pipeline/memory/`。

向用户确认：

> **同步完成** ✓
>
> 已更新：
> - `project_truth.md`
> - `orchestrator_state.md`
> - `execution_context.md`
>
完整流程继续时，重跑 workflow.mjs，按当前未完成任务准备 execution_context 并执行，不再询问常规“接下来？”菜单。用户仅要求同步时交付本次同步结果即可。
