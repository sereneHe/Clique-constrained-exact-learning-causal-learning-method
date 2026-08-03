#!/bin/sh

export PYTHONPATH="${PYTHONPATH}:../"
export KMP_DUPLICATE_LIB_OK=TRUE

CMD="python3 ./run_experiments.py --multirun --config-name=config"

max_clique_sizes="5"
seed="4"
edge_ratios="5"
lag_num="0"
data="cliquefree-er"

# d=20/25/30, n=200, T=7200: Baseline and Clique.
${CMD} experiment="CLIQUE" problem="${data}" problem.p="${lag_num}" ++problem.intra_edge_ratio="${edge_ratios}" ++problem.inter_edge_ratio="${edge_ratios}" problem.number_of_variables="20,25,30" problem.number_of_samples="200" problem.seed="${seed}" solver="milp,milp_cliquewidth" ++solver.max_clique_size="${max_clique_sizes}" solver.time_limit="7200"

# d=25/30, n=2000, T=5400: only Clique.
${CMD} experiment="CLIQUE" problem="${data}" problem.p="${lag_num}" ++problem.intra_edge_ratio="${edge_ratios}" ++problem.inter_edge_ratio="${edge_ratios}" problem.number_of_variables="25,30" problem.number_of_samples="2000" problem.seed="${seed}" solver="milp_cliquewidth" ++solver.max_clique_size="${max_clique_sizes}" solver.time_limit="5400"

# d=25/30, n=2000, T=7200: Baseline and Clique.
${CMD} experiment="CLIQUE" problem="${data}" problem.p="${lag_num}" ++problem.intra_edge_ratio="${edge_ratios}" ++problem.inter_edge_ratio="${edge_ratios}" problem.number_of_variables="25,30" problem.number_of_samples="2000" problem.seed="${seed}" solver="milp,milp_cliquewidth" ++solver.max_clique_size="${max_clique_sizes}" solver.time_limit="7200"
