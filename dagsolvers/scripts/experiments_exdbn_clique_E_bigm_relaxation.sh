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

${CMD} experiment="METHOD_E_BIG_M_SCALAR" problem="${data}" problem.p="${lag_num}" ++problem.intra_edge_ratio="${edge_ratios}" ++problem.inter_edge_ratio="${edge_ratios}" problem.number_of_variables="${vars}" problem.number_of_samples="${samples}" problem.seed="${seed}" solver="${solvers}" solver.method_variant=E1,E6,E2,E7,E3,E4 ++solver.max_clique_size="${max_clique_sizes}" solver.time_limit="${time_limits}" solver.experiment_diagnostics=true
${CMD} experiment="METHOD_E5_EDGE_SPECIFIC_MIJ" problem="${data}" problem.p="${lag_num}" ++problem.intra_edge_ratio="${edge_ratios}" ++problem.inter_edge_ratio="${edge_ratios}" problem.number_of_variables="${vars}" problem.number_of_samples="${samples}" problem.seed="${seed}" solver="${solvers}" solver.method_variant=E5 ++solver.max_clique_size="${max_clique_sizes}" solver.time_limit="${time_limits}" solver.experiment_diagnostics=true solver.big_m_mode=edge_specific solver.weights_bound=100 solver.edge_specific_safety_factor=1.01
