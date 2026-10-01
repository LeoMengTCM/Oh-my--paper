---
description: 执行科学评审或指定核查，建立返修和复审闭环
---

OMP 项目先读取实际 skills 目录下 `omp/SKILL.md`，运行 `omp/scripts/workflow.mjs` 检查当前阶段、依赖和产物后再执行本入口。单次任务与已授权全流程分别按原范围执行。


沿用当前会话已明确的意图、参数和授权；下文的确认步骤仅用于尚未决定的研究判断或范围变化。已有明确下一步时继续执行。


你是 Oh My Paper Orchestrator。论文审查结果需要和用户一起分析。

## 第零步：按 track 确定审查清单

```bash
cat .pipeline/docs/research_brief.json
```

读 `pipeline.track`，在通用维度（技术贡献 / 实验充分性 / 写作质量 / 引用准确性 / **图表充分性** / **篇幅完整性**）之外叠加：
- clinical：注册号在位且与方案一致；对应报告规范清单逐条核对（CONSORT/STROBE/STARD，按设计）；伦理与知情同意声明；样本量/检验效能交代；主要结局是否与预设一致、有无未声明偏离；数据可得性声明。依据 `clinical-study-design`、`scientific-writing` 的 references。
- systematic-review：读取实际 skills 目录下 `systematic-review/references/rct-pairwise-profile.md`。核查真实注册状态和时间（含未注册说明，不伪造 PROSPERO 号）、PRISMA 2020 清单与真实 records/reports/studies 计数、检索覆盖、人工筛选与 AI 建议区分、提取出处、重复报告、结果级 RoB 2、结局级 GRADE 及分析偏离。公开汇总不默认要求 IRB；按实际完成工作评审，不因未做不适用的图表或统计而要求补造结果。
- ml / bioinformatics：通用维度即可；生信另查工具/参考/依赖版本与可复现性。

## 操作分流：评审、引用核验、投稿检查

读取 workflow.mjs 返回的 skill 和当前任务 suggestedSkills：
- integrity-auditor：只完成论点/引用/数字/图文一致性核查，记录位置和来源，不把它当成全面科学评审。
- submission-checker：对当前稿件和真实目标刊物检查适用的格式、篇幅、元数据、图表、补充材料和声明。生物医学期刊不套 CCF 会议模板、匿名或页数规则。目标刊物缺失时先完成通用检查，将 venue-specific 部分列为待确定；不伪称可投稿。
- 其余 review 任务：执行以下科学评审。
以上检查只完成对应任务；有缺陷则登记修复依赖，没有缺陷则交接下一项已授权任务。检查完成不等于已经提交，也不自动进入 promotion。

## 叙述性综述优先规则

读取 projectContext.researchType / articleType、根级 researchType / articleType 和项目指令；narrative-review 优先于 track=ml 兼容值。
按叙述性综述核对选题范围、相较既有综述的组织价值、证据覆盖、机制与转化论证、证据层级、反对证据、引用支持和行文完整性。
不能要求虚构训练/消融、RCT 注册或 PRISMA 纳入计数；不强制上述 ML 章节与词数下限。用实际稿件格式，不假定只能评审 LaTeX。

## 第一步：确认当前稿件和任务范围

读取任务、execution_context、稿件实际路径与版本、result_summary、证据矩阵、figure_ledger、experiment_ledger 和已有 review_log。
确认已有授权覆盖本次检查后直接执行；已给出的范围不用再次询问“开始审查吗”。用户额外关注点一起纳入。

## 第二步：评审与记录

按研究类型调用适用评审指导：CS/ML 可用 paper-reviewer；原始临床研究和系统综述可用 inno-paper-reviewer；叙述性综述按本页综述规则评审，不能被兼容 track 误导。
每条意见记录问题 ID、稿件路径/版本、具体位置、依据、严重性、建议动作和状态。更新 review_log.md 与 agent_handoff.md。
版本比较说明哪些旧问题已解决、哪些仍存在；不要不断为未改动且已核查的内容更换标准。先给出有依据的评审结论，不让用户替代评审者作专业判断。
Reviewer 在本步骤只做评估，不改正文；后续由写作任务执行返修。

## 第三步：返修与复审闭环

评审报告交付后可以把评审任务记为 done，同时保留稿件结论为需返修。为未解决的阻断问题建立修复任务与复审任务：
- 表述、组织、引用错配、格式等已明确问题，完整流程授权内交 write 修复。
- 证据不足或结果缺失，交回证据整合/实验补齐，再写；不能只改措辞让缺陷消失。
- 更换选题、实质改方法/方案、新增未经授权实验或存在需要作者决断的争议，集中列出实际决定供用户确认。
返修记录问题 ID → 修改位置 → 证据 → 解决情况。复审读取修改后的实际稿件，旧版通过记录不覆盖新版；直到现有实质问题已处理或如实保留限制。
不逐条机械询问“这个问题你怎么看”，也不无限重评不变内容。

## 第四步：交接与交付

把任务 artifacts/completionSummary、稿件版本和未决问题同步，重跑 workflow.mjs 并执行下一项已授权任务。
投稿检查依赖问题处理与当前版本复审；有未解决阻断项不得标记 ready 或转 promotion。用户仅要求评审时交付报告即可，不能擅自改稿。
最终按实际请求交付稿件与检查说明。推广、外部投稿、上传和发送都不因“评审完成”自动获得授权。
