# Meta-analysis in R — runnable snippets

Two mainstream packages: `metafor` (flexible, model-first) and `meta`
(convenience wrappers). Install once: `install.packages(c("metafor","meta"))`.
统计模型、方差估计和区间方法由批准的 SAP 决定。下方随机效应代码是示例，不替代临床可合并性判断；
先核对独立研究、结局时间窗、字段单位及零事件规则，再执行。输出效应量、95% CI 和适用的异质性统计。
森林图使用单一效应尺度、研究标签和置信区间，不靠颜色区分结果；正式输出还需核对表格与图形布局。
少于 10 个独立研究不执行小样本效应检验，达到 10 个也不是自动执行条件。

## Binary outcomes (events / total per arm) — metafor

```r
library(metafor)
# df 须先明确映射字段；旧 data-extraction.csv 不能直接作为本示例输入。
# 每行一个独立研究的同一比较、结局和时间窗；零事件策略须在 SAP 中确定。
# 所需列：author, year, ev_t, n_t（干预组）, ev_c, n_c（对照组）。
measure <- "RR"                         # "RR" | "OR" | "RD"，由批准的方案决定
stopifnot(measure %in% c("RR", "OR", "RD"))
dat <- escalc(measure = measure,
              ai = ev_t, n1i = n_t,
              ci = ev_c, n2i = n_c,
              data = df, slab = paste(author, year))

res <- rma(yi, vi, data = dat, method = "REML")
summary(res)
if (measure %in% c("RR", "OR")) {
  pooled <- predict(res, transf = exp)  # 对数比值还原到比值尺度
  forest(res, transf = exp, refline = 1,
         header = c("Study", paste0(measure, " [95% CI]")))
} else {
  pooled <- predict(res)               # RD 保持风险差尺度，不能 exp
  forest(res, refline = 0, header = c("Study", "RD [95% CI]"))
}
print(pooled)
# 不自动运行 funnel/regtest；见下方小样本效应检验的适用条件。
```

## Continuous outcomes (mean, SD, n per arm) — metafor

```r
dat <- escalc(measure = "SMD",           # "MD" if all studies use the same scale
              m1i = mean_t, sd1i = sd_t, n1i = n_t,
              m2i = mean_c, sd2i = sd_c, n2i = n_c,
              data = df, slab = paste(author, year))
res <- rma(yi, vi, data = dat, method = "REML")
forest(res, header = TRUE)
```

## Pre-computed effects (e.g., hazard ratios from each paper) — generic inverse-variance

```r
# df: yi = log(HR), sei = standard error of log(HR)
res <- rma(yi = log_hr, sei = se_log_hr, data = df, method = "REML")
predict(res, transf = exp)               # pooled HR
```

## Subgroup analysis and meta-regression

```r
rma(yi, vi, mods = ~ subgroup, data = dat)      # test effect modification
rma(yi, vi, mods = ~ year + mean_age, data = dat)
```

## Sensitivity analysis

```r
leave1out(res)                                   # influence of each single study
rma(yi, vi, data = dat, subset = (risk_of_bias == "low"))  # restrict to low-RoB
```

## Same analyses with the `meta` package (convenience API)

```r
library(meta)
mb <- metabin(ev_t, n_t, ev_c, n_c, studlab = paste(author, year),
              data = df, sm = "RR", method = "MH", random = TRUE)
forest(mb)  # 小样本效应检验不默认执行，不能把 linreg 一律用于二分类结局

mc <- metacont(n_t, mean_t, sd_t, n_c, mean_c, sd_c,
               studlab = paste(author, year), data = df, sm = "SMD", random = TRUE)
summary(mc)
```

## 小样本效应检验：先确认适用性

先确认 `res` 是本次分析的模型。下列代码只在独立研究数足够且研究者已确认 SAP 中的检验适用时执行。
Egger 检验不能一律用于二分类结局或 SMD；不适用时采用预设的合适方法或说明未执行。
漏斗图不对称还可能来自异质性等原因，不是发表偏倚的确定证明。

```r
small_study_test <- "none"              # 只有 SAP 预设且适用时才改为 "egger"
if (small_study_test == "egger" && res$k >= 10L) {
  funnel(res)
  regtest(res, model = "lm", predictor = "sei")
} else {
  message("未执行 Egger 检验：未预设适用方法，或独立研究不足 10 项。")
}
```

## Reading heterogeneity
- **I²**：结合不确定性、效应方向与临床差异解释，不把 25/50/75% 当作固定的可合并性阈值。
- **τ²**：研究间方差的估计；估计为 0 不证明不存在异质性，也不应据此事后改为固定效应模型。
- 预测区间与平均效应的置信区间回答不同问题；研究少时要说明不确定性。

## API 核对来源

- [metafor forest.rma](https://wviechtb.github.io/metafor/reference/forest.rma.html)：`transf` 转换效应与坐标，`atransf` 只转换标签；参考线必须匹配实际坐标尺度。
- [metafor predict.rma](https://wviechtb.github.io/metafor/reference/predict.rma.html)：比值效应的对数尺度还原。
- 本文件是方法示例。结构化 RCT 输入使用 `scripts/meta_analysis.py` 和 `references/extraction-and-analysis.md`；不要直接把旧 CSV 交给这些片段。
