#!/bin/bash
#SBATCH --account=davisjam
#SBATCH --nodes=1
#SBATCH --ntasks=56
#SBATCH --gres=gpu:4
#SBATCH --qos=normal
#SBATCH --time=04:00:00
#SBATCH --partition=ai
#SBATCH --job-name=llm-doe-ollama
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
PREFLIGHT_MOCK_LIMIT="${PREFLIGHT_MOCK_LIMIT:-3}"

OLLAMA_SIF="${OLLAMA_SIF:-/scratch/gautschi/rcalvome/ollama.sif}"
OLLAMA_MODEL_BIND="${OLLAMA_MODEL_BIND:-/scratch/gautschi/rcalvome/.ollama}"
OLLAMA_MODELS_DIR="${OLLAMA_MODELS_DIR:-/root/.ollama}"
OLLAMA_PORT="${OLLAMA_PORT:-11434}"
OLLAMA_HOST="${OLLAMA_HOST:-0.0.0.0:${OLLAMA_PORT}}"
OLLAMA_STARTUP_TIMEOUT_SECONDS="${OLLAMA_STARTUP_TIMEOUT_SECONDS:-300}"

if ! command -v git >/dev/null 2>&1; then
  echo "git is required to clone the repository." >&2
  exit 1
fi

if ! command -v apptainer >/dev/null 2>&1; then
  if [[ -f /etc/profile.d/modules.sh ]]; then
    # Initialize environment-modules in non-interactive jobs when available.
    # shellcheck source=/dev/null
    source /etc/profile.d/modules.sh
  fi
  if command -v module >/dev/null 2>&1; then
    module load apptainer
  fi
fi

command -v apptainer >/dev/null 2>&1 || {
  echo "apptainer is not available in the current job environment." >&2
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
mkdir -p outputs

TMP_CONFIG="$(mktemp "${SLURM_TMPDIR:-/tmp}/llm_doe_config.XXXXXX.json")"
OLLAMA_LOG="${PROJECT_DIR}/outputs/ollama-server-${SLURM_JOB_ID:-manual}.log"

cleanup() {
  local exit_code=$?

  if [[ -n "${OLLAMA_PID:-}" ]] && kill -0 "${OLLAMA_PID}" 2>/dev/null; then
    kill "${OLLAMA_PID}" || true
    wait "${OLLAMA_PID}" || true
  fi

  rm -f "${TMP_CONFIG}"
  exit "${exit_code}"
}

trap cleanup EXIT

"${PYTHON_BIN}" - "${CONFIG_REL}" "${TMP_CONFIG}" "${OLLAMA_PORT}" "${PROJECT_DIR}" <<'PY'
"""Rewrite the experiment config so the backend points at the local Ollama port."""

from __future__ import annotations

import json
import sys
from pathlib import Path

source_path = Path(sys.argv[1])
target_path = Path(sys.argv[2])
port = sys.argv[3]
project_dir = Path(sys.argv[4]).resolve()

config = json.loads(source_path.read_text(encoding="utf-8"))
config["project_root"] = str(project_dir)
config.setdefault("backend", {})
config["backend"]["provider"] = "ollama"
config["backend"]["base_url"] = f"http://127.0.0.1:{port}"
target_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
PY

if [[ "${PREFLIGHT_MOCK_LIMIT}" != "0" ]]; then
  echo "Running mock preflight with limit ${PREFLIGHT_MOCK_LIMIT}..."
  "${PYTHON_BIN}" doe.py run \
    --config "${TMP_CONFIG}" \
    --dry-run \
    --clean \
    --force \
    --rebuild-data \
    --rebuild-design \
    --limit "${PREFLIGHT_MOCK_LIMIT}"
fi

echo "Starting Ollama with Apptainer..."
apptainer run \
  --env "OLLAMA_HOST=${OLLAMA_HOST}" \
  --env "OLLAMA_MODELS=${OLLAMA_MODELS_DIR}" \
  --nv \
  --bind "${OLLAMA_MODEL_BIND}:${OLLAMA_MODELS_DIR}" \
  "${OLLAMA_SIF}" serve >"${OLLAMA_LOG}" 2>&1 &

OLLAMA_PID=$!

echo "Waiting for Ollama API on http://127.0.0.1:${OLLAMA_PORT} ..."
ATTEMPTS=$(( OLLAMA_STARTUP_TIMEOUT_SECONDS / 5 ))
if (( ATTEMPTS < 1 )); then
  ATTEMPTS=1
fi

READY=0
"${PYTHON_BIN}" - "${OLLAMA_PORT}" "${ATTEMPTS}" <<'PY' && READY=1 || READY=0
"""Poll the Ollama tags endpoint until it becomes reachable or time runs out."""

from __future__ import annotations

import sys
import time
import urllib.error
import urllib.request

port = sys.argv[1]
attempts = int(sys.argv[2])
url = f"http://127.0.0.1:{port}/api/tags"

for _ in range(attempts):
    try:
        with urllib.request.urlopen(url, timeout=5):
            raise SystemExit(0)
    except urllib.error.URLError:
        time.sleep(5)

raise SystemExit(1)
PY

if (( READY == 0 )); then
  echo "Ollama did not become ready within ${OLLAMA_STARTUP_TIMEOUT_SECONDS} seconds." >&2
  echo "Inspect the server log at ${OLLAMA_LOG}" >&2
  exit 1
fi

echo "Ollama is ready. Launching real experiment..."
RUN_CMD=(
  "${PYTHON_BIN}" doe.py run
  --config "${TMP_CONFIG}"
  --clean
  --rebuild-data
  --rebuild-design
  --force
)

if [[ -n "${RUN_LIMIT}" ]]; then
  RUN_CMD+=(--limit "${RUN_LIMIT}")
fi

"${RUN_CMD[@]}"

echo "Writing aggregated summary..."
"${PYTHON_BIN}" doe.py summarize-results --config "${TMP_CONFIG}"

echo "Checkout directory: ${CHECKOUT_DIR}"
echo "Project directory: ${PROJECT_DIR}"
echo "Results CSV: ${PROJECT_DIR}/outputs/results.csv"
echo "Summary CSV: ${PROJECT_DIR}/outputs/results_summary.csv"
echo "Ollama log: ${OLLAMA_LOG}"
