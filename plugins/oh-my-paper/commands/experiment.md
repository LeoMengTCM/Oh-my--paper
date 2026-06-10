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

- **exploratory（ml / bioinformatics）**：设计可迭代的实验方案。把下面的任务交给 Codex（用 `codex-dispatch` 技能或 `/omp:delegate` 流程；Codex 不可用就自己执行）：
  ```
  阅读 .pipeline/memory/project_truth.md 和 .pipeline/memory/experiment_ledger.md（避免重复失败配置），使用 .claude/skills/inno-experiment-dev/SKILL.md 设计实验方案，写入 .pipeline/docs/experiment_plan.md，不要写代码
  ```
- **confirmatory（clinical / systematic-review）**：方案 = **已冻结**的 `protocol.md` + `sap.md`。**不要在这里"重新设计"**，只把预设分析具体化为可执行步骤（分析人群 ITT/PP、主要结局模型、缺失数据处理、多重性）。任何与冻结计划不一致之处，先记入 `.pipeline/memory/protocol_deviations.md` 再执行。

读取方案/分析步骤，用 `AskUserQuestion` 展示摘要，等确认：

> exploratory：数据集 / 基线 / 超参或流程 / 评估指标
> confirmatory：分析人群 / 主要结局与模型 / 预设亚组 / 缺失数据处理

选项：`方案可以，开始执行` / `调整某处` / `（仅 exploratory）重新设计`。

## 第三步：实现并运行

把下面的任务交给 Codex（用 `codex-dispatch` 技能或 `/omp:delegate` 流程，建议后台运行；Codex 不可用就自己执行）：

```
根据冻结方案（confirmatory：protocol.md + sap.md；exploratory：experiment_plan.md）实现并运行分析，结果追加到 .pipeline/memory/experiment_ledger.md
```

## 出图纪律（每轮强制，宁多勿缺）

**好论文的图是多面板大图拼出来的，而拼图的前提是子图素材足够多。写作阶段才发现缺图，就只能回头重跑实验——所以图在实验期出，每轮出，能画的全画。** 哪怕最后 80% 用不上，也比写作时缺一张强。

1. **数据图必须由分析代码画**（matplotlib/seaborn/R + `inno-experiment-analysis`）。**绝不用 `inno-figure-gen` 画任何带数据的图**——它是图像生成模型，画出来的数据点是编的。`inno-figure-gen` 只许画概念图、架构图、流程示意。
2. **每轮跑完立即清点可画清单，全部画掉**：
   - exploratory（ML）：训练/验证曲线、各数据集对比图、每个消融一张图、混淆矩阵、成功与失败样例可视化、超参敏感性曲线
   - 生信：QC 图、PCA/UMAP、火山图、聚类热图、富集分析条形图
   - confirmatory（临床/综述）：CONSORT/PRISMA/STROBE 流程图（**真实**计数）、主要与次要结局效应图（森林图）、Kaplan–Meier 曲线、亚组森林图、敏感性分析图
3. **每张图落三件套**：`figures/<名称>.pdf` + 同名数据 `<名称>.csv` + 绘图脚本 `plot_<名称>.py`。后期改样式、重绘、拼面板全靠这三样。
4. **按子图标准做素材**：单图当成未来大图里的 (a)(b)(c) 面板来画——字号、线宽、分辨率按拼接后仍可读的标准设置。
5. **登记 `.pipeline/memory/figure_ledger.md`**，每张图一行：

   ```markdown
   | 图名 | 路径 | 数据来源(run id) | 类型 | 拟用章节/面板 | 状态 |
   | val-curve-baseline | figures/val_curve_baseline.pdf | run-001 | 曲线 | experiments 图2(a) | draft |
   ```

## 第四步：结果回来后，由你决定下一步（按 analysisMode 分流）

读取 `experiment_ledger.md` 最新行，向用户展示结果；**同时读取 `figure_ledger.md`，报告本轮新增几张图、累计几张、哪些主要结果还没有图**。

**exploratory** — 用 `AskUserQuestion`：

选项（未达标时）：
- `调整超参，再跑一轮`
- `修改实验设计，重新来`
- `这个方向有问题，返回 /omp:ideate`
- `结果够用了，进入写作`

选项（达标时）：
- `很好，进入 /omp:write`
- `还想多跑几组对比实验`
- `图素材不够，先补图再写作`

**进入写作前的图检查**：选"进入 /omp:write"之前，对照 `figure_ledger.md` 确认每个主要结果、每个消融、每个数据集都至少有一张子图素材；缺的先补——写作阶段回头补图的代价远高于现在顺手画。

**confirmatory** — 预设分析**只跑一次，得到什么报什么**。**不提供"调整后再跑到达标"的选项**（反复重跑到显著是 p-hacking）。用 `AskUserQuestion`：
- `分析完成，进入写作` — 按 CONSORT/STROBE/STARD/PRISMA 如实报告，含预设与实际的任何偏离
- `发现了计划外现象` — 登记为**探索性/产生假设**的发现，另起一个 exploratory 分析，绝不混入确证结论
- `执行偏离了冻结计划` — 记入 `protocol_deviations.md` 并在报告中说明

## 收尾

按 Conductor 规则更新 `tasks.json`（标记完成）与 `project_truth.md`（追加进展）；本轮所有新图登记进 `figure_ledger.md`。
