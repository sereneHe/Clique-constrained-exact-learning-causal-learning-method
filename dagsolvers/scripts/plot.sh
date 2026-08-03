#!/bin/sh
set -eu

cd /Users/xiaoyuhe/project-bestdagsolverintheworld/dagsolvers

EXDBN_Y_AXIS="gap/lazy_count/runtime_seconds/f1score/shd"
EXDBN_METHOD_KEYS="milp,clique,clique_B1-F2,clique_B3,clique_C3,clique_E2"
# runningtime/shd/f1 vs nodes
EXDBN_SCENARIO_KEYS="cliquefree-er-4-0,cliquefree-er-5-0,cliquefree-sf-5-0" \
EXDBN_METHOD_KEYS="milp,clique,clique_B3,clique_C3" \
EXDBN_X_AXIS="nodes" \
EXDBN_SUMMARY_MODES="static" \
EXDBN_TIMELIMITS="1800" \
EXDBN_Y_AXIS="gap/lazy_count/runtime_seconds/f1score/shd" \
EXDBN_ROW_LABEL_SIDE="left" \
EXDBN_PLOT_FORMATS="png,pdf" \
EXDBN_PLOT_DPI=300 \
EXDBN_GENERATE_SUMMARY_TABLES=1 \
python3 plot_utils_seperate.py

EXDBN_SCENARIO_KEYS="cliquefree-er-4-0" \
EXDBN_METHOD_KEYS="milp,clique, clique_E2" \
EXDBN_X_AXIS="nodes" \
EXDBN_SUMMARY_MODES="static" \
EXDBN_TIMELIMITS="1800" \
EXDBN_Y_AXIS="shd" \
EXDBN_ROW_LABEL_SIDE="left" \
EXDBN_PLOT_FORMATS="png,pdf" \
EXDBN_PLOT_DPI=300 \
EXDBN_GENERATE_SUMMARY_TABLES=1 \
EXDBN_PLOT_OUTPUT_PREFIX="clique_E2" \
python3 plot_utils_seperate.py

# benchmarkprofiles vs problems 
EXDBN_TABLE_BASE_DIR="/Users/xiaoyuhe/project-bestdagsolverintheworld/dagsolvers/results" \
EXDBN_SCENARIO_KEYS="cliquefree-er-5-0,cliquefree-sf-5-0,cliquefree-er-4-0" \
EXDBN_METHOD_KEYS="milp,clique,clique_B3" \
EXDBN_Y_AXIS="gap/lazy_count/runtime_seconds/f1score/shd" \
EXDBN_PLOT_OUTPUT_DIR="/Users/xiaoyuhe/project-bestdagsolverintheworld/dagsolvers/reports" \
EXDBN_PLOT_OUTPUT_PREFIX="benchmarkprofiles_clique_B3" \
EXDBN_GENERATE_SUMMARY_TABLES=1 \
python3 plot_benchmarkprofiles.py

EXDBN_TABLE_BASE_DIR="/Users/xiaoyuhe/project-bestdagsolverintheworld/dagsolvers/results" \
EXDBN_SCENARIO_KEYS="cliquefree-er-5-0,cliquefree-sf-5-0,cliquefree-er-4-0" \
EXDBN_METHOD_KEYS="milp,clique,clique_C3" \
EXDBN_Y_AXIS="runtime_seconds" \
EXDBN_PLOT_OUTPUT_DIR="/Users/xiaoyuhe/project-bestdagsolverintheworld/dagsolvers/reports" \
EXDBN_PLOT_OUTPUT_PREFIX="benchmarkprofiles_clique_C3" \
EXDBN_GENERATE_SUMMARY_TABLES=1 \
python3 plot_benchmarkprofiles.py

# gap/lazy_count/F1/SHD vs timelimit
EXDBN_SCENARIO_KEYS="cliquefree-er-5-0" \
EXDBN_X_AXIS="timelimit" \
EXDBN_SUMMARY_MODES="static" \
EXDBN_FEATURES="20,25,30" \
EXDBN_Y_AXIS="gap/lazy_count/f1score/shd" \
EXDBN_ROW_TITLE="" \
EXDBN_ROW_LABEL_SIDE="right" \
EXDBN_PLOT_FORMATS="png,pdf" \
EXDBN_PLOT_DPI=300 \
EXDBN_GENERATE_SUMMARY_TABLES=1 \
python3 plot_utils_seperate.py

# # exdbn baseline comparison
# EXDBN_SCENARIO_KEYS="cliquefree-er-4-0,cliquefree-er-5-0,cliquefree-sf-5-0" \
# EXDBN_METHOD_KEYS="clique,clique_B3,clique_C3" \
# EXDBN_BASELINE_METHOD_KEYS="milp" \
# EXDBN_X_AXIS="nodes" \
# EXDBN_SUMMARY_MODES="static" \
# EXDBN_TIMELIMITS="1800" \
# EXDBN_Y_AXIS="f1score/shd" \
# EXDBN_GENERATE_SUMMARY_TABLES=1 \
# python3 plot_exdbn_baseline.py

# # runtime simulation vs nodes
# EXDBN_TABLE_BASE_DIR="/Users/xiaoyuhe/project-bestdagsolverintheworld/dagsolvers/results/cliquefree-er-5-0/" \
# EXDBN_PLOT_OUTPUT_DIR="/Users/xiaoyuhe/project-bestdagsolverintheworld/dagsolvers/reports" \
# EXDBN_PLOT_OUTPUT_PREFIX="runtime_without_timelimit" \
# EXDBN_GENERATE_SUMMARY_TABLES=1 \
# python3 plot_runtime_nodes.py

# # timelimit half comparison
# EXDBN_TABLE_BASE_DIR="/Users/xiaoyuhe/Causal-Methods/bestdagsolverintheworld-main/src/exdbn/results/exdbn/exdbn_run" \
# EXDBN_SCENARIO_KEYS="all" \
# EXDBN_PLOT_OUTPUT_DIR="/Users/xiaoyuhe/project-bestdagsolverintheworld/dagsolvers/reports" \
# EXDBN_PLOT_OUTPUT_PREFIX="methods_STL" \
# EXDBN_LEGEND_SHOW_TIMELIMIT=1 \
# EXDBN_GENERATE_SUMMARY_TABLES=1 \
# python3 plot_utils_seperate.py
