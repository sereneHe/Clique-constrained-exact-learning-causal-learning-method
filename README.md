# bestdagsolverintheworld

** A comprehensive causal discovery toolkit** combining algorithms ExDBN, ExDAG, Clique and experiments A-G.

Experiments base on [Erdős–Rényi](https://networkx.org/documentation/stable/reference/generated/networkx.generators.random_graphs.erdos_renyi_graph.html) and [Scale-Free](https://networkx.org/documentation/stable/reference/generated/networkx.generators.random_graphs.barabasi_albert_graph.html) / Barabási–Albert sythetic data.



## Evaluations

We report causal-recovery metrics SHD, NNZ, F1-score in `metrics_utils.py` jointly with primal and dual bounds, node throughput, MIPSOL rejection rates, root fractionality, and callback cost. 


### Methods

- `solve_milp.py` - solver for ExDBN and ExDAG
- `solve_milp_clique.py` - solver for all clique constrained method(clique, clique-B1-F2, clique-B3, clique-C3,clique-C5, clique-E2)
- `solve_milp_cliquewidth.py` - solver for clique constrained method


### Additional Resources

- **configs/** - Configuration files for solvers
- **results/** - Result tables
- **reports/** - Report demonstrations


## Quick Start
[Hydra](https://github.com/facebookresearch/hydra) manages configurations and [MLflow](https://github.com/mlflow/mlflow) records parameters, metrics, and run metadata. Experiments were executed on MetaCentrum~\cite{sitera2011metacentrum} using jobs allocated two CPUs, 32~GB RAM, and 30~GB of local scratch storage. The software environment uses Python~3.10, Gurobi, NetworkX, NumPy, and SciPy.


### Installation

Install dependencies:
```bash
pip install -r requirements-cluster.txt  # For cluster
pip install -r requirements-clique.txt    # For local
```

### Experiments

Run experiments using the scripts in the `scripts/` directory:
- `experiments_exdbn_clique.sh` - ExDBN and Clique experiments

- `summary_multiruns.sh` - summary results from multirun/

- `plot.sh` - plot results



