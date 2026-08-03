export PYTHONPATH=$PYTHONPATH:../
export  KMP_DUPLICATE_LIB_OK=TRUE

CMD="python3 run_experiments.py --multirun --config-name=config-cluster"

max_clique_sizes="5"
lag_num="0"
data="cliquefree-er,cliquefree-sf"
time_limits="1800,7200"
solvers="milp_clique"
edge_ratios="5"
edge_ratios="4"
samples="2000"
vars="20,25" 
seed="range(1,5)"
# ${CMD} experiment="CLIQUEWIDTH-original_control" solver=milp_cliquewidth solver.weights_bound=100
# ${CMD} experiment="CLIQUE" solver="milp_clique" solver.weights_bound=100 solver.experiment_diagnostics=false solver.print_clique_cuts=true solver.clique_cut_formulation=original solver.clique_cut_selection=original solver.enable_delayed_separation=false solver.enable_incumbent_repair=false solver.enable_fractional_separation=false solver.big_m_mode=scalar solver.enable_checkpoints=false problem="${data}" problem.p="${lag_num}" ++problem.intra_edge_ratio="${edge_ratios}" '++problem.inter_edge_ratio=${problem.intra_edge_ratio}' problem.number_of_variables="${vars}" problem.number_of_samples="${samples}" problem.seed="${seed}" ++solver.max_clique_size="${max_clique_sizes}" solver.time_limit="${time_limits}" +solver.gurobi_threads=2
${CMD} experiment="B1-first_min_k+1-F2-first_k+1_cut" solver="milp_clique" solver.weights_bound=100 solver.experiment_diagnostics=false solver.clique_cut_formulation=k_plus_1 solver.clique_cut_selection=first solver.max_clique_cuts_per_callback=1 solver.deduplicate_clique_cuts=false problem="${data}" problem.p="${lag_num}" ++problem.intra_edge_ratio="${edge_ratios}" '++problem.inter_edge_ratio=${problem.intra_edge_ratio}' problem.number_of_variables="${vars}" problem.number_of_samples="${samples}" problem.seed="${seed}" ++solver.max_clique_size="${max_clique_sizes}" solver.time_limit="${time_limits}" +solver.gurobi_threads=2
${CMD} experiment="B3-most_violated_k+1" solver="milp_clique" solver.weights_bound=100 solver.experiment_diagnostics=false solver.clique_cut_formulation=k_plus_1 solver.clique_cut_selection=most_violated solver.max_clique_cuts_per_callback=1 solver.deduplicate_clique_cuts=false problem="${data}" problem.p="${lag_num}" ++problem.intra_edge_ratio="${edge_ratios}" '++problem.inter_edge_ratio=${problem.intra_edge_ratio}' problem.number_of_variables="${vars}" problem.number_of_samples="${samples}" problem.seed="${seed}" ++solver.max_clique_size="${max_clique_sizes}" solver.time_limit="${time_limits}" +solver.gurobi_threads=2
${CMD} experiment="C3-local_LS_QR_repair" solver="milp_clique" solver.weights_bound=100 solver.experiment_diagnostics=false solver.enable_incumbent_repair=true solver.repair_variant=C3 solver.repair_refit_solver=qr problem="${data}" problem.p="${lag_num}" ++problem.intra_edge_ratio="${edge_ratios}" '++problem.inter_edge_ratio=${problem.intra_edge_ratio}' problem.number_of_variables="${vars}" problem.number_of_samples="${samples}" problem.seed="${seed}" ++solver.max_clique_size="${max_clique_sizes}" solver.time_limit="${time_limits}" +solver.gurobi_threads=2
${CMD} experiment="E2-big_M_20" solver="milp_clique" solver.experiment_diagnostics=false solver.big_m_mode=scalar solver.weights_bound=20 problem="${data}" problem.p="${lag_num}" ++problem.intra_edge_ratio="${edge_ratios}" '++problem.inter_edge_ratio=${problem.intra_edge_ratio}' problem.number_of_variables="${vars}" problem.number_of_samples="${samples}" problem.seed="${seed}" ++solver.max_clique_size="${max_clique_sizes}" solver.time_limit="${time_limits}" +solver.gurobi_threads=2

${CMD} experiment="CLIQUE1" solver="milp_cliquewidth,milp" problem="${data}" problem.p="${lag_num}" problem.intra_edge_ratio="${edge_ratios}" problem.inter_edge_ratio="${edge_ratios}" problem.number_of_variables="${vars}" problem.number_of_samples="${samples}" problem.seed="${seed}" ++solver.max_clique_size="${max_clique_sizes}" solver.time_limit="${time_limits}"
