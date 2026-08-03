#!/bin/sh

export PYTHONPATH="${PYTHONPATH}:../"
export KMP_DUPLICATE_LIB_OK=TRUE

CMD="python3 run_experiments.py --multirun --config-name=config-cluster"

${CMD} experiment="CLIQUE1" solver="milp_clique,milp" problem="cliquefree-er" problem.p="0" ++problem.intra_edge_ratio="5" ++problem.inter_edge_ratio="5" problem.number_of_variables="11,15,20,25,30,35,40" problem.number_of_samples="200,2000" problem.seed="range(1,11)" ++solver.max_clique_size="5" solver.time_limit="1800"

${CMD} experiment="CLIQUE2-4-0" solver="milp_clique,milp" problem="cliquefree-er" problem.p="0" ++problem.intra_edge_ratio="4" ++problem.inter_edge_ratio="4" problem.number_of_variables="9,10,15,20,25,30,35,40" problem.number_of_samples="200,2000" problem.seed="range(1,11)" ++solver.max_clique_size="5" solver.time_limit="1800"

${CMD} experiment="CLIQUE3-3-0" solver="milp_clique,milp" problem="cliquefree-er" problem.p="0" ++problem.intra_edge_ratio="3" ++problem.inter_edge_ratio="3" problem.number_of_variables="7,10,15,20,25,30,35,40" problem.number_of_samples="200,2000" problem.seed="range(1,11)" ++solver.max_clique_size="5" solver.time_limit="1800"

${CMD} experiment="CLIQUE4-sf" solver="milp_clique,milp" problem="cliquefree-sf" problem.p="0" ++problem.intra_edge_ratio="4" ++problem.inter_edge_ratio="4" problem.number_of_variables="9,10,15,20,25,30,35,40" problem.number_of_samples="200,2000" problem.seed="range(1,11)" ++solver.max_clique_size="5" solver.time_limit="1800"

${CMD} experiment="CLIQUE5-sf" solver="milp_clique,milp" problem="cliquefree-sf" problem.p="0" ++problem.intra_edge_ratio="5" ++problem.inter_edge_ratio="5" problem.number_of_variables="11,15,20,25,30,35,40" problem.number_of_samples="200,2000" problem.seed="range(1,11)" ++solver.max_clique_size="5" solver.time_limit="1800"

${CMD} experiment="CLIQUE6-2-1" solver="milp_clique,milp" problem="cliquefree-er" problem.p="1" ++problem.intra_edge_ratio="2" ++problem.inter_edge_ratio="2" problem.number_of_variables="10,15,20,25,30,35,40" problem.number_of_samples="200,2000" problem.seed="range(1,11)" ++solver.max_clique_size="5" solver.time_limit="1800"

${CMD} experiment="CLIQUE7-timelimit" solver="milp_clique,milp" problem="cliquefree-er" problem.p="0" ++problem.intra_edge_ratio="5" ++problem.inter_edge_ratio="5" problem.number_of_variables="15" problem.number_of_samples="200" problem.seed="range(1,11)" ++solver.max_clique_size="5" solver.time_limit="20,80,320,1280,5120,20480,81920"

${CMD} experiment="CLIQUE8-cliquesizelimit" solver="milp_clique" problem="cliquefree-er" problem.p="0" ++problem.intra_edge_ratio="5" ++problem.inter_edge_ratio="5" problem.number_of_variables="15" problem.number_of_samples="200" problem.seed="range(1,11)" solver.max_clique_size="3,7,9" solver.time_limit="1800"
# solver="edge_limit" problem.seed="range(1,41)"
