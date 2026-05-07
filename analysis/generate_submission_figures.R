source_tokens_path <- "report/tables/model_by_data_view_tokens.csv"
validity_path <- "report/tables/validity_rates.csv"
model_summary_path <- "report/tables/model_summary.csv"
anova_runtime_path <- "report/tables/anova_log_wall_clock.csv"
anova_tokens_path <- "report/tables/anova_total_tokens.csv"

token_plot_path <- "report/assets/figure_model_data_view_tokens_clean.png"
validity_plot_path <- "report/assets/figure_validity_by_model_prompt_clean.png"
runtime_plot_path <- "report/assets/figure_model_runtime_mean_clean.png"

tokens <- read.csv(source_tokens_path, check.names = FALSE)
validity <- read.csv(validity_path, check.names = FALSE)
model_summary <- read.csv(model_summary_path, check.names = FALSE)
anova_runtime <- read.csv(anova_runtime_path, check.names = FALSE)
anova_tokens <- read.csv(anova_tokens_path, check.names = FALSE)

model_labels <- c(
  "deepseek-ai/DeepSeek-V3.1" = "DeepSeek-V3.1",
  "moonshotai/Kimi-K2.5" = "Kimi-K2.5",
  "Qwen/Qwen3.5-9B" = "Qwen3.5-9B"
)

data_view_labels <- c(
  "summary_only" = "Summary\nonly",
  "stim_summary" = "Stimulus\nsummary",
  "stim_and_mouse_summary" = "Stim. +\nmouse"
)

prompt_labels <- c(
  "stim_paradigm_basic.md" = "Basic",
  "stim_paradigm_anova.md" = "ANOVA",
  "stim_paradigm_predictive.md" = "Predictive"
)

model_order <- c("deepseek-ai/DeepSeek-V3.1", "moonshotai/Kimi-K2.5", "Qwen/Qwen3.5-9B")
colors <- c("#3b82f6", "#f97316", "#10b981")

resid_runtime <- anova_runtime[trimws(anova_runtime$term) == "Residuals", ]
resid_tokens <- anova_tokens[trimws(anova_tokens$term) == "Residuals", ]

runtime_df <- resid_runtime$df
runtime_mse <- resid_runtime$mean_sq
token_df <- resid_tokens$df
token_mse <- resid_tokens$mean_sq

runtime_n_per_model <- 135
runtime_half_log <- qt(0.975, df = runtime_df) * sqrt(runtime_mse / runtime_n_per_model)
runtime_factor <- exp(runtime_half_log)

token_n_per_cell <- 45
token_half_width <- qt(0.975, df = token_df) * sqrt(token_mse / token_n_per_cell)

wilson_interval <- function(successes, n, conf = 0.95) {
  z <- qnorm(1 - (1 - conf) / 2)
  phat <- successes / n
  denom <- 1 + z^2 / n
  center <- (phat + z^2 / (2 * n)) / denom
  half <- z * sqrt((phat * (1 - phat) + z^2 / (4 * n)) / n) / denom
  c(lower = center - half, upper = center + half)
}

png(token_plot_path, width = 1800, height = 1200, res = 180)
par(mar = c(5.5, 5.2, 3.8, 1.2), cex.axis = 1.15, cex.lab = 1.2, cex.main = 1.35)

y_range <- c(min(tokens$total_token_count - token_half_width) * 0.95,
             max(tokens$total_token_count + token_half_width) * 1.03)
plot(
  x = c(1, 3), y = y_range,
  type = "n",
  xaxt = "n",
  xlab = "Data view",
  ylab = "Mean total tokens",
  main = "Model by Data View Interaction for Token Usage"
)
axis(1, at = 1:3, labels = unname(data_view_labels[c("summary_only", "stim_summary", "stim_and_mouse_summary")]))
grid(nx = NA, ny = NULL, col = "grey90", lty = "dotted")

for (i in seq_along(model_order)) {
  model_name <- model_order[i]
  subset_tokens <- tokens[tokens$model == model_name, ]
  subset_tokens <- subset_tokens[match(names(data_view_labels), subset_tokens$data_view), ]
  lines(1:3, subset_tokens$total_token_count, type = "b", lwd = 2.5, pch = 16 + i, col = colors[i])
  arrows(
    x0 = 1:3,
    y0 = subset_tokens$total_token_count - token_half_width,
    x1 = 1:3,
    y1 = subset_tokens$total_token_count + token_half_width,
    angle = 90,
    code = 3,
    length = 0.05,
    lwd = 1.4,
    col = colors[i]
  )
}

legend(
  "topleft",
  legend = unname(model_labels[model_order]),
  col = colors,
  lty = 1,
  lwd = 2.5,
  pch = 17:19,
  bty = "n",
  pt.cex = 1.1
)
dev.off()

validity_matrix <- matrix(NA_real_, nrow = length(model_order), ncol = length(prompt_labels))
validity_lower <- matrix(NA_real_, nrow = length(model_order), ncol = length(prompt_labels))
validity_upper <- matrix(NA_real_, nrow = length(model_order), ncol = length(prompt_labels))
colnames(validity_matrix) <- unname(prompt_labels)
rownames(validity_matrix) <- unname(model_labels[model_order])

for (i in seq_along(model_order)) {
  model_name <- model_order[i]
  subset_validity <- validity[validity$model == model_name & validity$data_view == "stim_and_mouse_summary", ]
  subset_validity <- subset_validity[match(names(prompt_labels), subset_validity$prompt), ]
  validity_matrix[i, ] <- subset_validity$valid_json
  successes <- round(subset_validity$valid_json * 15)
  for (j in seq_along(successes)) {
    interval <- wilson_interval(successes[j], 15)
    validity_lower[i, j] <- interval["lower"]
    validity_upper[i, j] <- interval["upper"]
  }
}

png(validity_plot_path, width = 1800, height = 1200, res = 180)
par(mar = c(6.0, 5.0, 3.8, 1.5), cex.axis = 1.1, cex.lab = 1.2, cex.main = 1.35)
bar_centers <- barplot(
  t(validity_matrix),
  beside = TRUE,
  ylim = c(0, 1.08),
  col = colors,
  names.arg = rownames(validity_matrix),
  las = 1,
  ylab = "Valid JSON rate",
  main = "Structured-output Validity by Model",
  legend.text = colnames(validity_matrix),
  args.legend = list(x = "topleft", horiz = TRUE, bty = "n", inset = c(0, -0.02))
)
grid(nx = NA, ny = NULL, col = "grey90", lty = "dotted")
arrows(
  x0 = bar_centers,
  y0 = as.vector(t(validity_lower)),
  x1 = bar_centers,
  y1 = as.vector(t(validity_upper)),
  angle = 90,
  code = 3,
  length = 0.04,
  lwd = 1.2
)
dev.off()

model_summary <- model_summary[match(model_order, model_summary$model), ]
runtime_lower <- model_summary$mean_wall_clock_seconds / runtime_factor
runtime_upper <- model_summary$mean_wall_clock_seconds * runtime_factor

png(runtime_plot_path, width = 1800, height = 1200, res = 180)
par(mar = c(6.2, 5.0, 3.8, 1.2), cex.axis = 1.1, cex.lab = 1.2, cex.main = 1.35)
bar_centers <- barplot(
  model_summary$mean_wall_clock_seconds,
  names.arg = unname(model_labels[model_summary$model]),
  col = colors,
  las = 1,
  ylab = "Mean wall-clock seconds",
  main = "Mean Runtime by Model"
)
grid(nx = NA, ny = NULL, col = "grey90", lty = "dotted")
arrows(
  x0 = bar_centers,
  y0 = runtime_lower,
  x1 = bar_centers,
  y1 = runtime_upper,
  angle = 90,
  code = 3,
  length = 0.05,
  lwd = 1.3
)
dev.off()
