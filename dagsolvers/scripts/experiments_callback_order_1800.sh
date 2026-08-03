#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
DAGSOLVERS_DIR=$(CDPATH= cd -- "${SCRIPT_DIR}/.." && pwd)
PROJECT_DIR=$(CDPATH= cd -- "${DAGSOLVERS_DIR}/.." && pwd)

cd "${DAGSOLVERS_DIR}" || exit 1

export PYTHONPATH="${PROJECT_DIR}:${DAGSOLVERS_DIR}:${PYTHONPATH:-}"
export KMP_DUPLICATE_LIB_OK=TRUE
export PYTHONUNBUFFERED=1
export EXDBN_DISABLE_STATIC_RUNTIME_CSV=1

CALLBACK_RESULT_DIR="${DAGSOLVERS_DIR}/results/callback_order_1800_运行结果"
CALLBACK_SUMMARY_OUTPUT="${CALLBACK_RESULT_DIR}/callback_order_1800_experiments.csv"
mkdir -p "${CALLBACK_RESULT_DIR}" "${DAGSOLVERS_DIR}/multirun"

run_and_summarize() {
    sweep_dir=$(mktemp -d "${DAGSOLVERS_DIR}/multirun/callback_order_1800.XXXXXX")
    python3 -u ./run_experiments.py --multirun --config-name=config-cluster \
        hydra.sweep.dir="${sweep_dir}" "$@"
    python3 ./scripts/summarize_ag_runs.py "${DAGSOLVERS_DIR}" \
        --experiment-prefix "CALLBACK_1800_" \
        --output "${CALLBACK_SUMMARY_OUTPUT}"
}

CMD="run_and_summarize"

max_clique_sizes="5"
vars="20"
samples="2000"
seed="range(1,5)"
edge_ratios="5"
lag_num="0"
data="cliquefree-er"
time_limits="1800"
solvers="milp_clique"


# ${CMD} experiment="CALLBACK_1800_CYCLE_ONLY" problem="${data}" problem.p="${lag_num}" ++problem.intra_edge_ratio="${edge_ratios}" ++problem.inter_edge_ratio="${edge_ratios}" problem.number_of_variables="${vars}" problem.number_of_samples="${samples}" problem.seed="${seed}" solver="${solvers}" ++solver.max_clique_size="${max_clique_sizes}" solver.time_limit="${time_limits}" solver.experiment_diagnostics=true ++solver.print_callback_events=true ++solver.print_retained_solutions=true solver.print_clique_cuts=true solver.enable_cycle_constraints=true solver.enable_clique_constraints=false
# ${CMD} experiment="CALLBACK_1800_CLIQUE_ONLY" problem="${data}" problem.p="${lag_num}" ++problem.intra_edge_ratio="${edge_ratios}" ++problem.inter_edge_ratio="${edge_ratios}" problem.number_of_variables="${vars}" problem.number_of_samples="${samples}" problem.seed="${seed}" solver="${solvers}" ++solver.max_clique_size="${max_clique_sizes}" solver.time_limit="${time_limits}" solver.experiment_diagnostics=true ++solver.print_callback_events=true ++solver.print_retained_solutions=true solver.print_clique_cuts=true solver.enable_cycle_constraints=false solver.enable_clique_constraints=true
# ${CMD} experiment="CALLBACK_1800_CYCLE_EARLY" problem="${data}" problem.p="${lag_num}" ++problem.intra_edge_ratio="${edge_ratios}" ++problem.inter_edge_ratio="${edge_ratios}" problem.number_of_variables="${vars}" problem.number_of_samples="${samples}" problem.seed="${seed}" solver="${solvers}" ++solver.max_clique_size="${max_clique_sizes}" solver.time_limit="${time_limits}" solver.experiment_diagnostics=true ++solver.print_callback_events=true ++solver.print_retained_solutions=true solver.print_clique_cuts=true solver.enable_cycle_constraints=true solver.enable_clique_constraints=true solver.separation_order=cycle_first solver.delayed_second_separation=true
# ${CMD} experiment="CALLBACK_1800_CLIQUE_EARLY" problem="${data}" problem.p="${lag_num}" ++problem.intra_edge_ratio="${edge_ratios}" ++problem.inter_edge_ratio="${edge_ratios}" problem.number_of_variables="${vars}" problem.number_of_samples="${samples}" problem.seed="${seed}" solver="${solvers}" ++solver.max_clique_size="${max_clique_sizes}" solver.time_limit="${time_limits}" solver.experiment_diagnostics=true ++solver.print_callback_events=true ++solver.print_retained_solutions=true solver.print_clique_cuts=true solver.enable_cycle_constraints=true solver.enable_clique_constraints=true solver.separation_order=clique_first solver.delayed_second_separation=true
${CMD} experiment="CALLBACK_1800_CYCLE_THEN_CLIQUE" problem="${data}" problem.p="${lag_num}" ++problem.intra_edge_ratio="${edge_ratios}" ++problem.inter_edge_ratio="${edge_ratios}" problem.number_of_variables="${vars}" problem.number_of_samples="${samples}" problem.seed="${seed}" solver="${solvers}" ++solver.max_clique_size="${max_clique_sizes}" solver.time_limit="${time_limits}" solver.experiment_diagnostics=true ++solver.print_callback_events=true ++solver.print_retained_solutions=true solver.print_clique_cuts=true solver.enable_cycle_constraints=true solver.enable_clique_constraints=true solver.separation_order=cycle_first solver.delayed_second_separation=false
${CMD} experiment="CALLBACK_1800_CLIQUE_THEN_CYCLE" problem="${data}" problem.p="${lag_num}" ++problem.intra_edge_ratio="${edge_ratios}" ++problem.inter_edge_ratio="${edge_ratios}" problem.number_of_variables="${vars}" problem.number_of_samples="${samples}" problem.seed="${seed}" solver="${solvers}" ++solver.max_clique_size="${max_clique_sizes}" solver.time_limit="${time_limits}" solver.experiment_diagnostics=true ++solver.print_callback_events=true ++solver.print_retained_solutions=true solver.print_clique_cuts=true solver.enable_cycle_constraints=true solver.enable_clique_constraints=true solver.separation_order=clique_first solver.delayed_second_separation=false
