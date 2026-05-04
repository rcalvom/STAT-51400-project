"""Command-line interface for building, running, and summarizing experiments."""

from __future__ import annotations

import argparse
import json

from .config import load_config
from .data_prep import build_data_artifacts
from .design import build_design
from .runner import run_experiment, summarize_results


def main() -> None:
    """Parse CLI arguments and dispatch to the requested pipeline command."""
    parser = argparse.ArgumentParser(description="Run a configurable DOE pipeline for LLM analyses.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_data_parser = subparsers.add_parser("build-data", help="Create dataset artifacts from the source CSV.")
    build_data_parser.add_argument("--config", default="configs/pilot_experiment.json")

    build_design_parser = subparsers.add_parser("build-design", help="Build the factorial design matrix.")
    build_design_parser.add_argument("--config", default="configs/pilot_experiment.json")

    run_parser = subparsers.add_parser("run", help="Execute the experiment runner.")
    run_parser.add_argument("--config", default="configs/pilot_experiment.json")
    run_parser.add_argument("--limit", type=int, default=None)
    run_parser.add_argument("--rebuild-data", action="store_true")
    run_parser.add_argument("--rebuild-design", action="store_true")
    run_parser.add_argument("--dry-run", action="store_true")
    run_parser.add_argument("--force", action="store_true")
    run_parser.add_argument("--clean", action="store_true")

    summary_parser = subparsers.add_parser("summarize-results", help="Aggregate finished runs by factor combination.")
    summary_parser.add_argument("--config", default="configs/pilot_experiment.json")

    args = parser.parse_args()
    config = load_config(args.config)

    if args.command == "build-data":
        result = build_data_artifacts(config)
    elif args.command == "build-design":
        design = build_design(config)
        result = {
            "json_path": design["json_path"],
            "csv_path": design["csv_path"],
            "n_runs": len(design["runs"]),
        }
    elif args.command == "run":
        result = run_experiment(
            config,
            limit=args.limit,
            rebuild_data=args.rebuild_data,
            rebuild_design=args.rebuild_design,
            dry_run=args.dry_run,
            force=args.force,
            clean=args.clean,
        )
    elif args.command == "summarize-results":
        result = summarize_results(config)
    else:
        raise ValueError(f"Unknown command: {args.command}")

    print(json.dumps(result, indent=2, ensure_ascii=False))
