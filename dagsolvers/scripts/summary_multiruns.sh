#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
DAGSOLVERS_DIR=$(CDPATH= cd -- "${SCRIPT_DIR}/.." && pwd)

SUMMARY_OUTPUT="${DAGSOLVERS_DIR}/results/experiments_exdbn_clique_summary.csv"

if [ "$#" -gt 0 ]; then
    SUMMARY_ROOT=$1
elif [ -d "${DAGSOLVERS_DIR}/mlruns" ]; then
    SUMMARY_ROOT=${DAGSOLVERS_DIR}
elif [ -d "${DAGSOLVERS_DIR}/../metacentrum_runs" ]; then
    SUMMARY_ROOT=${DAGSOLVERS_DIR}/../metacentrum_runs
else
    SUMMARY_ROOT=${DAGSOLVERS_DIR}
fi

python3 "${SCRIPT_DIR}/summarize_ag_runs.py" \
    "${SUMMARY_ROOT}" \
    --output "${SUMMARY_OUTPUT}"

echo "[SUMMARY] ${SUMMARY_OUTPUT}"
