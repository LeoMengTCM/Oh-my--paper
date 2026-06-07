---
name: plan
description: 审视全局进展，以问答形式确认下一步方向，更新研究计划
---

> **确认或选择类步骤用 AskUserQuestion 工具。构造调用时务必：①每个 question 带齐 question、header(不超过12字)、options(2到4项，每项含 label 与 description)、multiSelect 字段，缺任一个都会报 Invalid tool parameters；②字段全部用纯文本加半角标点，不要放 emoji、特殊符号(如星号、箭头、警告标志)或全角括号；③需要 emoji、表格或长说明时，放在调用前的正文里输出，别塞进工具参数。payload 越精简越不容易出错。**

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

读 `research_brief.json` 的 `pipeline.track`，仅当对应闸门通过才允许推进；否则用 `AskUserQuestion` 说明缺口并引导补齐：
- **clinical / systematic-review**：进入数据采集/分析前——`protocol.md` + `sap.md` 已冻结、已注册（ClinicalTrials.gov / PROSPERO）、过 IRB（综述无需 IRB）。
- **进入 publication（临床/综述强制）**：按报告规范清单核对——注册号在位；对应清单齐全（CONSORT / STROBE / STARD 或 PRISMA）；伦理与数据可得性声明；流程图/主结果图已就绪。核对依据见 `clinical-study-design`、`systematic-review`、`scientific-writing` 的 references。
- **ml / bioinformatics**：无硬闸门，但确认每阶段图已产出、版本/依赖可复现。

## 最后：更新状态文件

```omp_memory_sync
{
  "updates": [
    {
      "file": "orchestrator_state.md",
      "content": "（更新后的状态）"
    },
    {
      "file": "execution_context.md",
      "content": "（为下一步准备的任务包）"
    }
  ]
}
```
