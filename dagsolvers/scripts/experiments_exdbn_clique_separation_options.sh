#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
DAGSOLVERS_DIR=$(CDPATH= cd -- "${SCRIPT_DIR}/.." && pwd)
PROJECT_DIR=$(CDPATH= cd -- "${DAGSOLVERS_DIR}/.." && pwd)

cd "${DAGSOLVERS_DIR}" || exit 1

export PYTHONPATH="${PROJECT_DIR}:${DAGSOLVERS_DIR}:${PYTHONPATH:-}"
export KMP_DUPLICATE_LIB_OK=TRUE

CMD="python3 ./run_experiments.py --multirun --config-name=config-cluster"

data=${PROBLEM:-cliquefree-er}
lag_num=${LAGS:-0}
edge_ratios=${EDGE_RATIO:-4,5}
vars=${VARIABLES:-20}
samples=${SAMPLES:-2000}
seed=${SEEDS:-range(1,6)}
max_clique_sizes=${MAX_CLIQUE_SIZE:-5}
time_limits=${TIME_LIMIT:-1800}

export CLIQUE_SEPERATION_FORMULATION=${CLIQUE_SEPERATION_FORMULATION:-k_plus_1}
export CLIQUE_SEPERATION_SELECTION=${CLIQUE_SEPERATION_SELECTION:-first}
export CLIQUE_SEPERATION_TOP_K=${CLIQUE_SEPERATION_TOP_K:-5}
export CLIQUE_SEPERATION_MAX_JACCARD=${CLIQUE_SEPERATION_MAX_JACCARD:-0.8}
export CLIQUE_SEPERATION_DEDUP=${CLIQUE_SEPERATION_DEDUP:-true}

experiment="CLIQUE_SEPERATION_${CLIQUE_SEPERATION_FORMULATION}_${CLIQUE_SEPERATION_SELECTION}"

${CMD} experiment="${experiment}" problem="${data}" problem.p="${lag_num}" ++problem.intra_edge_ratio="${edge_ratios}" ++problem.inter_edge_ratio="${edge_ratios}" problem.number_of_variables="${vars}" problem.number_of_samples="${samples}" problem.seed="${seed}" solver=clique_separation_options ++solver.max_clique_size="${max_clique_sizes}" solver.time_limit="${time_limits}" solver.experiment_diagnostics=true
