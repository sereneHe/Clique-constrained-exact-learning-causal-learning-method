#!/bin/sh

export PYTHONPATH=$PYTHONPATH:../
export  KMP_DUPLICATE_LIB_OK=TRUE

CMD="python3 run_experiments.py --multirun --config-name=config-cluster"

vars="5, 10, 15, 20"
samples="20 , 50, 100, 500, 1000"
seed_range=10

#${CMD} experiment="EXMAG_NOTABU2" problem="ermag" problem.edge_ratio="2,3,5,7" problem.number_of_variables="${vars}" problem.number_of_samples="${samples}" solver="fci" problem.seed="range(0,${seed_range})"

#${CMD} experiment="EXMAG_NOTABU2" problem="bowfree_admg" problem.number_of_variables="${vars}" problem.pdir="0.4" problem.pbidir="0.3" problem.number_of_samples="${samples}" solver="fci"  problem.seed="range(0,${seed_range})"

#${CMD} experiment="EXMAG_NOTABU" problem="bowfree_admg" problem.number_of_variables="${vars}" problem.pdir="0.2" problem.pbidir="0.3" problem.number_of_samples="${samples}" solver="fci"  problem.seed="range(0,${seed_range})"

#${CMD} experiment="EXMAG_NOTABU2" problem="bowfree_admg" problem.number_of_variables="${vars}" problem.pdir="0.2" problem.pbidir="0.15" problem.number_of_samples="${samples}" solver="fci"  problem.seed="range(0,${seed_range})"

#${CMD} experiment="EXMAG_NOTABU2" problem="bowfree_admg" problem.number_of_variables="${vars}" problem.max_in_arrows=3 problem.pdir="0.4" problem.pbidir="0.3" problem.number_of_samples="${samples}" solver="fci"  problem.seed="range(0,${seed_range})"

#${CMD} experiment="EXMAG_NOTABU2" problem="bowfree_admg" problem.number_of_variables="${vars}" problem.max_in_arrows=3 problem.pdir="0.2" problem.pbidir="0.15" problem.number_of_samples="${samples}" solver="fci"  problem.seed="range(0,${seed_range})"


${CMD} experiment="EXMAG_NOTABU2" problem="bowfree_admg" problem.number_of_variables="${vars}" problem.max_in_arrows=3 problem.pdir="0.4" problem.pbidir="0.3" problem.number_of_samples="${samples}" solver="ip4ancadmg"  problem.seed="range(0,${seed_range})"

${CMD} experiment="EXMAG_NOTABU2" problem="bowfree_admg" problem.number_of_variables="${vars}" problem.max_in_arrows=3 problem.pdir="0.2" problem.pbidir="0.15" problem.number_of_samples="${samples}" solver="ip4ancadmg"  problem.seed="range(0,${seed_range})"



# 3bf  problem.max_in_arrows=3

# ipbm, fci, ip4ancadmg

# this for debuging
#${CMD} experiment="EXMAG3" problem="ermag" problem.edge_ratio="5" problem.number_of_variables="20" problem.number_of_samples="500" solver="exmag" solver.time_limit="900" problem.seed="0" hydra.launcher.timeout_min=150

# ratio 2,3,5,7

#${CMD} experiment="EXMAG_NOTABU2" problem="ermag" problem.edge_ratio="7" problem.number_of_variables="${vars}" problem.number_of_samples="${samples}" solver="exmag" solver.lambda1="100, 10" solver.reg_type="l1" solver.time_limit="7200" problem.seed="range(0,10)" hydra.launcher.timeout_min=150



#${CMD} experiment="EXMAG_NOTABU" problem="ermag" problem.edge_ratio="2, 3" problem.number_of_variables="${vars}" problem.number_of_samples="${samples}" solver="exmag" solver.lambda1="10, 0.001, 0.0001" solver.reg_type="l1,l2" solver.time_limit="7200" problem.seed="range(0,${seed_range})" hydra.launcher.timeout_min=150


#${CMD} experiment="EXMAG_NOTABU" problem="ermag" problem.edge_ratio="5, 7" problem.number_of_variables="${vars}" problem.number_of_samples="${samples}" solver="exmag" solver.lambda1="0.1, 0.01" solver.time_limit="7200" problem.seed="range(0,${seed_range})" hydra.launcher.timeout_min=150

#${CMD} experiment="EXMAG_NOTABU2" problem="bowfree_admg"  problem.number_of_variables="${vars}" problem.pdir="0.2" problem.pbidir="0.15" problem.number_of_samples="${samples}" solver="exmag"  solver.lambda1="10,1,0.1, 0.01,0.001" solver.reg_type="l1, l2" solver.time_limit="7200" hydra.launcher.timeout_min=200 problem.seed="range(0,${seed_range})"

#${CMD} experiment="EXMAG_NOTABU2" problem="bowfree_admg"  problem.number_of_variables="${vars}" problem.pdir="0.4" problem.pbidir="0.3" problem.number_of_samples="${samples}" solver="exmag"  solver.lambda1="1, 10" solver.time_limit="7200" hydra.launcher.timeout_min=150 problem.seed="range(0,${seed_range})"

#${CMD} experiment="EXMAG_NOTABU" problem="bowfree_admg"  problem.number_of_variables="${vars}" problem.pdir="0.2" problem.pbidir="0.3" problem.number_of_samples="${samples}" solver="exmag" hydra.launcher.mem_per_cpu="32G" solver.lambda1="0.1, 0.01" solver.time_limit="7200" hydra.launcher.timeout_min=150 problem.seed="range(0,${seed_range})"

#${CMD} experiment="EXMAG_NOTABU2" problem="bowfree_admg" problem.max_in_arrows=3 problem.number_of_variables="${vars}" problem.pdir="0.2" problem.pbidir="0.15" problem.number_of_samples="${samples}" solver="exmag"  solver.lambda1="1, 10"  solver.time_limit="7200" hydra.launcher.timeout_min=150 problem.seed="range(0,${seed_range})"

#${CMD} experiment="EXMAG_NOTABU2" problem="bowfree_admg" problem.max_in_arrows=3  problem.number_of_variables="${vars}" problem.pdir="0.4" problem.pbidir="0.3" problem.number_of_samples="${samples}" solver="exmag" solver.lambda1="1, 10"  solver.time_limit="7200"  hydra.launcher.timeout_min=150 problem.seed="range(0,${seed_range})"


