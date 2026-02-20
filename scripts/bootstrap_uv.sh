#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PYVER="$(cat "$REPO_DIR/.python-version" 2>/dev/null || echo "3.11")"

cd "$REPO_DIR"

if [[ ! -x ".venv/bin/python" ]]; then
  uv venv --python "$PYVER" .venv
fi

# Keep cluster-installed extras (notably pyslurm) instead of uninstalling them.
uv sync --no-dev --inexact

SCTRL_BIN="$(command -v scontrol || true)"
if [[ -z "$SCTRL_BIN" ]]; then
  echo "ERROR: scontrol not found in PATH; cannot determine cluster Slurm version."
  exit 1
fi

SLURM_VERSION="$("$SCTRL_BIN" --version | awk '{print $2}')"
SLURM_ROOT="/software/slurm-${SLURM_VERSION}"
PYSLURM_TAG="v${SLURM_VERSION}-1"
PYSLURM_GIT_URL="${PYSLURM_GIT_URL:-https://github.com/PySlurm/pyslurm.git}"
PYSLURM_SRC_BASE="$REPO_DIR/.cache/pyslurm-src"
PYSLURM_REPO="$PYSLURM_SRC_BASE/$PYSLURM_TAG"

if [[ ! -d "$SLURM_ROOT" ]]; then
  echo "ERROR: Expected Slurm install path not found: $SLURM_ROOT"
  exit 1
fi

CURRENT_PYSLURM_VER="$(
  .venv/bin/python - <<'PY'
import sys
try:
    import pyslurm
    print(getattr(pyslurm, "__version__", "unknown"))
except Exception:
    print("")
PY
)"

if [[ "$CURRENT_PYSLURM_VER" != "${SLURM_VERSION}."* ]]; then
  echo "Installing matching pyslurm for Slurm $SLURM_VERSION (tag $PYSLURM_TAG)..."
  uv pip install --python "$REPO_DIR/.venv/bin/python" setuptools wheel cython
  if [[ ! -d "$PYSLURM_REPO/.git" ]]; then
    mkdir -p "$PYSLURM_SRC_BASE"
    git clone --depth 1 --branch "$PYSLURM_TAG" "$PYSLURM_GIT_URL" "$PYSLURM_REPO"
  fi
  (
    cd "$PYSLURM_REPO"
    CC=/usr/bin/clang CXX=/usr/bin/clang++ \
      "$REPO_DIR/.venv/bin/python" setup.py build "--slurm=$SLURM_ROOT" install
  )
fi

.venv/bin/python - <<'PY'
import pyslurm
print(f"pyslurm import check: OK ({pyslurm.__version__})")
PY

echo "Ready. Run:"
echo "  ./run.sh --dry-run"
