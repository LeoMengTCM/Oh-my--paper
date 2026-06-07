# Sample-size & power cheatsheet (R)

Pre-specify α, power, and the **minimal clinically important difference (MCID)**, and
anchor expected rates/means to cited data. Then inflate for dropout and clustering.
Base R covers the common cases; `pwr` and `epiR` add convenience and effect sizes.
`install.packages(c("pwr","epiR"))` once if needed.

## Two means (continuous primary outcome)

```r
# Base R: detect a difference of `delta` given common SD `sd`
power.t.test(delta = 5, sd = 12, sig.level = 0.05, power = 0.90)  # -> n per group

# pwr, via standardized effect size d = delta / sd
library(pwr)
pwr.t.test(d = 5/12, sig.level = 0.05, power = 0.90, type = "two.sample")
```

## Two proportions (binary primary outcome)

```r
# control event rate 0.30, expected treatment rate 0.20
power.prop.test(p1 = 0.30, p2 = 0.20, sig.level = 0.05, power = 0.90)  # -> n per group

library(pwr)
pwr.2p.test(h = ES.h(0.30, 0.20), sig.level = 0.05, power = 0.90)
```

## Time-to-event (survival, log-rank)

```r
# Required number of EVENTS (Schoenfeld) for hazard ratio HR, then convert to n
hr <- 0.70; alpha <- 0.05; power <- 0.90
events <- (qnorm(1-alpha/2) + qnorm(power))^2 / (0.5*0.5*log(hr)^2)
events  # divide by the expected overall event probability to get enrolled N
# For full planning incl. accrual/follow-up use gsDesign::nSurv() or powerSurvEpi.
```

## Non-inferiority (different calculation!)

```r
# One-sided alpha, pre-agreed margin. Example for proportions with margin `m`.
# Powered on the NULL of "worse by at least m"; do NOT reuse a superiority n.
library(epiR)
epi.ssninfb(treat = 0.85, control = 0.85, delta = 0.10, n = NA,
            power = 0.80, r = 1, alpha = 0.025)  # delta = NI margin
```

## Adjustments applied AFTER the core calculation

```r
n_core   <- 210      # per group from above
dropout  <- 0.15     # expected loss to follow-up
n_enroll <- ceiling(n_core / (1 - dropout))     # inflate for dropout

# Cluster-randomized: design effect with mean cluster size m and ICC
m <- 20; icc <- 0.02
design_effect <- 1 + (m - 1) * icc
n_cluster <- ceiling(n_core * design_effect)
```

## Other common cases
- **Correlation**: `pwr::pwr.r.test(r = 0.3, power = 0.9)`
- **One-way ANOVA**: `pwr::pwr.anova.test(k = 3, f = 0.25, power = 0.9)`
- **Diagnostic accuracy**: size on the *expected sensitivity (in diseased)* and *specificity (in non-diseased)* CI width, then back out total N from disease prevalence (`epiR::epi.ssdxtest`).

> Report the tool/version, every input, and its source. A reviewer must be able to reproduce the number.
