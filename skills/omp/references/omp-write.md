---
description: 依据当前证据完成写作或返修，衔接引用核验与同行评审
---

OMP 项目先读取实际 skills 目录下 `omp/SKILL.md`，运行 `omp/scripts/workflow.mjs` 检查当前阶段、依赖和产物后再执行本入口。单次任务与已授权全流程分别按原范围执行。


沿用当前会话已明确的意图、参数和授权；下文的确认步骤仅用于尚未决定的研究判断或范围变化。已有明确下一步时继续执行。


你是 Oh My Paper Orchestrator。按已确定的范围连续完成写作，只在缺少实质研究决定时询问。

## 当前操作：新稿、返修还是回复

以当前任务的 workflow/suggestedSkills、review_log 和 execution_context 为准。返修读取当前稿件和具体问题，不重新从第一节开始写整篇；建立问题 ID → 修改位置 → 证据 → 状态的 revision_ledger。证据缺口先回到证据整合，不靠润色掩盖。
若路由指定 rebuttal-writer，处理用户提供的外部审稿意见；常规内部审稿返修不自动生成或发送审稿回复。

## 叙述性综述分支

先核对 brief 的 projectContext.researchType / articleType、根级 researchType / articleType 和项目指令。
narrative-review 优先于兼容的 track=ml：复用选定方向、评估结果、证据矩阵、已确认提纲、result_summary 和原引用库。
按实际格式在现有 Publication/、paper/ 或正文目录写作；借鉴参考文的机制—应用—转化障碍—展望结构时仍以内容需要和用户要求为准。
使用 scientific-writing 中适用的学术写作指导，不强制 ML 的 related_work/methodology/experiments、固定词数下限或原始临床研究 IMRaD。
已授权完整稿时连续完成所需章节和图注，不逐节停下来要求“继续”。引用与论点逐项对应，保留适用条件、反对证据和不确定性，不把叙述性综述说成系统综述。
按实际格式检查参考文献、图文对应与篇幅，调用 integrity-auditor 核查一致性；LaTeX 校验脚本仅用于 LaTeX，不能因 Markdown/Word 没有 main.tex 就改造项目。
写作或返修结束后执行本页“完成后”的交接，不继续下方 ML 默认章节流程。

## Promotion 分支

若当前阶段为 promotion 或用户要求汇报材料，复用已确认的论文与结果，读取
research-paper-handoff 和 making-academic-presentations，按需生成 slides、poster、
talk 或 demo 材料，写入 promotion/ 并更新任务记录。该分支不强制重新写整篇论文。
对外发布、发送材料或上传服务仅按用户授权进行；本地生成完成后给出可检查的文件。

## 第零步：系统综述写作规则

先读 `research_brief.json`。systematic-review 使用实际 skills 目录下 `systematic-review/references/rct-pairwise-profile.md` 与 scientific-writing：按 PRISMA 和期刊要求组织正文，下方 ML 章节、固定词数下限与消融图要求不适用。注册、筛选人数与方法必须来自真实记录，不把计划写成已执行。复用已核实的引用、结果和 `.R`/`.py` 图形脚本；缺证据列出缺口，不新增分析或编造结果。PRISMA 计数按共享 profile 调用只读脚本，partial 不能写成最终结果；统计只使用已核对的 completed 运行及其 summary/effects，SoF 草稿不冒充完成的 GRADE。官方 PRISMA 流程图渲染仍未实现。

## 第一步：确认写作范围

systematic-review 先读取 `systematic-review/references/writing-handoff.md`，按项目 publication.json 调用
`writing_handoff.py check`，需要导出时用 build 指向新目录。仅使用当前有效运行与核验引用；
partial 按 blockers 补齐，ready_for_drafting 不代表可以投稿。software_validation/public_benchmark
不得作为真实研究结果。负责人须登记所有待报告分析，不自行挑选有利运行。

先确定 LaTeX 工作区根目录：优先 `paper/`（推荐布局），若 `sections/` 直接在项目根目录则用根目录。下文路径都相对这个根。

```bash
ls paper/sections sections 2>/dev/null
cat .pipeline/memory/result_summary.md
cat .pipeline/memory/experiment_ledger.md
cat .pipeline/memory/figure_ledger.md   # 实验期攒下的图素材清单
```

向用户展示：

> **准备写作的章节**：
> - [ ] abstract.tex
> - [ ] introduction.tex
> - [ ] related_work.tex
> - [ ] methodology.tex
> - [ ] experiments.tex
> - [ ] conclusion.tex（可选）
>
> 已有文件：[列出 sections/ 下已存在的]

依据已确定的写作范围执行：完整稿继续未完成章节，返修只改实际问题；不要重复询问已经明确的范围。

## 引用铁律（贯穿全文）

参考文献唯一可信来源：survey 用 `build_bibliography.py` 生成的 `refs/references.bib`（来自真实 metadata，`bibliography.json` 可追溯）。

- 所有 `\cite{key}` 的 key 必须来自 `literature_bank.md` 的 cite_key 列。
- 引 survey 已有文献：直接用 cite_key，不重写元数据、不手写 bib。
- 引 survey 没有的新文献：先用 `search_and_download_papers.py` 确认真实存在 → `build_bibliography.py --origin write` 并入 `refs/references.bib` → 再 `\cite`；查不到就标 `[CITATION NEEDED]`，不要编。
- 绝不凭记忆写 `\cite` 或手写 bib 条目。

## 篇幅与完整性铁律（贯穿全文）

LLM 写论文的默认毛病是写得太短，把大量工作量压缩成几句话。按下限写足（英文词），删减留给 review：abstract 150–250；introduction ≥800（每个贡献点单独成段）；related_work ≥600（覆盖 bank 全部 accepted 主题簇）；methodology ≥1500（写到可复现：公式、设计理由、超参数表）；experiments ≥1500（**逐条覆盖 experiment_ledger 的每个实验**，每个消融各自成小节，禁止合写成一句）；conclusion ≥200。每节写完用 `wc -w` 报字数对照下限，低了要么扩写要么说明理由。

## 第二步：按节逐步执行

每节开始前，先告知用户：

> 现在写 **[节名]**，基于：[依赖的来源文件]

**摘要 + 引言：**
调用 `paper-writing` skill，根据 `.pipeline/memory/project_truth.md` 和 `.pipeline/memory/result_summary.md`，写 `sections/abstract.tex` 和 `sections/introduction.tex`，不捏造数据。

**相关工作：**
调用 `paper-writing` skill，基于 `.pipeline/memory/literature_bank.md`（accepted 的）写 `sections/related_work.tex`。引用遵守上面的引用铁律：只用 bank 的 cite_key，不手写 bib。

**方法论：**
调用 `paper-writing` skill，基于 `project_truth.md` 中的方法描述，写 `sections/methodology.tex`，包含必要数学公式。

**实验与结果：**
调用 `paper-writing` skill，基于 `.pipeline/memory/experiment_ledger.md` 和 `result_summary.md`，写 `sections/experiments.tex`，使用真实数据。写之前先把 experiment_ledger 逐条列成清单，每条对应正文一个小节或段落；写完逐条打勾核对，一条都不许漏。

每节完成后核对篇幅与证据，记录进度并继续已授权的下一节。用户指定单节时止于该范围；不要对完整写作任务逐节重复询问。

## 第三步：图表和引用

按已确定任务完成适用图表和引用审查；只有缺少设计选择或外部权限时询问。

**图表（组装，不是从零画）：** 读 `figure_ledger.md`，按"拟用章节/面板"把子图分组成多面板大图方案（如图2 = (a) 训练曲线 (b) 消融 (c) 敏感性 (d) 样例），先展示方案；用绘图脚本拼面板（matplotlib subplots 或 LaTeX subfigure）输出到 `assets/figures/`，统一字号配色。概念图/架构图才用 `inno-figure-gen`；**带数据的图一律来自实验期的绘图脚本，禁止用图像生成模型画**。核对：每个主要结果至少一图、每图被 `\ref` 且 caption 逐面板说明。缺图就列清单回 omp 的 experiment 工作流 用现成的 csv + plot 脚本补画，不要现编数据。

**引用审查：** 先跑 `audit_citations.py --sections-dir sections --tex main.tex --bib refs/references.bib` 机制化校验（dangling=编造/笔误，unsourced=手写 bib），退出非零先别进 review；再用 `integrity-auditor` skill 人工核实存疑项。

## 第四步：完整性核对（进入 review 前的门）

逐项检查并展示给用户：experiment_ledger 每条都有对应小节（列对照表）；figure_ledger 非 unused 的图都被 `\ref`；各节字数 vs 下限；abstract/introduction/conclusion 贡献点一致；关键数字与 result_summary.md 一致；跑 `integrity-auditor` skill 核验 claim 与证据、数值/术语/图表一致性；跑 `paper-humanization` skill 清掉防御性铺垫、重复 caveat、三项并列、破折号堆砌、内部工程状态叙述。有不过的先补齐再继续。

## 完成后

登记当前稿件的路径和版本、证据覆盖、图件、引用检查结果到任务和 handoff。没有安排下游检查时，按用户交付范围补充 integrity audit、科学评审及必要的返修/复审任务，设置依赖。
重跑 workflow.mjs：引用核验交 integrity-auditor，科学评审交 review，返修交 write，投稿准备核对交 submission-checker；不能把所有 publication 任务都解释为写作。
完整流程已授权时直接执行下一任务；评审还有阻断问题就进入修复再复审，不跳到 promotion。提交/上传/对外发送仍需相应授权。
