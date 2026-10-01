# PRISMA 2020 Flow Diagram — counts to fill in

优先从 `scripts/review_state.py prisma <综述记录目录>` 获取计数，字段规范见
`references/review-records.md`。该命令生成计数表，不是官方流程图。

区分 records、reports 与 studies，以及未完成筛选和未取得全文。
不能把“已筛选 − 排除”直接当作“已取得全文”；中间还包括尚未请求、获取中和未取得的报告。
只有完整的实际记录才能填最终流程图；partial 计数不得写成最终结果。

## Identification
- Records identified from databases:
  - MEDLINE/PubMed: ____
  - Embase: ____
  - Cochrane CENTRAL: ____
  - Other database(s) (____): ____
- Records identified from registers (ClinicalTrials.gov, etc.): ____
- Records identified from other sources (citation searching, hand-search, experts): ____
- **Total identified: ____**

## De-duplication
- Duplicate records removed: ____
- Records removed for other reasons before screening (e.g., automation tools, ineligible by metadata): ____

## Screening
- Records screened (title/abstract): ____
- Records excluded at title/abstract: ____

## Retrieval & full-text eligibility
- Reports sought for retrieval: ____
- Reports not retrieved: ____
- Reports assessed for full-text eligibility: ____
- Reports excluded at full text (list each reason + count):
  - Wrong population: ____
  - Wrong intervention/comparator: ____
  - Wrong outcome: ____
  - Wrong study design: ____
  - Other pre-specified eligibility reason: ____
  - Other (____): ____

同一研究的伴随报告不自动作为全文排除理由；关联到同一 study_id，避免重复计算研究。完全相同报告的重复题录在去重阶段处理。

## Included
- Studies included in the review: ____
- Reports of included studies: ____   (a single study can have multiple reports)
- Studies included in quantitative synthesis (meta-analysis): ____

---
Number of independent screeners: ____   Conflict resolution: discussion / third reviewer (____)
Date search last run: ____
