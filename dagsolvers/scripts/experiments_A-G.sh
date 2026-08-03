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

AG_SUMMARY_OUTPUT="${EXDBN_STATIC_CSV_BASE_DIR}/A-G_experiments.csv"
mkdir -p "${EXDBN_STATIC_CSV_BASE_DIR}" "${DAGSOLVERS_DIR}/multirun"

run_and_summarize() {
    sweep_dir=$(mktemp -d "${DAGSOLVERS_DIR}/multirun/Test_new.XXXXXX")
    summary_tmp="${AG_SUMMARY_OUTPUT}.tmp"

    refresh_summary() {
        if python3 ./scripts/summarize_ag_runs.py "${DAGSOLVERS_DIR}" \
            --finished-only --output "${summary_tmp}"; then
            mv -f "${summary_tmp}" "${AG_SUMMARY_OUTPUT}"
        else
            rm -f "${summary_tmp}"
        fi
    }

    python3 ./run_experiments.py --multirun --config-name=config-cluster \
        hydra.sweep.dir="${sweep_dir}" "$@" &
    experiment_pid=$!

    while kill -0 "${experiment_pid}" 2>/dev/null; do
        refresh_summary
        sleep 30
    done &
    summary_pid=$!

    experiment_status=0
    wait "${experiment_pid}" || experiment_status=$?
    kill "${summary_pid}" 2>/dev/null || true
    wait "${summary_pid}" 2>/dev/null || true
    refresh_summary
    return "${experiment_status}"
}

CMD="run_and_summarize"

max_clique_sizes="5"
vars="20"
samples="2000"
seed="range(1,3)"
edge_ratios="4,5"
lag_num="0"
data="cliquefree-er"
time_limits="1800"

COMMON="problem=${data} problem.p=${lag_num} ++problem.intra_edge_ratio=${edge_ratios} ++problem.inter_edge_ratio=\${problem.intra_edge_ratio} problem.number_of_variables=${vars} problem.number_of_samples=${samples} problem.seed=${seed} ++solver.max_clique_size=${max_clique_sizes} solver.time_limit=${time_limits} solver.experiment_diagnostics=true"

# # A：simultaneous 基线与修正后的 delayed separation hits=1/2/3。
# ${CMD} experiment="METHOD_A_SIMULTANEOUS_BASELINE" ${COMMON} solver=milp_clique solver.weights_bound=20 solver.enable_cycle_constraints=true solver.enable_clique_constraints=true solver.separation_order=cycle_first solver.delayed_second_separation=false
# DAGSOLVER_VARIANT=A ${CMD} experiment="METHOD_A_ESCALATION_HITS_1" ${COMMON} solver=delayed_separation solver.weights_bound=20 solver.dense_escalation_hits=1 solver.clique_separation_time_budget=0.02
# DAGSOLVER_VARIANT=A ${CMD} experiment="METHOD_A_ESCALATION_HITS_2" ${COMMON} solver=delayed_separation solver.weights_bound=20 solver.dense_escalation_hits=2 solver.clique_separation_time_budget=0.02
# DAGSOLVER_VARIANT=A ${CMD} experiment="METHOD_A_ESCALATION_HITS_3" ${COMMON} solver=delayed_separation solver.weights_bound=20 solver.dense_escalation_hits=3 solver.clique_separation_time_budget=0.02

# B/F：统一的 clique separation 形式与候选选择选项。
# CLIQUE_SEPERATION_FORMULATION=k_plus_1 CLIQUE_SEPERATION_SELECTION=first CLIQUE_SEPERATION_DEDUP=false ${CMD} experiment="CLIQUE_SEPERATION_K_PLUS_1_FIRST" ${COMMON} solver=clique_separation_options solver.weights_bound=20 solver.max_clique_cuts_per_callback=1
CLIQUE_SEPERATION_FORMULATION=k_plus_1 CLIQUE_SEPERATION_SELECTION=most_violated CLIQUE_SEPERATION_DEDUP=false ${CMD} experiment="CLIQUE_SEPERATION_K_PLUS_1_MOST_VIOLATED" ${COMMON} solver=clique_separation_options solver.weights_bound=20 solver.max_clique_cuts_per_callback=1
CLIQUE_SEPERATION_FORMULATION=k_plus_1 CLIQUE_SEPERATION_SELECTION=history CLIQUE_SEPERATION_DEDUP=false ${CMD} experiment="CLIQUE_SEPERATION_K_PLUS_1_HISTORY" ${COMMON} solver=clique_separation_options solver.weights_bound=20 solver.max_clique_cuts_per_callback=1
CLIQUE_SEPERATION_FORMULATION=k_plus_1 CLIQUE_SEPERATION_SELECTION=top_k_diverse CLIQUE_SEPERATION_TOP_K=5 CLIQUE_SEPERATION_MAX_JACCARD=0.6 CLIQUE_SEPERATION_DEDUP=true ${CMD} experiment="CLIQUE_SEPERATION_K_PLUS_1_TOP_5_DIVERSE" ${COMMON} solver=clique_separation_options solver.weights_bound=20 solver.max_clique_cuts_per_callback=5
CLIQUE_SEPERATION_FORMULATION=maximal CLIQUE_SEPERATION_SELECTION=all CLIQUE_SEPERATION_DEDUP=true ${CMD} experiment="CLIQUE_SEPERATION_MAXIMAL_ALL" ${COMMON} solver=clique_separation_options solver.weights_bound=20 solver.max_clique_cuts_per_callback=0

# D：保留无 fractional 基线；重新验证修改后的 root 与 selective non-root separation。
DAGSOLVER_VARIANT=D1 ${CMD} experiment="METHOD_D1_NO_FRACTIONAL_M20" ${COMMON} solver=fractional_separation solver.weights_bound=20
DAGSOLVER_VARIANT=D2 ${CMD} experiment="METHOD_D2_ROOT_EXHAUSTIVE_M20" ${COMMON} solver=fractional_separation solver.weights_bound=20 solver.fractional_root_only=true solver.fractional_violation_tolerance=1e-4 solver.fractional_separation_time_budget=0.005
DAGSOLVER_VARIANT=D3 ${CMD} experiment="METHOD_D3_ROOT_GREEDY_WEIGHTED_M20" ${COMMON} solver=fractional_separation solver.weights_bound=20 solver.fractional_root_only=true solver.fractional_greedy_starts=10 solver.fractional_violation_tolerance=1e-4 solver.fractional_separation_time_budget=0.005
DAGSOLVER_VARIANT=D4 ${CMD} experiment="METHOD_D4_SELECTIVE_NONROOT_M20" ${COMMON} solver=fractional_separation solver.weights_bound=20 solver.fractional_root_only=false solver.nonroot_separation_frequency=100 solver.nonroot_max_cuts_per_callback=1 solver.fractional_violation_tolerance=1e-4 solver.fractional_separation_time_budget=0.005 solver.fractional_max_zero_rounds=3
DAGSOLVER_VARIANT=D5 ${CMD} experiment="METHOD_D5_HISTORY_GUIDED_SELECTIVE_M20" ${COMMON} solver=fractional_separation solver.weights_bound=20 solver.fractional_root_only=false solver.dense_history_min_hits=2 solver.nonroot_separation_frequency=50 solver.nonroot_max_cuts_per_callback=1 solver.fractional_violation_tolerance=1e-4 solver.fractional_separation_time_budget=0.005 solver.fractional_max_zero_rounds=3

# # E：围绕此前表现最好的 M=20 增加 M=15/25，并保留 edge-specific Mij。
# ${CMD} experiment="METHOD_E_BIG_M_15" ${COMMON} solver=bigm_relaxation solver.big_m_mode=scalar solver.weights_bound=15
# ${CMD} experiment="METHOD_E_BIG_M_20" ${COMMON} solver=bigm_relaxation solver.big_m_mode=scalar solver.weights_bound=20
# ${CMD} experiment="METHOD_E_BIG_M_25" ${COMMON} solver=bigm_relaxation solver.big_m_mode=scalar solver.weights_bound=25
# ${CMD} experiment="METHOD_E_EDGE_SPECIFIC_MIJ" ${COMMON} solver=bigm_relaxation solver.big_m_mode=edge_specific solver.weights_bound=100 solver.edge_specific_safety_factor=1.01

# # G：单次连续求解并保存完整 checkpoints。
# DAGSOLVER_VARIANT=G ${CMD} experiment="METHOD_G_CONTINUOUS_CHECKPOINTS" problem="${data}" problem.p="${lag_num}" ++problem.intra_edge_ratio="${edge_ratios}" '++problem.inter_edge_ratio=${problem.intra_edge_ratio}' problem.number_of_variables="${vars}" problem.number_of_samples="${samples}" problem.seed="${seed}" solver=time_limit_optimization ++solver.max_clique_size="${max_clique_sizes}" solver.weights_bound=20 solver.time_limit=7200 solver.checkpoint_times="[5,15,30,60,120,300,600,1000,1200,1800,2700,3600,5400,7200]" solver.experiment_diagnostics=true

# echo "[ALL DONE] Selected and revised A--G experiments completed."

# C：保留 no-repair 基线、表现较好的 QR/C5，以及修正总预算后的 C6。
DAGSOLVER_VARIANT=C1 ${CMD} experiment="METHOD_C1_NO_REPAIR" ${COMMON} solver=repair_incumbent solver.weights_bound=20
DAGSOLVER_VARIANT=C3 ${CMD} experiment="METHOD_C3_LOCAL_LEAST_SQUARES_QR" ${COMMON} solver=repair_incumbent solver.weights_bound=20 solver.repair_refit_solver=qr
DAGSOLVER_VARIANT=C5 ${CMD} experiment="METHOD_C5_VALIDATED_AUTO_REFIT_RETRY" ${COMMON} solver=repair_incumbent solver.weights_bound=20 solver.repair_refit_solver=auto solver.repair_deletion_score=violation_loss solver.repair_max_retries=2 solver.repair_ridge_alpha=0.001
cut_cache_dir="${DAGSOLVERS_DIR}/repair_cut_cache"
DAGSOLVER_VARIANT=C6 ${CMD} experiment="METHOD_C6_BUILD_VALID_CUT_CACHE" ${COMMON} solver=repair_incumbent solver.weights_bound=20 solver.time_limit=180 solver.repair_cut_cache_mode=write solver.repair_cut_cache_dir="${cut_cache_dir}"
DAGSOLVER_VARIANT=C6 ${CMD} experiment="METHOD_C6_REUSE_VALID_CUT_CACHE" ${COMMON} solver=repair_incumbent solver.weights_bound=20 solver.time_limit=1620 solver.repair_cut_cache_mode=read solver.repair_cut_cache_dir="${cut_cache_dir}"
