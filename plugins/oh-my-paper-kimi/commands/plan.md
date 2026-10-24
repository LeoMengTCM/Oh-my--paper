---
name: plan
description: 审视全局进展，以问答形式确认下一步方向，更新研究计划
---

> **确认或选择类步骤用 AskUserQuestion 工具。构造调用时务必：①每个 question 带齐 question、header(不超过12字)、options(2到4项，每项含 label 与 description)、multiSelect 字段，缺任一个都会报 Invalid tool parameters；②字段全部用纯文本加半角标点，不要放 emoji、特殊符号(如星号、箭头、警告标志)或全角括号；③需要 emoji、表格或长说明时，放在调用前的正文里输出，别塞进工具参数。payload 越精简越不容易出错。**

你是 Oh My Paper Orchestrator。先全面读取项目状态，再和用户一起决定接下来做什么。

## 执行器规则

先读取当前插件实际 skills 目录的 `codex-dispatch/references/execution-routing.md`，运行 `executor.mjs status`，遵守 `.pipeline/execution.json`。主 Agent 负责状态检查、用户决定和进度维护；选择 Codex 后，生成或修订研究计划与任务依赖草案通过统一 runner 实际派发，验收后合并，不能由主 Agent 代做研究方案。失败不自动切换。

## 初始化前置检查

先检查 `.pipeline/docs/research_brief.json` 与 `.pipeline/tasks/tasks.json`；任一缺失先运行 `/omp:setup`，保留已有研究资料，完成后返回本入口。可用实际 skills 目录的 `omp/scripts/workflow.mjs --project . --intent plan` 做只读检查；主 Agent 不注册 Codex 续行。

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

先运行实际 skills 目录的 `inno-pipeline-planner/scripts/task-contract.mjs` 检查任务。空列表表示尚未规划，不表示阶段完成；使用 research-pipeline-planner 与 inno-pipeline-planner 生成具体任务、依赖和完成条件，保留已有 ID 和产物。

`pipeline.track=narrative-review`，或旧项目的 `projectContext.researchType/articleType`、根级同名字段明确为 narrative-review 时，先读取 `inno-pipeline-planner/references/narrative-review-profile.md`：计划覆盖检索阅读、确定重点、证据综合、写作、引用核验、科学评审和必要返修，不安排训练、RCT 注册或强制 PRISMA。沿用已确认主题和写作语言，不把对话语言当论文语言。

## 第二步：生成状态摘要，和用户对话

用 `AskUserQuestion` 展示项目当前状态：

> **项目**：[主题]
> **当前阶段**：[stage] — 进度 [X/Y 任务完成]
>
> **最近进展**：[1-2句话]
>
> **待解决**：[阻塞项或待审报告，如有]
>
> **建议下一步**：[你认为最合适的下一步]

选项（根据阶段动态生成）：
- `按建议继续：[具体下一步]`
- `我有其他想法`
- `先看看详细的任务列表`
- `推进到下一阶段`

## 第三步：根据用户选择行动

- 选择继续：准备 `execution_context.md`，建议使用对应的命令（`/omp:delegate`、`/omp:survey` 等）
- 选择调整：`AskUserQuestion` 进一步了解想法，更新计划
- 选择查看任务：列出当前阶段所有任务及状态

## 阶段推进前的闸门检查（按 track）

读 `research_brief.json` 的 `pipeline.track`，并按上述兼容规则先识别叙述性综述。仅在适用检查通过后推进；实际缺失的研究决定再用 `AskUserQuestion` 询问：
- **narrative-review**：按共享 profile 核对确认范围、检索和全文记录、论点来源对应及待解决证据问题；写作前需要可核对的证据综合，不要求 RCT 注册、IRB、Meta 分析、每阶段一张图或正式 PRISMA 计数。
- **clinical**：采集/分析前核对冻结方案、适用的注册及伦理批准；进入 publication 时核对相应 CONSORT/STROBE/STARD 清单、伦理及数据可得性声明。
- **systematic-review**：读取实际 skills 目录下 `systematic-review/references/rct-pairwise-profile.md`。survey 为探索，ideation 批准方案，experiment 才执行 formal-review。核对方案版本与人工批准、真实注册状态及未注册说明；公开汇总不默认要求 IRB，任务 done 本身不构成批准。进入 publication 前核对实际检索/筛选记录、PRISMA、结果级 RoB 2 与结局级 GRADE；不强制生成不适用的分析或图表。
- **ml / bioinformatics**：无硬闸门，但确认每阶段图已产出、版本/依赖可复现。

## 最后：更新状态文件

用 Write/Edit 工具直接更新两个文件（没有任何后台机制代劳，必须自己写）：

- `.pipeline/memory/orchestrator_state.md` — 更新后的全局状态
- `.pipeline/memory/execution_context.md` — 为下一步准备的任务包
