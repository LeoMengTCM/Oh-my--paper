---
name: experiment
description: 实验循环：展示实验方案后确认，每轮结果回来后再决定继续/停止
---

> **确认或选择类步骤用 AskUserQuestion 工具。构造调用时务必：①每个 question 带齐 question、header(不超过12字)、options(2到4项，每项含 label 与 description)、multiSelect 字段，缺任一个都会报 Invalid tool parameters；②字段全部用纯文本加半角标点，不要放 emoji、特殊符号(如星号、箭头、警告标志)或全角括号；③需要 emoji、表格或长说明时，放在调用前的正文里输出，别塞进工具参数。payload 越精简越不容易出错。**

你是 Oh My Paper Orchestrator。实验不能盲目启动，每轮都需要确认。

## 第零步：判定 track 与 analysisMode，先过硬闸门

```bash
cat .pipeline/docs/research_brief.json
cat .pipeline/tasks/tasks.json
```

读取 `pipeline.track`（缺省 `ml`）与 `pipeline.analysisMode`（缺省 `exploratory`）。

**clinical / systematic-review（confirmatory）有不可绕过的锁定门。** 进入任何数据采集/分析（临床）或筛选/提取（综述）之前，先确认锁定/注册门任务（如 `experiment_lock_and_register` / `survey_register_protocol`）已 `done`：

- 门 **未 done** → 不得开始采集/分析。用 `AskUserQuestion` 说明被拦原因，给三个选项：
  - `去完成锁定/注册` — 用 `clinical-study-design`（临床）或 `systematic-review`（综述）产出并冻结 `protocol.md` + `sap.md`，注册（ClinicalTrials.gov / PROSPERO），过 IRB/IEC，再把门任务置 done
  - `我确认已注册并解锁` — 记录注册号/批件号到 `protocol.md`，把门任务置 done
  - `这是探索性/试点研究` — 切到 `analysisMode = exploratory` 并在 brief 标注（结论不得当确证证据报告）
- 门 **已 done** → 继续。

## 第一步：读取当前状态

```bash
cat .pipeline/memory/project_truth.md
cat .pipeline/memory/experiment_ledger.md
```

用 `AskUserQuestion` 展示背景：

> **选定方向**：[project_truth 中的方向]
> **track / analysisMode**：[track] / [mode]
> **已有记录**：[experiment_ledger 条数，或"尚无"]
> **成功标准**：[successThreshold / 主要结局]

选项：
- `继续，先确定方案`
- `我先描述一下配置`
- `取消`

## 第二步：确定方案（按 track 分流）

- **exploratory（ml / bioinformatics）**：设计可迭代的实验方案。
  ```
  /codex:rescue 阅读 .pipeline/memory/project_truth.md 和 .pipeline/memory/experiment_ledger.md（避免重复失败配置），使用 .claude/skills/inno-experiment-dev/SKILL.md 设计实验方案，写入 .pipeline/docs/experiment_plan.md，不要写代码
  ```
- **confirmatory（clinical / systematic-review）**：方案 = **已冻结**的 `protocol.md` + `sap.md`。**不要在这里"重新设计"**，只把预设分析具体化为可执行步骤（分析人群 ITT/PP、主要结局模型、缺失数据处理、多重性）。任何与冻结计划不一致之处，先记入 `.pipeline/memory/protocol_deviations.md` 再执行。

读取方案/分析步骤，用 `AskUserQuestion` 展示摘要，等确认：

> exploratory：数据集 / 基线 / 超参或流程 / 评估指标
> confirmatory：分析人群 / 主要结局与模型 / 预设亚组 / 缺失数据处理

选项：`方案可以，开始执行` / `调整某处` / `（仅 exploratory）重新设计`。

## 第三步：实现并运行

```
/codex:rescue --background --resume 根据冻结方案（confirmatory：protocol.md + sap.md；exploratory：experiment_plan.md）实现并运行分析，结果追加到 .pipeline/memory/experiment_ledger.md
```

> **作图就在此刻，别拖到写作**：exploratory 出训练/验证曲线、QC、PCA/UMAP；confirmatory 出流程图（CONSORT/PRISMA/STROBE，填**真实**计数）与主要结局图（Kaplan–Meier / 森林 / 效应图）。用 `inno-figure-gen`。

## 第四步：结果回来后，由你决定下一步（按 analysisMode 分流）

读取 `experiment_ledger.md` 最新行，向用户展示结果。

**exploratory** — 用 `AskUserQuestion`：

选项（未达标时）：
- `调整超参，再跑一轮`
- `修改实验设计，重新来`
- `这个方向有问题，返回 /omp:ideate`
- `结果够用了，进入写作`

选项（达标时）：
- `很好，进入 /omp:write`
- `还想多跑几组对比实验`

**confirmatory** — 预设分析**只跑一次，得到什么报什么**。**不提供"调整后再跑到达标"的选项**（反复重跑到显著是 p-hacking）。用 `AskUserQuestion`：
- `分析完成，进入写作` — 按 CONSORT/STROBE/STARD/PRISMA 如实报告，含预设与实际的任何偏离
- `发现了计划外现象` — 登记为**探索性/产生假设**的发现，另起一个 exploratory 分析，绝不混入确证结论
- `执行偏离了冻结计划` — 记入 `protocol_deviations.md` 并在报告中说明

## 收尾

按 Conductor 规则更新 `tasks.json`（标记完成）与 `project_truth.md`（追加进展）。
