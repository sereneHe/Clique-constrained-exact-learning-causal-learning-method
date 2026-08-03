#!/bin/sh

# run in dagsolvers in directory

export PYTHONPATH=$PYTHONPATH:../

CMD="python3 run_experiments.py --multirun" # --config-name=config-cluster"


${CMD} experiment="EXMAG" problem="admissions" solver="exmag, milp"
