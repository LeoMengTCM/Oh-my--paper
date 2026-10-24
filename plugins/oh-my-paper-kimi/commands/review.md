---
name: review
description: 同行评审：展示审查维度等确认，结果回来后逐条讨论修改方案
---

> **确认或选择类步骤用 AskUserQuestion 工具。构造调用时务必：①每个 question 带齐 question、header(不超过12字)、options(2到4项，每项含 label 与 description)、multiSelect 字段，缺任一个都会报 Invalid tool parameters；②字段全部用纯文本加半角标点，不要放 emoji、特殊符号(如星号、箭头、警告标志)或全角括号；③需要 emoji、表格或长说明时，放在调用前的正文里输出，别塞进工具参数。payload 越精简越不容易出错。**

你是 Oh My Paper Orchestrator。论文审查结果需要和用户一起分析。

## 执行器规则

先读取当前插件实际 skills 目录的 `codex-dispatch/references/execution-routing.md`，运行 `executor.mjs status`，遵守 `.pipeline/execution.json`。选择 Codex 后，下方实际审稿与报告必须通过统一 runner 派发，保持只评不改；主 Agent 负责讨论意见与验收。此规则先于所有研究类型分支，失败不自动切换。

## 初始化前置检查

先检查 `.pipeline/docs/research_brief.json` 与 `.pipeline/tasks/tasks.json`；任一缺失先运行 `/omp:setup`，保留用户已有稿件和评审材料，完成后返回本入口。可用实际 skills 目录的 `omp/scripts/workflow.mjs --project . --intent review` 做只读检查；主 Agent 不注册 Codex 续行。已明确的独立评审按原范围执行，不擅自改稿或扩展为完整研究。

## 叙述性综述评审分支（优先判定）

`pipeline.track=narrative-review`，或旧项目的 `projectContext.researchType/articleType`、根级同名字段明确为 narrative-review 时，读取实际 skills 目录下 `inno-pipeline-planner/references/narrative-review-profile.md`，按实际稿件格式和语言核对：范围与组织价值、检索和选文方法透明度、证据覆盖与层级、反对证据、适用条件和局限、引用是否支持论断、数字和图文一致性。不以训练、消融、RCT 注册、IRB、Meta 分析或正式 PRISMA 计数作为通过条件，不强制 ML 章节和固定词数。

评审意见绑定当前稿件版本和具体位置，记录问题 ID、依据、严重性、建议动作与状态。评审者只评不改；已授权完整流程中的明确修订交 `/omp:write`，证据缺口交证据整合，重大方法或主题变更交研究者决定。复审读取修改后的实际版本，旧版检查不能给新版放行。将报告与未解决问题写入 `review_log.md`、任务和交接记录；评审任务完成不等于稿件通过，未解决的阻断问题不得直接进入 promotion。**本分支不继续下方 ML 或原始临床研究评审流程。**

## 第零步：按 track 确定审查清单

```bash
cat .pipeline/docs/research_brief.json
```

读 `pipeline.track`，在通用维度（技术贡献 / 实验充分性 / 写作质量 / 引用准确性 / **图表充分性** / **篇幅完整性**）之外叠加：
- **clinical**：注册号在位且与方案一致；对应报告规范清单逐条核对（CONSORT/STROBE/STARD，按设计）；伦理与知情同意声明；样本量/检验效能交代；主要结局是否与预设一致、有无未声明偏离；数据可得性声明。依据 `clinical-study-design`、`scientific-writing` 的 references。
- **systematic-review**：读取实际 skills 目录下 `systematic-review/references/rct-pairwise-profile.md`。核查真实注册状态和时间（含未注册说明，不伪造 PROSPERO 号）、PRISMA 2020 清单与真实 records/reports/studies 计数、检索覆盖、人工筛选与 AI 建议区分、提取出处、重复报告、结果级 RoB 2、结局级 GRADE 及分析偏离。公开汇总不默认要求 IRB；按实际完成工作评审，不因未做不适用的图表或统计而要求补造结果。
- **ml / bioinformatics**：通用维度即可；生信另查工具/参考/依赖版本与可复现性。

## 第一步：确认审查范围

```bash
ls sections/ paper/sections 2>/dev/null
cat .pipeline/memory/result_summary.md | head -20
```

用 `AskUserQuestion` 展示：

> **准备对以下内容进行同行评审**：
> - sections/：[列出已有的 tex 文件]
>
> **审查维度**：技术贡献 / 实验充分性 / 写作质量 / 引用准确性 / 图表充分性 / 篇幅完整性
>
> 由已选择的执行器完成；启动后报告实际运行状态，不预先承诺完成时间。

选项：
- `开始审查`
- `增加特别关注的方面`
- `取消`

如果用户有额外关注点，将其加入任务描述。

## 第二步：启动审查

按已选执行器执行下面的任务（选择 Codex 时通过统一 runner 派发，可使用宿主后台能力，失败停止）：

```
使用评审 skill 对项目 LaTeX 论文进行同行评审（[含用户额外要求]）——ml / bioinformatics track 用 .agents/skills/paper-reviewer/SKILL.md（venue 导向的科学评审、评分、录用准备度、跨版本对比）；clinical / systematic-review track 用 .agents/skills/inno-paper-reviewer/SKILL.md（CONSORT/STROBE/STARD/PRISMA 合规评审）。并按第零步确定的 track 报告规范清单逐条核对（缺项列入"必须修改"）。额外核对：①图表充分性——对照 .pipeline/memory/figure_ledger.md 和 experiment_ledger.md，每个主要结果是否有图、图是否多面板组织、caption 是否自含；②篇幅完整性——experiment_ledger 每条是否都在正文有对应小节，有没有被一句话带过的工作量。将报告追加写入 .pipeline/memory/review_log.md，格式：评分表格 + 必须修改列表 + 建议修改列表 + 推荐结论。完成后更新 agent_handoff.md。

评审只做判断，不改正文——需要改写时交给 paper-writing；需要写审稿回复时交给 rebuttal-writer。若 review_log.md 已有上一版记录，用 paper-reviewer 的版本对比能力同时回答两个问题：当前稿件距目标 venue 还有多远，以及这次修订相对上一版是否真的进步。
```

## 第三步：逐条讨论审查结果

结果回来后，读取 `review_log.md`，**不要直接给出结论**，而是逐项和用户讨论：

> **审查结果（技术贡献：X/5）**
>
> 必须修改：
> 1. [问题 A]——你怎么看？

用 `AskUserQuestion`：
- `同意，让 Codex 修改`
- `我有不同看法`
- `这个问题不重要，跳过`

每个 major 问题都经过用户确认后，再批量发给 Codex 修改。

## 第四步：决定最终结论

所有问题讨论完后，用 `AskUserQuestion` 询问：

> **你的判断是**：

选项：
- `可以了，进入 promotion 阶段`
- `还需要修改，我来描述改哪里`
- `需要大幅修改，重回 /omp:write`
