#!/bin/sh

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
DAGSOLVERS_DIR=$(CDPATH= cd -- "${SCRIPT_DIR}/.." && pwd)
PROJECT_DIR=$(CDPATH= cd -- "${DAGSOLVERS_DIR}/.." && pwd)

cd "${DAGSOLVERS_DIR}" || exit 1

export PYTHONPATH="${PROJECT_DIR}:${DAGSOLVERS_DIR}:${PYTHONPATH:-}"
export KMP_DUPLICATE_LIB_OK=TRUE

CMD="python3 ./run_experiments.py --multirun --config-name=config-cluster"

max_clique_sizes="5"
vars="20"
samples="2000"
seed="range(1,6)"
edge_ratios="4,5"
lag_num="0"
data="cliquefree-er"
time_limits="1800"
solvers="bigm_relaxation"

# Comma-separated Hydra sweep of scalar Big-M values.
BIG_M_OPTIONS=${BIG_M_OPTIONS:-"10,15,20,25,50,100"}
# Select scalar, edge_specific, or all Method E variants.
BIG_M_MODE=${BIG_M_MODE:-all}
# Global fallback/cap used only by the edge-specific option.
BIG_M_EDGE_FALLBACK=${BIG_M_EDGE_FALLBACK:-100}
BIG_M_EDGE_SAFETY_FACTOR=${BIG_M_EDGE_SAFETY_FACTOR:-1.01}
BIG_M_EDGE_CONDITION_LIMIT=${BIG_M_EDGE_CONDITION_LIMIT:-1.0e10}

COMMON="problem=${data} problem.p=${lag_num} ++problem.intra_edge_ratio=${edge_ratios} ++problem.inter_edge_ratio=${edge_ratios} problem.number_of_variables=${vars} problem.number_of_samples=${samples} problem.seed=${seed} solver=${solvers} ++solver.max_clique_size=${max_clique_sizes} solver.time_limit=${time_limits} solver.experiment_diagnostics=true"

case "${BIG_M_MODE}" in
    scalar)
        ${CMD} experiment="METHOD_E_BIG_M_OPTIONS" ${COMMON} solver.big_m_mode=scalar solver.weights_bound="${BIG_M_OPTIONS}"
        ;;
    edge_specific)
        ${CMD} experiment="METHOD_E_EDGE_SPECIFIC_MIJ" ${COMMON} solver.big_m_mode=edge_specific solver.weights_bound="${BIG_M_EDGE_FALLBACK}" solver.edge_specific_safety_factor="${BIG_M_EDGE_SAFETY_FACTOR}" solver.edge_specific_condition_limit="${BIG_M_EDGE_CONDITION_LIMIT}"
        ;;
    all)
        ${CMD} experiment="METHOD_E_BIG_M_OPTIONS" ${COMMON} solver.big_m_mode=scalar solver.weights_bound="${BIG_M_OPTIONS}"
        ${CMD} experiment="METHOD_E_EDGE_SPECIFIC_MIJ" ${COMMON} solver.big_m_mode=edge_specific solver.weights_bound="${BIG_M_EDGE_FALLBACK}" solver.edge_specific_safety_factor="${BIG_M_EDGE_SAFETY_FACTOR}" solver.edge_specific_condition_limit="${BIG_M_EDGE_CONDITION_LIMIT}"
        ;;
    *)
        echo "Invalid BIG_M_MODE=${BIG_M_MODE}; expected scalar, edge_specific, or all" >&2
        exit 2
        ;;
esac
