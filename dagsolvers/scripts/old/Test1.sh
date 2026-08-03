#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

# Unified entry point.  Both groups run by default; either group can be
# disabled without editing this file:
#   RUN_AG=0 ./experiments_clique_cut_strategies.sh
#   RUN_DIAGNOSTICS=0 ./experiments_clique_cut_strategies.sh
RUN_AG=${RUN_AG:-1}
RUN_DIAGNOSTICS=${RUN_DIAGNOSTICS:-1}

# Fast diagnostic defaults, aligned with the A--G pilot scripts.  Explicit
# environment values supplied by the caller still take precedence.
export PROBLEM=${PROBLEM:-cliquefree-er}
export LAGS=${LAGS:-0}
export EDGE_RATIO=${EDGE_RATIO:-5}
export VARIABLES=${VARIABLES:-11}
export SAMPLES=${SAMPLES:-200}
export SEEDS=${SEEDS:-range(1,3)}
export MAX_CLIQUE_SIZE=${MAX_CLIQUE_SIZE:-5}
export TIME_LIMIT=${TIME_LIMIT:-1000}

run_script() {
    label=$1
    script=$2
    if [ ! -f "${script}" ]; then
        echo "[ERROR] Missing ${label}: ${script}" >&2
        exit 1
    fi
    echo "[START] ${label} $(date '+%Y-%m-%d %H:%M:%S')"
    sh "${script}"
    echo "[DONE]  ${label} $(date '+%Y-%m-%d %H:%M:%S')"
}

if [ "${RUN_AG}" = "1" ]; then
    # run_script "A Delayed Separation" \
    #     "${SCRIPT_DIR}/experiments_exdbn_clique_A_delayed_separation.sh"
    # run_script "B Controlled Cut Addition" \
    #     "${SCRIPT_DIR}/experiments_exdbn_clique_B_controlled_cut_addition.sh"
    # run_script "C Repair Incumbent" \
    #     "${SCRIPT_DIR}/experiments_exdbn_clique_C_repair_incumbent.sh"
    # run_script "D Fractional Separation" \
    #     "${SCRIPT_DIR}/experiments_exdbn_clique_D_fractional_separation.sh"
    run_script "E Big-M Relaxation" \
        "${SCRIPT_DIR}/experiments_exdbn_clique_E_bigm_relaxation.sh"
    run_script "F Stronger Clique Cuts" \
        "${SCRIPT_DIR}/experiments_exdbn_clique_F_stronger_clique_cuts.sh"
    run_script "G Time-Limit Optimization" \
        "${SCRIPT_DIR}/experiments_exdbn_clique_G_time_limit_optimization.sh"
fi

if [ "${RUN_DIAGNOSTICS}" = "1" ]; then
    run_script "Clique diagnostics" "${SCRIPT_DIR}/diagnostics.sh"
fi

echo "[ALL DONE] Requested clique experiments completed."
