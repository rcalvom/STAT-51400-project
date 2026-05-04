"""Prompt assembly helpers for combining templates, dataset artifacts, and run metadata."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .config import resolve_project_path
from .utils import read_json, read_text


def load_artifact_manifest(config: dict[str, Any]) -> dict[str, str]:
    """Load the artifact manifest created during the data preparation stage."""
    artifact_dir = resolve_project_path(config, config.get("artifacts", {}).get("dir", "artifacts/data"))
    manifest_path = artifact_dir / "artifact_manifest.json"
    return read_json(manifest_path)


def build_system_prompt(config: dict[str, Any], reasoning_profile_name: str | None) -> str:
    """Construct the system prompt, optionally extending it with a reasoning profile suffix."""
    base_prompt = config.get(
        "system_prompt",
        "You are a careful statistician and design-of-experiments consultant. Work only from the supplied data artifacts.",
    )
    if not reasoning_profile_name:
        return base_prompt

    profiles = config.get("reasoning_profiles", {})
    profile = profiles.get(reasoning_profile_name)
    if not profile:
        return base_prompt

    suffix = profile.get("system_suffix", "")
    return base_prompt if not suffix else f"{base_prompt}\n\n{suffix}"


def resolve_reasoning_options(config: dict[str, Any], reasoning_profile_name: str | None) -> dict[str, Any]:
    """Resolve optional Ollama runtime options associated with a named reasoning profile."""
    if not reasoning_profile_name:
        return {}

    profiles = config.get("reasoning_profiles", {})
    profile = profiles.get(reasoning_profile_name, {})
    return profile.get("ollama_options", {})


def render_user_prompt(config: dict[str, Any], run: dict[str, Any]) -> str:
    """Fill a prompt template with run metadata and the selected dataset artifact bundle."""
    settings = run["settings"]
    template_path = resolve_project_path(config, settings["prompt_template"])
    template = read_text(template_path)
    data_view_name = settings["data_view"]
    data_bundle = build_data_bundle(config, data_view_name)

    context = {
        "project_name": config.get("project_name", "llm_doe_project"),
        "analysis_goal": config.get(
            "analysis_goal",
            "Analyze the dataset and propose a defensible design-of-experiments framing plus a statistical analysis plan.",
        ),
        "data_view": data_view_name,
        "run_id": str(run["run_id"]),
        "replication": str(run["replication"]),
        "factor_levels": ", ".join(f"{name}={label}" for name, label in sorted(run["factor_levels"].items())),
        "data_bundle": data_bundle,
    }
    return replace_placeholders(template, context)


def build_data_bundle(config: dict[str, Any], data_view_name: str) -> str:
    """Assemble the text block that embeds the artifacts selected by a data view."""
    manifest = load_artifact_manifest(config)
    data_views = config.get("data_views", {})
    if data_view_name not in data_views:
        raise KeyError(f"Unknown data view: {data_view_name}")

    data_view = data_views[data_view_name]
    max_chars = int(data_view.get("max_chars_per_artifact", 12000))
    blocks: list[str] = []

    for artifact_name in data_view["artifacts"]:
        artifact_path = Path(manifest[artifact_name])
        content = artifact_path.read_text(encoding="utf-8")
        if len(content) > max_chars:
            content = content[:max_chars] + "\n... [truncated]"
        language = artifact_path.suffix.lstrip(".") or "text"
        blocks.append(
            "\n".join(
                [
                    f"## Artifact: {artifact_name}",
                    f"Source file: {artifact_path.name}",
                    f"```{language}",
                    content,
                    "```",
                ]
            )
        )

    return "\n\n".join(blocks)


def replace_placeholders(template: str, context: dict[str, str]) -> str:
    """Perform simple placeholder substitution for `{{name}}` style template variables."""
    rendered = template
    for key, value in context.items():
        rendered = rendered.replace(f"{{{{{key}}}}}", value)
    return rendered
