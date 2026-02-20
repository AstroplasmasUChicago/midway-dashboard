#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="$SCRIPT_DIR/.venv/bin/python"

cd "$SCRIPT_DIR"
export PATH="/software/slurm-current-el8-x86_64/bin:/software/modules/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
export OMP_NUM_THREADS=1

if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="$(command -v python3)"
fi

exec nice -n20 "$PYTHON_BIN" "$SCRIPT_DIR/periodic_slurm_status.py" "$@"
