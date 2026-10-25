#!/usr/bin/env Rscript
# meta_analysis.R — 第 7 站標準版（R + meta 套件）
#
# 用法：
#   Rscript meta_analysis.R --outcomes extraction_outcomes.csv --outcome "TAM" --timepoint "12w" \
#       --measure MD --out results/ [--rob rob.csv] [--subgroup design] [--studies extraction.csv]
#
# 教學重點：
#   * meta 套件的 metacont()（連續）與 metabin()（二元）就是整個 meta-analysis 的核心。
#   * 我們先把資料「清乾淨」（SD 換算、方向統一），再丟給它。
#   * 每一步都把結果寫進 results/，稿件裡的每個數字都要能回溯到這裡。

suppressPackageStartupMessages({
  for (p in c("meta", "metafor", "optparse")) {
    if (!requireNamespace(p, quietly = TRUE)) install.packages(p, repos = "https://cloud.r-project.org")
    library(p, character.only = TRUE)
  }
})

`%||%` <- function(a, b) if (is.null(a)) b else a  # R < 4.4 沒有內建

opt <- OptionParser() |>
  add_option("--outcomes", type = "character") |>
  add_option("--studies", type = "character", default = NULL, help = "extraction.csv，用來取亞組變項") |>
  add_option("--rob", type = "character", default = NULL) |>
  add_option("--outcome", type = "character") |>
  add_option("--timepoint", type = "character", default = NULL) |>
  add_option("--measure", type = "character", default = "MD", help = "MD / SMD / RR / OR") |>
  add_option("--subgroup", type = "character", default = NULL, help = "studies 檔裡的欄位名") |>
  add_option("--out", type = "character", default = "results/") |>
  parse_args()

# ---------- 0. 閘門：在題目工作區內時，上游全部簽核且未被改動才准開工 ----------
# 目錄結構：<root>/projects/<題目>/07_analysis/ ；root 是放 gate.py 的那層
find_root <- function() {
  p <- normalizePath(getwd())
  for (i in 1:6) { if (file.exists(file.path(p, "gate.py"))) return(p); p <- dirname(p) }
  NULL
}
root <- find_root()
proj_dir <- dirname(normalizePath(getwd()))          # projects/<題目>
in_project <- !is.null(root) && file.exists(file.path(proj_dir, "manifest.json")) &&
  normalizePath(dirname(proj_dir)) == normalizePath(file.path(root, "projects"))
if (in_project) {
  rc <- system2("python3", c(file.path(root, "gate.py"), "check", basename(proj_dir), "07"))
  if (rc != 0) stop("第 07 站不能開工：上游尚未簽核或已被改動（見上方訊息）。")
} else {
  message("⚠ 不在任何題目的工作區內，跳過閘門檢查。正式作業請在 projects/<題目>/07_analysis/ 底下執行。")
}

dir.create(opt$out, showWarnings = FALSE, recursive = TRUE)
log_line <- function(...) cat(sprintf(...), "\n", file = file.path(opt$out, "summary.txt"), append = TRUE)
file.create(file.path(opt$out, "summary.txt"))

# ---------- 1. 讀資料、篩 outcome 與時間點 ----------
d <- read.csv(opt$outcomes, stringsAsFactors = FALSE)
d <- d[d$outcome == opt$outcome, ]
# 時間點保護：同一研究不同追蹤時間不能混進同一張森林圖（同一群病人會被算兩次）
tps <- unique(d$timepoint)
if (is.null(opt$timepoint)) {
  if (length(tps) > 1) stop(sprintf("此 outcome 有 %d 個時間點（%s），必須用 --timepoint 指定其中一個。", length(tps), paste(tps, collapse = ", ")))
} else {
  d <- d[d$timepoint == opt$timepoint, ]
}
if (nrow(d) < 2) stop("少於 2 篇，無法合併。")
dup_ids <- d$id[duplicated(d$id)]
if (length(dup_ids) > 0) stop(sprintf("研究 ID 重複：%s。多臂試驗請先在第 5 站決定合併或選臂，再跑分析。", paste(unique(dup_ids), collapse = ", ")))
log_line("Outcome: %s | Timepoint: %s | Measure: %s | k = %d", opt$outcome, opt$timepoint %||% "all", opt$measure, nrow(d))

# ---------- 2. 清資料：SD 換算與方向統一 ----------
# Cochrane Handbook 6.5.2.x：
#   mean_se : SD = SE × √n
#   mean_ci : sd 欄填的是 95% CI 寬度 (upper − lower)，SD = √n × 寬度 / 3.92
#   median/IQR 需在第 5 站先以 Wan/Luo 法換算成 mean_sd。
fix_sd <- function(sd, n, how) {
  ifelse(how == "mean_se", sd * sqrt(n),
  ifelse(how == "mean_ci", sqrt(n) * sd / 3.92,
         sd))
}
if (opt$measure %in% c("MD", "SMD")) {
  conv <- d$reported_as != "mean_sd"
  if (any(conv)) {
    log_line("注意：%d 列的 SD 由 %s 換算而來，請確認。", sum(conv), paste(unique(d$reported_as[conv]), collapse = ","))
    d$sd_int[conv] <- fix_sd(d$sd_int[conv], d$n_int[conv], d$reported_as[conv])
    d$sd_ctl[conv] <- fix_sd(d$sd_ctl[conv], d$n_ctl[conv], d$reported_as[conv])
  }
  # 方向統一：higher_is_better == "no" 的 outcome（例如疼痛）乘 -1，讓「正值 = 介入組較好」
  flip <- d$higher_is_better == "no"
  if (any(flip)) { d$mean_int[flip] <- -d$mean_int[flip]; d$mean_ctl[flip] <- -d$mean_ctl[flip]; log_line("方向翻轉 %d 列（higher_is_better = no）", sum(flip)) }
}

# 亞組變項（來自 studies 檔）
if (!is.null(opt$subgroup) && !is.null(opt$studies)) {
  s <- read.csv(opt$studies, stringsAsFactors = FALSE)
  d$subgroup <- s[[opt$subgroup]][match(d$id, s$id)]
}
# 偏倚（來自 rob 檔）給敏感度用
if (!is.null(opt$rob)) {
  r <- read.csv(opt$rob, stringsAsFactors = FALSE)
  d$rob <- r$overall[match(d$id, r$id)]
}
d$label <- paste(d$id, d$year %||% "", sep = " ")

# ---------- 3. 主分析：隨機效應（REML）為主，同時報固定效應 ----------
if (opt$measure %in% c("MD", "SMD")) {
  m <- metacont(n.e = n_int, mean.e = mean_int, sd.e = sd_int,
                n.c = n_ctl, mean.c = mean_ctl, sd.c = sd_ctl,
                studlab = label, data = d, sm = opt$measure,
                method.tau = "REML", common = TRUE, random = TRUE,
                subgroup = if (!is.null(opt$subgroup)) subgroup else NULL)
} else {
  m <- metabin(event.e = events_int, n.e = n_int, event.c = events_ctl, n.c = n_ctl,
               studlab = label, data = d, sm = opt$measure, method = "MH",
               method.tau = "REML", common = TRUE, random = TRUE,
               subgroup = if (!is.null(opt$subgroup)) subgroup else NULL)
}
sink(file.path(opt$out, "summary.txt"), append = TRUE); print(summary(m)); sink()

# ---------- 4. 森林圖與漏斗圖 ----------
png(file.path(opt$out, "forest.png"), width = 2400, height = 300 + 120 * nrow(d), res = 200)
forest(m, sortvar = TE, prediction = TRUE, print.tau2 = TRUE, print.I2 = TRUE)
dev.off()

png(file.path(opt$out, "funnel.png"), width = 1600, height = 1400, res = 200)
funnel(m, studlab = TRUE, contour = c(0.9, 0.95, 0.99))
dev.off()

# ---------- 5. 發表偏倚：Egger（k ≥ 10 才做） ----------
if (nrow(d) >= 10) {
  eg <- metabias(m, method.bias = "linreg")
  capture.output(eg, file = file.path(opt$out, "egger.txt"))
} else {
  writeLines("k < 10，Egger 檢定檢力不足，未執行（Cochrane Handbook 13.3.5.4）。", file.path(opt$out, "egger.txt"))
}

# ---------- 6. 敏感度：leave-one-out；排除高偏倚 ----------
loo <- metainf(m, pooled = "random")
write.csv(data.frame(excluded = loo$studlab, TE = loo$TE, lower = loo$lower, upper = loo$upper, I2 = loo$I2),
          file.path(opt$out, "leave_one_out.csv"), row.names = FALSE)
if (!is.null(opt$rob)) {
  keep <- !(d$rob %in% c("High", "Serious", "Critical"))
  if (sum(keep) >= 2 && sum(keep) < nrow(d)) {
    m_low <- update(m, subset = keep)
    log_line("\n排除高偏倚後 (k=%d)：隨機效應 %s = %.3f [%.3f, %.3f]", sum(keep), opt$measure,
             m_low$TE.random, m_low$lower.random, m_low$upper.random)
  }
}

# ---------- 7. 亞組表 ----------
if (!is.null(opt$subgroup)) {
  sg <- data.frame(subgroup = m$subgroup.levels, k = m$k.w, TE = m$TE.random.w,
                   lower = m$lower.random.w, upper = m$upper.random.w, I2 = m$I2.w)
  write.csv(sg, file.path(opt$out, "subgroup.csv"), row.names = FALSE)
  log_line("亞組差異檢定 p = %.3f", m$pval.Q.b.random)
}

# ---------- 8. 留痕：呼叫 gate.py 記錄這次分析 ----------
if (in_project) {
  note <- sprintf("meta_analysis.R %s@%s %s k=%d RE=%.3f I2=%.0f%% out=%s", opt$outcome, opt$timepoint %||% "all",
                  opt$measure, nrow(d), m$TE.random, m$I2 * 100, opt$out)
  system2("python3", c(file.path(root, "gate.py"), "log", basename(proj_dir), "07", "--by", "meta_analysis.R", "--note", shQuote(note)))
}
cat("完成。請閱讀", file.path(opt$out, "summary.txt"), "並撰寫 interpretation.md。\n")
