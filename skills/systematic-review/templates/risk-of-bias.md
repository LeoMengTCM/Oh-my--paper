# Risk-of-bias assessment — pick the tool by design

Assess each included study with the tool that matches its design. For RoB 2 and
ROBINS-I, assess **per outcome** (a study can be low risk for one outcome and high
for another). Record a judgement *and a one-line rationale* for every domain, then an
overall judgement.

## RoB 2 — randomized controlled trials
Domains (each: Low / Some concerns / High):
1. Bias arising from the randomization process
2. Bias due to deviations from intended interventions (effect of assignment / adhering)
3. Bias due to missing outcome data
4. Bias in measurement of the outcome
5. Bias in selection of the reported result

使用当前版本官方 RoB 2 的信号问题和决策规则，记录算法建议与人工判断。任何域 high 通常要求总体 high；所有域 low 才能总体 low。多个 some_concerns 若显著降低对结果的信任，也可能总体 high，因此不能简单采用“最差域”。人工偏离算法建议时保留理由。

此处只是域清单，不是完整 RoB 2 工具。正式表格与说明见 <https://www.riskofbias.info/welcome/rob-2>。SR-04 的 `rob2.jsonl` 还需关联具体研究、比较、结局、时间、人群、目标效应和完整人工评估文件，字段见 `references/extraction-and-analysis.md`；代码检查不等于人工评估已真实完成。

## ROBINS-I — non-randomized studies of interventions
Domains (Low / Moderate / Serious / Critical / No information):
1. Confounding
2. Selection of participants into the study
3. Classification of interventions
4. Deviations from intended interventions
5. Missing data
6. Measurement of outcomes
7. Selection of the reported result

Pre-specify the confounders and any co-interventions before assessing.

## QUADAS-2 — diagnostic accuracy studies
Four domains, each rated for risk of bias (and the first three also for applicability):
1. Patient selection
2. Index test
3. Reference standard
4. Flow and timing

## Newcastle–Ottawa Scale — cohort / case-control (lightweight alternative)
Stars across Selection / Comparability / Outcome (cohort) or Exposure (case-control);
typically 0–9 stars. State your good/fair/poor thresholds in the protocol.

---
**Reporting:** present a risk-of-bias summary (traffic-light) figure and feed each
judgement into the GRADE "risk of bias" domain for the affected outcome.
