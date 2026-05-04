"""Build factorial treatment combinations and export them as reusable design matrices."""

from __future__ import annotations

import itertools
import json
import random
from copy import deepcopy
from typing import Any

from .config import resolve_project_path
from .utils import ensure_dir, flatten_dict, write_csv, write_json


INFERENCE_OPTION_NAMES = {
    "temperature",
    "top_p",
    "top_k",
    "seed",
    "min_p",
    "stop",
    "max_tokens",
    "repeat_penalty",
    "repetition_penalty",
    "presence_penalty",
    "frequency_penalty",
    "num_predict",
    "num_ctx",
}


def build_design(config: dict[str, Any]) -> dict[str, Any]:
    """Generate the full factorial design, apply randomization, and persist the result."""
    design_config = config["design"]
    factors = design_config["factors"]
    replications = int(design_config.get("replications", 1))
    random_seed = int(design_config.get("random_seed", 51400))
    randomize = bool(design_config.get("randomize", True))
    base_settings = deepcopy(config.get("run_defaults", {}))

    normalized_factors = []
    for factor in factors:
        levels = [normalize_level(factor["name"], raw_level) for raw_level in factor["levels"]]
        normalized_factors.append({"name": factor["name"], "levels": levels})

    runs: list[dict[str, Any]] = []
    run_id = 1
    for replication in range(1, replications + 1):
        for combination in itertools.product(*[factor["levels"] for factor in normalized_factors]):
            settings = deepcopy(base_settings)
            factor_levels: dict[str, str] = {}
            for factor, level in zip(normalized_factors, combination, strict=True):
                factor_levels[factor["name"]] = level["label"]
                settings = merge_dicts(settings, level["payload"])

            runs.append(
                {
                    "run_id": run_id,
                    "replication": replication,
                    "factor_levels": factor_levels,
                    "settings": settings,
                }
            )
            run_id += 1

    if randomize:
        rng = random.Random(random_seed)
        rng.shuffle(runs)

    for position, run in enumerate(runs, start=1):
        run["randomized_position"] = position

    output_dir = ensure_dir(resolve_project_path(config, config.get("outputs", {}).get("dir", "outputs")))
    json_path = output_dir / "design_matrix.json"
    csv_path = output_dir / "design_matrix.csv"

    write_json(
        json_path,
        {
            "random_seed": random_seed,
            "replications": replications,
            "randomized": randomize,
            "factors": [factor["name"] for factor in normalized_factors],
            "runs": runs,
        },
    )
    write_design_csv(csv_path, runs)

    return {
        "json_path": str(json_path),
        "csv_path": str(csv_path),
        "runs": runs,
    }


def normalize_level(factor_name: str, raw_level: Any) -> dict[str, Any]:
    """Normalize a factor level into a standard label-plus-payload representation."""
    if isinstance(raw_level, dict):
        if "label" not in raw_level:
            raise ValueError(f"Factor '{factor_name}' has a level without a 'label'.")
        payload = {key: value for key, value in raw_level.items() if key != "label"}
        return {"label": str(raw_level["label"]), "payload": payload}

    return {"label": str(raw_level), "payload": implicit_payload(factor_name, raw_level)}


def implicit_payload(factor_name: str, value: Any) -> dict[str, Any]:
    """Map shorthand factor values into the settings payload used by the runner."""
    if factor_name in INFERENCE_OPTION_NAMES:
        return {"inference_options": {factor_name: value}}
    return {factor_name: value}


def merge_dicts(left: dict[str, Any], right: dict[str, Any], path: str = "") -> dict[str, Any]:
    """Recursively merge two settings dictionaries and reject conflicting leaf values."""
    merged = deepcopy(left)
    for key, value in right.items():
        joined = f"{path}.{key}" if path else key
        if key not in merged:
            merged[key] = deepcopy(value)
            continue

        existing = merged[key]
        if isinstance(existing, dict) and isinstance(value, dict):
            merged[key] = merge_dicts(existing, value, joined)
            continue

        if existing != value:
            raise ValueError(f"Conflicting factor payloads for '{joined}': {existing!r} vs {value!r}")

    return merged


def write_design_csv(path, runs: list[dict[str, Any]]) -> None:
    """Write a flat CSV representation of the design matrix for inspection and analysis."""
    if not runs:
        write_csv(path, [], ["run_id", "replication", "randomized_position"])
        return

    factor_columns = sorted({f"factor_{name}" for run in runs for name in run["factor_levels"]})
    setting_columns = sorted({key for run in runs for key in flatten_dict(run["settings"]).keys()})
    fieldnames = ["run_id", "replication", "randomized_position"] + factor_columns + setting_columns + ["settings_json"]

    rows: list[dict[str, Any]] = []
    for run in runs:
        row = {
            "run_id": run["run_id"],
            "replication": run["replication"],
            "randomized_position": run["randomized_position"],
            "settings_json": json.dumps(run["settings"], ensure_ascii=False, sort_keys=True),
        }
        for name, label in run["factor_levels"].items():
            row[f"factor_{name}"] = label
        for key, value in flatten_dict(run["settings"]).items():
            row[key] = value
        rows.append(row)

    write_csv(path, rows, fieldnames)
