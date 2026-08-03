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
solvers="delayed_separation"

# Baseline: inspect and submit both cycle and clique violations in the same
# MIPSOL callback; no delayed escalation.
${CMD} experiment="METHOD_A_SIMULTANEOUS_BASELINE" problem="${data}" problem.p="${lag_num}" ++problem.intra_edge_ratio="${edge_ratios}" ++problem.inter_edge_ratio="${edge_ratios}" problem.number_of_variables="${vars}" problem.number_of_samples="${samples}" problem.seed="${seed}" solver="milp_clique" ++solver.max_clique_size="${max_clique_sizes}" solver.time_limit="${time_limits}" solver.experiment_diagnostics=true solver.enable_cycle_constraints=true solver.enable_clique_constraints=true solver.separation_order=cycle_first solver.delayed_second_separation=false

# Compare when a recurring dense region should escalate from a cycle cut to a
# first-minimal (k+1) clique cut. The solver records dense-region hit counts,
# escalation reasons, and whether the region recurs after escalation.
DAGSOLVER_VARIANT=A ${CMD} experiment="METHOD_A_ESCALATION_HITS_1" problem="${data}" problem.p="${lag_num}" ++problem.intra_edge_ratio="${edge_ratios}" ++problem.inter_edge_ratio="${edge_ratios}" problem.number_of_variables="${vars}" problem.number_of_samples="${samples}" problem.seed="${seed}" solver="${solvers}" ++solver.max_clique_size="${max_clique_sizes}" solver.time_limit="${time_limits}" solver.experiment_diagnostics=true solver.dense_escalation_hits=1 solver.clique_separation_time_budget=0.02
DAGSOLVER_VARIANT=A ${CMD} experiment="METHOD_A_ESCALATION_HITS_2" problem="${data}" problem.p="${lag_num}" ++problem.intra_edge_ratio="${edge_ratios}" ++problem.inter_edge_ratio="${edge_ratios}" problem.number_of_variables="${vars}" problem.number_of_samples="${samples}" problem.seed="${seed}" solver="${solvers}" ++solver.max_clique_size="${max_clique_sizes}" solver.time_limit="${time_limits}" solver.experiment_diagnostics=true solver.dense_escalation_hits=2 solver.clique_separation_time_budget=0.02
DAGSOLVER_VARIANT=A ${CMD} experiment="METHOD_A_ESCALATION_HITS_3" problem="${data}" problem.p="${lag_num}" ++problem.intra_edge_ratio="${edge_ratios}" ++problem.inter_edge_ratio="${edge_ratios}" problem.number_of_variables="${vars}" problem.number_of_samples="${samples}" problem.seed="${seed}" solver="${solvers}" ++solver.max_clique_size="${max_clique_sizes}" solver.time_limit="${time_limits}" solver.experiment_diagnostics=true solver.dense_escalation_hits=3 solver.clique_separation_time_budget=0.02
