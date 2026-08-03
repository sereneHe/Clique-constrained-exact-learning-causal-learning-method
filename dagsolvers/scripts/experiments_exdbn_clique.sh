export PYTHONPATH=$PYTHONPATH:../
export  KMP_DUPLICATE_LIB_OK=TRUE

CMD="python3 run_experiments.py --multirun --config-name=config-cluster"

${CMD} experiment="C3-local_LS_QR_repair" solver="milp_clique" solver.weights_bound=100 solver.experiment_diagnostics=false solver.enable_incumbent_repair=true solver.repair_variant=C3 solver.repair_refit_solver=qr problem="${data}" problem.p="${lag_num}" ++problem.intra_edge_ratio="${edge_ratios}" '++problem.inter_edge_ratio=${problem.intra_edge_ratio}' problem.number_of_variables="${vars}" problem.number_of_samples="${samples}" problem.seed="${seed}" ++solver.max_clique_size="${max_clique_sizes}" solver.time_limit="${time_limits}" +solver.gurobi_threads=2 

${CMD} experiment="CLIQUE1" solver="milp_clique,milp,clique-B3,clique-C3" problem="cliquefree-er,cliquefree-sf" problem.p="0" problem.intra_edge_ratio="5" problem.inter_edge_ratio="5" problem.number_of_variables="11,15,20,25,30,35,40,45,50" problem.number_of_samples="200,2000" problem.seed="range(1,5)" ++solver.max_clique_size="5" solver.time_limit="1800"

${CMD} experiment="CLIQUE2" solver="milp_clique" problem="cliquefree-er" problem.p="0" problem.intra_edge_ratio="5" problem.inter_edge_ratio="5" problem.number_of_variables="20" problem.number_of_samples="200,2000" problem.seed="range(0,10)" ++solver.max_clique_size="3,4" solver.time_limit="60, 120, 300, 600, 1200, 1800, 2700, 3600, 5400, 7200"

${CMD} experiment="CLIQUE2" solver="milp" problem="cliquefree-er" problem.p="0" problem.intra_edge_ratio="5" problem.inter_edge_ratio="5" problem.number_of_variables="20" problem.number_of_samples="200,2000" problem.seed="range(0,10)" solver.time_limit="60,120,300,600,1200,1800,2700,3600,5400,7200"
