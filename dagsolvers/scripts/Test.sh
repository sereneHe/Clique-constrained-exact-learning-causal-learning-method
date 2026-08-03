#!/bin/sh
set -u

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
seed="range(1,3)"
edge_ratios="4"
lag_num="0"
data="cliquefree-er"
time_limits="1200"

for edge_ratio in ${edge_ratios}; do
COMMON="problem=${data} problem.p=${lag_num} ++problem.intra_edge_ratio=${edge_ratio} ++problem.inter_edge_ratio=${edge_ratio} problem.number_of_variables=${vars} problem.number_of_samples=${samples} problem.seed=${seed} ++solver.max_clique_size=${max_clique_sizes} solver.time_limit=${time_limits} solver.experiment_diagnostics=true"

# A：baseline 和 hits=1 已完成；hits=2 只缺 ratio=5；hits=3 两个 ratio 都缺。
if [ "${edge_ratio}" = "5" ]; then
${CMD} experiment="METHOD_A_ESCALATION_HITS_2" ${COMMON} solver=delayed_separation solver.method_variant=A solver.dense_escalation_hits=2 solver.clique_separation_time_budget=0.02
fi
${CMD} experiment="METHOD_A_ESCALATION_HITS_3" ${COMMON} solver=delayed_separation solver.method_variant=A solver.dense_escalation_hits=3 solver.clique_separation_time_budget=0.02

# B：保留已验证较好的 first-minimal，以及修改后的 score/diversity/history 版本。
${CMD} experiment="METHOD_B1_FIRST_MINIMAL_K_PLUS_1" ${COMMON} solver=controlled_cut_addition solver.method_variant=B1 solver.max_clique_cuts_per_callback=1 solver.deduplicate_clique_cuts=false
${CMD} experiment="METHOD_B6_ORIGINAL_MOST_VIOLATED" ${COMMON} solver=controlled_cut_addition solver.method_variant=B6 solver.max_clique_cuts_per_callback=1 solver.deduplicate_clique_cuts=false
${CMD} experiment="METHOD_B2_TOP_3_SCORE_DIVERSE" ${COMMON} solver=controlled_cut_addition solver.method_variant=B4 solver.clique_top_k=3 solver.max_clique_cuts_per_callback=3 solver.max_cut_jaccard_similarity=0.8 solver.deduplicate_clique_cuts=false
${CMD} experiment="METHOD_B3_TOP_5_JACCARD_DIVERSE" ${COMMON} solver=controlled_cut_addition solver.method_variant=B4 solver.clique_top_k=5 solver.max_clique_cuts_per_callback=5 solver.max_cut_jaccard_similarity=0.6 solver.deduplicate_clique_cuts=false
${CMD} experiment="METHOD_B4_HISTORY_HIT_PRIORITY" ${COMMON} solver=controlled_cut_addition solver.method_variant=B3 solver.max_clique_cuts_per_callback=1 solver.deduplicate_clique_cuts=false
${CMD} experiment="METHOD_B5_TOP_5_DIVERSE_DEDUP" ${COMMON} solver=controlled_cut_addition solver.method_variant=B5 solver.clique_top_k=5 solver.max_clique_cuts_per_callback=5 solver.max_cut_jaccard_similarity=0.6 solver.deduplicate_clique_cuts=true

# C：保留 no-repair 基线、表现较好的 QR/C5，以及修正总预算后的 C6。
${CMD} experiment="METHOD_C1_NO_REPAIR" ${COMMON} solver=repair_incumbent solver.method_variant=C1
${CMD} experiment="METHOD_C3_LOCAL_LEAST_SQUARES_QR" ${COMMON} solver=repair_incumbent solver.method_variant=C3 solver.repair_refit_solver=qr
${CMD} experiment="METHOD_C5_VALIDATED_AUTO_REFIT_RETRY" ${COMMON} solver=repair_incumbent solver.method_variant=C5 solver.repair_refit_solver=auto solver.repair_deletion_score=violation_loss solver.repair_max_retries=2 solver.repair_ridge_alpha=0.001
cut_cache_dir="${DAGSOLVERS_DIR}/repair_cut_cache/ratio_${edge_ratio}"
${CMD} experiment="METHOD_C6_BUILD_VALID_CUT_CACHE" ${COMMON} solver=repair_incumbent solver.method_variant=C6 solver.time_limit=180 solver.repair_cut_cache_mode=write solver.repair_cut_cache_dir="${cut_cache_dir}"
${CMD} experiment="METHOD_C6_REUSE_VALID_CUT_CACHE" ${COMMON} solver=repair_incumbent solver.method_variant=C6 solver.time_limit=1620 solver.repair_cut_cache_mode=read solver.repair_cut_cache_dir="${cut_cache_dir}"

# D：保留无 fractional 基线；重新验证修改后的 root 与 selective non-root separation。
${CMD} experiment="METHOD_D1_NO_FRACTIONAL_M20" ${COMMON} solver=fractional_separation solver.method_variant=D1 solver.weights_bound=20
${CMD} experiment="METHOD_D2_ROOT_EXHAUSTIVE_M20" ${COMMON} solver=fractional_separation solver.method_variant=D2 solver.weights_bound=20 solver.fractional_root_only=true solver.fractional_violation_tolerance=1e-4 solver.fractional_separation_time_budget=0.005
${CMD} experiment="METHOD_D3_ROOT_GREEDY_WEIGHTED_M20" ${COMMON} solver=fractional_separation solver.method_variant=D3 solver.weights_bound=20 solver.fractional_root_only=true solver.fractional_greedy_starts=10 solver.fractional_violation_tolerance=1e-4 solver.fractional_separation_time_budget=0.005
${CMD} experiment="METHOD_D4_SELECTIVE_NONROOT_M20" ${COMMON} solver=fractional_separation solver.method_variant=D4 solver.weights_bound=20 solver.fractional_root_only=false solver.nonroot_separation_frequency=100 solver.nonroot_max_cuts_per_callback=1 solver.fractional_violation_tolerance=1e-4 solver.fractional_separation_time_budget=0.005 solver.fractional_max_zero_rounds=3
${CMD} experiment="METHOD_D5_HISTORY_GUIDED_SELECTIVE_M20" ${COMMON} solver=fractional_separation solver.method_variant=D5 solver.weights_bound=20 solver.fractional_root_only=false solver.dense_history_min_hits=2 solver.nonroot_separation_frequency=50 solver.nonroot_max_cuts_per_callback=1 solver.fractional_violation_tolerance=1e-4 solver.fractional_separation_time_budget=0.005 solver.fractional_max_zero_rounds=3

# E：围绕此前表现最好的 M=20 增加 M=15/25，并保留 edge-specific Mij。
${CMD} experiment="METHOD_E6_BIG_M_15" ${COMMON} solver=bigm_relaxation solver.method_variant=E6
${CMD} experiment="METHOD_E2_BIG_M_20" ${COMMON} solver=bigm_relaxation solver.method_variant=E2
${CMD} experiment="METHOD_E7_BIG_M_25" ${COMMON} solver=bigm_relaxation solver.method_variant=E7
${CMD} experiment="METHOD_E5_EDGE_SPECIFIC_MIJ" ${COMMON} solver=bigm_relaxation solver.method_variant=E5 solver.big_m_mode=edge_specific solver.weights_bound=100 solver.edge_specific_safety_factor=1.01

# F：只保留已修正且此前表现最好的 deterministic first (k+1) cut。
${CMD} experiment="METHOD_F2_FIRST_K_PLUS_1" ${COMMON} solver=stronger_clique_cuts solver.method_variant=F2 solver.max_clique_cuts_per_callback=1 solver.deduplicate_clique_cuts=true

# G：单次连续求解并保存完整 checkpoints。
${CMD} experiment="METHOD_G_CONTINUOUS_CHECKPOINTS" problem="${data}" problem.p="${lag_num}" ++problem.intra_edge_ratio="${edge_ratio}" ++problem.inter_edge_ratio="${edge_ratio}" problem.number_of_variables="${vars}" problem.number_of_samples="${samples}" problem.seed="${seed}" solver=time_limit_optimization solver.method_variant=G ++solver.max_clique_size="${max_clique_sizes}" solver.time_limit=7200 solver.checkpoint_times="[5,15,30,60,120,300,600,1000,1200,1800,2700,3600,5400,7200]" solver.experiment_diagnostics=true

done

echo "[ALL DONE] Selected and revised A--G experiments completed."
