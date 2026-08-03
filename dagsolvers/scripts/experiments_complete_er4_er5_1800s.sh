#!/bin/sh

# Complete the missing 1800-second paired ExDBN/Clique benchmark runs in:
#   results/cliquefree-er-4-0
#   results/cliquefree-er-5-0
# Target node grids:
#   ER4: 9,15,20,25,30,35,40,45,50
#   ER5: 11,15,20,25,30,35,40,45,50
# A result is complete once seeds 1--4 exist.  Do not extend completed cells
# to seeds 5--10.  Every genuinely missing combination below uses 1800s.

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
DAGSOLVERS_DIR=$(CDPATH= cd -- "${SCRIPT_DIR}/.." && pwd)
PROJECT_DIR=$(CDPATH= cd -- "${DAGSOLVERS_DIR}/.." && pwd)

cd "${DAGSOLVERS_DIR}" || exit 1

export PYTHONPATH="${PROJECT_DIR}:${DAGSOLVERS_DIR}:${PYTHONPATH:-}"
export KMP_DUPLICATE_LIB_OK=TRUE

CMD="python3 ./run_experiments.py --multirun --config-name=config-cluster"
max_clique_sizes="5"
lag_num="0"
data="cliquefree-er"
time_limits="1800"

# ER4 d=9,15,20,25,30,35 already contain seeds 1--4 and need no rerun.
edge_ratios="4"
samples="200,2000"

# ER4 d=40: ExDBN is complete (1--4); Clique only lacks seed 4.
vars="40"
seed="4"
solvers="milp_clique"
${CMD} experiment="CLIQUE2-4-0-COMPLETE-D40-CLIQUE" problem="${data}" problem.p="${lag_num}" ++problem.intra_edge_ratio="${edge_ratios}" ++problem.inter_edge_ratio="${edge_ratios}" problem.number_of_variables="${vars}" problem.number_of_samples="${samples}" problem.seed="${seed}" solver="${solvers}" ++solver.max_clique_size="${max_clique_sizes}" solver.time_limit="${time_limits}"

# ER4 d=45,n=200: ExDBN has 1--3; Clique has 1--2.
vars="45"
samples="200"
seed="4"
solvers="milp"
${CMD} experiment="CLIQUE2-4-0-COMPLETE-D45-N200-EXDBN" problem="${data}" problem.p="${lag_num}" ++problem.intra_edge_ratio="${edge_ratios}" ++problem.inter_edge_ratio="${edge_ratios}" problem.number_of_variables="${vars}" problem.number_of_samples="${samples}" problem.seed="${seed}" solver="${solvers}" ++solver.max_clique_size="${max_clique_sizes}" solver.time_limit="${time_limits}"
seed="3,4"
solvers="milp_clique"
${CMD} experiment="CLIQUE2-4-0-COMPLETE-D45-N200-CLIQUE" problem="${data}" problem.p="${lag_num}" ++problem.intra_edge_ratio="${edge_ratios}" ++problem.inter_edge_ratio="${edge_ratios}" problem.number_of_variables="${vars}" problem.number_of_samples="${samples}" problem.seed="${seed}" solver="${solvers}" ++solver.max_clique_size="${max_clique_sizes}" solver.time_limit="${time_limits}"

# ER4 d=45,n=2000 and all d=50 cells are still absent.
samples="2000"
seed="range(1,5)"
solvers="milp_clique,milp"
${CMD} experiment="CLIQUE2-4-0-COMPLETE-D45-N2000" problem="${data}" problem.p="${lag_num}" ++problem.intra_edge_ratio="${edge_ratios}" ++problem.inter_edge_ratio="${edge_ratios}" problem.number_of_variables="${vars}" problem.number_of_samples="${samples}" problem.seed="${seed}" solver="${solvers}" ++solver.max_clique_size="${max_clique_sizes}" solver.time_limit="${time_limits}"
vars="50"
samples="200,2000"
${CMD} experiment="CLIQUE2-4-0-COMPLETE-D50" problem="${data}" problem.p="${lag_num}" ++problem.intra_edge_ratio="${edge_ratios}" ++problem.inter_edge_ratio="${edge_ratios}" problem.number_of_variables="${vars}" problem.number_of_samples="${samples}" problem.seed="${seed}" solver="${solvers}" ++solver.max_clique_size="${max_clique_sizes}" solver.time_limit="${time_limits}"

# ER5 d=11,15,20,25,30 already contain seeds 1--4 and need no rerun.
edge_ratios="5"
solvers="milp_clique,milp"

# ER5 d=35,n=200: Clique has 1--3; ExDBN is absent.
vars="35"
samples="200"
seed="range(1,5)"
solvers="milp"
${CMD} experiment="CLIQUE1-5-0-COMPLETE-D35-N200-EXDBN" problem="${data}" problem.p="${lag_num}" ++problem.intra_edge_ratio="${edge_ratios}" ++problem.inter_edge_ratio="${edge_ratios}" problem.number_of_variables="${vars}" problem.number_of_samples="${samples}" problem.seed="${seed}" solver="${solvers}" ++solver.max_clique_size="${max_clique_sizes}" solver.time_limit="${time_limits}"
seed="4"
solvers="milp_clique"
${CMD} experiment="CLIQUE1-5-0-COMPLETE-D35-N200-CLIQUE" problem="${data}" problem.p="${lag_num}" ++problem.intra_edge_ratio="${edge_ratios}" ++problem.inter_edge_ratio="${edge_ratios}" problem.number_of_variables="${vars}" problem.number_of_samples="${samples}" problem.seed="${seed}" solver="${solvers}" ++solver.max_clique_size="${max_clique_sizes}" solver.time_limit="${time_limits}"

# ER5 d=35,n=2000 is absent for both solvers.
samples="2000"
seed="range(1,5)"
solvers="milp_clique,milp"
${CMD} experiment="CLIQUE1-5-0-COMPLETE-D35-N2000" problem="${data}" problem.p="${lag_num}" ++problem.intra_edge_ratio="${edge_ratios}" ++problem.inter_edge_ratio="${edge_ratios}" problem.number_of_variables="${vars}" problem.number_of_samples="${samples}" problem.seed="${seed}" solver="${solvers}" ++solver.max_clique_size="${max_clique_sizes}" solver.time_limit="${time_limits}"

# ER5 d=40,45,50 remain entirely absent.
vars="40,45,50"
samples="200,2000"
${CMD} experiment="CLIQUE1-5-0-COMPLETE-D40-D50" problem="${data}" problem.p="${lag_num}" ++problem.intra_edge_ratio="${edge_ratios}" ++problem.inter_edge_ratio="${edge_ratios}" problem.number_of_variables="${vars}" problem.number_of_samples="${samples}" problem.seed="${seed}" solver="${solvers}" ++solver.max_clique_size="${max_clique_sizes}" solver.time_limit="${time_limits}"
