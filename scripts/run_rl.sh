#!/usr/bin/env bash
set -euo pipefail

TARGET_DATE="${1:-}"
FLOW_TYPE="${2:-}"

if [[ -z "$TARGET_DATE" || -z "$FLOW_TYPE" ]]; then
  echo "Uso: bash scripts/run_rl.sh <TARGET_DATE> <FLOW_TYPE>"
  echo "Ejemplo: bash scripts/run_rl.sh 2026-03-01 ISSUING"
  exit 1
fi

if [[ ! -f "settlement_data.xlsx" ]]; then
  echo "ERROR: falta settlement_data.xlsx"
  exit 1
fi

if [[ ! -f "ipom_data.xlsx" ]]; then
  echo "ERROR: falta ipom_data.xlsx"
  exit 1
fi

python main.py --fecha-objetivo "$TARGET_DATE" --tipo-flujo "$FLOW_TYPE"
