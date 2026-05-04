You are running experiment `{{project_name}}`.

Run metadata:
- Run ID: `{{run_id}}`
- Replication: `{{replication}}`
- Factor levels: `{{factor_levels}}`
- Data view: `{{data_view}}`

Primary task:
{{analysis_goal}}

Analyze performance by stimulation paradigm using only these five performance variables:
- Time-to-Target
- Success
- Path Efficiency
- Average Speed
- AD

Interpret AD as angular dispersion. Restrict attention to the five stimulation paradigms in the supplied data artifacts:
- Combined
- ICMS Only
- Dim Visual Only
- Bright Visual Only
- Sham

Use only the supplied artifacts below:

{{data_bundle}}

Return valid JSON only with these keys:
- `research_question`
- `stim_paradigms_compared`
- `response_variables`
- `descriptive_findings`
- `strongest_group_differences`
- `practical_interpretation`
- `limitations`
- `recommended_next_analysis`

Use exactly those eight top-level keys and no others.
Do not use performance-variable names or stimulation-paradigm names as top-level keys.
Do not return placeholder values like "string"; fill each field with real content from the supplied artifacts.
Use this JSON shape:
{
  "research_question": "string",
  "stim_paradigms_compared": ["string"],
  "response_variables": ["string"],
  "descriptive_findings": ["string"],
  "strongest_group_differences": ["string"],
  "practical_interpretation": "string",
  "limitations": ["string"],
  "recommended_next_analysis": "string"
}
