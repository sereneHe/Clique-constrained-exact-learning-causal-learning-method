#!/bin/sh

export PYTHONPATH=$PYTHONPATH:../
export KMP_DUPLICATE_LIB_OK=TRUE

CONFIG_NAME="${EXDBN_CONFIG_NAME:-config}"
PLOT_FLAG="${EXDBN_PLOT:-false}"
HYDRA_LAUNCHER="${EXDBN_HYDRA_LAUNCHER:-}"
REPEAT_COUNT="${EXDBN_REPEAT_COUNT:-5}"

CMD="python3 run_experiments.py --multirun --config-name=${CONFIG_NAME} ${HYDRA_LAUNCHER} plot=${PLOT_FLAG}"
PLOT_CMD="python3 plot_solver_performance.py"

samples="200, 2000"
seeds="$(python3 - "${REPEAT_COUNT}" <<'PY'
import sys

repeat_count = int(sys.argv[1])
print(",".join(str(seed) for seed in range(1, repeat_count + 1)))
PY
)"
degrees="1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32,33,34,35,36"

# # ER-2-0
# vars="5, 10, 15, 20, 25"

# ${CMD} experiment="EXDBN2_CLIQUE" problem="er" problem.generator="notears" problem.normalize="false" problem.edge_ratio="2" problem.number_of_variables="${vars}" problem.number_of_samples="${samples}" problem.sem_type="gauss" problem.seed="1" solver="milp,milp_cliquewidth"

# for degree in ${degrees}
# do
# ${CMD} experiment="EXDBN2_EDGE_LIMIT" problem="er" problem.generator="notears" problem.normalize="false" problem.edge_ratio="2" problem.number_of_variables="${vars}" problem.number_of_samples="${samples}" problem.sem_type="gauss" problem.seed="1" solver="edge_limit" solver.max_in_degree="${degree}" solver.max_out_degree="${degree}"
# done

# # ER-3-0
# vars="7, 10, 15, 20, 25"

# ${CMD} experiment="EXDBN2_CLIQUE" problem="er" problem.generator="notears" problem.normalize="false" problem.edge_ratio="3" problem.number_of_variables="${vars}" problem.number_of_samples="${samples}" problem.sem_type="gauss" problem.seed="1" solver="milp,milp_cliquewidth"

# for degree in ${degrees}
# do
# ${CMD} experiment="EXDBN2_EDGE_LIMIT" problem="er" problem.generator="notears" problem.normalize="false" problem.edge_ratio="3" problem.number_of_variables="${vars}" problem.number_of_samples="${samples}" problem.sem_type="gauss" problem.seed="1" solver="edge_limit" solver.max_in_degree="${degree}" solver.max_out_degree="${degree}"
# done

# # ER-4-0
# vars="9, 10, 15, 20, 25"

# ${CMD} experiment="EXDBN2_CLIQUE" problem="er" problem.generator="notears" problem.normalize="false" problem.edge_ratio="4" problem.number_of_variables="${vars}" problem.number_of_samples="${samples}" problem.sem_type="gauss" problem.seed="1" solver="milp,milp_cliquewidth"

# for degree in ${degrees}
# do
# ${CMD} experiment="EXDBN2_EDGE_LIMIT" problem="er" problem.generator="notears" problem.normalize="false" problem.edge_ratio="4" problem.number_of_variables="${vars}" problem.number_of_samples="${samples}" problem.sem_type="gauss" problem.seed="1" solver="edge_limit" solver.max_in_degree="${degree}" solver.max_out_degree="${degree}"
# done

# ER-5-0
vars="11, 15, 20, 25"

${CMD} experiment="EXDBN2_CLIQUE" problem="er" problem.generator="notears" problem.normalize="false" problem.edge_ratio="5" problem.number_of_variables="${vars}" problem.number_of_samples="${samples}" problem.sem_type="gauss" problem.seed="${seeds}" solver="milp,milp_cliquewidth"

for degree in ${degrees}
do
${CMD} experiment="EXDBN2_EDGE_LIMIT" problem="er" problem.generator="notears" problem.normalize="false" problem.edge_ratio="5" problem.number_of_variables="${vars}" problem.number_of_samples="${samples}" problem.sem_type="gauss" problem.seed="1" solver="edge_limit" solver.max_in_degree="${degree}" solver.max_out_degree="${degree}"
done
