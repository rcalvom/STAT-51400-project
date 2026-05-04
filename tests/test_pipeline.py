"""End-to-end tests for the mock pipeline execution and result export flow."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from llm_doe.config import load_config
from llm_doe.runner import run_experiment, summarize_results


class PipelineTests(unittest.TestCase):
    """Exercise the pipeline using a temporary dataset and the mock backend."""

    def test_mock_pipeline(self) -> None:
        """The runner should execute, summarize, and clean results in a temporary workspace."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            (tmp / "configs").mkdir()
            (tmp / "prompts").mkdir()

            csv_path = tmp / "data.csv"
            csv_path.write_text(
                "\n".join(
                    [
                        "Session,Trial,Time-to-Target,Success,Stim Paradigm,Tuning Width,Path Efficiency,Average Speed,Total Distance,AD,Target Crosses,Mouse",
                        "1,1,1.5,1,Combined,Narrow,0.7,10.1,12.0,0.3,0,M1",
                        "1,2,2.0,0,Sham,Wide,0.4,6.5,18.0,0.5,1,M1",
                        "2,1,1.2,1,Combined,Wide,0.8,11.0,10.0,0.2,0,M2"
                    ]
                ),
                encoding="utf-8",
            )

            prompt_path = tmp / "prompts" / "prompt.md"
            prompt_path.write_text(
                """
                Run {{run_id}}
                {{analysis_goal}}
                {{data_bundle}}
                Return valid JSON only.
                """.strip(),
                encoding="utf-8",
            )

            config_path = tmp / "configs" / "config.json"
            config = {
                "project_root": "..",
                "analysis_goal": "Test the pipeline.",
                "backend": {"provider": "mock", "response_format": "json"},
                "data": {
                    "csv_path": "data.csv",
                    "sample_rows": 2,
                    "row_filters": [
                        {
                            "column": "Stim Paradigm",
                            "include": ["Combined"]
                        }
                    ],
                    "numeric_columns": [
                        "Session",
                        "Trial",
                        "Time-to-Target",
                        "Success",
                        "Path Efficiency",
                        "Average Speed",
                        "Total Distance",
                        "AD",
                        "Target Crosses"
                    ],
                    "group_summaries": [
                        {
                            "name": "summary_by_stim_tuning",
                            "keys": ["Stim Paradigm", "Tuning Width"],
                            "metrics": ["Success", "Time-to-Target"]
                        }
                    ]
                },
                "artifacts": {"dir": "artifacts/data"},
                "data_views": {
                    "summary_only": {
                        "artifacts": ["overview_markdown", "summary_by_stim_tuning"]
                    }
                },
                "reasoning_profiles": {
                    "low": {
                        "system_suffix": "Stay concise.",
                        "ollama_options": {"num_predict": 50}
                    }
                },
                "design": {
                    "replications": 1,
                    "random_seed": 11,
                    "randomize": False,
                    "factors": [
                        {"name": "model", "levels": ["mock-1", "mock-2"]},
                        {"name": "temperature", "levels": [0.1]},
                        {"name": "reasoning_profile", "levels": ["low"]},
                        {"name": "prompt_template", "levels": ["prompts/prompt.md"]},
                        {"name": "data_view", "levels": ["summary_only"]}
                    ]
                },
                "outputs": {"dir": "outputs"}
            }
            config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")

            loaded = load_config(config_path)
            summary = run_experiment(loaded)
            self.assertEqual(summary["executed_runs"], 2)
            dataset_profile = json.loads((tmp / "artifacts" / "data" / "dataset_profile.json").read_text(encoding="utf-8"))
            self.assertEqual(dataset_profile["row_count"], 2)
            aggregate = summarize_results(loaded)
            self.assertTrue(Path(aggregate["summary_csv"]).exists())

            cleaned = run_experiment(loaded, limit=1, clean=True)
            self.assertEqual(cleaned["executed_runs"], 1)
            results_rows = (tmp / "outputs" / "results.jsonl").read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(results_rows), 1)


if __name__ == "__main__":
    unittest.main()
