#!/bin/sh

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
DAGSOLVERS_DIR=$(CDPATH= cd -- "${SCRIPT_DIR}/.." && pwd)
PROJECT_DIR=$(CDPATH= cd -- "${DAGSOLVERS_DIR}/.." && pwd)

cd "${DAGSOLVERS_DIR}" || exit 1

export PYTHONPATH="${PROJECT_DIR}:${DAGSOLVERS_DIR}:${PYTHONPATH:-}"
export KMP_DUPLICATE_LIB_OK=TRUE

SCRIPT_TAG="experiments_exdbn_clique1"
MULTIRUN_BASE_DIR="${DAGSOLVERS_DIR}/multirun/${SCRIPT_TAG}"
RESULTS_DIR="${DAGSOLVERS_DIR}/results/concurrent_runs/${SCRIPT_TAG}"
STATIC_RESULTS_DIR="${RESULTS_DIR}/static"
SUMMARY_OUTPUT="${RESULTS_DIR}/${SCRIPT_TAG}_summary.csv"

mkdir -p "${MULTIRUN_BASE_DIR}" "${STATIC_RESULTS_DIR}" "${DAGSOLVERS_DIR}/logs"

BATCH_RUN_ROOT=$(mktemp -d "${MULTIRUN_BASE_DIR}/batch.XXXXXX")
export EXDBN_STATIC_CSV_BASE_DIR="${STATIC_RESULTS_DIR}"
export EXDBN_BATCH_RUN_ROOT="${BATCH_RUN_ROOT}"
export EXDBN_BATCH_SUMMARY_OUTPUT="${SUMMARY_OUTPUT}"
export EXDBN_SUMMARY_REFRESH_SECONDS="${EXDBN_SUMMARY_REFRESH_SECONDS:-300}"
CMD="python3 ./run_experiments.py --multirun --config-name=config-cluster"

# Synthetic-data sweep. Comma-separated values generate different instances.
max_clique_sizes="5"
lag_num="0"
data="cliquefree-sf"
time_limits="1800"
solvers="milp_clique"
edge_ratios="5"


# All solver/callback/A--G/diagnostics defaults are defined in:
# experiments_conf/solver/milp_clique.yaml
run_case() {
    experiment_name=$1
    shift
    sweep_dir=$(mktemp -d "${BATCH_RUN_ROOT}/${experiment_name}.XXXXXX")
    ${CMD} hydra.sweep.dir="${sweep_dir}" experiment="${experiment_name}" problem="${data}" problem.p="${lag_num}" ++problem.intra_edge_ratio="${edge_ratios}" '++problem.inter_edge_ratio=${problem.intra_edge_ratio}' problem.number_of_variables="${vars}" problem.number_of_samples="${samples}" problem.seed="${seed}" ++solver.max_clique_size="${max_clique_sizes}" solver.time_limit="${time_limits}" +solver.gurobi_threads=2 "$@"
}

samples="2000"
vars="20" 
seed="1,2,3,4"
run_case "C3-local_LS_QR_repair" solver="${solvers}" solver.weights_bound=100 solver.experiment_diagnostics=false solver.enable_incumbent_repair=true solver.repair_variant=C3 solver.repair_refit_solver=qr

# run_case "CLIQUEWIDTH-original_control" solver=milp_cliquewidth solver.weights_bound=100
# run_case "CLIQUE" solver="${solvers}" solver.weights_bound=100 solver.experiment_diagnostics=false solver.print_clique_cuts=true solver.clique_cut_formulation=original solver.clique_cut_selection=original solver.enable_delayed_separation=false solver.enable_incumbent_repair=false solver.enable_fractional_separation=false solver.big_m_mode=scalar solver.enable_checkpoints=false
# run_case "B1-first_min_k+1-F2-first_k+1_cut" solver="${solvers}" solver.weights_bound=100 solver.experiment_diagnostics=false solver.clique_cut_formulation=k_plus_1 solver.clique_cut_selection=first solver.max_clique_cuts_per_callback=1 solver.deduplicate_clique_cuts=false
# run_case "B3-most_violated_k+1" solver="${solvers}" solver.weights_bound=100 solver.experiment_diagnostics=false solver.clique_cut_formulation=k_plus_1 solver.clique_cut_selection=most_violated solver.max_clique_cuts_per_callback=1 solver.deduplicate_clique_cuts=false
# run_case "C3-local_LS_QR_repair" solver="${solvers}" solver.weights_bound=100 solver.experiment_diagnostics=false solver.enable_incumbent_repair=true solver.repair_variant=C3 solver.repair_refit_solver=qr
# run_case "E2-big_M_20" solver="${solvers}" solver.experiment_diagnostics=false solver.big_m_mode=scalar solver.weights_bound=20
