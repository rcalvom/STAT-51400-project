"""General-purpose filesystem, serialization, and formatting utilities used by the pipeline."""

from __future__ import annotations

import csv
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def ensure_dir(path: str | Path) -> Path:
    """Create a directory and its parents when needed, then return the resulting path."""
    target = Path(path)
    target.mkdir(parents=True, exist_ok=True)
    return target


def write_json(path: str | Path, payload: Any) -> None:
    """Write a Python object to JSON using UTF-8 and stable pretty formatting."""
    target = Path(path)
    ensure_dir(target.parent)
    with target.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)


def read_json(path: str | Path) -> Any:
    """Read a JSON file and return the decoded Python object."""
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def append_jsonl(path: str | Path, payload: dict[str, Any]) -> None:
    """Append one JSON object as a single line in a JSONL file."""
    target = Path(path)
    ensure_dir(target.parent)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    """Read a JSONL file into a list of JSON objects, skipping blank lines."""
    target = Path(path)
    if not target.exists():
        return []
    records: list[dict[str, Any]] = []
    with target.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def append_csv_row(
    path: str | Path,
    row: dict[str, Any],
    fieldnames: list[str],
) -> None:
    """Append one row to a CSV file, creating the header if the file does not yet exist."""
    target = Path(path)
    ensure_dir(target.parent)
    needs_header = not target.exists()
    with target.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        if needs_header:
            writer.writeheader()
        writer.writerow({key: row.get(key, "") for key in fieldnames})


def write_csv(
    path: str | Path,
    rows: list[dict[str, Any]],
    fieldnames: list[str],
) -> None:
    """Write a full CSV file from ordered field names and a list of row dictionaries."""
    target = Path(path)
    ensure_dir(target.parent)
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def read_text(path: str | Path) -> str:
    """Read a UTF-8 text file into a string."""
    return Path(path).read_text(encoding="utf-8")


def write_text(path: str | Path, text: str) -> None:
    """Write a UTF-8 text file, creating parent directories first when needed."""
    target = Path(path)
    ensure_dir(target.parent)
    target.write_text(text, encoding="utf-8")


def flatten_dict(payload: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    """Flatten a nested dictionary using dotted keys for downstream CSV export."""
    flat: dict[str, Any] = {}
    for key, value in payload.items():
        full_key = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            flat.update(flatten_dict(value, full_key))
        else:
            flat[full_key] = value
    return flat


def utc_timestamp() -> str:
    """Return the current UTC timestamp as an ISO 8601 string."""
    return datetime.now(UTC).isoformat()


def ns_to_seconds(value: int | None) -> float | None:
    """Convert a nanosecond duration to rounded seconds, preserving missing values."""
    if value is None:
        return None
    return round(value / 1_000_000_000, 6)
