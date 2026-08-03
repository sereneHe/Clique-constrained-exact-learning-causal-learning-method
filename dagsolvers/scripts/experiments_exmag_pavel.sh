#!/bin/sh

export PYTHONPATH=$PYTHONPATH:../
export  KMP_DUPLICATE_LIB_OK=TRUE

CMD="python3 run_experiments.py --multirun --config-name=config-cluster"

vars="5, 10, 15, 20"
samples="20 , 50, 100, 500, 1000"
seed_range=10

#${CMD} experiment="EXMAG" problem="ermag" problem.edge_ratio="2" problem.number_of_variables="${vars}" problem.number_of_samples="${samples}" solver="fci" problem.seed="range(0,${seed_range})"

#${CMD} experiment="EXMAG" problem="bowfree_admg" problem.max_in_arrows=3 problem.number_of_variables="${vars}" problem.pdir="0.2" problem.pbidir="0.15" problem.number_of_samples="${samples}" solver="ipbm"  problem.seed="range(0,${seed_range})"


#${CMD} experiment="EXMAG" problem="ermag" problem.edge_ratio="3,5,7,10" problem.number_of_variables="${vars}" problem.number_of_samples="${samples}" solver="exmag" solver.time_limit="900" problem.seed="range(0,${seed_range})"

${CMD} experiment="EXMAG" problem="bowfree_admg" problem.max_in_arrows=3  problem.number_of_variables="${vars}" problem.pdir="0.2" problem.pbidir="0.15" problem.number_of_samples="${samples}" solver="exmag" hydra.launcher.mem_per_cpu="32G" solver.time_limit="900" problem.seed="range(0,${seed_range})"


#python3 ../cluster_computing/extract_experiments_data.py EXMAG EXMAG.csv
