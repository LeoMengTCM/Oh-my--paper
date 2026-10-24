---
name: experiment
description: 实验循环：展示实验方案后确认，每轮结果回来后再决定继续/停止
---

> **确认或选择类步骤用 AskUserQuestion 工具。构造调用时务必：①每个 question 带齐 question、header(不超过12字)、options(2到4项，每项含 label 与 description)、multiSelect 字段，缺任一个都会报 Invalid tool parameters；②字段全部用纯文本加半角标点，不要放 emoji、特殊符号(如星号、箭头、警告标志)或全角括号；③需要 emoji、表格或长说明时，放在调用前的正文里输出，别塞进工具参数。payload 越精简越不容易出错。**

你是 Oh My Paper Orchestrator。实验不能盲目启动，每轮都需要确认。

## 执行器规则

先读取当前插件实际 skills 目录的 `codex-dispatch/references/execution-routing.md`，运行 `executor.mjs status`，遵守 `.pipeline/execution.json`。选择 Codex 后，下方实验设计、实现、运行及综述证据提取与综合必须通过统一 runner 实际派发；主 Agent 负责审批确认与验收。此规则先于所有研究类型分支，失败不自动切换。

## 初始化前置检查

先检查 `.pipeline/docs/research_brief.json` 与 `.pipeline/tasks/tasks.json`；任一缺失先运行 `/omp:setup`，保留已有资料，完成后返回本入口。可用实际 skills 目录的 `omp/scripts/workflow.mjs --project . --intent experiment` 做只读检查；主 Agent 不注册 Codex 续行。空任务表先规划，不依据主题猜测实验类型。

## 叙述性综述分支（优先判定）

`pipeline.track=narrative-review`，或旧项目的 `projectContext.researchType/articleType`、根级同名字段明确为 narrative-review 时，先读实际 skills 目录的 `inno-pipeline-planner/references/narrative-review-profile.md`。本阶段是证据提取、核对和综合：

1. 复用确认的综述重点、提纲、文献库和真实全文；缺少材料时补检索或如实标明缺口。
2. 按主要论点记录来源、全文定位、研究设计、适用人群和条件、反对证据与不确定性；核对关键数值，不把摘要级材料说成已读全文。
3. 形成与章节对应的证据矩阵和 `result_summary.md`，按实际需要登记图表，不伪造新实验或合并效应。
4. 核验后登记任务产物和完成说明，更新 ledger 与交接记录，继续已授权的 `/omp:write`；实质改变主题或研究方法时才请求新决定。

不运行下方训练或远程实验循环，不要求 RCT、Meta、IRB、PRISMA 计数、消融、固定图数或成功阈值优化。**完成本分支后不继续下方通用实验流程。**

## 第零步：判定 track 与 analysisMode，先过硬闸门

```bash
cat .pipeline/docs/research_brief.json
cat .pipeline/tasks/tasks.json
```

读取 `pipeline.track`（缺省 `ml`）；`pipeline.analysisMode` 缺省时，clinical / systematic-review 为 `confirmatory`，其他为 `exploratory`。

**systematic-review 先走独立分支**：读取实际 skills 目录下 `systematic-review/references/rct-pairwise-profile.md`，按 formal-review 的前置检查执行。核对具体方案版本的人工批准、真实注册状态、筛选记录、研究归并和分析输入；任务 done 本身不是批准证据，切换 exploratory 也不能绕过正式综述规则。公开汇总数据不默认要求 IRB；未注册需如实说明并由用户确认，不伪造注册号。按 profile 完成本次正式检索、筛选或合成子任务后，更新 `experiment_ledger.md`、`figure_ledger.md`、`tasks.json` 和 `project_truth.md`，**不继续下方通用实验循环**。仅运行适用且获批准的分析和图表；允许错误修复后重跑，不为显著性改变方案。

**clinical 有锁定门。** 数据采集/分析前核对 `protocol.md`、`sap.md`、适用的注册与伦理材料及研究者批准，不能只检查 `experiment_lock_and_register` 为 done。材料缺失时先补齐；探索性/试点标记不能代替适用的伦理或数据授权。其他 track 继续下方流程。

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

- **exploratory（ml / bioinformatics）**：设计可迭代的实验方案。按已选执行器执行下面的任务（选择 Codex 时通过统一 runner 派发，失败停止）：
  ```
  阅读 .pipeline/memory/project_truth.md 和 .pipeline/memory/experiment_ledger.md（避免重复失败配置），使用 .claude/skills/inno-experiment-dev/SKILL.md 设计实验方案，写入 .pipeline/docs/experiment_plan.md，不要写代码
  ```
- **confirmatory（clinical / systematic-review）**：方案 = **已冻结**的 `protocol.md` + `sap.md`。**不要在这里"重新设计"**，只把预设分析具体化为可执行步骤（分析人群 ITT/PP、主要结局模型、缺失数据处理、多重性）。任何与冻结计划不一致之处，先记入 `.pipeline/memory/protocol_deviations.md` 再执行。

读取方案/分析步骤，用 `AskUserQuestion` 展示摘要，等确认：

> exploratory：数据集 / 基线 / 超参或流程 / 评估指标
> confirmatory：分析人群 / 主要结局与模型 / 预设亚组 / 缺失数据处理

选项：`方案可以，开始执行` / `调整某处` / `（仅 exploratory）重新设计`。

## 第三步：实现并运行

按已选执行器执行下面的任务（选择 Codex 时通过统一 runner 派发，可使用宿主后台能力，失败停止）：

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

**confirmatory** — 按预设方案如实报告；允许错误修复后重跑、确定性复现和预设敏感性分析。**不提供“调整后再跑到达标”的选项**；方法变更先获批准再记入 `protocol_deviations.md`。用 `AskUserQuestion`：
- `分析完成，进入写作` — 按 CONSORT/STROBE/STARD/PRISMA 如实报告，含预设与实际的任何偏离
- `发现了计划外现象` — 登记为**探索性/产生假设**的发现，另起一个 exploratory 分析，绝不混入确证结论
- `执行偏离了冻结计划` — 记入 `protocol_deviations.md` 并在报告中说明

## 收尾

按 Conductor 规则更新 `tasks.json`（标记完成）与 `project_truth.md`（追加进展）；本轮所有新图登记进 `figure_ledger.md`。
