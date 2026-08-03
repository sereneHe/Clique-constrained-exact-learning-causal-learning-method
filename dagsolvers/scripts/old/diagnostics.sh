#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
DAGSOLVERS_DIR=$(CDPATH= cd -- "${SCRIPT_DIR}/.." && pwd)
PROJECT_DIR=$(CDPATH= cd -- "${DAGSOLVERS_DIR}/.." && pwd)
cd "${DAGSOLVERS_DIR}"
export PYTHONPATH="${PROJECT_DIR}:${DAGSOLVERS_DIR}:${PYTHONPATH:-}"
export KMP_DUPLICATE_LIB_OK=TRUE

CMD="python3 ./run_experiments.py --multirun --config-name=config"
problem=${PROBLEM:-cliquefree-er}
lags=${LAGS:-0}
ratio=${EDGE_RATIO:-5}
variables=${VARIABLES:-20}
samples=${SAMPLES:-2000}
seeds=${SEEDS:-range(1,6)}
clique_size=${MAX_CLIQUE_SIZE:-5}
time_limit=${TIME_LIMIT:-7200}
common="problem=${problem} problem.p=${lags} ++problem.intra_edge_ratio=${ratio} ++problem.inter_edge_ratio=${ratio} problem.number_of_variables=${variables} problem.number_of_samples=${samples} problem.seed=${seeds} solver=milp_clique solver.max_clique_size=${clique_size} solver.time_limit=${time_limit} solver.experiment_diagnostics=true"
controlled_common="problem=${problem} problem.p=${lags} ++problem.intra_edge_ratio=${ratio} ++problem.inter_edge_ratio=${ratio} problem.number_of_variables=${variables} problem.number_of_samples=${samples} problem.seed=${seeds} solver=controlled_cut_addition solver.max_clique_size=${clique_size} solver.time_limit=${time_limit} solver.experiment_diagnostics=true solver.enable_fractional_clique_cuts=false"

# 实验1：基线；每次 MIPSOL 提交检测到的全部 cycle cuts 和全部 clique cuts，不限制每个 callback 的 cuts 数量。
${CMD} experiment="CLIQUE_ALL_CUTS" ${common} solver.callback_mode=all_cycles solver.clique_callback_mode=all_cliques solver.max_cycle_cuts_per_callback=0 solver.max_clique_cuts_per_callback=0

# 实验2：最小批量；每次 MIPSOL 只提交第一条 cycle cut 和第一条 clique cut。
${CMD} experiment="CLIQUE_FIRST_CUT" ${common} solver.callback_mode=first_cycle solver.clique_callback_mode=first_clique

# 实验3：结构优先；每次 MIPSOL 提交最短 cycle cut 和规模最大的 violated clique cut。
${CMD} experiment="CLIQUE_SHORTEST_LARGEST" ${common} solver.callback_mode=shortest_cycle solver.clique_callback_mode=largest_clique

# 实验4：Top-K；比较每次 callback 最多选择1、3、5、10条候选 cuts，未选择的 valid cuts 后续再次违反时仍可提交。
${CMD} experiment="CLIQUE_TOP_1" ${common} solver.callback_mode=top_k_cycles solver.clique_callback_mode=top_k_cliques solver.cycle_top_k=1 solver.clique_top_k=1
${CMD} experiment="CLIQUE_TOP_3" ${common} solver.callback_mode=top_k_cycles solver.clique_callback_mode=top_k_cliques solver.cycle_top_k=3 solver.clique_top_k=3
${CMD} experiment="CLIQUE_TOP_5" ${common} solver.callback_mode=top_k_cycles solver.clique_callback_mode=top_k_cliques solver.cycle_top_k=5 solver.clique_top_k=5
${CMD} experiment="CLIQUE_TOP_10" ${common} solver.callback_mode=top_k_cycles solver.clique_callback_mode=top_k_cliques solver.cycle_top_k=10 solver.clique_top_k=10

# 实验5：完全去重；检测全部 cuts，但已实际提交过的 canonical cycle/clique constraint 不再重复提交。
${CMD} experiment="CLIQUE_ALL_DEDUP" ${common} solver.callback_mode=all_cycles solver.clique_callback_mode=all_cliques solver.deduplicate_cycle_cuts=true solver.deduplicate_clique_cuts=true

# 实验6：只添加 cycle constraints；对应 ExDBN 的约束消融基线，不检查 clique-number 限制。
${CMD} experiment="CLIQUE_ONLY_CYCLE" ${common} solver.enable_cycle_constraints=true solver.enable_clique_constraints=false

# 实验7：只添加 clique constraints；仅用于 callback/constraint 成本消融，最终解可能有环，不能视为合法 DAG 结果。
${CMD} experiment="CLIQUE_ONLY_CLIQUE_ABLATION" ${common} solver.enable_cycle_constraints=false solver.enable_clique_constraints=true

# 实验8：先检查 clique；若当前候选违反 clique，则本轮直接拒绝并延迟 cycle separation。
${CMD} experiment="CLIQUE_CLIQUE_FIRST" ${common} solver.enable_cycle_constraints=true solver.enable_clique_constraints=true solver.separation_order=clique_first solver.delayed_second_separation=true

# 实验9：先检查 cycle；若当前候选违反 cycle，则本轮直接拒绝并延迟 clique separation。
${CMD} experiment="CLIQUE_CYCLE_FIRST" ${common} solver.enable_cycle_constraints=true solver.enable_clique_constraints=true solver.separation_order=cycle_first solver.delayed_second_separation=true

# 实验10：同时检查；同一个 MIPSOL 中无论 cycle 是否违反，都继续执行 clique separation。
${CMD} experiment="CLIQUE_SIMULTANEOUS" ${common} solver.enable_cycle_constraints=true solver.enable_clique_constraints=true solver.separation_order=cycle_first solver.delayed_second_separation=false

# 实验11：Big-M 对比；其他参数固定，只比较 M=20、50、100。
${CMD} experiment="CLIQUE_BIG_M" ${common} solver.weights_bound=20,50,100

# 实验12：一次大量与少量多次；比较每个 callback 最多提交1、3、5、10条 cycle/clique cuts。
${CMD} experiment="CLIQUE_BATCH_1" ${common} solver.callback_mode=all_cycles solver.clique_callback_mode=all_cliques solver.max_cycle_cuts_per_callback=1 solver.max_clique_cuts_per_callback=1
${CMD} experiment="CLIQUE_BATCH_3" ${common} solver.callback_mode=all_cycles solver.clique_callback_mode=all_cliques solver.max_cycle_cuts_per_callback=3 solver.max_clique_cuts_per_callback=3
${CMD} experiment="CLIQUE_BATCH_5" ${common} solver.callback_mode=all_cycles solver.clique_callback_mode=all_cliques solver.max_cycle_cuts_per_callback=5 solver.max_clique_cuts_per_callback=5
${CMD} experiment="CLIQUE_BATCH_10" ${common} solver.callback_mode=all_cycles solver.clique_callback_mode=all_cliques solver.max_cycle_cuts_per_callback=10 solver.max_clique_cuts_per_callback=10

# 实验13：选择性 cuts；优先 Top-5，并跳过所有已经提交过的完全重复 constraints。
${CMD} experiment="CLIQUE_PRIORITY_TOP_K_DEDUP" ${common} solver.callback_mode=top_k_cycles solver.clique_callback_mode=top_k_cliques solver.cycle_top_k=5 solver.clique_top_k=5 solver.deduplicate_cycle_cuts=true solver.deduplicate_clique_cuts=true

# 实验14：root 阶段积极强化；只在 root relaxation 添加 violated fractional clique user cuts，每轮最多20条。
${CMD} experiment="CLIQUE_ROOT_AGGRESSIVE" ${common} solver.enable_fractional_clique_cuts=true solver.fractional_root_only=true solver.root_max_cuts_per_round=20

# 实验15：root 积极、后续节点低频；root 每轮最多20条，非root每10个节点检查一次且最多5条。
${CMD} experiment="CLIQUE_ROOT_AND_SPARSE_NONROOT" ${common} solver.enable_fractional_clique_cuts=true solver.fractional_root_only=false solver.root_max_cuts_per_round=20 solver.nonroot_max_cuts_per_callback=5 solver.nonroot_separation_frequency=10

# PPT B1：Controlled Cut Addition；只加入第一条 minimal (k+1) clique lazy cut。
${CMD} experiment="METHOD_B1_FIRST_MINIMAL_K_PLUS_1" ${controlled_common} solver.method_variant=B1 solver.max_clique_cuts_per_callback=1 solver.deduplicate_clique_cuts=false

# PPT B2：加入本次 MIPSOL 检测到的全部 unique (k+1) candidates，不设置 callback cut 上限。
${CMD} experiment="METHOD_B2_ALL_K_PLUS_1" ${controlled_common} solver.method_variant=B2 solver.max_clique_cuts_per_callback=0 solver.deduplicate_clique_cuts=false

# PPT B3：选择 violation 最大的一条 (k+1) cut；整数 MIPSOL 上常出现并列，代码使用确定性 tie-break。
${CMD} experiment="METHOD_B3_MOST_VIOLATED" ${controlled_common} solver.method_variant=B3 solver.max_clique_cuts_per_callback=1 solver.deduplicate_clique_cuts=false

# PPT B4：按 violation 排序，每个 callback 最多加入 Top-5 (k+1) cuts，不做历史去重。
${CMD} experiment="METHOD_B4_TOP_5" ${controlled_common} solver.method_variant=B4 solver.clique_top_k=5 solver.max_clique_cuts_per_callback=5 solver.deduplicate_clique_cuts=false

# PPT B5：Top-5 + 全局 canonical 去重 + 每个 callback 最多5条，用于测量重复提交成本。
${CMD} experiment="METHOD_B5_TOP_5_DEDUP_CAP_5" ${controlled_common} solver.method_variant=B5 solver.clique_top_k=5 solver.max_clique_cuts_per_callback=5 solver.deduplicate_clique_cuts=true
