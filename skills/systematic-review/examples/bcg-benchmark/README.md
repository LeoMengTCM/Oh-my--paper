# BCG 公开数值基准

复现 Viechtbauer (2010), *Conducting Meta-Analyses in R with the metafor Package*,
Journal of Statistical Software 36(3), [DOI: 10.18637/jss.v036.i03](https://doi.org/10.18637/jss.v036.i03)
第 14 页的 REML 模型结果。参考值来自论文印刷数值；四位小数的绝对容差为 0.00005，
不在测试中用被测函数生成期望值。

原始计数通过已安装的 `metadat::dat.bcg` 读取，保留为 `dataset.csv`。
`source.json` 保存实际版本、许可和分配类型；本次验证使用 metadat 1.6.0，许可 GPL (>= 2)。
仓库不重新分发原论文 PDF 或数据表；只提供调用公开数据包的脚本。
官方 R 包 metafor 附带论文 PDF，可用 `system.file("doc/metafor.pdf", package="metafor")` 查找。

从仓库根目录运行，需要 R、metafor、jsonlite 和 metadat：

```bash
python3 skills/systematic-review/examples/bcg-benchmark/run_benchmark.py --out /path/to/new-bcg-run
```

脚本读取原表后明确计算每组总人数，以同一 `pairwise_meta.R` 内核计算 RR/REML，
保存输入、代码、结果、图表、R session 信息及 `benchmark.json` 比较报告。
退出 0 表示匹配参考值，2 表示计算失败或数值不匹配，1 表示入口错误。
输出目录必须是新目录，脚本不联网、不安装包。

13 项研究包含 7 random、2 alternate、4 systematic。这是 `public_benchmark`，
不会生成筛选决定、人工批准、RoB 2 或临床运行清单，`ready_for_drafting` 始终为 false。
研究用 Python 入口仍只接受经批准的平行组 RCT 记录；此基准仅调用数值内核，
不能作为真实系统综述从检索到写作的端到端验收。
