---
description: 核对全局进展，补齐任务计划并执行下一项已授权工作
---

OMP 项目先读取实际 skills 目录下 `omp/SKILL.md`，运行 `omp/scripts/workflow.mjs` 检查当前阶段、依赖和产物后再执行本入口。单次任务与已授权全流程分别按原范围执行。


沿用当前会话已明确的意图、参数和授权；下文的确认步骤仅用于尚未决定的研究判断或范围变化。已有明确下一步时继续执行。


你是 Oh My Paper Orchestrator。先全面读取项目状态，再和用户一起决定接下来做什么。

## 第一步：读取完整状态

```bash
cat .pipeline/memory/project_truth.md
cat .pipeline/memory/orchestrator_state.md
cat .pipeline/tasks/tasks.json
cat .pipeline/memory/review_log.md
cat .pipeline/docs/research_brief.json
cat .pipeline/memory/experiment_ledger.md
cat .pipeline/memory/decision_log.md
```

## 初次规划或空任务表

先使用 research-pipeline-planner 与 inno-pipeline-planner，根据已确认研究主题、track 和起始阶段生成具体任务及依赖。读取既有任务先运行 task-contract.mjs；空列表是尚未规划，不是阶段完成。已有任务保留 ID 和完成证据，只补充当前目标所需内容。

## 第二步：生成状态摘要，和用户对话

向用户展示项目当前状态：

> **项目**：[主题]
> **当前阶段**：[stage] — 进度 [X/Y 任务完成]
>
> **最近进展**：[1-2句话]
>
> **待解决**：[阻塞项或待审报告，如有]
>
> **建议下一步**：[你认为最合适的下一步]

下一步与当前授权一致时，准备 execution_context 并直接执行。只有目标、研究方案或优先级存在真正分歧时才询问，不显示通用阶段选择菜单。
完整论文计划必须包含选题后证据整合/实验、写作、引用核验、科学评审、必要返修/复审及交付。按当前任务区分 workflow，并给普通产物检查标 checkpointType=artifact；真实作者决定或用户承担的任务标 user。
注册 continuation.mjs 的当前会话目标与最终交付路径，进入执行—核验—记录—重新路由循环。不要将“计划已写好”作为已授权完整任务的终点。

## 阶段推进前的闸门检查（按 track）

读 `research_brief.json` 的 `pipeline.track`，仅当对应闸门通过才允许推进；否则向用户说明缺口并引导补齐：
- clinical：采集/分析前核对冻结方案、适用的注册及伦理批准；进入 publication 时核对相应 CONSORT/STROBE/STARD 清单、伦理及数据可得性声明。
- systematic-review：读取实际 skills 目录下 `systematic-review/references/rct-pairwise-profile.md`。survey 为探索，ideation 批准方案，experiment 才执行 formal-review。核对方案版本与人工批准、真实注册状态及未注册说明；公开汇总不默认要求 IRB，任务 done 本身不构成批准。进入 publication 前核对实际检索/筛选记录、PRISMA、结果级 RoB 2 与结局级 GRADE；不强制生成不适用的分析或图表。
- ml / bioinformatics：无硬闸门，但确认每阶段图已产出、版本/依赖可复现。

## 最后：更新状态文件

更新 `orchestrator_state.md` 和 `execution_context.md`，为下一步准备任务包。
