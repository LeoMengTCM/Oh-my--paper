# SR-04 实施计划：带出处的提取与成对 Meta 分析

日期：2026-09-29
依据：已批准的总体设计与用户继续推进下一阶段的指令。

## 本轮交付

在既有 SR-02 记录上新增提取、结果级 RoB 2 记录与分析计划规范；提供 `meta_analysis.py validate|run` 和 R/metafor 执行器。仅支持平行组 RCT、两组比较、RR/MD/SMD。分析数据、计划、原文出处索引、代码、结果表、图、R session 与运行状态共同保存。

不实现自动从 PDF 推断数字、自动 RoB 2 算法、自动 GRADE、网状/诊断/IPD Meta、多臂/整群/交叉 RCT 的自动处理。程序检查登记记录的结构和关系，不证明原文真实或人类实际核对过。

## 数据和前置条件

- 继续使用 review.json、approvals、reports、studies、screening_decisions；正式分析要求当前检索/筛选/研究归并记录完整。
- `extractions.jsonl`：稳定 extraction_id、study_id、protocol_version、comparison_id、outcome_id、timepoint_id、analysis_population、measurement_type、effect_measure、unit、scale_id、direction、研究组标识、人工核对者和时间。
- 数值保存在 `data`，并保留 `original_data`。首版只接受值未转换的 identity 提取；转换后的单位、方向或估算 SD 必须回到研究者明确处理，不能暗中改变。缺失不是 0。
- 每个关键数值通过 `provenance` 引用 `evidence` 中的原文报告、定位和摘录；来源报告必须当前纳入且归并至同一研究。
- `rob2.jsonl`：结果级对象（研究、比较、结局、时间、人群）、工具版本、五个域的人工判断和理由、总体判断、完整人工评估文件及确认者。只读校验，不把域列表当作完整 RoB 2 自动实现。
- 分析计划 JSON 指定完整选择的 extraction_ids，明确比较/结局/时间窗/分析人群、单位、方向、效应量、REML、区间方法 z/knha、置信水平，以及 RR 的零单元校正与双零事件处理。计划记录具体方案版本及人工批准，不允许程序按结果挑方法。

同一分析中的 study_id 不可重复。MD 要求单位和量表一致；SMD 可以不同量表，但方向和测量类型必须一致。不自动翻转方向、合并时间点、混用末次值/变化值或推算缺失方差。

## 统计约定

- RR 在对数尺度分析、比值尺度展示；MD/SMD 不做指数转换。
- RR 校正必须明确为 none 或 constant_0.5；后者对含零单元的 2×2 表四个单元加 0.5。双零事件处理必须明确；若选择 exclude，保留完整输入并输出排除理由，不从系统综述中删除研究。
- MD 使用独立组方差；SMD 使用 metafor 的 Hedges' g，correct=TRUE、vtype=LS，记录软件版本与参数。
- 2 项以上可计算研究才做 REML 合并；区间方法来自计划，不为显著性更换。
- 只有 1 项研究时展示单项效应，不伪造异质性或合并分析。
- 无可计算效应时输出 not_estimable 与理由，允许结束本次执行但不伪造零效应。
- 不自动执行 Egger、亚组、敏感性分析或 GRADE；它们须另有预设方案。

## CLI 与输出

```text
meta_analysis.py validate <review-dir> --plan <plan.json>
meta_analysis.py run <review-dir> --plan <plan.json> --out <不存在的新目录>
```

validate 只读；run 先校验，再检查 R/metafor/jsonlite，输出至新目录，不覆盖旧结果或修改权威研究记录。结果目录包含运行清单、输入 CSV、来源/方案快照、R 代码、effects.csv、summary.json、排除说明、forest.pdf/png（有可计算效应时）、sessionInfo 和执行日志。失败保留 failed 状态与日志，不写成 completed。

生成供 agent 登记的 ledger 条目，不擅自修改其他目录的 experiment_ledger 或 figure_ledger。

## 验证

- Python 离线测试：出处缺失、未人工确认、来源未纳入、版本变化、重复研究、单位/方向/结局/人群不匹配、事件数越界、缺失、非支持设计、输入不变及输出不覆盖。
- 真实 R 测试只使用合成数据：RR、MD、SMD 单项值，解析可得的等方差 REML 例子，零单元与双零事件，单研究、无可计算结果、结果尺度、计划区间方法及失败状态。
- 本机使用隔离临时 R 库安装 metafor，不改全局库。记录实际版本。必须如实区分依赖失败、测试失败与通过。
- 使用黑白森林图、直接研究标签和置信区间，不以颜色承担身份。PNG 与 PDF 使用相同绘图函数；生成后目视检查轴、参考线、标签和布局。
- CI 增加要求统计依赖存在的验证入口，不能把统计测试跳过当作发布验收通过。

不提交、不推送，不运行真实患者数据或真实课题分析。
