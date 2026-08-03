#!/bin/sh

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
DAGSOLVERS_DIR=$(CDPATH= cd -- "${SCRIPT_DIR}/.." && pwd)
PROJECT_DIR=$(CDPATH= cd -- "${DAGSOLVERS_DIR}/.." && pwd)

cd "${DAGSOLVERS_DIR}" || exit 1

export PYTHONPATH="${PROJECT_DIR}:${DAGSOLVERS_DIR}:${PYTHONPATH:-}"
export  KMP_DUPLICATE_LIB_OK=TRUE

mkdir -p "${DAGSOLVERS_DIR}/multirun"
SWEEP_DIR=$(mktemp -d "${DAGSOLVERS_DIR}/multirun/exdbn_clique.XXXXXX")
CMD="python3 ./run_experiments.py --multirun --config-name=config-cluster hydra.sweep.dir=${SWEEP_DIR}"

max_clique_sizes="5"
vars="20"
samples="2000"
seed="range(1,6)"
edge_ratios="5"
lag_num="0"
data="cliquefree-er"
time_limits="60,120,300,600,1200,1800,2700,3600,5400,7200"
#solvers="milp_clique"
solvers="milp"


${CMD} experiment="CLIQUE" problem="${data}" problem.p="${lag_num}" ++problem.intra_edge_ratio="${edge_ratios}" ++problem.inter_edge_ratio="${edge_ratios}" problem.number_of_variables="${vars}" problem.number_of_samples="${samples}" problem.seed="${seed}" solver="${solvers}" ++solver.max_clique_size="${max_clique_sizes}" solver.time_limit="${time_limits}"
