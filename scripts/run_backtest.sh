#!/usr/bin/env bash
set -euo pipefail

RL_VALUE="${1:-}"
START_DATE="${2:-}"
END_DATE="${3:-}"
FLOW_TYPE="${4:-}"

if [[ -z "$RL_VALUE" || -z "$START_DATE" || -z "$END_DATE" || -z "$FLOW_TYPE" ]]; then
  echo "Uso: bash scripts/run_backtest.sh <RL> <START> <END> <FLOW>"
  echo "Ejemplo: bash scripts/run_backtest.sh 123456 2025-01-01 2025-06-30 ISSUING"
  exit 1
fi

python contrast_method.py \
  --rl-reference-estimated "$RL_VALUE" \
  --period-start "$START_DATE" \
  --period-end "$END_DATE" \
  --tipo-flujo "$FLOW_TYPE"