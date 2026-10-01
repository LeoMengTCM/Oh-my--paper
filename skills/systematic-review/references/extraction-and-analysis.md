# SR-04：提取证据与成对 Meta 分析

首版只处理平行组 RCT、两组独立样本的 RR/MD/SMD。Python 校验研究记录与计划，R/metafor 计算效应量并生成森林图。它不是自动 PDF 数据提取器，也不是自动 RoB 2 或 GRADE 评估器。

## 使用

从实际 `systematic-review` 技能目录解析脚本，在研究项目中使用：

```bash
python3 scripts/meta_analysis.py validate /path/to/project/.pipeline/systematic-review \
  --plan /path/to/analysis_plan.json

python3 scripts/meta_analysis.py run /path/to/project/.pipeline/systematic-review \
  --plan /path/to/analysis_plan.json --out /path/to/new-analysis-directory \
  --reason prespecified_analysis
```

- validate 只读，不需要安装 R 包。
- run 先校验，再检查 R/metafor/jsonlite，结果只写入不存在的新目录，不覆盖旧运行或修改权威研究文件。
- `--rscript` 或 `RSCRIPT` 指定 Rscript 可执行文件；不接受一整串 shell 命令。
- `--reason` 记录此次是预设分析、复现或错误修复；它不代替方案变更的人工批准。
- 退出 0：校验 ready，或本次执行 completed；不是整项研究或投稿准备已完成。
- 退出 1：格式、数值、选择、出处、方法或输出目录错误。
- 退出 2：研究流程尚未完成、人工判断不可合并、依赖缺失，或运行 failed。根据 reason/status 处理，不为得到显著结果修改分析。

## 前置记录

沿用 `review-records.md` 的研究目录。正式统计前要求当前检索、筛选与研究归并完整；未解决分歧、过期批准或 partial 来源不能被忽略。

在目录中增加：

- `extractions.jsonl`：逐项结果的提取记录。
- `rob2.jsonl`：针对具体结果的人工偏倚评价记录。

每行带 schema_version=1。旧版本和未选择记录可以保留；分析只使用计划显式列出的 extraction_ids。程序不替研究者决定哪些结局或研究应被选择，也不证明选择覆盖全部可用证据。

## 分析计划

计划是 JSON 对象，必填：

| 字段 | 说明 |
|---|---|
| schema_version、analysis_id、protocol_version | schema 为 1，方案版本必须是当前版本 |
| extraction_ids | 明确选择的提取 ID，不重复；同一分析不得重复 study_id |
| comparison_id、outcome_id、timepoint_id、analysis_population | 预设比较、结局、时间窗与分析人群 |
| measurement_type | final 或 change，不混用末次值和变化值 |
| effect_measure | RR、MD 或 SMD |
| unit、scale_id | 单位与量表；MD/RR 必须与输入一致；SMD 允许不同量表和单位，但必须是可比较的同一结局 |
| direction | lower_is_better 或 higher_is_better；不自动翻转量表 |
| model | 首版为 REML |
| ci_method、confidence_level | z 或 knha，置信水平介于 0 和 1 |
| target_effect | assignment 或 adherence，必须与人工 RoB 2 对象一致 |
| clinically_poolable、pooling_rationale | 人工可合并性判断及依据；false 不运行 Meta，转叙述性综合 |
| approved_by、approved_at | 登记的人类与批准时间，不早于当前研究方案批准 |

RR 另需：

- `zero_cell_correction`: none 或 constant_0.5。
- `double_zero_policy`: error 或 exclude。

可选 `plot_title`、`font_family`。字体必须在本机已有；脚本不自动安装字体。

这些字段是人工决定的记录，不是身份认证或电子签名。批准后改变计划内容必须按项目规则升级版本、重新确认并记录偏离；仅保留原批准字段不代表新计划也已获批。

## 提取记录

extractions.jsonl 必填：

- extraction_id、study_id、protocol_version。
- 与计划一致的 comparison_id、outcome_id、timepoint_id、analysis_population、measurement_type、direction、effect_measure。
- label（森林图研究标签）、unit、scale_id、intervention_arm、comparator_arm。
- verified_by、verified_at：人类核对记录，不用 AI 身份代替。
- risk_of_bias_id：指向该结果的 RoB 2 记录。
- data、original_data、transformation、evidence、provenance。

### 数值

RR 的 data 和 original_data 都只包含：

```json
{"n_intervention":100,"n_comparator":100,"events_intervention":20,"events_comparator":40}
```

MD/SMD 的数值字段：

```json
{"n_intervention":20,"n_comparator":20,"mean_intervention":9,"mean_comparator":10,"sd_intervention":1,"sd_comparator":1}
```

首版 transformation 只能为 identity，data 与 original_data 的数值必须相同。原文字符、表述和全角数值可留在 quote 中。缺失不能填 0，SD 估算、单位转换、效应方向翻转和中位数转均值不在本版自动处理范围。

n 必须为正整数；连续结局每组至少 2 人；事件数在 0 到 n 之间；SD 非负且效应方差不能为零。R 还会再次检查效应和方差有限，禁止隐式 NA 删除。

### 出处

```json
{
  "evidence": [{
    "evidence_id": "table-2",
    "report_id": "report-1",
    "document_path": "../literature/corpus/papers/paper-1/paper.pdf",
    "locator": "第5页，表2，12周结局",
    "quote": "填写实际原文摘录"
  }],
  "provenance": {
    "n_intervention": "table-2",
    "n_comparator": "table-2",
    "events_intervention": "table-2",
    "events_comparator": "table-2"
  }
}
```

每个数值必须关联出处。来源报告必须当前纳入且归并到同一研究；文档路径相对研究记录目录，也可为绝对路径。程序检查文件存在、定位和摘录非空及人工核对者，不自动证明摘录与 PDF 原文一致，也不证明数字提取正确。核对仍由研究者完成。

多篇报告可以为同一条提取提供不同出处；同一研究不能在同一分析中因多篇报告被重复计数。

## 结果级 RoB 2 记录

每条含 assessment_id、study_id、protocol_version、comparison_id、outcome_id、timepoint_id、analysis_population、target_effect、tool="RoB2"、tool_version、reviewed_by、reviewed_at、assessment_document、overall_judgment 和 domains。

domains 必须有 randomization、deviations、missing_data、measurement、selection 五个键；每个值含 judgment（low/some_concerns/high）和 rationale。assessment_document 指向非空的完整人工评估文件，保留信号问题、依据、算法建议与人工理由。

脚本只检查结果关联及明显矛盾，例如高风险域不能对应总体低风险；不会执行完整官方 RoB 2 算法。多个 some_concerns 可能导致总体 high，不能简单用“最差域”替代人工判断。

计算器使用原始两组汇总统计，不自动进行依从性校正或因果调整。若目标效应需要调整后的估计量及协方差，不能只更改 target_effect 字段来代替正确方法。

## 统计处理

- RR 使用 log(RR) 分析、比值尺度展示。constant_0.5 对至少一个零单元的 2×2 表四格均加 0.5；这也会改变用于计算的分母，原输入不改写。
- 双零事件选 exclude 时，记录在 exclusions.csv 和 summary.json，不从系统综述中删研究。
- MD 为干预减对照，使用独立组方差。
- SMD 为 Hedges' g，metafor escalc 的 correct=TRUE、vtype=LS。不把不同结局仅因可标准化就合并。
- 至少 2 项可计算研究才拟合 REML；z/knha 由计划指定。
- 单研究为 single_study：正常显示单项正态 CI，但不报告合并模型、τ²/I²/Q。
- 无可计算效应为 not_estimable：估计值为 null，不画森林图，不用零替代。
- 不自动运行 Egger、亚组、敏感性分析或 GRADE。

## 运行目录

- run_manifest.json：运行 ID、输入位置、原因、running/completed/failed、版本及产物。
- prepared.json、input.csv：冻结的计划与本次计算输入。
- source_snapshot.json：选中提取、原始值、出处索引、研究与人工评价记录；不复制或上传论文全文。
- pairwise_meta.R：实际执行代码副本，可配合 input.csv 和 prepared.json 重现计算。
- effects.csv、exclusions.csv、summary.json：单项/合并结果及明确排除。
- forest.pdf、forest.png：同一绘图函数输出；超过 40 项时 PDF 分页，并提供 forest-page-NNN.png。forest.png 仅为首张，汇总菱形始终使用全部被分析研究。
- sessionInfo.txt、run.stdout.txt、run.stderr.txt：软件环境和日志。
- ledger_entries.md：供负责人核查后追加到实验/图表记录，程序不直接改项目记忆。
- summary_of_findings_draft.csv：从本次结果生成的 SoF 草稿，区分选择与实际计算的研究/人数；certainty、基线风险和绝对效应留空，grade_status=not_assessed，不能作为完成的 GRADE 表。

R 返回 0 不足以标完成；Python 还核对结果 schema、选择数量、效应量、区间方法、实际效应行和图形产物。失败保留 failed 状态与日志，不覆盖旧运行。

## 依赖与验证

本轮实测：R 4.6.0、metafor 5.2.1、jsonlite 2.0.0。示例测试只用合成数据，验证 RR、MD、SMD、REML、Knapp–Hartung、零单元、单研究和分页。已在本机检查中文 MD/RR PNG 与 PDF 字体显示；其他系统的字体仍须目视复核。

安装到独立 R 库的示例（请先选择库路径）：

```r
lib <- "/path/to/isolated-r-library"
dir.create(lib, recursive=TRUE, showWarnings=FALSE)
install.packages(c("metafor", "jsonlite"), lib=lib, repos="https://cloud.r-project.org")
```

运行时通过 R_LIBS_USER 使用该库。仓库 `npm run test:sr:stats` 强制要求统计依赖，缺失不能跳过；普通 npm test 会明确跳过不可执行的统计测试。CI 另有真实统计任务，并检查已测试包版本；若 CRAN 默认版本变化，需经复核后更新版本要求，不把新版本默认为已经验收。

尚未验证真实研究原文、真实人工评估、远端服务器或临床结论；不能把软件回归通过写成研究证据有效。
