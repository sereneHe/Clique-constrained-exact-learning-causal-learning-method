set -eu

cd /Users/xiaoyuhe/project-bestdagsolverintheworld/dagsolvers

EXDBN_SCENARIO_KEYS="cliquefree-er-4-0,cliquefree-er-5-0,cliquefree-sf-5-0" \
EXDBN_METHOD_KEYS="clique,clique_B3,clique_C3" \
EXDBN_BASELINE_METHOD_KEYS="milp" \
EXDBN_X_AXIS="nodes" \
EXDBN_SUMMARY_MODES="static" \
EXDBN_TIMELIMITS="1800" \
EXDBN_Y_AXIS="gap/lazy_count/runtime_seconds/f1score/shd" \
EXDBN_GENERATE_SUMMARY_TABLES=1 \
python3 plot_exdbn_baseline.py