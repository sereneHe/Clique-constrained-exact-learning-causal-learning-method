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
solvers="stronger_clique_cuts"

${CMD} experiment="METHOD_F1_MAXIMAL_CUT" problem="${data}" problem.p="${lag_num}" ++problem.intra_edge_ratio="${edge_ratios}" ++problem.inter_edge_ratio="${edge_ratios}" problem.number_of_variables="${vars}" problem.number_of_samples="${samples}" problem.seed="${seed}" solver="${solvers}" solver.method_variant=F1 ++solver.max_clique_size="${max_clique_sizes}" solver.time_limit="${time_limits}" solver.max_clique_cuts_per_callback=0 solver.deduplicate_clique_cuts=true
${CMD} experiment="METHOD_F2_FIRST_K_PLUS_1" problem="${data}" problem.p="${lag_num}" ++problem.intra_edge_ratio="${edge_ratios}" ++problem.inter_edge_ratio="${edge_ratios}" problem.number_of_variables="${vars}" problem.number_of_samples="${samples}" problem.seed="${seed}" solver="${solvers}" solver.method_variant=F2 ++solver.max_clique_size="${max_clique_sizes}" solver.time_limit="${time_limits}" solver.experiment_diagnostics=true solver.max_clique_cuts_per_callback=1 solver.deduplicate_clique_cuts=true
${CMD} experiment="METHOD_F3_TOP_5_K_PLUS_1" problem="${data}" problem.p="${lag_num}" ++problem.intra_edge_ratio="${edge_ratios}" ++problem.inter_edge_ratio="${edge_ratios}" problem.number_of_variables="${vars}" problem.number_of_samples="${samples}" problem.seed="${seed}" solver="${solvers}" solver.method_variant=F3 ++solver.max_clique_size="${max_clique_sizes}" solver.time_limit="${time_limits}" solver.clique_top_k=5 solver.max_clique_cuts_per_callback=5 solver.deduplicate_clique_cuts=true
${CMD} experiment="METHOD_F4_ALL_UNIQUE_K_PLUS_1" problem="${data}" problem.p="${lag_num}" ++problem.intra_edge_ratio="${edge_ratios}" ++problem.inter_edge_ratio="${edge_ratios}" problem.number_of_variables="${vars}" problem.number_of_samples="${samples}" problem.seed="${seed}" solver="${solvers}" solver.method_variant=F4 ++solver.max_clique_size="${max_clique_sizes}" solver.time_limit="${time_limits}" solver.max_clique_cuts_per_callback=0 solver.deduplicate_clique_cuts=true
