#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="/home/cernetic/pyslurm/freya/u/mihac/pyslurm"
SCRIPT_PATH="$REPO_DIR/periodic_slurm_status.py"
VENV_PY="$REPO_DIR/.venv/bin/python"
LOG_DIR="$REPO_DIR/logs"
LOG_FILE="$LOG_DIR/cron_periodic_slurm_status.log"
LOCK_FILE="/tmp/caslake_status_plot.lock"

mkdir -p "$LOG_DIR"
cd "$REPO_DIR"

PATH="/software/slurm-current-el8-x86_64/bin:/software/modules/bin:/usr/local/bin:/usr/bin:/bin"
export PATH
export OMP_NUM_THREADS=1

if [[ -x "$VENV_PY" ]]; then
  PYTHON_BIN="$VENV_PY"
else
  PYTHON_BIN="$(command -v python3)"
fi

{
  exec 9>"$LOCK_FILE"
  if ! flock -n 9; then
    echo "[$(date -Iseconds)] skipped (previous run still active)"
    exit 0
  fi

  echo "[$(date -Iseconds)] start"
  if nice -n20 "$PYTHON_BIN" "$SCRIPT_PATH"; then
    echo "[$(date -Iseconds)] ok"
  else
    rc=$?
    echo "[$(date -Iseconds)] failed (exit=$rc)"
    exit "$rc"
  fi
} >>"$LOG_FILE" 2>&1
