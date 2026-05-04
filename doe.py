"""Convenience entry point for running the DOE CLI from the project root."""

from pathlib import Path
import sys

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

load_dotenv(ROOT / ".env", override=False)

from llm_doe.cli import main


if __name__ == "__main__":
    main()
