"""Helpers for loading experiment configuration files and resolving project paths."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_config(config_path: str | Path) -> dict[str, Any]:
    """Load a JSON config file and annotate it with resolved internal paths."""
    path = Path(config_path).expanduser().resolve()
    with path.open("r", encoding="utf-8") as handle:
        config = json.load(handle)

    project_root_setting = config.get("project_root", ".")
    project_root = (path.parent / project_root_setting).resolve()
    config["_config_path"] = str(path)
    config["_project_root"] = str(project_root)
    return config


def project_root(config: dict[str, Any]) -> Path:
    """Return the resolved project root stored on a loaded config object."""
    return Path(config["_project_root"])


def config_path(config: dict[str, Any]) -> Path:
    """Return the absolute path of the config file used to build the config object."""
    return Path(config["_config_path"])


def resolve_project_path(config: dict[str, Any], value: str | Path) -> Path:
    """Resolve a path relative to the configured project root unless it is already absolute."""
    path = Path(value)
    if path.is_absolute():
        return path
    return (project_root(config) / path).resolve()
