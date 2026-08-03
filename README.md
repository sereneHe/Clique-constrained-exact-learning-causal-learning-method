This repository combines algorithms ExDBN, ExDAG, Clique and experiments A-G. The source code, scripts, data generation code and instructions will help one to reproduce the results of paper `Clique Constraints for Exact Causal Structure Learning`.

Experiments base on cliquefree-[Erdős–Rényi](https://networkx.org/documentation/stable/reference/generated/networkx.generators.random_graphs.erdos_renyi_graph.html) and cliquefree-[Scale-Free / Barabási–Albert](https://networkx.org/documentation/stable/reference/generated/networkx.generators.random_graphs.barabasi_albert_graph.html) sythetic data.



## Evaluations

We report causal-recovery metrics SHD, NNZ, F1-score in `metrics_utils.py` jointly with primal and dual bounds, node throughput, MIPSOL rejection rates, root fractionality, and callback cost. 


### Methods

- `solve_milp.py` - solver for ExDBN and ExDAG
- `solve_milp_clique.py` - solver for all clique constrained method(clique, clique-B1-F2, clique-B3, clique-C3,clique-C5, clique-E2)
- `solve_milp_cliquewidth.py` - solver for clique constrained method
- `solve_milp_edge_limit.py` - solver for edge-limited method


### Additional Resources

- **experiments_conf/** - Configuration files for solvers
- **multiruns/** - Running details
- **results/** - Result tables
- **reports/** - Report demonstrations


## Quick Start
[Hydra](https://github.com/facebookresearch/hydra) manages configurations and [MLflow](https://github.com/mlflow/mlflow) records parameters and metrics.


### Installation

Install dependencies:
```bash
pip install -r requirements-cluster.txt  # For cluster
pip install -r requirements-clique.txt    # For local
```
### Gurobi License

Download gurobi.lic under project route.

### Experiments

Run experiments using the scripts in the `scripts/` directory:
- `scripts/experiments_exdbn_clique.sh` - ExDBN and Clique experiments

- `scripts/summary_multiruns.sh` - summary results from multiruns/

- `scripts/plot.sh` - plot results



