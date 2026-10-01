# 合成成对 Meta 分析示例

所有研究、报告、提取值、原文摘录和人工批准都是**合成测试数据**，不是临床证据，不得复制成真实研究记录。

从 `systematic-review` 技能目录运行：

```bash
python3 scripts/meta_analysis.py validate examples/pairwise-analysis \
  --plan examples/pairwise-analysis/analysis_plan.json

# 需要本机 R、metafor、jsonlite；结果必须使用新的目录。
python3 scripts/meta_analysis.py run examples/pairwise-analysis \
  --plan examples/pairwise-analysis/analysis_plan.json \
  --out /path/to/new-synthetic-analysis --reason software_validation
```

三个研究的 MD 分别为 -1、-2、-3，每项方差为 0.1。预设 REML + z 区间的解析参考结果：

- 合并 MD = -2。
- tau² = 0.9。
- SE = sqrt(1/3)。
- 95% CI 约为 [-3.131585734, -0.868414266]。

这些参考值用于测试软件，不是研究发现。完整字段和边界见 `../../references/extraction-and-analysis.md`。

输出的 SoF 文件是草稿，GRADE、基线风险与绝对效应没有自动生成。图表需要人工复核，运行成功不等于研究或投稿准备完成。
