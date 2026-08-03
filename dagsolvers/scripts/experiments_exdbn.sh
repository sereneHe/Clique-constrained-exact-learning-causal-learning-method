#!/bin/sh

export PYTHONPATH="${PYTHONPATH}:../"
export KMP_DUPLICATE_LIB_OK=TRUE

CMD="python3 run_experiments.py --multirun --config-name=config-cluster"

samples="200"
num_seeds="10"
edge_ratios="5"
lag_num="0"
vars="15,20,25,30,35"
max_clique_sizes="5"
time_limits="1800"
# max_clique_sizes="3,5,7,9"
# time_limits="30,60,120,180,300,600,1200,1800"

${CMD} experiment="EXDBN2_CLIQUE" solver="milp,milp_cliquewidth,edge_limit" problem="cliquefree-er" problem.normalize="false" problem.p="${lag_num}"  ++problem.intra_edge_ratio="${edge_ratios}" ++problem.inter_edge_ratio="${edge_ratios}" ++problem.w_min_inter="0.2" ++problem.w_max_inter="0.4" ++problem.w_min_intra="0.5" ++problem.w_max_intra="2" ++problem.w_decay="1.1" problem.number_of_variables="${vars}" problem.number_of_samples="${samples}" problem.seed="range(1,${num_seeds})" ++solver.max_clique_size="${max_clique_sizes}" solver.time_limit="${time_limits}"

# edge_ratios="2"
# lag_num="1"
# vars="10,15,20,25,30,35"
# ${CMD} experiment="EXDBN2_CLIQUE" solver="edge_limit" problem="${data}" problem.normalize="false" problem.p="${lag_num}"  ++problem.intra_edge_ratio="${edge_ratios}" ++problem.inter_edge_ratio="${edge_ratios}" ++problem.w_min_inter="0.2" ++problem.w_max_inter="0.4" ++problem.w_min_intra="0.5" ++problem.w_max_intra="2" ++problem.w_decay="1.1" problem.number_of_variables="${vars}" problem.number_of_samples="${samples}" problem.seed="range(1,${num_seeds})" ++solver.max_clique_size="${max_clique_sizes}"
