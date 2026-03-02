#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "$0")" && pwd)"
# Use agent name (first arg value after --agents) as result subfolder; fallback to timestamp.
AGENT_NAME=""
for arg in "$@"; do
  if [ "$arg" = "--agents" ] || [ "$arg" = "--agent" ]; then
    AGENT_NEXT=1
    continue
  fi
  if [ "${AGENT_NEXT:-0}" -eq 1 ]; then
    AGENT_NAME="$arg"
    break
  fi
done
AGENT_NAME=${AGENT_NAME:-$(date +%Y%m%d_%H%M%S)}
HOST_RESULTS="$ROOT/results/$AGENT_NAME"
mkdir -p "$HOST_RESULTS"

# Writable cache for venvs that is outside the code tree
HOST_VENVS="$ROOT/.run_cache/venvs"
mkdir -p "$HOST_VENVS"

# Host screenshots directory (per agent) to persist captures
HOST_SCREENSHOTS="$ROOT/screenshots/$AGENT_NAME"
mkdir -p "$HOST_SCREENSHOTS"

# Host logs directory (per agent)
HOST_LOGS="$ROOT/results/$AGENT_NAME/logs"
mkdir -p "$HOST_LOGS"

# Pass all args to entrypoint; mount repo and per-run results for persistence.
docker run -it --rm \
  -p 6080:6080 \
  -v "$ROOT:/home/computeruse/NoisyBenchmark:ro" \
  -v "$HOST_RESULTS:/home/computeruse/results" \
  -v "$HOST_VENVS:/home/computeruse/.venvs" \
  -v "$HOST_SCREENSHOTS:/home/computeruse/screenshots" \
  -v "$HOST_LOGS:/home/computeruse/logs" \
  -e RESULTS_DIR=/home/computeruse/results \
  -e SCREENSHOT_DIR=/home/computeruse/screenshots \
  -e VENV_DIR=/home/computeruse/.venvs \
  -e LOG_DIR=/home/computeruse/logs \
  -w /home/computeruse/NoisyBenchmark \
  desktop-agent "$@"
