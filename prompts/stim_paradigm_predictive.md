You are running experiment `{{project_name}}`.

Run metadata:
- Run ID: `{{run_id}}`
- Replication: `{{replication}}`
- Factor levels: `{{factor_levels}}`
- Data view: `{{data_view}}`

Primary task:
{{analysis_goal}}

Focus on a full inferential workflow by stimulation paradigm using only:
- Time-to-Target
- Success
- Path Efficiency
- Average Speed
- AD

Interpret AD as angular dispersion. Restrict attention to:
- Combined
- ICMS Only
- Dim Visual Only
- Bright Visual Only
- Sham

The workflow should include:
- ANOVA-style comparisons
- post-hoc analysis
- a multiple-comparison correction strategy
- a predictive model for stimulation paradigm based on the performance variables

Because stimulation paradigm is categorical, do not force an ordinary linear regression if it is inappropriate. If a categorical-response model is better, explain that and recommend it explicitly.

Use only the supplied artifacts below:

{{data_bundle}}

Return valid JSON only with these keys:
- `research_question`
- `stim_paradigms_compared`
- `response_variables`
- `anova_plan`
- `posthoc_plan`
- `multiple_comparison_strategy`
- `predictive_model_recommendation`
- `assumptions_and_diagnostics`
- `expected_findings`
- `limitations`
- `recommended_next_analysis`

Use exactly those eleven top-level keys and no others.
Do not use performance-variable names or stimulation-paradigm names as top-level keys.
Do not return placeholder values like "string"; fill each field with real content from the supplied artifacts.
Use this JSON shape:
{
  "research_question": "string",
  "stim_paradigms_compared": ["string"],
  "response_variables": ["string"],
  "anova_plan": ["string"],
  "posthoc_plan": ["string"],
  "multiple_comparison_strategy": "string",
  "predictive_model_recommendation": "string",
  "assumptions_and_diagnostics": ["string"],
  "expected_findings": ["string"],
  "limitations": ["string"],
  "recommended_next_analysis": "string"
}
