#!/usr/bin/env bash
set -euo pipefail

echo "Validando inputs..."

[[ -f "settlement_data.xlsx" ]] && echo "OK settlement_data.xlsx" || { echo "FALTA settlement_data.xlsx"; exit 1; }
[[ -f "ipom_data.xlsx" ]] && echo "OK ipom_data.xlsx" || { echo "FALTA ipom_data.xlsx"; exit 1; }

echo "Todo correcto ✅"
