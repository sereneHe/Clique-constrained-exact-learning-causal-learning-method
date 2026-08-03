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
solvers="repair_incumbent"
cut_cache_dir="${DAGSOLVERS_DIR}/repair_cut_cache"
cache_build_time="180"
cache_reuse_time="1620"

DAGSOLVER_VARIANT=C1 ${CMD} experiment="METHOD_C1_NO_REPAIR" problem="${data}" problem.p="${lag_num}" ++problem.intra_edge_ratio="${edge_ratios}" ++problem.inter_edge_ratio="${edge_ratios}" problem.number_of_variables="${vars}" problem.number_of_samples="${samples}" problem.seed="${seed}" solver="${solvers}" ++solver.max_clique_size="${max_clique_sizes}" solver.time_limit="${time_limits}"
DAGSOLVER_VARIANT=C2 ${CMD} experiment="METHOD_C2_GREEDY_EDGE_DELETION" problem="${data}" problem.p="${lag_num}" ++problem.intra_edge_ratio="${edge_ratios}" ++problem.inter_edge_ratio="${edge_ratios}" problem.number_of_variables="${vars}" problem.number_of_samples="${samples}" problem.seed="${seed}" solver="${solvers}" ++solver.max_clique_size="${max_clique_sizes}" solver.time_limit="${time_limits}"
DAGSOLVER_VARIANT=C3 ${CMD} experiment="METHOD_C3_LOCAL_LEAST_SQUARES_QR" problem="${data}" problem.p="${lag_num}" ++problem.intra_edge_ratio="${edge_ratios}" ++problem.inter_edge_ratio="${edge_ratios}" problem.number_of_variables="${vars}" problem.number_of_samples="${samples}" problem.seed="${seed}" solver="${solvers}" ++solver.max_clique_size="${max_clique_sizes}" solver.time_limit="${time_limits}" solver.repair_refit_solver=qr
DAGSOLVER_VARIANT=C4 ${CMD} experiment="METHOD_C4_LOCAL_RIDGE_CBSETSOLUTION" problem="${data}" problem.p="${lag_num}" ++problem.intra_edge_ratio="${edge_ratios}" ++problem.inter_edge_ratio="${edge_ratios}" problem.number_of_variables="${vars}" problem.number_of_samples="${samples}" problem.seed="${seed}" solver="${solvers}" ++solver.max_clique_size="${max_clique_sizes}" solver.time_limit="${time_limits}" solver.repair_ridge_alpha=0.001
DAGSOLVER_VARIANT=C5 ${CMD} experiment="METHOD_C5_VALIDATED_AUTO_REFIT_RETRY" problem="${data}" problem.p="${lag_num}" ++problem.intra_edge_ratio="${edge_ratios}" ++problem.inter_edge_ratio="${edge_ratios}" problem.number_of_variables="${vars}" problem.number_of_samples="${samples}" problem.seed="${seed}" solver="${solvers}" ++solver.max_clique_size="${max_clique_sizes}" solver.time_limit="${time_limits}" solver.experiment_diagnostics=true solver.repair_refit_solver=auto solver.repair_deletion_score=violation_loss solver.repair_max_retries=2 solver.repair_ridge_alpha=0.001

# C6 is deliberately two-stage: first collect only globally valid cycle/clique
# cuts, then pre-add that cache in a fresh solve.  Arbitrary rejected regions
# are not cached because excluding them could remove a valid optimum.
DAGSOLVER_VARIANT=C6 ${CMD} experiment="METHOD_C6_BUILD_VALID_CUT_CACHE" problem="${data}" problem.p="${lag_num}" ++problem.intra_edge_ratio="${edge_ratios}" ++problem.inter_edge_ratio="${edge_ratios}" problem.number_of_variables="${vars}" problem.number_of_samples="${samples}" problem.seed="${seed}" solver="${solvers}" ++solver.max_clique_size="${max_clique_sizes}" solver.time_limit="${cache_build_time}" solver.repair_ridge_alpha=0.001 solver.repair_cut_cache_mode=write solver.repair_cut_cache_dir="${cut_cache_dir}"
DAGSOLVER_VARIANT=C6 ${CMD} experiment="METHOD_C6_REUSE_VALID_CUT_CACHE" problem="${data}" problem.p="${lag_num}" ++problem.intra_edge_ratio="${edge_ratios}" ++problem.inter_edge_ratio="${edge_ratios}" problem.number_of_variables="${vars}" problem.number_of_samples="${samples}" problem.seed="${seed}" solver="${solvers}" ++solver.max_clique_size="${max_clique_sizes}" solver.time_limit="${cache_reuse_time}" solver.repair_ridge_alpha=0.001 solver.repair_cut_cache_mode=read solver.repair_cut_cache_dir="${cut_cache_dir}"
