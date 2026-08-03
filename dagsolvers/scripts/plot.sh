#!/bin/sh
set -eu

cd /Users/xiaoyuhe/project-bestdagsolverintheworld/dagsolvers

# # timelimit half comparison
# EXDBN_TABLE_BASE_DIR="/Users/xiaoyuhe/Causal-Methods/bestdagsolverintheworld-main/src/exdbn/results/exdbn/exdbn_run" \
# EXDBN_SCENARIO_KEYS="all" \
# EXDBN_PLOT_OUTPUT_DIR="/Users/xiaoyuhe/project-bestdagsolverintheworld/dagsolvers/reports" \
# EXDBN_PLOT_OUTPUT_PREFIX="methods_STL" \
# EXDBN_LEGEND_SHOW_TIMELIMIT=1 \
# EXDBN_GENERATE_SUMMARY_TABLES=1 \
# python3 plot_utils_seperate.py

# runningtime/shd/f1 vs nodes 
EXDBN_SCENARIO_KEYS="cliquefree-er-4-0,cliquefree-er-5-0,cliquefree-sf-5-0" \
EXDBN_X_AXIS="nodes" \
EXDBN_SUMMARY_MODES="static" \
EXDBN_TIMELIMITS="1800" \
EXDBN_Y_AXIS="gap/lazy_count/runtime_seconds/f1score/shd" \
EXDBN_GENERATE_SUMMARY_TABLES=1 \
python3 plot_utils_seperate.py

# # benchmarkprofiles vs problems 
# EXDBN_TABLE_BASE_DIR="/Users/xiaoyuhe/project-bestdagsolverintheworld/dagsolvers/results" \
# EXDBN_SCENARIO_KEYS="cliquefree-er-5-0,cliquefree-sf-4-0,cliquefree-er-2-1" \
# EXDBN_PLOT_OUTPUT_DIR="/Users/xiaoyuhe/project-bestdagsolverintheworld/dagsolvers/reports" \
# EXDBN_PLOT_OUTPUT_PREFIX="benchmarkprofiles" \
# EXDBN_GENERATE_SUMMARY_TABLES=1 \
# python3 plot_benchmarkprofiles.py

# # runtime simulation vs nodes
# EXDBN_TABLE_BASE_DIR="/Users/xiaoyuhe/project-bestdagsolverintheworld/dagsolvers/results/cliquefree-er-5-0/" \
# EXDBN_PLOT_OUTPUT_DIR="/Users/xiaoyuhe/project-bestdagsolverintheworld/dagsolvers/reports" \
# EXDBN_PLOT_OUTPUT_PREFIX="runtime_without_timelimit" \
# EXDBN_GENERATE_SUMMARY_TABLES=1 \
# python3 plot_runtime_nodes.py

# gap/lazy_count/F1/SHD vs timelimit
EXDBN_SCENARIO_KEYS="cliquefree-er-5-0" \
EXDBN_X_AXIS="timelimit" \
EXDBN_SUMMARY_MODES="static" \
EXDBN_FEATURES="20,25,30" \
EXDBN_Y_AXIS="gap/lazy_count/f1score/shd" \
EXDBN_ROW_TITLE="cliquefree-er-5-0" \
EXDBN_GENERATE_SUMMARY_TABLES=1 \
python3 plot_utils_seperate.py
