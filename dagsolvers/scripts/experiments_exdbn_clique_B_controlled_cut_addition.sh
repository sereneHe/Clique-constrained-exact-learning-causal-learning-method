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
solvers="controlled_cut_addition"

${CMD} experiment="METHOD_B1_FIRST_MINIMAL_K_PLUS_1" problem="${data}" problem.p="${lag_num}" ++problem.intra_edge_ratio="${edge_ratios}" ++problem.inter_edge_ratio="${edge_ratios}" problem.number_of_variables="${vars}" problem.number_of_samples="${samples}" problem.seed="${seed}" solver="${solvers}" solver.method_family_name=controlled_cut_addition solver.method_variant=B1 ++solver.max_clique_size="${max_clique_sizes}" solver.time_limit="${time_limits}" solver.experiment_diagnostics=true solver.max_clique_cuts_per_callback=1 solver.deduplicate_clique_cuts=false
${CMD} experiment="METHOD_B6_ORIGINAL_MOST_VIOLATED" problem="${data}" problem.p="${lag_num}" ++problem.intra_edge_ratio="${edge_ratios}" ++problem.inter_edge_ratio="${edge_ratios}" problem.number_of_variables="${vars}" problem.number_of_samples="${samples}" problem.seed="${seed}" solver="${solvers}" solver.method_family_name=controlled_cut_addition solver.method_variant=B6 ++solver.max_clique_size="${max_clique_sizes}" solver.time_limit="${time_limits}" solver.experiment_diagnostics=true solver.max_clique_cuts_per_callback=1 solver.deduplicate_clique_cuts=false
${CMD} experiment="METHOD_B2_TOP_3_SCORE_DIVERSE" problem="${data}" problem.p="${lag_num}" ++problem.intra_edge_ratio="${edge_ratios}" ++problem.inter_edge_ratio="${edge_ratios}" problem.number_of_variables="${vars}" problem.number_of_samples="${samples}" problem.seed="${seed}" solver="${solvers}" solver.method_family_name=controlled_cut_addition solver.method_variant=B4 ++solver.max_clique_size="${max_clique_sizes}" solver.time_limit="${time_limits}" solver.experiment_diagnostics=true solver.clique_top_k=3 solver.max_clique_cuts_per_callback=3 solver.max_cut_jaccard_similarity=0.8 solver.deduplicate_clique_cuts=false
${CMD} experiment="METHOD_B3_TOP_5_JACCARD_DIVERSE" problem="${data}" problem.p="${lag_num}" ++problem.intra_edge_ratio="${edge_ratios}" ++problem.inter_edge_ratio="${edge_ratios}" problem.number_of_variables="${vars}" problem.number_of_samples="${samples}" problem.seed="${seed}" solver="${solvers}" solver.method_family_name=controlled_cut_addition solver.method_variant=B4 ++solver.max_clique_size="${max_clique_sizes}" solver.time_limit="${time_limits}" solver.experiment_diagnostics=true solver.clique_top_k=5 solver.max_clique_cuts_per_callback=5 solver.max_cut_jaccard_similarity=0.6 solver.deduplicate_clique_cuts=false
${CMD} experiment="METHOD_B4_HISTORY_HIT_PRIORITY" problem="${data}" problem.p="${lag_num}" ++problem.intra_edge_ratio="${edge_ratios}" ++problem.inter_edge_ratio="${edge_ratios}" problem.number_of_variables="${vars}" problem.number_of_samples="${samples}" problem.seed="${seed}" solver="${solvers}" solver.method_family_name=controlled_cut_addition solver.method_variant=B3 ++solver.max_clique_size="${max_clique_sizes}" solver.time_limit="${time_limits}" solver.experiment_diagnostics=true solver.max_clique_cuts_per_callback=1 solver.deduplicate_clique_cuts=false
${CMD} experiment="METHOD_B5_TOP_5_DIVERSE_DEDUP" problem="${data}" problem.p="${lag_num}" ++problem.intra_edge_ratio="${edge_ratios}" ++problem.inter_edge_ratio="${edge_ratios}" problem.number_of_variables="${vars}" problem.number_of_samples="${samples}" problem.seed="${seed}" solver="${solvers}" solver.method_family_name=controlled_cut_addition solver.method_variant=B5 ++solver.max_clique_size="${max_clique_sizes}" solver.time_limit="${time_limits}" solver.experiment_diagnostics=true solver.clique_top_k=5 solver.max_clique_cuts_per_callback=5 solver.max_cut_jaccard_similarity=0.6 solver.deduplicate_clique_cuts=true
