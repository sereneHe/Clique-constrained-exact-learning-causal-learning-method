#!/bin/sh

export PYTHONPATH=$PYTHONPATH:../
export  KMP_DUPLICATE_LIB_OK=TRUE

CMD="python3 run_experiments.py --multirun --config-name=config-cluster"

edge_ratios="2"
vars="5, 10, 15, 20, 25"
samples="20, 50, 100, 500, 1000"
noise="gauss, exp, uniform"

${CMD} experiment="EXDAG3" problem="sf"  problem.edge_ratio="2, 3" problem.number_of_variables="${vars}" problem.number_of_samples="${samples}" solver="dagma"  problem.noise_scale="0.8" problem.noise_scale_variance="0.4"  problem.seed="range(0,5)"

#${CMD} experiment="EXDAG" problem="er, sf" problem.sem_type="${noise}" problem.edge_ratio="${edge_ratios}" problem.number_of_variables="${vars}" problem.number_of_samples="${samples}" solver="notears" solver.lambda1="0.03" problem.seed="range(0,10)"

#${CMD} experiment="EXDAG" problem="er, sf" problem.sem_type="${noise}" problem.edge_ratio="${edge_ratios}" problem.number_of_variables="${vars}" problem.number_of_samples="${samples}" solver="dagma" problem.seed="range(0,10)"

#${CMD} experiment="EXDAG" problem="er, sf" problem.sem_type="${noise}" problem.edge_ratio="${edge_ratios}" problem.number_of_variables="${vars}" problem.number_of_samples="${samples}" solver="boss" problem.seed="range(0,10)"

#${CMD} experiment="EXDAG" problem="er, sf" problem.sem_type="${noise}" problem.number_of_variables="10" solver="gobnilp" problem.number_of_samples="10,100,1000"
