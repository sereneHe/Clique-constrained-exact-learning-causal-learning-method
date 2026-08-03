#!/bin/sh

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
DAGSOLVERS_DIR=$(CDPATH= cd -- "${SCRIPT_DIR}/.." && pwd)
RESULTS_DIR="${DAGSOLVERS_DIR}/results"

# 两个输入 table 的位置；需要比较其他结果时只修改这里。
export CHECKPOINT_TABLE="${CHECKPOINT_TABLE:-${RESULTS_DIR}/第二次A-G实验记录/第二次A-G实验记录.csv}"
export TIMELIMIT_TABLE_GLOB="${TIMELIMIT_TABLE_GLOB:-${RESULTS_DIR}/cliquefree-er-5-0/static_n2000/clique_runtime_static_cliquefree-er-5-0_gauss_d20_n2000_*s_5clique.csv}"

# average（默认）：checkpoint 与独立 TimeLimit 分别跨各自 seeds 取平均值。
# by_seed：只比较两边都存在的相同 seed，忽略不匹配的 seed。
export COMPARE_MODE="${COMPARE_MODE:-by_seed}"

# 输出位置也可以在运行前通过环境变量覆盖。
export OUTPUT_TABLE="${OUTPUT_TABLE:-${RESULTS_DIR}/第二次A-G实验记录/G_continuous_checkpoints_vs_independent_timelimits.csv}"

python3 "${SCRIPT_DIR}/compare_checkpoint_timelimit.py"
