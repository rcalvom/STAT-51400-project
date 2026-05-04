"""Dataset summarization utilities used to create compact artifacts for prompt injection."""

from __future__ import annotations

import csv
import math
import random
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import resolve_project_path
from .utils import ensure_dir, write_csv, write_json, write_text


@dataclass
class RunningStats:
    """Online summary statistics for one numeric column."""

    count: int = 0
    mean: float = 0.0
    m2: float = 0.0
    minimum: float | None = None
    maximum: float | None = None
    missing: int = 0

    def add(self, value: str) -> None:
        """Incorporate one CSV cell value into the running summary."""
        if value == "":
            self.missing += 1
            return
        numeric = float(value)
        self.count += 1
        delta = numeric - self.mean
        self.mean += delta / self.count
        delta2 = numeric - self.mean
        self.m2 += delta * delta2
        self.minimum = numeric if self.minimum is None else min(self.minimum, numeric)
        self.maximum = numeric if self.maximum is None else max(self.maximum, numeric)

    def summary(self) -> dict[str, Any]:
        """Return a serializable summary of the accumulated numeric statistics."""
        variance = self.m2 / (self.count - 1) if self.count > 1 else 0.0
        return {
            "count": self.count,
            "missing": self.missing,
            "mean": round(self.mean, 6) if self.count else None,
            "sd": round(math.sqrt(variance), 6) if self.count > 1 else 0.0,
            "min": round(self.minimum, 6) if self.minimum is not None else None,
            "max": round(self.maximum, 6) if self.maximum is not None else None,
        }


@dataclass
class GroupAccumulator:
    """Accumulate grouped means for a fixed set of response metrics."""

    metrics: list[str]
    count: int = 0
    sums: dict[str, float] = field(default_factory=dict)
    non_missing: dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Initialize per-metric totals after dataclass construction."""
        self.sums = {metric: 0.0 for metric in self.metrics}
        self.non_missing = {metric: 0 for metric in self.metrics}

    def add(self, row: dict[str, str]) -> None:
        """Update grouped totals from one CSV row."""
        self.count += 1
        for metric in self.metrics:
            raw = row.get(metric, "")
            if raw == "":
                continue
            self.sums[metric] += float(raw)
            self.non_missing[metric] += 1

    def to_row(self, key_names: list[str], key_values: tuple[str, ...]) -> dict[str, Any]:
        """Convert the accumulator into one flat CSV-ready output row."""
        row: dict[str, Any] = {name: value for name, value in zip(key_names, key_values, strict=True)}
        row["n"] = self.count
        for metric in self.metrics:
            denominator = self.non_missing[metric]
            row[f"mean_{metric}"] = round(self.sums[metric] / denominator, 6) if denominator else ""
        return row


def infer_numeric_columns(csv_path: Path, sample_limit: int = 250) -> list[str]:
    """Infer numeric columns by sampling early rows and testing float conversion."""
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            return []

        candidates = {field: True for field in reader.fieldnames}
        seen = {field: 0 for field in reader.fieldnames}
        for row in reader:
            for field in reader.fieldnames:
                value = row.get(field, "")
                if value == "" or seen[field] >= sample_limit or not candidates[field]:
                    continue
                seen[field] += 1
                try:
                    float(value)
                except ValueError:
                    candidates[field] = False
            if all(count >= sample_limit or not candidates[field] for field, count in seen.items()):
                break

    return [field for field, is_numeric in candidates.items() if is_numeric]


def row_matches_filters(row: dict[str, str], row_filters: list[dict[str, Any]]) -> bool:
    """Return whether a CSV row satisfies all configured include/exclude filter rules."""
    for row_filter in row_filters:
        value = row.get(row_filter["column"], "")
        include = row_filter.get("include")
        exclude = row_filter.get("exclude")

        if include is not None and value not in include:
            return False
        if exclude is not None and value in exclude:
            return False

    return True


def build_data_artifacts(config: dict[str, Any]) -> dict[str, str]:
    """Create dataset profile, overview, samples, and grouped summary artifacts from the source CSV."""
    data_config = config["data"]
    csv_path = resolve_project_path(config, data_config["csv_path"])
    artifact_dir = ensure_dir(resolve_project_path(config, config.get("artifacts", {}).get("dir", "artifacts/data")))

    numeric_columns = data_config.get("numeric_columns")
    if not numeric_columns:
        numeric_columns = infer_numeric_columns(csv_path)

    columns_to_keep = data_config.get("columns_to_keep")
    row_filters = data_config.get("row_filters", [])
    sample_rows = int(data_config.get("sample_rows", 25))
    sample_seed = int(data_config.get("sample_seed", 51400))
    group_summaries = data_config.get("group_summaries", [])

    numeric_stats = {column: RunningStats() for column in numeric_columns}
    categorical_counts: dict[str, Counter[str]] = defaultdict(Counter)
    missing_counts: Counter[str] = Counter()
    groups: dict[str, dict[tuple[str, ...], GroupAccumulator]] = {}
    sample: list[dict[str, str]] = []
    sample_rng = random.Random(sample_seed)
    source_row_count = 0
    row_count = 0
    fieldnames: list[str] = []

    for group_spec in group_summaries:
        groups[group_spec["name"]] = {}

    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        source_fieldnames = reader.fieldnames or []
        if columns_to_keep:
            missing_columns = [column for column in columns_to_keep if column not in source_fieldnames]
            if missing_columns:
                raise KeyError(f"Configured columns_to_keep are missing from the CSV: {missing_columns}")
            fieldnames = columns_to_keep
        else:
            fieldnames = source_fieldnames
        categorical_columns = [column for column in fieldnames if column not in numeric_columns]

        for raw_row in reader:
            source_row_count += 1
            if not row_matches_filters(raw_row, row_filters):
                continue

            row = {column: raw_row.get(column, "") for column in fieldnames}
            row_count += 1

            if len(sample) < sample_rows:
                sample.append(row)
            else:
                pick = sample_rng.randint(1, row_count)
                if pick <= sample_rows:
                    sample[pick - 1] = row

            for column in fieldnames:
                value = row.get(column, "")
                if value == "":
                    missing_counts[column] += 1

            for column in numeric_columns:
                numeric_stats[column].add(row.get(column, ""))

            for column in categorical_columns:
                value = row.get(column, "")
                if value != "":
                    categorical_counts[column][value] += 1

            for group_spec in group_summaries:
                group_name = group_spec["name"]
                keys = tuple(row[key] for key in group_spec["keys"])
                accumulator = groups[group_name].get(keys)
                if accumulator is None:
                    accumulator = GroupAccumulator(metrics=group_spec["metrics"])
                    groups[group_name][keys] = accumulator
                accumulator.add(row)

    profile = {
        "dataset_path": str(csv_path),
        "source_row_count": source_row_count,
        "row_count": row_count,
        "column_count": len(fieldnames),
        "columns": fieldnames,
        "row_filters": row_filters,
        "missing_counts": dict(sorted(missing_counts.items())),
        "numeric_summary": {column: stats.summary() for column, stats in numeric_stats.items()},
        "categorical_summary": {
            column: {
                "levels": len(counter),
                "top_levels": counter.most_common(10),
            }
            for column, counter in sorted(categorical_counts.items())
        },
    }

    overview = build_markdown_overview(profile)

    manifest: dict[str, str] = {}

    dataset_profile_path = artifact_dir / "dataset_profile.json"
    write_json(dataset_profile_path, profile)
    manifest["dataset_profile"] = str(dataset_profile_path)

    overview_path = artifact_dir / "dataset_overview.md"
    write_text(overview_path, overview)
    manifest["overview_markdown"] = str(overview_path)

    sample_path = artifact_dir / "sample_rows.csv"
    write_csv(sample_path, sample, fieldnames)
    manifest["sample_rows"] = str(sample_path)

    for group_spec in group_summaries:
        rows: list[dict[str, Any]] = []
        name = group_spec["name"]
        keys = group_spec["keys"]
        for key_values, accumulator in sorted(groups[name].items()):
            rows.append(accumulator.to_row(keys, key_values))
        fieldnames_for_group = keys + ["n"] + [f"mean_{metric}" for metric in group_spec["metrics"]]
        group_path = artifact_dir / f"{name}.csv"
        write_csv(group_path, rows, fieldnames_for_group)
        manifest[name] = str(group_path)

    manifest_path = artifact_dir / "artifact_manifest.json"
    write_json(manifest_path, manifest)
    return manifest


def build_markdown_overview(profile: dict[str, Any]) -> str:
    """Render a human-readable markdown overview from the computed dataset profile."""
    lines: list[str] = []
    lines.append("# Dataset overview")
    lines.append("")
    if "source_row_count" in profile:
        lines.append(f"- Source rows: {profile['source_row_count']}")
    lines.append(f"- Rows after filters: {profile['row_count']}")
    lines.append(f"- Columns: {profile['column_count']}")
    lines.append(f"- Column names: {', '.join(profile['columns'])}")
    if profile.get("row_filters"):
        lines.append(f"- Row filters: {profile['row_filters']}")
    lines.append("")
    lines.append("## Numeric summary")
    lines.append("")
    for column, summary in profile["numeric_summary"].items():
        lines.append(
            f"- {column}: n={summary['count']}, missing={summary['missing']}, "
            f"mean={summary['mean']}, sd={summary['sd']}, min={summary['min']}, max={summary['max']}"
        )
    lines.append("")
    lines.append("## Categorical summary")
    lines.append("")
    for column, summary in profile["categorical_summary"].items():
        top_levels = ", ".join(f"{label} ({count})" for label, count in summary["top_levels"])
        lines.append(f"- {column}: {summary['levels']} levels. Top values: {top_levels}")
    lines.append("")
    lines.append("## Missingness")
    lines.append("")
    for column, count in profile["missing_counts"].items():
        lines.append(f"- {column}: {count}")
    return "\n".join(lines)
