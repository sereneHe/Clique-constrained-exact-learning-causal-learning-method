#!/bin/sh

export PYTHONPATH=$PYTHONPATH:../
export  KMP_DUPLICATE_LIB_OK=TRUE

CMD="python3 run_experiments.py --multirun --config-name=config-cluster"

vars="5, 10, 15, 20, 25"
samples="20, 50, 100, 500, 1000"
seed_range=10

${CMD} experiment="EXMAG" problem="bowfree_admg" problem.number_of_variables="${vars}" problem.number_of_samples="${samples}" solver="exmag, milp" problem.seed="range(0,${seed_range})"

python3 ../cluster_computing/extract_experiments_data.py EXMAG EXMAG.csv
