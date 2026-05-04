"""Tests for design-matrix construction and export behavior."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from llm_doe.config import load_config
from llm_doe.design import build_design


class DesignTests(unittest.TestCase):
    """Validate that factorial designs are generated with the expected size and outputs."""

    def test_factorial_size(self) -> None:
        """A two-by-two design replicated twice should yield eight runs and two output files."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            (tmp / "configs").mkdir()
            (tmp / "outputs").mkdir()
            config_path = tmp / "configs" / "config.json"
            config_path.write_text(
                """
                {
                  "project_root": "..",
                  "design": {
                    "replications": 2,
                    "random_seed": 123,
                    "randomize": true,
                    "factors": [
                      {"name": "model", "levels": ["a", "b"]},
                      {"name": "temperature", "levels": [0.1, 0.5]}
                    ]
                  },
                  "outputs": {
                    "dir": "outputs"
                  }
                }
                """.strip(),
                encoding="utf-8",
            )

            config = load_config(config_path)
            result = build_design(config)
            self.assertEqual(len(result["runs"]), 8)
            self.assertTrue(Path(result["json_path"]).exists())
            self.assertTrue(Path(result["csv_path"]).exists())
            first_run = result["runs"][0]
            self.assertIn("inference_options", first_run["settings"])
            self.assertIn("temperature", first_run["settings"]["inference_options"])


if __name__ == "__main__":
    unittest.main()
