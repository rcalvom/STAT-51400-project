"""Execution and result-logging utilities for DOE runs against live or mock backends."""

from __future__ import annotations

import json
import random
import re
import time
from pathlib import Path
from typing import Any

from .config import resolve_project_path
from .data_prep import build_data_artifacts
from .design import build_design
from .ollama_client import OllamaClient
from .prompting import build_system_prompt, render_user_prompt, resolve_reasoning_options
from .together_client import TogetherClient
from .utils import (
    append_jsonl,
    ensure_dir,
    flatten_dict,
    ns_to_seconds,
    read_json,
    read_jsonl,
    utc_timestamp,
    write_csv,
    write_json,
    write_text,
)


def run_experiment(
    config: dict[str, Any],
    *,
    limit: int | None = None,
    rebuild_data: bool = False,
    rebuild_design: bool = False,
    dry_run: bool = False,
    force: bool = False,
    clean: bool = False,
) -> dict[str, Any]:
    """Execute the configured runs, persist artifacts, and log per-run metrics."""
    output_dir = ensure_dir(resolve_project_path(config, config.get("outputs", {}).get("dir", "outputs")))
    artifact_dir = resolve_project_path(config, config.get("artifacts", {}).get("dir", "artifacts/data"))
    manifest_path = artifact_dir / "artifact_manifest.json"
    design_path = output_dir / "design_matrix.json"

    if rebuild_data or not manifest_path.exists():
        build_data_artifacts(config)
    if rebuild_design or not design_path.exists():
        build_design(config)

    design = read_json(design_path)
    runs = design["runs"]
    if limit is not None:
        runs = runs[:limit]

    results_jsonl = output_dir / "results.jsonl"
    results_csv = output_dir / "results.csv"
    prompts_dir = ensure_dir(output_dir / "prompts")
    responses_dir = ensure_dir(output_dir / "responses")
    if clean:
        clean_run_outputs(output_dir, prompts_dir, responses_dir)

    completed_run_ids = set()
    if not force:
        completed_run_ids = {record["run_id"] for record in read_jsonl(results_jsonl)}

    backend_config = config.get("backend", {})
    provider = "mock" if dry_run else backend_config.get("provider", "ollama")
    response_format = backend_config.get("response_format")
    client = None

    if provider == "ollama":
        client = OllamaClient(
            base_url=backend_config.get("base_url", "http://127.0.0.1:11434"),
            timeout_seconds=int(backend_config.get("timeout_seconds", 600)),
        )
        client.healthcheck()
    elif provider == "together":
        client = TogetherClient(
            base_url=backend_config.get("base_url", "https://api.together.ai/v1"),
            api_key=backend_config.get("api_key"),
            api_key_env=backend_config.get("api_key_env", "TOGETHER_API_KEY"),
            timeout_seconds=int(backend_config.get("timeout_seconds", 600)),
        )
        client.healthcheck()
    elif provider != "mock":
        raise ValueError(f"Unsupported backend provider: {provider}")

    fieldnames = build_results_fieldnames(runs)
    executed = 0
    skipped = 0

    for run in runs:
        if run["run_id"] in completed_run_ids:
            skipped += 1
            continue

        prompt_text = render_user_prompt(config, run)
        system_prompt = build_system_prompt(config, run["settings"].get("reasoning_profile"))
        expected_json_keys = extract_expected_json_keys(prompt_text)
        prompt_path = prompts_dir / f"run_{run['run_id']:04d}.md"
        write_text(prompt_path, prompt_text)

        record = build_base_record(run, prompt_path)
        record["backend_provider"] = provider
        record["expected_json_key_count"] = len(expected_json_keys)
        record["started_at_utc"] = utc_timestamp()

        start = time.perf_counter()
        try:
            if provider == "mock":
                response = mock_response(run, prompt_text)
            else:
                settings = run["settings"]
                options = resolve_inference_options(config, settings, provider)
                response = client.generate(
                    model=settings["model"],
                    prompt=prompt_text,
                    system=system_prompt,
                    options=options,
                    response_format=resolve_response_format(provider, response_format, expected_json_keys),
                )

            wall_clock = time.perf_counter() - start
            response_path = responses_dir / f"run_{run['run_id']:04d}.json"
            write_json(
                response_path,
                {
                    "run_id": run["run_id"],
                    "system_prompt": system_prompt,
                    "user_prompt": prompt_text,
                    "response": response,
                },
            )

            record.update(extract_response_metrics(response))
            record.update(score_response_schema(response.get("response", ""), expected_json_keys))
            record["status"] = "success"
            record["wall_clock_seconds"] = round(wall_clock, 6)
            record["response_path"] = str(response_path)
            record["ended_at_utc"] = utc_timestamp()
        except Exception as exc:  # noqa: BLE001
            wall_clock = time.perf_counter() - start
            record["status"] = "error"
            record["error"] = str(exc)
            record["wall_clock_seconds"] = round(wall_clock, 6)
            record["ended_at_utc"] = utc_timestamp()

        append_jsonl(results_jsonl, record)
        executed += 1

    rewrite_results_csv(results_jsonl, results_csv, fieldnames)

    summary = {
        "executed_runs": executed,
        "skipped_runs": skipped,
        "results_jsonl": str(results_jsonl),
        "results_csv": str(results_csv),
    }
    write_json(output_dir / "latest_run_summary.json", summary)
    return summary


def summarize_results(config: dict[str, Any]) -> dict[str, Any]:
    """Aggregate successful run metrics by treatment combination for downstream analysis."""
    output_dir = resolve_project_path(config, config.get("outputs", {}).get("dir", "outputs"))
    results_path = output_dir / "results.jsonl"
    records = [normalize_result_record(record) for record in read_jsonl(results_path) if record.get("status") == "success"]

    grouped: dict[tuple[tuple[str, str], ...], list[dict[str, Any]]] = {}
    for record in records:
        key = tuple(sorted(record["factor_levels"].items()))
        grouped.setdefault(key, []).append(record)

    rows: list[dict[str, Any]] = []
    for key, members in grouped.items():
        row = {f"factor_{name}": value for name, value in key}
        row["n_runs"] = len(members)
        row["mean_wall_clock_seconds"] = mean_numeric(members, "wall_clock_seconds")
        row["mean_input_token_count"] = mean_numeric(members, "input_token_count")
        row["mean_output_token_count"] = mean_numeric(members, "output_token_count")
        row["mean_total_token_count"] = mean_numeric(members, "total_token_count")
        row["mean_total_duration_seconds"] = mean_numeric(members, "total_duration_seconds")
        row["mean_schema_completeness"] = mean_numeric(members, "response_schema_completeness")
        rows.append(row)

    fieldnames = sorted({key for row in rows for key in row.keys()})
    summary_path = output_dir / "results_summary.csv"
    write_csv(summary_path, rows, fieldnames)
    return {"summary_csv": str(summary_path), "groups": len(rows)}


def clean_run_outputs(output_dir: Path, prompts_dir: Path, responses_dir: Path) -> None:
    """Remove prior run logs and generated prompt/response files while keeping the design matrix."""
    for path in [
        output_dir / "results.jsonl",
        output_dir / "results.csv",
        output_dir / "results_summary.csv",
        output_dir / "latest_run_summary.json",
    ]:
        if path.exists():
            path.unlink()

    clear_directory_files(prompts_dir)
    clear_directory_files(responses_dir)


def clear_directory_files(directory: Path) -> None:
    """Delete all regular files in a directory without removing the directory itself."""
    if not directory.exists():
        return
    for path in directory.iterdir():
        if path.is_file():
            path.unlink()


def build_base_record(run: dict[str, Any], prompt_path: Path) -> dict[str, Any]:
    """Build the initial result record before execution-specific metrics are added."""
    record = {
        "run_id": run["run_id"],
        "replication": run["replication"],
        "randomized_position": run["randomized_position"],
        "prompt_path": str(prompt_path),
        "status": "pending",
        "error": "",
        "response_path": "",
        "factor_levels": run["factor_levels"],
    }
    for name, label in run["factor_levels"].items():
        record[f"factor_{name}"] = label

    flat_settings = flatten_dict(run["settings"])
    for key, value in flat_settings.items():
        record[f"setting_{key}"] = value

    if "model" in run["settings"]:
        record["model"] = run["settings"]["model"]
    if "data_view" in run["settings"]:
        record["data_view"] = run["settings"]["data_view"]
    if "prompt_template" in run["settings"]:
        record["prompt_template"] = run["settings"]["prompt_template"]
    if "reasoning_profile" in run["settings"]:
        record["reasoning_profile"] = run["settings"]["reasoning_profile"]

    return record


def build_results_fieldnames(runs: list[dict[str, Any]]) -> list[str]:
    """Compute the CSV schema for result exports based on factors and run settings."""
    factor_columns = sorted({f"factor_{name}" for run in runs for name in run["factor_levels"]})
    setting_columns = sorted({f"setting_{key}" for run in runs for key in flatten_dict(run["settings"]).keys()})
    metric_columns = [
        "run_id",
        "replication",
        "randomized_position",
        "status",
        "backend_provider",
        "model",
        "data_view",
        "prompt_template",
        "reasoning_profile",
        "started_at_utc",
        "ended_at_utc",
        "wall_clock_seconds",
        "input_token_count",
        "output_token_count",
        "total_token_count",
        "total_duration_seconds",
        "load_duration_seconds",
        "prompt_eval_duration_seconds",
        "eval_duration_seconds",
        "response_json_valid",
        "expected_json_key_count",
        "response_filled_key_count",
        "response_schema_completeness",
        "done_reason",
        "error",
        "prompt_path",
        "response_path",
    ]
    return metric_columns[:9] + factor_columns + setting_columns + metric_columns[9:]


def extract_response_metrics(response: dict[str, Any]) -> dict[str, Any]:
    """Extract token counts, durations, and basic validity flags from a normalized response."""
    text = response.get("response", "")
    input_token_count = response.get("prompt_eval_count")
    output_token_count = response.get("eval_count")
    total_token_count = response.get("total_token_count")
    metrics = {
        "input_token_count": input_token_count,
        "output_token_count": output_token_count,
        "total_token_count": total_token_count,
        "total_duration_seconds": ns_to_seconds(response.get("total_duration")),
        "load_duration_seconds": ns_to_seconds(response.get("load_duration")),
        "prompt_eval_duration_seconds": ns_to_seconds(response.get("prompt_eval_duration")),
        "eval_duration_seconds": ns_to_seconds(response.get("eval_duration")),
        "done_reason": response.get("done_reason", ""),
        "response_json_valid": False,
    }

    try:
        json.loads(text)
        metrics["response_json_valid"] = True
    except json.JSONDecodeError:
        pass

    if metrics["total_token_count"] is None and isinstance(input_token_count, int) and isinstance(output_token_count, int):
        metrics["total_token_count"] = input_token_count + output_token_count

    return metrics


def resolve_inference_options(
    config: dict[str, Any],
    settings: dict[str, Any],
    provider: str,
) -> dict[str, Any]:
    """Merge generic and legacy runtime options for the selected inference backend."""
    options = dict(settings.get("ollama_options", {}))
    options.update(settings.get("inference_options", {}))
    if provider == "ollama":
        options.update(resolve_reasoning_options(config, settings.get("reasoning_profile")))
    return options


def resolve_response_format(
    provider: str,
    backend_response_format: Any,
    expected_json_keys: list[str],
) -> Any:
    """Translate backend response-format settings into the provider-specific API payload."""
    if provider == "together":
        if isinstance(backend_response_format, dict):
            return backend_response_format
        if backend_response_format == "json" and expected_json_keys:
            return {
                "type": "json_schema",
                "json_schema": {
                    "name": "llm_doe_response",
                    "schema": build_json_schema(expected_json_keys),
                },
            }
        return None
    return backend_response_format


def build_json_schema(expected_json_keys: list[str]) -> dict[str, Any]:
    """Build a permissive JSON schema from the prompt's expected top-level keys."""
    return {
        "type": "object",
        "properties": {key: {} for key in expected_json_keys},
        "required": expected_json_keys,
        "additionalProperties": True,
    }


def normalize_result_record(record: dict[str, Any]) -> dict[str, Any]:
    """Backfill legacy result rows so older logs can be summarized with the current schema."""
    normalized = dict(record)
    if "input_token_count" not in normalized and "prompt_eval_count" in normalized:
        normalized["input_token_count"] = normalized.get("prompt_eval_count")
    if "output_token_count" not in normalized and "eval_count" in normalized:
        normalized["output_token_count"] = normalized.get("eval_count")
    if "total_token_count" not in normalized:
        input_token_count = normalized.get("input_token_count")
        output_token_count = normalized.get("output_token_count")
        if isinstance(input_token_count, int) and isinstance(output_token_count, int):
            normalized["total_token_count"] = input_token_count + output_token_count
    return normalized


def rewrite_results_csv(results_jsonl: Path, results_csv: Path, fieldnames: list[str]) -> None:
    """Rebuild the tabular CSV export from the canonical JSONL log."""
    rows = [normalize_result_record(record) for record in read_jsonl(results_jsonl)]
    write_csv(results_csv, rows, fieldnames)


def extract_expected_json_keys(prompt_text: str) -> list[str]:
    """Parse the explicit JSON-key section from a prompt for schema scoring."""
    marker = "Return valid JSON only with these keys:"
    start = prompt_text.find(marker)
    if start == -1:
        return []

    keys: list[str] = []
    trailing = prompt_text[start + len(marker) :].splitlines()
    for line in trailing:
        stripped = line.strip()
        if not stripped:
            if keys:
                break
            continue

        match = re.fullmatch(r"- `([^`]+)`", stripped)
        if match:
            keys.append(match.group(1))
            continue

        if keys:
            break

    return keys


def score_response_schema(response_text: str, expected_keys: list[str]) -> dict[str, Any]:
    """Score how completely a model response filled the expected JSON schema."""
    metrics = {
        "response_filled_key_count": None,
        "response_schema_completeness": None,
    }
    if not expected_keys:
        return metrics

    try:
        payload = json.loads(response_text)
    except json.JSONDecodeError:
        return metrics

    if not isinstance(payload, dict):
        return metrics

    filled = 0
    for key in expected_keys:
        value = payload.get(key)
        if value not in (None, "", [], {}):
            filled += 1

    metrics["response_filled_key_count"] = filled
    metrics["response_schema_completeness"] = round(filled / len(expected_keys), 6)
    return metrics


def mock_response(run: dict[str, Any], prompt_text: str) -> dict[str, Any]:
    """Generate deterministic synthetic responses for offline testing and smoke runs."""
    seed = 1000 + int(run["run_id"])
    rng = random.Random(seed)
    response_payload = build_mock_payload(prompt_text)
    response_text = json.dumps(response_payload, ensure_ascii=False)

    prompt_tokens = max(50, len(prompt_text) // 4)
    eval_tokens = rng.randint(180, 340)
    total_duration = rng.randint(2_000_000_000, 5_500_000_000)
    return {
        "model": run["settings"].get("model", "mock-model"),
        "response": response_text,
        "done": True,
        "done_reason": "stop",
        "prompt_eval_count": prompt_tokens,
        "eval_count": eval_tokens,
        "total_duration": total_duration,
        "load_duration": rng.randint(50_000_000, 150_000_000),
        "prompt_eval_duration": rng.randint(200_000_000, 600_000_000),
        "eval_duration": rng.randint(1_000_000_000, 4_000_000_000),
    }


def build_mock_payload(prompt_text: str) -> dict[str, Any]:
    """Create a schema-aligned mock response body from the keys requested in a prompt."""
    expected_keys = extract_expected_json_keys(prompt_text)
    shared_values: dict[str, Any] = {
        "research_question": "How does navigation performance differ across the five selected stimulation paradigms?",
        "stim_paradigms_compared": [
            "Combined",
            "ICMS Only",
            "Dim Visual Only",
            "Bright Visual Only",
            "Sham",
        ],
        "response_variables": [
            "Time-to-Target",
            "Success",
            "Path Efficiency",
            "Average Speed",
            "AD",
        ],
        "descriptive_findings": [
            "Sham appears to have the lowest mean success and the highest mean time-to-target.",
            "Combined and Bright Visual Only appear stronger than ICMS Only and Dim Visual Only on several summary metrics.",
        ],
        "strongest_group_differences": [
            "Sham differs substantially from Combined on success and time-to-target.",
            "Combined and Bright Visual Only appear relatively similar on path efficiency and average speed.",
        ],
        "practical_interpretation": "The grouped summaries suggest that stimulation paradigm is associated with meaningful differences in navigation performance.",
        "limitations": [
            "These conclusions come from summary artifacts rather than raw-trial modeling in the mock backend.",
            "Formal inference still depends on model assumptions and appropriate treatment of each response variable.",
        ],
        "recommended_next_analysis": "Fit per-response stimulation-paradigm comparisons and inspect diagnostics before final interpretation.",
        "anova_plan": [
            "Use stimulation paradigm as the primary grouping factor for each response variable.",
            "Check whether each response is suitable for classical ANOVA before relying on omnibus tests.",
        ],
        "assumptions_and_diagnostics": [
            "Inspect residual normality and variance homogeneity for continuous outcomes.",
            "Treat Success as a binary response that may need a generalized model rather than plain ANOVA.",
        ],
        "posthoc_plan": [
            "Use pairwise post-hoc comparisons only when the omnibus comparison is informative.",
            "Prioritize contrasts involving Sham versus the active stimulation paradigms.",
        ],
        "expected_findings": [
            "Sham is likely to perform worse than the active stimulation paradigms.",
            "Combined may rank among the strongest paradigms on success and navigation efficiency.",
        ],
        "multiple_comparison_strategy": "Use a multiple-comparison correction such as Tukey-style familywise control or a false-discovery-rate approach when many pairwise contrasts are reported.",
        "predictive_model_recommendation": "Because stimulation paradigm is categorical, prefer a multiclass classification model rather than ordinary linear regression if raw-trial prediction is attempted.",
        "recommended_design": "Treat each LLM run as an experimental unit while comparing how prompts and runtime settings affect the analysis of stimulation paradigm.",
        "experimental_units": "One LLM analysis run over the filtered stimulation-paradigm data view.",
        "main_patterns": [
            "Sham looks substantially weaker than the active stimulation paradigms.",
            "Combined and Bright Visual Only appear comparatively strong on several performance summaries.",
        ],
    }

    payload: dict[str, Any] = {}
    for key in expected_keys:
        payload[key] = shared_values.get(key, f"Mock value for {key}.")

    return payload


def mean_numeric(records: list[dict[str, Any]], field: str) -> float | None:
    """Compute the arithmetic mean of one numeric field across a list of result records."""
    values = [record[field] for record in records if isinstance(record.get(field), (int, float))]
    if not values:
        return None
    return round(sum(values) / len(values), 6)
