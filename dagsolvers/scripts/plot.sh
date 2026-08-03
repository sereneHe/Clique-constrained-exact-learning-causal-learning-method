#!/bin/sh
set -eu

cd /Users/xiaoyuhe/project-bestdagsolverintheworld/dagsolvers

# timelimit half comparison
EXDBN_TABLE_BASE_DIR="/Users/xiaoyuhe/Causal-Methods/bestdagsolverintheworld-main/src/exdbn/results/exdbn/exdbn_run" \
EXDBN_SCENARIO_KEYS="all" \
EXDBN_PLOT_OUTPUT_DIR="/Users/xiaoyuhe/project-bestdagsolverintheworld/dagsolvers/reports" \
EXDBN_PLOT_OUTPUT_PREFIX="methods_STL" \
EXDBN_LEGEND_SHOW_TIMELIMIT=1 \
EXDBN_GENERATE_SUMMARY_TABLES=1 \
python3 plot_utils_seperate.py

# runningtime/shd/f1 vs nodes 
EXDBN_TABLE_BASE_DIR="/Users/xiaoyuhe/project-bestdagsolverintheworld/dagsolvers/results" \
EXDBN_SCENARIO_KEYS="cliquefree-er-5-0,cliquefree-sf-4-0,cliquefree-er-2-1" \
EXDBN_PLOT_OUTPUT_DIR="/Users/xiaoyuhe/project-bestdagsolverintheworld/dagsolvers/reports" \
EXDBN_PLOT_OUTPUT_PREFIX="methods" \
EXDBN_GENERATE_SUMMARY_TABLES=1 \
python3 plot_utils_seperate.py
#EXDBN_SUMMARY_MODES=static \

# benchmarkprofiles vs problems 
EXDBN_TABLE_BASE_DIR="/Users/xiaoyuhe/project-bestdagsolverintheworld/dagsolvers/results" \
EXDBN_SCENARIO_KEYS="cliquefree-er-5-0,cliquefree-sf-4-0,cliquefree-er-2-1" \
EXDBN_PLOT_OUTPUT_DIR="/Users/xiaoyuhe/project-bestdagsolverintheworld/dagsolvers/reports" \
EXDBN_PLOT_OUTPUT_PREFIX="benchmarkprofiles" \
EXDBN_GENERATE_SUMMARY_TABLES=1 \
python3 plot_benchmarkprofiles.py

# runtime simulation vs nodes
EXDBN_TABLE_BASE_DIR="/Users/xiaoyuhe/project-bestdagsolverintheworld/dagsolvers/results/cliquefree-er-5-0/" \
EXDBN_PLOT_OUTPUT_DIR="/Users/xiaoyuhe/project-bestdagsolverintheworld/dagsolvers/reports" \
EXDBN_PLOT_OUTPUT_PREFIX="runtime_without_timelimit" \
EXDBN_GENERATE_SUMMARY_TABLES=1 \
python3 plot_runtime_nodes.py

# gap vs timelimit
EXDBN_TABLE_BASE_DIR="/Users/xiaoyuhe/project-bestdagsolverintheworld/dagsolvers/results/cliquefree-er-3-0" \
EXDBN_PLOT_OUTPUT_DIR="/Users/xiaoyuhe/project-bestdagsolverintheworld/dagsolvers/reports" \
EXDBN_PLOT_OUTPUT_PREFIX="gap_timelimit" \
EXDBN_GENERATE_SUMMARY_TABLES=1 \
python3 plot_gap_timelimit.py
# EXDBN_MILP_LOG="/Users/xiaoyuhe/project-bestdagsolverintheworld/dagsolvers/multirun/2026-05-25/14-50-21/0/run_experiments.log" \
# EXDBN_CLIQUE_LOG="/Users/xiaoyuhe/project-bestdagsolverintheworld/dagsolvers/multirun/2026-05-25/17-06-19/0/run_experiments.log" \
