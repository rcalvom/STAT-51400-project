#!/usr/bin/env Rscript

# Generate manuscript-ready tables and figures for the LLM DOE project.

options(stringsAsFactors = FALSE)

dir.create("report", showWarnings = FALSE)
dir.create("report/assets", showWarnings = FALSE, recursive = TRUE)
dir.create("report/tables", showWarnings = FALSE, recursive = TRUE)

results <- read.csv("outputs/results.csv", stringsAsFactors = FALSE)
stim_summary <- read.csv("artifacts/data/summary_by_stim_paradigm.csv", stringsAsFactors = FALSE)

results$wall_clock_seconds <- as.numeric(results$wall_clock_seconds)
results$input_token_count <- as.numeric(results$input_token_count)
results$output_token_count <- as.numeric(results$output_token_count)
results$total_token_count <- as.numeric(results$total_token_count)
results$valid_json <- results$response_json_valid == "True"
results$length_capped <- results$done_reason == "length"
results$model_label <- results$factor_model
results$model <- factor(
  results$model,
  levels = c(
    "deepseek-ai/DeepSeek-V3.1",
    "moonshotai/Kimi-K2.5",
    "Qwen/Qwen3.5-9B"
  )
)
results$temperature <- factor(
  as.character(results$factor_temperature),
  levels = c("0", "0.25", "0.5", "0.75", "1")
)
results$prompt <- factor(
  basename(results$prompt_template),
  levels = c(
    "stim_paradigm_basic.md",
    "stim_paradigm_anova.md",
    "stim_paradigm_predictive.md"
  )
)
results$data_view <- factor(
  results$data_view,
  levels = c("summary_only", "stim_summary", "stim_and_mouse_summary")
)

format_num <- function(x, digits = 3) {
  ifelse(is.na(x), "", formatC(x, digits = digits, format = "f", big.mark = ","))
}

write_table <- function(df, path) {
  write.csv(df, path, row.names = FALSE, na = "")
}

design_table <- data.frame(
  factor = c("Model", "Temperature", "Prompt template", "Data view", "Replication"),
  levels = c(
    "3: DeepSeek-V3.1, Kimi-K2.5, Qwen3.5-9B",
    "5: 0.00, 0.25, 0.50, 0.75, 1.00",
    "3: basic, ANOVA, predictive",
    "3: summary_only, stim_summary, stim_and_mouse_summary",
    "3 repeated runs per treatment combination"
  ),
  notes = c(
    "Together AI serverless models with reasoning disabled.",
    "Treated as a categorical factor.",
    "Increasing inferential specificity across the three prompts.",
    "Controls how much dataset context is exposed to the model.",
    "Full factorial CRD: 3 x 5 x 3 x 3 x 3 = 405 runs."
  )
)
write_table(design_table, "report/tables/design_factors.csv")

project_summary <- data.frame(
  metric = c(
    "Completed runs",
    "Treatment combinations",
    "Replications per treatment",
    "Valid JSON responses",
    "JSON validity rate",
    "Length-capped responses",
    "Length-cap rate",
    "Total input tokens",
    "Total output tokens",
    "Total tokens",
    "Mean wall-clock seconds per run",
    "Total wall-clock seconds across runs",
    "Reported Together cost (USD)",
    "Estimated direct token cost for final 405-run sweep (USD)",
    "Average reported cost per run (USD)"
  ),
  value = c(
    nrow(results),
    135,
    3,
    sum(results$valid_json),
    round(mean(results$valid_json), 4),
    sum(results$length_capped),
    round(mean(results$length_capped), 4),
    sum(results$input_token_count),
    sum(results$output_token_count),
    sum(results$total_token_count),
    round(mean(results$wall_clock_seconds), 3),
    round(sum(results$wall_clock_seconds), 3),
    1.11,
    round(
      sum(
        ifelse(results$model == "deepseek-ai/DeepSeek-V3.1",
               results$input_token_count * 0.60 / 1e6 + results$output_token_count * 1.70 / 1e6,
        ifelse(results$model == "moonshotai/Kimi-K2.5",
               results$input_token_count * 0.50 / 1e6 + results$output_token_count * 2.80 / 1e6,
               results$input_token_count * 0.10 / 1e6 + results$output_token_count * 0.15 / 1e6))
      ),
      4
    ),
    round(1.11 / nrow(results), 5)
  )
)
write_table(project_summary, "report/tables/project_summary.csv")

model_summary <- aggregate(
  cbind(
    wall_clock_seconds,
    input_token_count,
    output_token_count,
    total_token_count,
    valid_json = as.numeric(results$valid_json),
    length_capped = as.numeric(results$length_capped)
  ) ~ model,
  data = results,
  FUN = mean
)
names(model_summary) <- c(
  "model",
  "mean_wall_clock_seconds",
  "mean_input_tokens",
  "mean_output_tokens",
  "mean_total_tokens",
  "valid_json_rate",
  "length_cap_rate"
)
write_table(model_summary, "report/tables/model_summary.csv")

token_interaction <- aggregate(
  total_token_count ~ model + data_view,
  data = results,
  FUN = mean
)
write_table(token_interaction, "report/tables/model_by_data_view_tokens.csv")

validity_summary <- aggregate(
  valid_json ~ model + prompt + data_view,
  data = results,
  FUN = mean
)
write_table(validity_summary, "report/tables/validity_rates.csv")

fit_wall <- aov(log(wall_clock_seconds) ~ model * temperature * prompt * data_view, data = results)
fit_tokens <- aov(total_token_count ~ model * temperature * prompt * data_view, data = results)

anova_to_df <- function(fit) {
  tab <- summary(fit)[[1]]
  df <- data.frame(
    term = rownames(tab),
    df = tab[, "Df"],
    sum_sq = tab[, "Sum Sq"],
    mean_sq = tab[, "Mean Sq"],
    f_value = tab[, "F value"],
    p_value = tab[, "Pr(>F)"],
    row.names = NULL
  )
  total_ss <- sum(df$sum_sq, na.rm = TRUE)
  residual_ss <- df$sum_sq[df$term == "Residuals"]
  df$eta_sq <- df$sum_sq / total_ss
  df$partial_eta_sq <- ifelse(
    df$term == "Residuals",
    NA,
    df$sum_sq / (df$sum_sq + residual_ss)
  )
  df
}

anova_wall <- anova_to_df(fit_wall)
anova_tokens <- anova_to_df(fit_tokens)
write_table(anova_wall, "report/tables/anova_log_wall_clock.csv")
write_table(anova_tokens, "report/tables/anova_total_tokens.csv")

paradigm_context <- stim_summary[, c(
  "Stim.Paradigm",
  "n",
  "mean_Success",
  "mean_Time.to.Target",
  "mean_Path.Efficiency",
  "mean_Average.Speed",
  "mean_AD"
)]
write_table(paradigm_context, "report/tables/source_data_summary.csv")

palette_models <- c("#3b82f6", "#f97316", "#10b981")
palette_prompts <- c("#60a5fa", "#34d399", "#f59e0b")

png("report/assets/figure_source_data_context.png", width = 1600, height = 700, res = 150)
par(mfrow = c(1, 2), mar = c(8, 4.5, 3, 1))
barplot(
  stim_summary$mean_Success,
  names.arg = stim_summary$Stim.Paradigm,
  las = 2,
  col = "#3b82f6",
  main = "Mean Success by Stimulation Paradigm",
  ylab = "Mean success"
)
barplot(
  stim_summary$mean_Time.to.Target,
  names.arg = stim_summary$Stim.Paradigm,
  las = 2,
  col = "#f97316",
  main = "Mean Time-to-Target by Stimulation Paradigm",
  ylab = "Mean time-to-target"
)
dev.off()

png("report/assets/figure_model_latency_boxplot.png", width = 1400, height = 800, res = 150)
par(mar = c(8, 5, 3, 1))
boxplot(
  wall_clock_seconds ~ model,
  data = results,
  las = 2,
  col = palette_models,
  main = "Wall-Clock Runtime by Model",
  ylab = "Seconds"
)
dev.off()

png("report/assets/figure_model_data_view_tokens.png", width = 1400, height = 800, res = 150)
par(mar = c(5, 5, 3, 1))
interaction.plot(
  x.factor = results$data_view,
  trace.factor = results$model,
  response = results$total_token_count,
  fun = mean,
  type = "b",
  pch = c(16, 17, 15),
  col = palette_models,
  lwd = 2,
  ylab = "Mean total tokens",
  xlab = "Data view",
  main = "Model x Data View Interaction for Token Usage",
  legend = FALSE
)
legend(
  "topleft",
  legend = levels(results$model),
  col = palette_models,
  lty = 1,
  pch = c(16, 17, 15),
  bty = "n"
)
dev.off()

png("report/assets/figure_validity_by_model_prompt.png", width = 1500, height = 850, res = 150)
valid_matrix <- xtabs(valid_json ~ model + prompt, data = results) / xtabs(~ model + prompt, data = results)
barplot(
  t(valid_matrix),
  beside = TRUE,
  col = palette_models,
  ylim = c(0, 1.05),
  ylab = "Structured-output validity rate",
  main = "Valid JSON Rate by Model and Prompt",
  legend.text = rownames(valid_matrix),
  args.legend = list(x = "topright", bty = "n")
)
abline(h = seq(0, 1, by = 0.1), col = "#e5e7eb", lty = 3)
dev.off()

png("report/assets/figure_prompt_latency_model.png", width = 1400, height = 800, res = 150)
interaction.plot(
  x.factor = results$prompt,
  trace.factor = results$model,
  response = results$wall_clock_seconds,
  fun = mean,
  type = "b",
  pch = c(16, 17, 15),
  col = palette_models,
  lwd = 2,
  ylab = "Mean wall-clock seconds",
  xlab = "Prompt template",
  main = "Model x Prompt Pattern for Runtime",
  legend = FALSE
)
legend(
  "topleft",
  legend = levels(results$model),
  col = palette_models,
  lty = 1,
  pch = c(16, 17, 15),
  bty = "n"
)
dev.off()

png("report/assets/figure_diagnostics.png", width = 1500, height = 1500, res = 150)
par(mfrow = c(2, 2), mar = c(4.5, 4.5, 2.5, 1))
plot(
  fitted(fit_wall),
  resid(fit_wall),
  pch = 16,
  col = "#3b82f688",
  main = "Residuals vs Fitted: log(runtime)",
  xlab = "Fitted values",
  ylab = "Residuals"
)
abline(h = 0, lty = 2, col = "gray40")
qqnorm(resid(fit_wall), pch = 16, col = "#3b82f688", main = "Q-Q Plot: log(runtime)")
qqline(resid(fit_wall), col = "gray40", lwd = 2)
plot(
  fitted(fit_tokens),
  resid(fit_tokens),
  pch = 16,
  col = "#f9731688",
  main = "Residuals vs Fitted: total tokens",
  xlab = "Fitted values",
  ylab = "Residuals"
)
abline(h = 0, lty = 2, col = "gray40")
qqnorm(resid(fit_tokens), pch = 16, col = "#f9731688", main = "Q-Q Plot: total tokens")
qqline(resid(fit_tokens), col = "gray40", lwd = 2)
dev.off()

session_info <- capture.output(sessionInfo())
writeLines(session_info, "report/tables/r_session_info.txt")
