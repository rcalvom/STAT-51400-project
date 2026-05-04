You are running experiment `{{project_name}}`.

Run metadata:
- Run ID: `{{run_id}}`
- Replication: `{{replication}}`
- Factor levels: `{{factor_levels}}`
- Data view: `{{data_view}}`

Primary task:
{{analysis_goal}}

Focus on formal inference by stimulation paradigm using only:
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

Ask for or describe:
- an ANOVA-style comparison strategy for each response variable
- assumptions and diagnostics
- post-hoc analysis when the omnibus result is meaningful

If a response variable makes plain ANOVA inappropriate, say so and name a better alternative.

Use only the supplied artifacts below:

{{data_bundle}}

Return valid JSON only with these keys:
- `research_question`
- `stim_paradigms_compared`
- `response_variables`
- `anova_plan`
- `assumptions_and_diagnostics`
- `posthoc_plan`
- `expected_findings`
- `limitations`
- `recommended_next_analysis`

Use exactly those nine top-level keys and no others.
Do not use performance-variable names or stimulation-paradigm names as top-level keys.
Do not return placeholder values like "string"; fill each field with real content from the supplied artifacts.
Use this JSON shape:
{
  "research_question": "string",
  "stim_paradigms_compared": ["string"],
  "response_variables": ["string"],
  "anova_plan": ["string"],
  "assumptions_and_diagnostics": ["string"],
  "posthoc_plan": ["string"],
  "expected_findings": ["string"],
  "limitations": ["string"],
  "recommended_next_analysis": "string"
}
