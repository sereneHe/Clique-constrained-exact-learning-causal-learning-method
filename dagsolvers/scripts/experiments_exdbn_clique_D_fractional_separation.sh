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
solvers="fractional_separation"

DAGSOLVER_VARIANT=D1 ${CMD} experiment="METHOD_D1_NO_FRACTIONAL_M20" problem="${data}" problem.p="${lag_num}" ++problem.intra_edge_ratio="${edge_ratios}" ++problem.inter_edge_ratio="${edge_ratios}" problem.number_of_variables="${vars}" problem.number_of_samples="${samples}" problem.seed="${seed}" solver="${solvers}" ++solver.max_clique_size="${max_clique_sizes}" solver.time_limit="${time_limits}" solver.weights_bound=20
DAGSOLVER_VARIANT=D2 ${CMD} experiment="METHOD_D2_ROOT_EXHAUSTIVE_M20" problem="${data}" problem.p="${lag_num}" ++problem.intra_edge_ratio="${edge_ratios}" ++problem.inter_edge_ratio="${edge_ratios}" problem.number_of_variables="${vars}" problem.number_of_samples="${samples}" problem.seed="${seed}" solver="${solvers}" ++solver.max_clique_size="${max_clique_sizes}" solver.time_limit="${time_limits}" solver.weights_bound=20 solver.fractional_root_only=true solver.fractional_violation_tolerance=1e-4 solver.fractional_separation_time_budget=0.005
DAGSOLVER_VARIANT=D3 ${CMD} experiment="METHOD_D3_ROOT_GREEDY_WEIGHTED_M20" problem="${data}" problem.p="${lag_num}" ++problem.intra_edge_ratio="${edge_ratios}" ++problem.inter_edge_ratio="${edge_ratios}" problem.number_of_variables="${vars}" problem.number_of_samples="${samples}" problem.seed="${seed}" solver="${solvers}" ++solver.max_clique_size="${max_clique_sizes}" solver.time_limit="${time_limits}" solver.weights_bound=20 solver.fractional_root_only=true solver.fractional_greedy_starts=10 solver.fractional_violation_tolerance=1e-4 solver.fractional_separation_time_budget=0.005
DAGSOLVER_VARIANT=D4 ${CMD} experiment="METHOD_D4_SELECTIVE_NONROOT_M20" problem="${data}" problem.p="${lag_num}" ++problem.intra_edge_ratio="${edge_ratios}" ++problem.inter_edge_ratio="${edge_ratios}" problem.number_of_variables="${vars}" problem.number_of_samples="${samples}" problem.seed="${seed}" solver="${solvers}" ++solver.max_clique_size="${max_clique_sizes}" solver.time_limit="${time_limits}" solver.weights_bound=20 solver.experiment_diagnostics=true solver.fractional_root_only=false solver.nonroot_separation_frequency=100 solver.nonroot_max_cuts_per_callback=1 solver.fractional_violation_tolerance=1e-4 solver.fractional_separation_time_budget=0.005 solver.fractional_max_zero_rounds=3
DAGSOLVER_VARIANT=D5 ${CMD} experiment="METHOD_D5_HISTORY_GUIDED_SELECTIVE_M20" problem="${data}" problem.p="${lag_num}" ++problem.intra_edge_ratio="${edge_ratios}" ++problem.inter_edge_ratio="${edge_ratios}" problem.number_of_variables="${vars}" problem.number_of_samples="${samples}" problem.seed="${seed}" solver="${solvers}" ++solver.max_clique_size="${max_clique_sizes}" solver.time_limit="${time_limits}" solver.weights_bound=20 solver.experiment_diagnostics=true solver.fractional_root_only=false solver.dense_history_min_hits=2 solver.nonroot_separation_frequency=50 solver.nonroot_max_cuts_per_callback=1 solver.fractional_violation_tolerance=1e-4 solver.fractional_separation_time_budget=0.005 solver.fractional_max_zero_rounds=3
