CMD="python3 run_experiments.py --multirun --config-name=config-cluster"

${CMD} experiment="CLIQUE_WIDTH2" solver="milp_clique" problem="cliquefree-er" problem.p="0" problem.intra_edge_ratio="5" problem.inter_edge_ratio="5" problem.number_of_variables="20" problem.number_of_samples="200,2000" problem.seed="range(0,10)" ++solver.max_clique_size="3,4" solver.time_limit="60, 120, 300, 600, 1200, 1800, 2700, 3600, 5400, 7200"

${CMD} experiment="CLIQUE_WIDTH2" solver="milp" problem="cliquefree-er" problem.p="0" problem.intra_edge_ratio="5" problem.inter_edge_ratio="5" problem.number_of_variables="20" problem.number_of_samples="200,2000" problem.seed="range(0,10)" solver.time_limit="60,120,300,600,1200,1800,2700,3600,5400,7200"
