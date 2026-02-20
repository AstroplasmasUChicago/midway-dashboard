#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

while true; do
  "$SCRIPT_DIR/run.sh"
  sleep 290
done
