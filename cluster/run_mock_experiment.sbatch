#!/bin/bash
#SBATCH --account=davisjam
#SBATCH --nodes=1
#SBATCH --ntasks=4
#SBATCH --qos=normal
#SBATCH --time=01:00:00
#SBATCH --partition=ai
#SBATCH --job-name=llm-doe-mock
#SBATCH --output=slurm-%x-%j.out
#SBATCH --error=slurm-%x-%j.err

set -euo pipefail

SCRATCH_ROOT="${SCRATCH_ROOT:-/scratch/gautschi/rcalvome}"
REPO_URL="${REPO_URL:-git@github.com:rcalvom/phd-notes.git}"
REPO_REF="${REPO_REF:-}"
REPO_DIR_NAME="${REPO_DIR_NAME:-phd-notes-${SLURM_JOB_ID:-manual}}"
CHECKOUT_DIR="${SCRATCH_ROOT}/${REPO_DIR_NAME}"
PROJECT_SUBDIR="${PROJECT_SUBDIR:-Spring_2026/STAT-51400/project}"
PROJECT_DIR="${CHECKOUT_DIR}/${PROJECT_SUBDIR}"
CONFIG_REL="${CONFIG_REL:-configs/full_factorial.json}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
RUN_LIMIT="${RUN_LIMIT:-}"

command -v git >/dev/null 2>&1 || {
  echo "git is required to clone the repository." >&2
  exit 1
}

command -v "${PYTHON_BIN}" >/dev/null 2>&1 || {
  echo "Configured Python interpreter was not found: ${PYTHON_BIN}" >&2
  exit 1
}

"${PYTHON_BIN}" - <<'PY'
"""Fail early when the job environment provides an unsupported Python version."""

from __future__ import annotations

import sys

if sys.version_info < (3, 11):
    raise SystemExit(f"Python 3.11+ is required, found {sys.version.split()[0]}.")
PY

if [[ -e "${CHECKOUT_DIR}" ]]; then
  echo "Checkout directory already exists: ${CHECKOUT_DIR}" >&2
  echo "Set REPO_DIR_NAME to a different value if you want a separate clone." >&2
  exit 1
fi

mkdir -p "${SCRATCH_ROOT}"

if [[ -n "${REPO_REF}" ]]; then
  git clone --branch "${REPO_REF}" --single-branch "${REPO_URL}" "${CHECKOUT_DIR}"
else
  git clone "${REPO_URL}" "${CHECKOUT_DIR}"
fi

if [[ ! -d "${PROJECT_DIR}" ]]; then
  echo "Expected project directory does not exist after clone: ${PROJECT_DIR}" >&2
  exit 1
fi

cd "${PROJECT_DIR}"

RUN_CMD=(
  "${PYTHON_BIN}" doe.py run
  --config "${CONFIG_REL}"
  --dry-run
  --clean
  --rebuild-data
  --rebuild-design
  --force
)

if [[ -n "${RUN_LIMIT}" ]]; then
  RUN_CMD+=(--limit "${RUN_LIMIT}")
fi

"${RUN_CMD[@]}"
"${PYTHON_BIN}" doe.py summarize-results --config "${CONFIG_REL}"

echo "Checkout directory: ${CHECKOUT_DIR}"
echo "Project directory: ${PROJECT_DIR}"
echo "Results CSV: ${PROJECT_DIR}/outputs/results.csv"
echo "Summary CSV: ${PROJECT_DIR}/outputs/results_summary.csv"
