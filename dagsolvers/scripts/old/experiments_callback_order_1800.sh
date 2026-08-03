#!/bin/sh
set -eu

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
seed="range(1,5)"
edge_ratios="4,5"
lag_num="0"
data="cliquefree-er"
time_limits="1800"
solvers="milp_clique"

COMMON="problem=${data} problem.p=${lag_num} ++problem.intra_edge_ratio=${edge_ratios} ++problem.inter_edge_ratio=${edge_ratios} problem.number_of_variables=${vars} problem.number_of_samples=${samples} problem.seed=${seed} solver=${solvers} ++solver.max_clique_size=${max_clique_sizes} solver.time_limit=${time_limits} solver.experiment_diagnostics=true"

# 1. Cycle-only：仅检测并添加 cycle lazy constraints。
${CMD} experiment="CALLBACK_1800_CYCLE_ONLY" ${COMMON} solver.enable_cycle_constraints=true solver.enable_clique_constraints=false

# 2. Clique-only：仅检测并添加 clique lazy constraints；仅作消融，不保证输出为 DAG。
${CMD} experiment="CALLBACK_1800_CLIQUE_ONLY" ${COMMON} solver.enable_cycle_constraints=false solver.enable_clique_constraints=true

# 3. Cycle-first：先检查 cycle；若违反，本次 MIPSOL 不再执行 clique separation。
${CMD} experiment="CALLBACK_1800_CYCLE_FIRST" ${COMMON} solver.enable_cycle_constraints=true solver.enable_clique_constraints=true solver.separation_order=cycle_first solver.delayed_second_separation=true

# 4. Clique-first：先检查 clique；若违反，本次 MIPSOL 不再执行 cycle separation。
${CMD} experiment="CALLBACK_1800_CLIQUE_FIRST" ${COMMON} solver.enable_cycle_constraints=true solver.enable_clique_constraints=true solver.separation_order=clique_first solver.delayed_second_separation=true
