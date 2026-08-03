#!/bin/sh
set -eu

if [ "$#" -ne 2 ]; then
  echo "usage: $0 LOG_PATH SUMMARY_DIR" >&2
  exit 2
fi

LOG_PATH=$1
SUMMARY_DIR=$2
PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
export PATH="/Library/Frameworks/Python.framework/Versions/3.11/bin:/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"

mkdir -p "$(dirname -- "${LOG_PATH}")" "${SUMMARY_DIR}"
exec >>"${LOG_PATH}" 2>&1

cd "${PROJECT_DIR}"
echo "[RUNNER] clean callback-order experiment started at $(date '+%Y-%m-%d %H:%M:%S %Z')"
dagsolvers/scripts/experiments_callback_order_1800.sh
python3 dagsolvers/scripts/summarize_callback_order.py \
  "${LOG_PATH}" --output-dir "${SUMMARY_DIR}"
echo "[RUNNER] clean callback-order experiment finished at $(date '+%Y-%m-%d %H:%M:%S %Z')"
