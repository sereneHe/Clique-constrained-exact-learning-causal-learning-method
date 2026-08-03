#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
DAGSOLVERS_DIR=$(CDPATH= cd -- "${SCRIPT_DIR}/.." && pwd)
PROJECT_DIR=$(CDPATH= cd -- "${DAGSOLVERS_DIR}/.." && pwd)

cd "${DAGSOLVERS_DIR}" || exit 1

export PYTHONPATH="${PROJECT_DIR}:${DAGSOLVERS_DIR}:${PYTHONPATH:-}"
export KMP_DUPLICATE_LIB_OK=TRUE
# Keep A--G tables separate from historical result CSVs.
export EXDBN_STATIC_CSV_BASE_DIR="${DAGSOLVERS_DIR}/results/Test_new"
export EXDBN_DISABLE_STATIC_RUNTIME_CSV=1

AG_SUMMARY_OUTPUT="${DAGSOLVERS_DIR}/results/最新7种方法/ER-4-0-MISS-CDE-实验记录_100M_1800s.csv"
mkdir -p "${EXDBN_STATIC_CSV_BASE_DIR}" "$(dirname "${AG_SUMMARY_OUTPUT}")" "${DAGSOLVERS_DIR}/multirun"

run_and_summarize() {
    sweep_dir=$(mktemp -d "${DAGSOLVERS_DIR}/multirun/Test_new.XXXXXX")
    sweep_summary="${sweep_dir}/A-G_experiments.csv"
    python3 ./run_experiments.py --multirun --config-name=config-cluster \
        hydra.sweep.dir="${sweep_dir}" "$@"
    python3 ./scripts/summarize_ag_runs.py "${DAGSOLVERS_DIR}" \
        --run-root "${sweep_dir}" --output "${sweep_summary}"
    python3 ./scripts/merge_ag_summary.py "${sweep_summary}" "${AG_SUMMARY_OUTPUT}"
}

CMD="run_and_summarize"

max_clique_sizes="5"
vars="20"
samples="2000"
seed="range(1,6)"
edge_ratios="4"
lag_num="0"
data="cliquefree-er"
time_limits="1800"

COMMON="problem=${data} problem.p=${lag_num} ++problem.intra_edge_ratio=${edge_ratios} ++problem.inter_edge_ratio=\${problem.intra_edge_ratio} problem.number_of_variables=${vars} problem.number_of_samples=${samples} problem.seed=${seed} ++solver.max_clique_size=${max_clique_sizes} solver.time_limit=${time_limits} solver.experiment_diagnostics=true"

# # 0. Independent historical cliquewidth implementation used as a control.
# ${CMD} experiment="CLIQUEWIDTH-original_control" ${COMMON} solver=milp_cliquewidth solver.weights_bound=100

# # 1. Unified MILP Clique baseline: no A--G enhancement enabled.
# ${CMD} experiment="CLIQUE" ${COMMON} solver=milp_clique solver.weights_bound=100 solver.clique_cut_formulation=original solver.clique_cut_selection=original solver.enable_delayed_separation=false solver.enable_incumbent_repair=false solver.enable_fractional_separation=false solver.big_m_mode=scalar solver.enable_checkpoints=false

# # 2. B1/F2: submit one first minimal (k+1) inequality per callback.
# ${CMD} experiment="B1-first_min_k+1-F2-first_k+1_cut" ${COMMON} solver=milp_clique solver.weights_bound=20 solver.clique_cut_formulation=k_plus_1 solver.clique_cut_selection=first solver.max_clique_cuts_per_callback=1 solver.deduplicate_clique_cuts=false

# # 3. B3: among the minimal (k+1) candidates, submit the most violated one.
# ${CMD} experiment="B3-most_violated_k+1" ${COMMON} solver=milp_clique solver.weights_bound=20 solver.clique_cut_formulation=k_plus_1 solver.clique_cut_selection=most_violated solver.max_clique_cuts_per_callback=1 solver.deduplicate_clique_cuts=false

# 4. C3: greedily repair the support and locally refit changed columns by QR LS.
${CMD} experiment="C3-local_LS_QR_repair" ${COMMON} solver=milp_clique solver.weights_bound=100 solver.enable_incumbent_repair=true solver.repair_variant=C3 solver.repair_refit_solver=qr

# 5. C5: validated violation/loss-aware repair with refit and explicit retries.
${CMD} experiment="C5-validated_auto_refit_retry" ${COMMON} solver=milp_clique solver.weights_bound=100 solver.enable_incumbent_repair=true solver.repair_variant=C5 solver.repair_refit_solver=auto solver.repair_deletion_score=violation_loss solver.repair_max_retries=2 solver.repair_ridge_alpha=0.001

# 6. E2: tighter scalar Big-M; M=20 was the strongest saved Big-M result.
${CMD} experiment="E2-big_M_20" ${COMMON} solver=milp_clique solver.big_m_mode=scalar solver.weights_bound=100

echo "[ALL DONE] CLIQUEWIDTH control, CLIQUE baseline and five recommended variants completed."
