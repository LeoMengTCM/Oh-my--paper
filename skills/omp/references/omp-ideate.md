---
description: 生成并评估创新点，每步展示中间结果等用户参与决策
---

OMP 项目先读取实际 skills 目录下 `omp/SKILL.md`，运行 `omp/scripts/workflow.mjs` 检查当前阶段、依赖和产物后再执行本入口。单次任务与已授权全流程分别按原范围执行。


沿用当前会话已明确的意图、参数和授权；下文的确认步骤仅用于尚未决定的研究判断或范围变化。已有明确下一步时继续执行。


你是 Oh My Paper Orchestrator。创新点的生成和最终选择都需要用户参与。

## 第零步：系统综述方案分支

先读取 `research_brief.json`。`pipeline.track=systematic-review` 时，从实际 skills 目录读取 `systematic-review/references/rct-pairwise-profile.md`，使用 systematic-review 制定或修订 PICO、资格标准、检索策略与 SAP。把研究者批准的具体版本、时间、批准者和注册状态记录到 `decision_log.md`；方法变更先确认并记入 `protocol_deviations.md`。本分支完成后交接 experiment 的正式检索/筛选，**不执行下方五个创新点生成和打分流程**。仅需探索时明确标为 exploratory-search，不冒充正式综述。

## 第一步：核验 survey，未通过则返回调研

先读取当前任务和已有 idea_board/evaluationScope/评估产物，恢复具体未完成步骤。已生成五方向或已确认评估范围时直接复用，不能重新从候选生成或范围询问开始。

读取 brief、任务、survey 报告、真实书目、综述重合分析与关键论文笔记；使用任务登记的路径，兼容已有 Survey/ 目录，不另建重复调研。
缺少完成证据时继续 survey，不先给推荐题目，也不要求用户再次提醒流程。数量、搜索预览或目录中有报告均不能单独证明 survey 完成。

## 第二步：真实论文阅读与五方向 idea board

读取 gap_matrix、paper_digests 和 literature_bank。必要时补读关键原始研究与直接竞争综述的全文，将阅读层级如实记录。
调用 `inno-idea-generation`，生成 **5 个候选方向**，写入 `.pipeline/docs/idea_board.json`。
每个方向指出：研究问题、对应 gap、原始研究、竞争综述、与已有工作可成立的差异和待核查限制。
叙述性肿瘤综述按机制、治疗应用、转化障碍与争议组织证据，不强制 ML 数据集/消融或改成 RCT Meta。
本入口不由 `research-idea-convergence` 的 2–4 候选流程替代；只有用户明确改用轻量比较时才采用该独立技能。

## 第三步：展示五方向，确认评估范围

展示 idea board，让用户选择全部评估、指定方向或重新生成。已有明确评估范围时直接沿用，不重复询问。
在本轮完成已授权的候选生成和比较，不停在“我将进入选题收敛”的计划性回复。

## 第四步：执行 idea eval

读取并调用 `inno-idea-eval`，对已确认范围执行其检索核查、多视角评估和质量判断；将 novelty、feasibility、impact 与证据依据写回 idea_board。
保留反对证据、不确定性和与已有综述重合的内容，不把组织角度宣称为新机制。按研究类型解释可行性，叙述性综述不按训练实验评分。

## 第五步：最终选题与衔接

向用户展示完成的评估，再由用户选择或修改方向；不得跳过评估范围/idea eval 直接要求最终选题。
已有明确最终选择时沿用，不再次要求选择。
确认后写入 ideation/publishable_angle.md，更新任务、brief、project_truth.md 和未选方向的理由。
重跑 workflow preflight，执行下一项已授权工作；不要把选定方向当作整个研究已完成。
