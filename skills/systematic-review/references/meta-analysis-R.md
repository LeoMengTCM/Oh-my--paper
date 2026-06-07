# Meta-analysis in R — runnable snippets

Two mainstream packages: `metafor` (flexible, model-first) and `meta`
(convenience wrappers). Install once: `install.packages(c("metafor","meta"))`.
Prefer a **random-effects** model for clinical reviews. Report the pooled effect with
95% CI, heterogeneity (I², τ², Q), a forest plot, and — with ≥10 studies — a funnel
plot and Egger's test.

## Binary outcomes (events / total per arm) — metafor

```r
library(metafor)
# df columns: author, year, ev_t, n_t (intervention), ev_c, n_c (comparator)
dat <- escalc(measure = "RR",            # "RR" | "OR" | "RD"
              ai = ev_t, n1i = n_t,
              ci = ev_c, n2i = n_c,
              data = df, slab = paste(author, year))

res <- rma(yi, vi, data = dat, method = "REML")   # random-effects
summary(res)                                       # pooled est, CI, I^2, tau^2, Q, p
predict(res, transf = exp)                         # back-transform log-RR/OR to ratio scale

forest(res, atransf = exp, refline = 1,
       header = c("Study", "RR [95% CI]"))
funnel(res); regtest(res)                          # Egger's test (use only if k >= 10)
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
forest(mb); funnel(mb); metabias(mb, method = "linreg")   # Egger

mc <- metacont(n_t, mean_t, sd_t, n_c, mean_c, sd_c,
               studlab = paste(author, year), data = df, sm = "SMD", random = TRUE)
summary(mc)
```

## Reading heterogeneity
- **I²**: ~25% low, ~50% moderate, ~75% high. High I² → explain it (subgroups), do not just pool harder.
- **τ²**: between-study variance on the effect scale; 0 means a fixed-effect model would have sufficed.
- A wide prediction interval (`predict(res)`) is often more honest than the CI of the mean effect.
