---
description: 执行实验或综述证据整合，核对已有授权并衔接写作
---

OMP 项目先读取实际 skills 目录下 `omp/SKILL.md`，运行 `omp/scripts/workflow.mjs` 检查当前阶段、依赖和产物后再执行本入口。单次任务与已授权全流程分别按原范围执行。


沿用当前会话已明确的意图、参数和授权；下文的确认步骤仅用于尚未决定的研究判断或范围变化。已有明确下一步时继续执行。


你是 Oh My Paper Orchestrator。先核对方案与已有授权，执行预设工作；只为新增研究决策询问用户。

## 叙述性综述分支（优先判定研究实质）

读取 brief 的 projectContext.researchType / articleType、根级 researchType / articleType 和项目指令。
narrative-review 即使保留 track=ml 兼容值，也执行文献证据整合：
1. 读取用户已选方向、评估报告、既有提纲、文献库与尚未解决的问题，不重做选题。
2. 为主要论点登记来源、证据层级、研究条件、反对证据、全文定位及可支持的表述边界；必要缺口补检索/核读。
3. 形成与章节对应的证据矩阵、图表计划和 `.pipeline/memory/result_summary.md`，复用已有路径；结果摘要写文献证据，不伪造新实验。
4. 检查覆盖与出处，登记本任务 artifacts/completionSummary 及交接说明，重跑路由，继续已授权写作。
本分支不调用训练/远程实验循环，不强制 RCT、Meta、IRB、消融或训练图。方法或主题发生实质改变时才请求新决定。完成后不继续下方 ML/临床循环。

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

核对选定方向、analysisMode、既有运行和成功标准；按已确认的计划继续，缺少实质研究决定时才询问。

## 第二步：确定方案（按 track 分流）

- exploratory（ml / bioinformatics）：阅读 `project_truth.md` 和 `experiment_ledger.md`（避免重复失败配置），用 skills 下的 `inno-experiment-dev/SKILL.md` 设计可迭代的实验方案，写入 `.pipeline/docs/experiment_plan.md`。
- confirmatory（clinical / systematic-review）：方案 = 已冻结的 `protocol.md` + `sap.md`，不要在这里重新设计；只把预设分析具体化为可执行步骤（分析人群 ITT/PP、主要结局模型、缺失数据处理、多重性）。任何与冻结计划不一致之处，先记入 `.pipeline/memory/protocol_deviations.md` 再执行。

复用既有方案批准；新方案或实质方法变更须取得适用确认，已获准步骤直接执行。

## 第三步：实现并运行

根据冻结方案（confirmatory：protocol.md + sap.md；exploratory：experiment_plan.md）实现并运行分析，把每次结果追加到 `.pipeline/memory/experiment_ledger.md`。

## 出图纪律（每轮强制，宁多勿缺）

好论文的图是多面板大图 (a)(b)(c) 拼出来的，素材必须在实验期攒够——写作时才发现缺图就得回头重跑。规则：

1. **数据图必须由分析代码画**（matplotlib/seaborn/R + `inno-experiment-analysis`）。**绝不用 `inno-figure-gen` 画带数据的图**——图像生成模型画的数据点是编的；它只许画概念图/架构图/流程示意。
2. **每轮跑完把能画的全画掉**：训练/验证曲线、各数据集对比、每个消融、混淆矩阵、样例可视化（exploratory ML）；QC、PCA/UMAP、火山图、热图、富集条形图（生信）；CONSORT/PRISMA/STROBE 流程图（真实计数）、森林图、KM 曲线、亚组与敏感性分析（confirmatory）。哪怕 80% 最后用不上也画。
3. **每张图落三件套**：`figures/<名>.pdf` + `<名>.csv` + `plot_<名>.py`，字号线宽按"拼进大图后仍可读"设置。
4. **登记 `.pipeline/memory/figure_ledger.md`**：`| 图名 | 路径 | 数据来源(run id) | 类型 | 拟用章节/面板 | 状态 |`

## 第四步：结果回来后，由你决定下一步（按 analysisMode 分流）

读取 `experiment_ledger.md` 最新行，向用户展示结果；同时读取 `figure_ledger.md`，报告本轮新增几张图、累计几张、哪些主要结果还没有图。

exploratory — 按已授权迭代次数、资源范围和停止标准处理；只有新增研究决策时才询问：
- 未达标：调整超参再跑一轮 / 修改实验设计重新来 / 这个方向有问题返回 omp 的 ideate 工作流 / 结果够用了进入写作
- 达标：很好进入 omp 的 write 工作流 / 还想多跑几组对比实验 / 图素材不够先补图再写作

进入写作前的图检查：对照 `figure_ledger.md` 确认每个主要结果、每个消融、每个数据集都至少有一张子图素材；缺的先补。

confirmatory — 按预设方案如实报告；允许错误修复后重跑、确定性复现和预设敏感性分析。不提供“调整后再跑到达标”的选项；方法变更先获批准再记入 `protocol_deviations.md`。按已批准结果完成后直接交接写作；确需新决定时才询问：
- 分析完成，进入写作 — 按 CONSORT/STROBE/STARD/PRISMA 如实报告，含预设与实际的任何偏离
- 发现了计划外现象 — 登记为探索性/产生假设的发现，另起一个 exploratory 分析，绝不混入确证结论
- 执行偏离了冻结计划 — 记入 `protocol_deviations.md` 并在报告中说明

## 本次任务收尾与写作交接

将运行或证据矩阵、适用图表、关键结论和限制登记到任务 artifacts/completionSummary、result_summary.md 与 agent_handoff.md。
明确哪些结果可用于哪些章节，哪些缺口仍需补证。已批准计划内的执行和错误修复不反复询问“是否继续”。
重跑 workflow.mjs，读下一项任务的入口并执行；需要新增实验或修改确证分析方案时保留研究者决策，不替用户改变方法。
