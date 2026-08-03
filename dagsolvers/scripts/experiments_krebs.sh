#!/bin/sh

export PYTHONPATH=$PYTHONPATH:../
export  KMP_DUPLICATE_LIB_OK=TRUE

CMD="python3 run_experiments.py --multirun --config-name=config-cluster"



${CMD} experiment="KREBS_CYCLE" problem="krebs" problem.variant="krebs1NotNormalized, krebs3NotNormalized" problem.measurements="range(1,100)" solver="milp" hydra.launcher.mem_per_cpu="16G" solver.time_limit="82800"


