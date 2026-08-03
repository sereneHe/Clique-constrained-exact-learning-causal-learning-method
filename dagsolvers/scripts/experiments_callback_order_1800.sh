export PYTHONPATH=$PYTHONPATH:../
export  KMP_DUPLICATE_LIB_OK=TRUE

CMD="python3 run_experiments.py --multirun --config-name=config-cluster"

max_clique_sizes="5"
vars="20"
samples="2000"
seed="range(1,6)"
edge_ratios="4"
lag_num="0"
data="cliquefree-er"
time_limits="1800"
solvers="milp_clique"


# ${CMD} experiment="CALLBACK_1800_CYCLE_ONLY" problem="${data}" problem.p="${lag_num}" ++problem.intra_edge_ratio="${edge_ratios}" ++problem.inter_edge_ratio="${edge_ratios}" problem.number_of_variables="${vars}" problem.number_of_samples="${samples}" problem.seed="${seed}" solver="${solvers}" ++solver.max_clique_size="${max_clique_sizes}" solver.time_limit="${time_limits}" solver.experiment_diagnostics=true ++solver.print_callback_events=true ++solver.print_retained_solutions=true solver.print_clique_cuts=true solver.enable_cycle_constraints=true solver.enable_clique_constraints=false
# ${CMD} experiment="CALLBACK_1800_CLIQUE_ONLY" problem="${data}" problem.p="${lag_num}" ++problem.intra_edge_ratio="${edge_ratios}" ++problem.inter_edge_ratio="${edge_ratios}" problem.number_of_variables="${vars}" problem.number_of_samples="${samples}" problem.seed="${seed}" solver="${solvers}" ++solver.max_clique_size="${max_clique_sizes}" solver.time_limit="${time_limits}" solver.experiment_diagnostics=true ++solver.print_callback_events=true ++solver.print_retained_solutions=true solver.print_clique_cuts=true solver.enable_cycle_constraints=false solver.enable_clique_constraints=true
${CMD} experiment="CALLBACK_1800_CYCLE_THEN_CLIQUE" problem="${data}" problem.p="${lag_num}" ++problem.intra_edge_ratio="${edge_ratios}" ++problem.inter_edge_ratio="${edge_ratios}" problem.number_of_variables="${vars}" problem.number_of_samples="${samples}" problem.seed="${seed}" solver="${solvers}" ++solver.max_clique_size="${max_clique_sizes}" solver.time_limit="${time_limits}" solver.experiment_diagnostics=true ++solver.print_callback_events=true ++solver.print_retained_solutions=true solver.print_clique_cuts=true solver.enable_cycle_constraints=true solver.enable_clique_constraints=true solver.separation_order=cycle_first solver.delayed_second_separation=false
${CMD} experiment="CALLBACK_1800_CLIQUE_THEN_CYCLE" problem="${data}" problem.p="${lag_num}" ++problem.intra_edge_ratio="${edge_ratios}" ++problem.inter_edge_ratio="${edge_ratios}" problem.number_of_variables="${vars}" problem.number_of_samples="${samples}" problem.seed="${seed}" solver="${solvers}" ++solver.max_clique_size="${max_clique_sizes}" solver.time_limit="${time_limits}" solver.experiment_diagnostics=true ++solver.print_callback_events=true ++solver.print_retained_solutions=true solver.print_clique_cuts=true solver.enable_cycle_constraints=true solver.enable_clique_constraints=true solver.separation_order=clique_first solver.delayed_second_separation=false
