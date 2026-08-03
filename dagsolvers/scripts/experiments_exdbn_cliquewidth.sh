#!/bin/sh

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
DAGSOLVERS_DIR=$(CDPATH= cd -- "${SCRIPT_DIR}/.." && pwd)
PROJECT_DIR=$(CDPATH= cd -- "${DAGSOLVERS_DIR}/.." && pwd)

cd "${DAGSOLVERS_DIR}" || exit 1

export PYTHONPATH="${PROJECT_DIR}:${DAGSOLVERS_DIR}:${PYTHONPATH:-}"
export  KMP_DUPLICATE_LIB_OK=TRUE

# Keep this experiment batch separate from historical A--G results.  Override
# EXDBN_CLIQUEWIDTH_RESULTS_DIR when a different destination is needed.
RESULTS_DIR=${EXDBN_CLIQUEWIDTH_RESULTS_DIR:-"${DAGSOLVERS_DIR}/results/A-G实验记录/第四次实验结果"}
MULTIRUN_DIR="${RESULTS_DIR}/multirun"
export EXDBN_STATIC_CSV_BASE_DIR="${RESULTS_DIR}"

mkdir -p "${MULTIRUN_DIR}"
SWEEP_DIR=$(mktemp -d "${MULTIRUN_DIR}/exdbn_cliquewidth.XXXXXX")
CMD="python3 ./run_experiments.py --multirun --config-name=config-cluster hydra.sweep.dir=${SWEEP_DIR}"

max_clique_sizes="5"
vars="20"
samples="2000"
seed="range(1,6)"
edge_ratios="5"
lag_num="0"
data="cliquefree-er"
time_limits="60,120,300,600,1200,1800,2700,3600,5400,7200"
solvers="milp,milp_cliquewidth"


${CMD} experiment="CLIQUE" problem="${data}" problem.p="${lag_num}" ++problem.intra_edge_ratio="${edge_ratios}" ++problem.inter_edge_ratio="${edge_ratios}" problem.number_of_variables="${vars}" problem.number_of_samples="${samples}" problem.seed="${seed}" solver="${solvers}" ++solver.max_clique_size="${max_clique_sizes}" solver.time_limit="${time_limits}"

echo "[RUN OUTPUT] ${SWEEP_DIR}"
echo "[RESULT CSV ROOT] ${RESULTS_DIR}"
