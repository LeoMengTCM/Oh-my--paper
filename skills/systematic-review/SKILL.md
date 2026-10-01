---
id: systematic-review
name: systematic-review
description: Run a PRISMA 2020 systematic review and meta-analysis end to end from protocol and search through screening, risk-of-bias, evidence synthesis, and GRADE.
version: 1.0.0
stages: [survey, ideation, experiment, publication]
tools: [read_file, search_project, write_file, run_terminal]
domains: [clinical-medicine]
primaryIntent: research
intents: [research, writing]
keywords: [systematic-review, meta-analysis, prisma, grade, risk-of-bias, rob2, robins-i, quadas, forest-plot, evidence-synthesis]
status: verified
---

# systematic-review

本技能支持可追溯的系统综述及适合时的 Meta 分析。RCT 干预疗效任务先读
`references/rct-pairwise-profile.md`：明确探索与正式综述、方案批准、真实注册状态及分析边界。
系统综述不是精选论文阅读；注册值得优先完成，但不能把是否有注册号作为两者的唯一区别。
下述资源提供方法指导、起始模板、只读记录校验，以及受限范围的 RR/MD/SMD 统计适配器；不会自动完成全文筛选、原文数据提取、RoB 2 或 GRADE 判断。

Pair this skill with `pubmed-search` and `clinicaltrials-gov` for the searches, and
with `clinical-study-design` when the protocol needs PICO and registration support.

## Bundled resources

- `references/review-records.md` — JSON/JSONL 字段、人工判断与裁决、版本失效、导入预览和退出码
- `scripts/review_state.py` — 只读 validate / prisma，输出真实记录对应的 JSON 或 Markdown 计数
- `scripts/import_records.py` — PubMed JSON / RIS / CSV 导入预览，保留既有报告 ID，不自动写回
- `examples/rct-pairwise/` — 可运行的合成筛选示例，绝不能混入真实研究证据
- `references/extraction-and-analysis.md` — 提取出处、结果级人工 RoB 2 与分析计划规范
- `scripts/meta_analysis.py` / `scripts/pairwise_meta.R` — 校验后运行 RR/MD/SMD，保留输入、代码、结果与失败状态
- `examples/pairwise-analysis/` — 合成统计示例，含可手算的 REML 参考值
- `references/writing-handoff.md` — 当前分析、引用核验、部分交接与写作状态规范
- `scripts/writing_handoff.py` — 只读 check / 新目录 build，保留实际数字和待处理事项
- `examples/bcg-benchmark/` — 已发表 BCG 数据的数值复现，不作为真实临床综述验收

- `templates/prisma-flow.md` — the PRISMA 2020 flow-diagram counts to fill in as you screen
- `templates/data-extraction.csv` — a starting data-extraction sheet (one row per included study)
- `templates/risk-of-bias.md` — which RoB tool to use and the domains to record
- `references/meta-analysis-R.md` — copy-paste R (`metafor` / `meta`) for pooling, forest/funnel plots, and heterogeneity

Resolve all paths from this skill's directory; write every artifact into the active
project workspace (e.g. `survey/systematic-review/`), never back into the skill.

## 结构化记录的执行入口

先读 `references/review-records.md`。研究记录写入项目的 `.pipeline/systematic-review/`，与既有 PDF/OCR 文献库分开；不要在 skill 目录内写真实研究数据。

```bash
python3 scripts/review_state.py validate /path/to/project/.pipeline/systematic-review
python3 scripts/review_state.py prisma /path/to/project/.pipeline/systematic-review --format markdown
```

路径从本技能目录解析。退出 1 先修记录，退出 2 根据具体待处理事项继续工作，不把它误报为工具失败或全部完成。只有当前方案批准缺失时阻止依赖批准的筛选；正常的待筛选、检索 partial 或分歧应进入对应任务，不能等到“全部筛完”才允许开始筛选。退出 0 仅表示当前检索/筛选/归并记录完整，不代表 RoB、GRADE 或统计已完成。既有项目迁移须先确认，不用合成示例伪造人工批准。

## 统计执行入口

需要 RCT 成对 Meta 时先读 `references/extraction-and-analysis.md`。以 `extractions.jsonl` 保存有原文出处、原始值和人工核对记录的数据，`rob2.jsonl` 关联具体结果；旧 CSV 不会被猜测转换。

```bash
python3 scripts/meta_analysis.py validate /path/to/project/.pipeline/systematic-review --plan /path/to/analysis_plan.json
python3 scripts/meta_analysis.py run /path/to/project/.pipeline/systematic-review --plan /path/to/analysis_plan.json --out /path/to/new-run
```

范围仅为平行两组 RCT 的 RR/MD/SMD。零单元、双零事件和区间方法来自计划，不因结果方向更换；单研究、无可计算效应不伪装成合并结果。读取 run_manifest.json 确认 completed 后，再核对 summary.json、effects.csv 与图表；failed 不能写作已完成。ledger_entries.md 供负责人核查后登记，SoF 草稿的 GRADE 等字段必须继续人工评估。

## 写作交接入口

先读 `references/writing-handoff.md`，用项目的 publication.json 明确登记全部分析、报告引用键与核验证据：

```bash
python3 scripts/writing_handoff.py check /path/to/review --config /path/to/review/publication.json
python3 scripts/writing_handoff.py build /path/to/review --config /path/to/review/publication.json --out /path/to/new-handoff
```

只交接当前版本、输入匹配且产物未改动的 completed 运行。partial 包按 blockers 补齐后重新检查，
不能当作完整研究结果；ready_for_drafting 不代表已完成 GRADE 或可投稿。
review.json 与配置须登记相同 purpose；software_validation/public_benchmark 不成为真实研究写作包。
Crossref/人工记录核验只检查保存证据的一致性，引用语境需继续审查。

## Workflow (PRISMA 2020)

### 1. 先确定方案与批准版本，如实记录注册
定义 PICO/PECO、资格标准、检索策略、主要/次要结局、时间窗和 SAP。
正式筛选前由研究者批准具体版本，在 `decision_log.md` 留下批准者和时间。
尽可能前瞻性注册（如适用的 PROSPERO），但 planned/submitted 不得写成 registered；
未注册或不适用时说明理由并由研究者确认继续，不倒填注册或批准时间。
公开汇总数据不默认要求 IRB；具体数据来源有额外审批要求时另行核实。

### 2. Build and record the search strategy
- Search **at least two databases** plus a trial registry. For clinical questions that means MEDLINE (`pubmed-search`), and typically Embase and the Cochrane CENTRAL trials register; add `clinicaltrials-gov` for unpublished/ongoing studies to probe publication bias.
- Combine controlled vocabulary (MeSH/Emtree) with free-text synonyms for each PICO concept; join concepts with AND, synonyms with OR.
- **Record verbatim**: the exact query per database, the date run, and the number of hits. Save these — they populate the "Identification" box of the PRISMA flow and the reproducibility appendix.

### 3. De-duplicate and screen in two stages
- De-duplicate across databases; log the number removed.
- **Title/abstract screening**, then **full-text screening**, ideally by **two independent reviewers** with conflicts resolved by discussion or a third reviewer. Record inter-rater agreement if reported.
- 分别保留人工独立筛选、AI 建议与最终裁决。两名 AI 不等于两位研究者；单人流程如实报告限制。无法取得全文单列，不当作资格排除。
- For every full-text exclusion, record **one reason**. Keep a running tally in `templates/prisma-flow.md`.

### 4. Extract data
旧 `templates/data-extraction.csv` 仅为起始交换模板。实际提取必须区分研究与报告，
并按比较、结局、时间点和分析人群记录，保留页/表/章节出处、原始值与转换规则。
多份报告不能重复计入研究；缺失不当作 0。关键数据由研究者核对，AI 提取不能冒充双人独立提取。
该表尚未自动映射到 R 示例，必须先明确字段、单位和效应方向。

### 5. Assess risk of bias
Pick the tool that matches the design (see `templates/risk-of-bias.md`):
- **RoB 2** — randomized trials
- **ROBINS-I** — non-randomized studies of interventions
- **QUADAS-2** — diagnostic accuracy studies
- **Newcastle–Ottawa Scale** — cohort/case-control (a common lightweight alternative)
Assess per outcome where the tool requires it; never collapse to a single ad-hoc score.

### 6. Synthesize
- **Always** provide a structured narrative synthesis. Add a **meta-analysis only when studies are clinically and methodologically similar enough to pool** — otherwise synthesize without meta-analysis (SWiM) and say why.
- Choose the effect measure by outcome type: RR/OR/RD (binary), MD/SMD (continuous), HR (time-to-event).
- Prefer a **random-effects** model in clinical reviews (between-study heterogeneity is expected). Report the pooled estimate with 95% CI, **heterogeneity (I², τ², Cochran's Q)**, and a **forest plot**.
- Pre-specify **subgroup and sensitivity analyses**; do not data-dredge.
- 当独立研究数 ≥10 且方案预设的方法适用于该效应量时，再考虑小样本效应检验；不能把 Egger 检验一律用于二分类或 SMD。漏斗图不对称不是发表偏倚的确定证明，见 `references/meta-analysis-R.md`。

### 7. Rate certainty with GRADE
Rate certainty **per outcome** (High → Moderate → Low → Very low), downgrading for
risk of bias, inconsistency, indirectness, imprecision, and publication bias (and,
for observational evidence, upgrading for large effect / dose-response / plausible
confounding working against the effect). Summarize in a GRADE Summary-of-Findings table.

### 8. Report to PRISMA 2020
Report against the **PRISMA 2020 checklist** and include the **flow diagram**
(`templates/prisma-flow.md`). Hand the manuscript to the `scientific-writing` skill,
which already knows the PRISMA reporting guideline, and verify every citation with
`integrity-auditor`.

## Guardrails

- Never report a pooled estimate without heterogeneity statistics and a risk-of-bias assessment of its contributing studies.
- Do not pool clinically heterogeneous studies just because the numbers allow it.
- 保存完整检索式、运行时间、参数、命中/取回数和原始结果，以便复查；数据库会变化，不保证未来重跑计数完全相同。
- If a tool (R, a database) is unavailable, state the blocker and produce the manual artifact (hand-built search string, narrative synthesis) rather than skipping the step.
