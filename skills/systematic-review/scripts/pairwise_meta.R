# 仅分析已人工确认、每项研究一行的独立平行两组随机试验。
# 原始提取、人工决策与分析计划的留存由调用方负责；本脚本只写分析结果。

fail <- function(...) stop(..., call. = FALSE)

scalar_choice <- function(value, choices, field) {
  if (!is.character(value) || length(value) != 1L || is.na(value) ||
      !(value %in% choices)) {
    fail(field, " must be one of: ", paste(choices, collapse = ", "))
  }
  value
}

scalar_text <- function(value, field) {
  if (!is.character(value) || length(value) != 1L || is.na(value) ||
      !nzchar(trimws(value))) {
    fail(field, " must be a non-empty string")
  }
  value
}

read_inputs <- function(prepared_path, input_path) {
  prepared <- jsonlite::read_json(prepared_path, simplifyVector = FALSE)
  if (!is.list(prepared) || !is.numeric(prepared$schema_version) ||
      length(prepared$schema_version) != 1L ||
      !identical(as.numeric(prepared$schema_version), 1)) {
    fail("prepared.json schema_version must be 1")
  }
  analysis_id <- scalar_text(prepared$analysis_id, "analysis_id")
  plan <- prepared$plan
  if (!is.list(plan) || is.null(names(plan))) fail("plan must be a JSON object")
  measure <- scalar_choice(plan$effect_measure, c("RR", "MD", "SMD"), "effect_measure")
  scalar_choice(plan$model, "REML", "model")
  scalar_choice(plan$ci_method, c("z", "knha"), "ci_method")
  scalar_choice(plan$direction, c("lower_is_better", "higher_is_better"), "direction")
  confidence <- plan$confidence_level
  if (!is.numeric(confidence) || length(confidence) != 1L ||
      !is.finite(confidence) || confidence <= 0 || confidence >= 1) {
    fail("confidence_level must be a finite number strictly between 0 and 1")
  }
  if (measure == "RR") {
    scalar_choice(plan$zero_cell_correction, c("none", "constant_0.5"), "zero_cell_correction")
    scalar_choice(plan$double_zero_policy, c("error", "exclude"), "double_zero_policy")
  }
  if (!is.null(plan$plot_title)) scalar_text(plan$plot_title, "plot_title")
  if (!is.null(plan$font_family)) scalar_text(plan$font_family, "font_family")

  # 全部先按文本读取，避免缺失值、非法数值或重复列名被读取器悄悄改写。
  dat <- utils::read.csv(input_path, colClasses = "character", check.names = FALSE,
                         na.strings = character(), stringsAsFactors = FALSE,
                         fileEncoding = "UTF-8", blank.lines.skip = FALSE)
  numeric_fields <- c("n_intervention", "n_comparator", "events_intervention",
                      "events_comparator", "mean_intervention", "sd_intervention",
                      "mean_comparator", "sd_comparator")
  required <- c("extraction_id", "study_id", "label", "rob_judgment", numeric_fields)
  if (anyDuplicated(names(dat))) fail("input.csv has duplicate column names")
  missing_fields <- setdiff(required, names(dat))
  if (length(missing_fields)) {
    fail("input.csv is missing columns: ", paste(missing_fields, collapse = ", "))
  }
  for (field in c("extraction_id", "study_id", "label")) {
    if (any(is.na(dat[[field]]) | !nzchar(trimws(dat[[field]])))) {
      fail(field, " must not be missing or blank")
    }
  }
  if (anyDuplicated(trimws(dat$study_id))) fail("input.csv has duplicate study_id values")
  if (anyDuplicated(trimws(dat$extraction_id))) fail("input.csv has duplicate extraction_id values")
  for (field in numeric_fields) {
    text <- trimws(dat[[field]])
    present <- !is.na(text) & nzchar(text)
    values <- suppressWarnings(as.numeric(text))
    invalid <- present & !is.finite(values)
    if (any(invalid)) {
      fail(field, " must contain finite numbers; extraction_id: ",
           paste(dat$extraction_id[invalid], collapse = ", "))
    }
    dat[[field]] <- values
  }
  needed <- c("n_intervention", "n_comparator", if (measure == "RR") {
    c("events_intervention", "events_comparator")
  } else {
    c("mean_intervention", "sd_intervention", "mean_comparator", "sd_comparator")
  })
  for (field in needed) {
    if (any(!is.finite(dat[[field]]))) fail(field, " must not be missing; no implicit omission is allowed")
  }
  for (arm in c("intervention", "comparator")) {
    n <- dat[[paste0("n_", arm)]]
    if (any(n <= 0 | n != floor(n))) fail("n_", arm, " must contain positive integers")
    if (measure == "RR") {
      events <- dat[[paste0("events_", arm)]]
      if (any(events < 0 | events > n | events != floor(events))) {
        fail("events_", arm, " must contain integers between 0 and n_", arm)
      }
    } else {
      if (any(n < 2)) fail("Continuous outcomes require n >= 2 in each arm")
      if (any(dat[[paste0("sd_", arm)]] < 0)) fail("sd_", arm, " must be non-negative")
    }
  }
  list(analysis_id = analysis_id, plan = plan, data = dat)
}

# 单项置信区间一律使用正态近似；合并置信区间由指定的模型检验方法产生。
check_effects <- function(yi, vi) {
  if (any(!is.finite(yi)) || any(!is.finite(vi) | vi <= 0)) {
    fail("Every analyzed study must have finite yi and finite vi > 0; check zero cells and SDs")
  }
}

display_values <- function(values, measure) {
  result <- if (measure == "RR") exp(values) else values
  if (any(!is.finite(result)) || (measure == "RR" && any(result <= 0))) {
    fail("Effect or confidence limit is not representable on the display scale")
  }
  result
}

# 按显示宽度换行，中文或没有空格的长标签也保留完整内容。
wrap_label <- function(label, width = 44L) {
  paragraphs <- strsplit(label, "\n", fixed = TRUE)[[1L]]
  lines <- character()
  for (paragraph in paragraphs) {
    chars <- strsplit(paragraph, "", fixed = TRUE)[[1L]]
    line <- ""
    used <- 0L
    for (ch in chars) {
      size <- nchar(ch, type = "width")
      if (used + size > width && nzchar(line)) {
        lines <- c(lines, line)
        line <- ""
        used <- 0L
      }
      line <- paste0(line, ch)
      used <- used + size
    }
    lines <- c(lines, line)
  }
  paste(lines, collapse = "\n")
}

format_number <- function(value) trimws(formatC(value, digits = 4L, format = "g"))

# 只使用系统已有字体；Cairo 的默认 sans 在部分系统中不会自动补齐中文字形。
select_plot_font <- function(plan, labels) {
  if (!is.null(plan$font_family)) return(plan$font_family)
  if (!any(grepl("\\p{Han}", labels, perl = TRUE))) return("sans")
  if (identical(Sys.info()[["sysname"]], "Darwin") &&
      file.exists("/System/Library/Fonts/STHeiti Light.ttc")) return("Heiti SC")
  windows_font <- file.path(Sys.getenv("WINDIR", unset = ""), "Fonts", "msyh.ttc")
  if (.Platform$OS.type == "windows" && file.exists(windows_font)) return("Microsoft YaHei")
  fc_list <- Sys.which("fc-list")
  if (nzchar(fc_list)) {
    installed <- tryCatch(system2(fc_list, c(":lang=zh", "family"), stdout = TRUE, stderr = FALSE),
                           error = function(e) character())
    if (is.null(attr(installed, "status"))) {
      families <- trimws(unlist(strsplit(installed, ",", fixed = TRUE)))
      preferred <- c("Noto Sans CJK SC", "Noto Sans SC", "PingFang SC", "Heiti SC",
                     "Microsoft YaHei", "WenQuanYi Zen Hei", "Sarasa UI SC", "Arial Unicode MS")
      available <- preferred[preferred %in% families]
      if (length(available)) return(available[1])
      families <- families[nzchar(families) & !grepl("LastResort", families, fixed = TRUE)]
      if (length(families)) return(families[1])
    }
  }
  warning("No installed CJK font could be verified. Cairo will try sans:lang=zh-cn; inspect Chinese labels before using the plots, or set plan.font_family to an existing CJK font.", call. = FALSE)
  "sans:lang=zh-cn"
}

# 所有页面使用同一尺度和全体研究的合并结果，不在分页后重新拟合。
plot_forests <- function(effects, summary, plan, out_dir) {
  k <- nrow(effects)
  if (!k) return(invisible(0L))
  if (!isTRUE(capabilities("cairo")) || !isTRUE(capabilities("png"))) {
    fail("Forest plots require R cairo and png support; no packages or fonts will be installed")
  }
  pages <- split(seq_len(k), ceiling(seq_len(k) / 40L))
  font_family <- select_plot_font(plan, c(effects$label, plan$plot_title))
  labels <- vapply(effects$label, wrap_label, character(1))
  line_counts <- lengths(strsplit(labels, "\n", fixed = TRUE))
  units <- line_counts + 0.3
  heights <- vapply(pages, function(index) max(5.5, 2.0 + 0.22 * (sum(units[index]) + 6)), numeric(1))
  critical <- stats::qnorm((1 - plan$confidence_level) / 2, lower.tail = FALSE)
  ci_low <- effects$yi - critical * effects$se
  ci_high <- effects$yi + critical * effects$se
  limits <- range(c(ci_low, ci_high, 0, summary$ci_lower_analysis,
                    summary$ci_upper_analysis), finite = TRUE)
  span <- diff(limits)
  if (!is.finite(span) || span <= 0) fail("Cannot construct a finite forest-plot axis")
  alim <- limits + c(-1, 1) * 0.04 * span
  span <- diff(alim)
  xlim <- c(alim[1] - 1.12 * span, alim[2] + 0.91 * span)
  if (any(!is.finite(xlim))) fail("Cannot construct a finite forest-plot layout")
  at <- pretty(alim, n = 5)
  at <- at[at >= alim[1] & at <= alim[2]]
  if (plan$effect_measure == "RR") {
    # 对数坐标保持分析尺度，刻度和数值栏显示风险比。
    exponents <- seq(floor(alim[1] / log(10)), ceiling(alim[2] / log(10)))
    candidates <- as.vector(outer(log(c(1, 2, 5)), exponents * log(10), "+"))
    candidates <- sort(candidates[candidates >= alim[1] & candidates <= alim[2]])
    if (length(candidates) >= 3L && length(candidates) <= 10L) at <- candidates
    if (length(candidates) > 10L) {
      at <- sort(unique(c(0, candidates[round(seq(1, length(candidates), length.out = 7))])))
    }
    at <- at[is.finite(exp(at)) & exp(at) > 0]
  }
  transform <- if (plan$effect_measure == "RR") exp else NULL
  title <- if (is.null(plan$plot_title)) "Pairwise meta-analysis" else plan$plot_title
  direction <- if (plan$direction == "lower_is_better") {
    "Lower outcome values are better (lower_is_better)"
  } else {
    "Higher outcome values are better (higher_is_better)"
  }
  measure_label <- switch(plan$effect_measure, RR = "Risk ratio (log scale)",
                          MD = "Mean difference", SMD = "Hedges g")
  interval_text <- function(est, low, high) {
    paste0(format_number(est), " [", format_number(low), ", ", format_number(high), "]")
  }
  annotations <- interval_text(effects$estimate, effects$ci_lower, effects$ci_upper)
  pooled <- summary$analysis_status == "pooled"
  sizes <- if (pooled) 1.35 * sqrt(effects$weight_percent / max(effects$weight_percent)) else 1.35
  confidence_label <- paste0(format(100 * plan$confidence_level, trim = TRUE), "% CI")

  draw_page <- function(page_number) {
    index <- pages[[page_number]]
    page_units <- units[index]
    rows <- rev(cumsum(rev(page_units))) - page_units / 2 + 1
    top <- sum(page_units) + 1
    graphics::par(mar = c(5.8, 0.8, 4.5, 0.8), family = font_family, fg = "black", bg = "white")
    metafor::forest(effects$yi[index], vi = effects$vi[index],
                    ci.lb = ci_low[index], ci.ub = ci_high[index],
                    slab = labels[index], rows = rows, ylim = c(-2.8, top + 2),
                    xlim = xlim, alim = alim, at = at, refline = 0,
                    atransf = transform, level = 100 * plan$confidence_level,
                    annotate = FALSE, header = FALSE, pch = 15,
                    psize = if (pooled) sizes[index] else sizes,
                    col = "black", colci = "black", lty = c("solid", "solid"),
                    cex = 0.85, cex.axis = 0.8, digits = 3,
                    xlab = paste0(measure_label, ": Intervention vs comparator"),
                    textpos = xlim)
    graphics::text(xlim[1], top + 1, "Study", pos = 4, cex = 0.9, font = 2)
    graphics::text(xlim[2], top + 1, paste0(plan$effect_measure, " [", confidence_label, "]"),
                   pos = 2, cex = 0.9, font = 2)
    graphics::text(xlim[2], rows, annotations[index], pos = 2, cex = 0.85)
    if (pooled) {
      metafor::addpoly(summary$estimate_analysis, ci.lb = summary$ci_lower_analysis,
                       ci.ub = summary$ci_upper_analysis, rows = -0.4,
                       mlab = paste0("REML (all ", k, " studies)"),
                       atransf = transform, annotate = FALSE, cex = 0.85,
                       col = "black", border = "black")
      graphics::text(xlim[2], -0.4,
                     interval_text(summary$estimate, summary$ci_lower, summary$ci_upper),
                     pos = 2, cex = 0.85, font = 2)
      footer <- paste0("Squares: study estimates; area proportional to REML weight. Lines: normal ", confidence_label,
                       ".\nDiamond: overall REML estimate (", plan$ci_method, ", ", confidence_label, ").")
    } else {
      graphics::text(xlim[1], -0.4, "Single study: no pooled estimate or heterogeneity statistics", pos = 4, cex = 0.85)
      footer <- paste0("Square: study estimate. Line: normal ", confidence_label, ". No meta-analysis was fitted.")
    }
    page_title <- if (length(pages) > 1L) paste0(title, " | Page ", page_number, "/", length(pages)) else title
    graphics::mtext(paste(strwrap(page_title, width = 100), collapse = "\n"), side = 3, line = 2.5, cex = 1.1)
    graphics::mtext(paste0("Intervention vs comparator | ", direction), side = 3, line = 0.8, cex = 0.8)
    graphics::mtext(footer, side = 1, line = 4.1, cex = 0.7)
  }
  render_pdf <- function() {
    grDevices::cairo_pdf(file.path(out_dir, "forest.pdf"), width = 13, height = max(heights),
                         pointsize = 11, onefile = TRUE, family = font_family, bg = "white")
    on.exit(grDevices::dev.off(), add = TRUE)
    for (page in seq_along(pages)) draw_page(page)
  }
  render_png <- function(page, filename) {
    grDevices::png(filename, width = 13, height = heights[page], units = "in", res = 160,
                   pointsize = 11, type = "cairo", bg = "white")
    on.exit(grDevices::dev.off(), add = TRUE)
    draw_page(page)
  }
  render_pdf()
  render_png(1L, file.path(out_dir, "forest.png"))
  if (length(pages) > 1L) {
    for (page in seq_along(pages)) {
      render_png(page, file.path(out_dir, sprintf("forest-page-%03d.png", page)))
    }
  }
  invisible(length(pages))
}

main <- function() {
  args <- commandArgs(trailingOnly = TRUE)
  if (length(args) != 3L) fail("Usage: Rscript --vanilla pairwise_meta.R <prepared.json> <input.csv> <out-dir>")
  for (package in c("metafor", "jsonlite")) {
    if (!requireNamespace(package, quietly = TRUE)) fail("Required R package is not installed: ", package)
  }
  old_options <- options(na.action = "na.fail")
  on.exit(options(old_options), add = TRUE)
  warnings <- character()
  withCallingHandlers({
    inputs <- read_inputs(args[1], args[2])
    plan <- inputs$plan
    dat <- inputs$data
    measure <- plan$effect_measure
    k_selected <- nrow(dat)
    excluded <- data.frame(extraction_id = character(), study_id = character(), reason = character())
    if (measure == "RR") {
      double_zero <- dat$events_intervention == 0 & dat$events_comparator == 0
      if (any(double_zero)) {
        if (plan$double_zero_policy == "error") {
          fail("Double-zero-event studies are not estimable as RR; double_zero_policy=error; study_id: ",
               paste(dat$study_id[double_zero], collapse = ", "))
        }
        excluded <- data.frame(extraction_id = dat$extraction_id[double_zero],
                                study_id = dat$study_id[double_zero], reason = "double_zero_events")
        dat <- dat[!double_zero, , drop = FALSE]
        warnings <- c(warnings, paste0(nrow(excluded), " double-zero-event study/studies explicitly excluded by plan."))
      }
    }
    k <- nrow(dat)
    corrected <- rep(FALSE, k)
    yi <- vi <- numeric()
    if (k) {
      if (measure == "RR") {
        add <- if (plan$zero_cell_correction == "constant_0.5") 0.5 else 0
        ai <- dat$events_intervention
        bi <- dat$n_intervention - ai
        ci <- dat$events_comparator
        di <- dat$n_comparator - ci
        corrected <- add > 0 & (ai == 0 | bi == 0 | ci == 0 | di == 0)
        es <- metafor::escalc(measure = "RR", ai = ai, bi = bi, ci = ci, di = di,
                              add = add, to = "only0", drop00 = FALSE)
      } else {
        es <- metafor::escalc(measure = measure, m1i = dat$mean_intervention,
                              sd1i = dat$sd_intervention, n1i = dat$n_intervention,
                              m2i = dat$mean_comparator, sd2i = dat$sd_comparator,
                              n2i = dat$n_comparator, vtype = "LS", correct = TRUE)
      }
      yi <- as.numeric(es$yi)
      vi <- as.numeric(es$vi)
      if (length(yi) != k || length(vi) != k) fail("Effect calculation changed the number of studies")
      check_effects(yi, vi)
    }
    if (any(corrected)) {
      warnings <- c(warnings, paste0(sum(corrected), " study/studies received 0.5 in all four cells because at least one cell was zero (to=only0)."))
    }
    critical <- stats::qnorm((1 - plan$confidence_level) / 2, lower.tail = FALSE)
    se <- sqrt(vi)
    study_low <- yi - critical * se
    study_high <- yi + critical * se
    effects <- data.frame(extraction_id = dat$extraction_id, study_id = dat$study_id,
                          label = dat$label, yi = yi, vi = vi, se = se,
                          estimate = display_values(yi, measure),
                          ci_lower = display_values(study_low, measure),
                          ci_upper = display_values(study_high, measure),
                          weight_percent = rep(NA_real_, k), corrected = corrected,
                          stringsAsFactors = FALSE)
    # 不可用的统计量使用 NA，经 jsonlite 明确写为 null，绝不用零代替。
    summary <- list(schema_version = 1L, analysis_id = inputs$analysis_id,
                    analysis_status = if (k >= 2L) "pooled" else if (k == 1L) "single_study" else "not_estimable",
                    k_selected = k_selected, k_analyzed = k, k_excluded = nrow(excluded),
                    measure = measure, model_requested = plan$model, model_applied = NA_character_,
                    ci_method_requested = plan$ci_method, ci_method_applied = NA_character_,
                    confidence_level = plan$confidence_level, direction = plan$direction,
                    display_scale = switch(measure, RR = "ratio", MD = "difference", SMD = "standardized_difference"),
                    estimate = NA_real_, ci_lower = NA_real_, ci_upper = NA_real_,
                    estimate_analysis = NA_real_, ci_lower_analysis = NA_real_, ci_upper_analysis = NA_real_,
                    se_analysis = NA_real_, tau2 = NA_real_, I2 = NA_real_, Q = NA_real_, Q_p = NA_real_)
    if (k >= 2L) {
      fit <- metafor::rma(yi = yi, vi = vi, method = "REML", test = plan$ci_method,
                          level = 100 * plan$confidence_level)
      if (fit$k != k) fail("Model fitting changed the number of studies; implicit omission is forbidden")
      summary$model_applied <- "REML"
      summary$ci_method_applied <- plan$ci_method
      summary$estimate_analysis <- as.numeric(fit$b)
      summary$ci_lower_analysis <- as.numeric(fit$ci.lb)
      summary$ci_upper_analysis <- as.numeric(fit$ci.ub)
      summary$se_analysis <- as.numeric(fit$se)
      summary$tau2 <- as.numeric(fit$tau2)
      summary$I2 <- as.numeric(fit$I2)
      summary$Q <- as.numeric(fit$QE)
      summary$Q_p <- as.numeric(fit$QEp)
      effects$weight_percent <- as.numeric(stats::weights(fit))
      values <- unlist(summary[c("estimate_analysis", "ci_lower_analysis", "ci_upper_analysis",
                                 "se_analysis", "tau2", "I2", "Q", "Q_p")], use.names = FALSE)
      if (any(!is.finite(values)) || any(!is.finite(effects$weight_percent))) {
        fail("REML returned non-finite results; no result will be silently substituted")
      }
    } else if (k == 1L) {
      summary$ci_method_applied <- "normal_single_study"
      summary$estimate_analysis <- yi[1]
      summary$ci_lower_analysis <- study_low[1]
      summary$ci_upper_analysis <- study_high[1]
      summary$se_analysis <- se[1]
      warnings <- c(warnings, "Only one study is analyzable: a normal study CI is reported; no pooled model or heterogeneity statistics were estimated.")
    } else {
      warnings <- c(warnings, "No studies are analyzable: estimates are null and no forest plot is produced.")
    }
    if (k) {
      summary$estimate <- display_values(summary$estimate_analysis, measure)
      summary$ci_lower <- display_values(summary$ci_lower_analysis, measure)
      summary$ci_upper <- display_values(summary$ci_upper_analysis, measure)
    }
    summary$forest_pages <- as.integer(ceiling(k / 40L))
    if (summary$forest_pages > 1L) {
      warnings <- c(warnings, paste0("Forest plot has ", summary$forest_pages,
        " pages (at most 40 studies per page). forest.pdf contains all pages; forest.png is page 1; forest-page-NNN.png contains each page. Pooled diamonds use all analyzed studies, not page-specific subsets."))
    }
    out_dir <- args[3]
    if (!dir.exists(out_dir) && !dir.create(out_dir, recursive = TRUE)) fail("Cannot create output directory: ", out_dir)
    owned <- "^(summary\\.json|effects\\.csv|exclusions\\.csv|sessionInfo\\.txt|forest\\.(pdf|png)|forest-page-[0-9]+\\.png)$"
    if (length(list.files(out_dir, pattern = owned))) {
      fail("Output artifacts already exist; use a fresh output directory to avoid stale results")
    }
    plot_forests(effects, summary, plan, out_dir)
    utils::write.csv(effects, file.path(out_dir, "effects.csv"), row.names = FALSE, na = "", fileEncoding = "UTF-8")
    utils::write.csv(excluded, file.path(out_dir, "exclusions.csv"), row.names = FALSE, na = "", fileEncoding = "UTF-8")
    writeLines(capture.output(utils::sessionInfo()), file.path(out_dir, "sessionInfo.txt"), useBytes = TRUE)
    summary$excluded <- lapply(seq_len(nrow(excluded)), function(i) as.list(excluded[i, , drop = FALSE]))
    summary$warnings <- as.list(unique(warnings))
    summary$software <- list(R = as.character(getRversion()),
                             metafor = as.character(utils::packageVersion("metafor")),
                             jsonlite = as.character(utils::packageVersion("jsonlite")))
    jsonlite::write_json(summary, file.path(out_dir, "summary.json"), auto_unbox = TRUE,
                         na = "null", digits = 17, pretty = TRUE)
  }, warning = function(w) {
    warnings <<- c(warnings, conditionMessage(w))
    invokeRestart("muffleWarning")
  })
}

tryCatch(main(), error = function(e) {
  message("pairwise_meta: ", conditionMessage(e))
  quit(save = "no", status = 1L)
})
