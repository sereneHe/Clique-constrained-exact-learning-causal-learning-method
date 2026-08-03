import numpy as np

# install
# pip install causal-learn


def solve_fci(X):
    from causallearn.search.ConstraintBased.FCI import fci
    graph, edges = fci(X, alpha=0.05)
    n = graph.get_num_nodes()

    B_est = np.zeros((n, n))
    W_bi_est = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            if graph.graph[j,i] == 1 and graph.graph[i,j] == -1: # i --> j
                B_est[i,j] = 1
            elif graph.graph[j,i] == 1 and graph.graph[i,j] == 1: # i <-> j, == common confounder
                W_bi_est[i,j] = 1 # it's going to be symmetric. W_bi_est it's going to be symmetric.
            elif graph.graph[j,i] == 1 and graph.graph[i,j] == 2: #  i o-> j.
                B_est[i,j] = 2
            elif graph.graph[i,j] == -1 and graph.graph[j,i] == -1: # indicates i --- j == selection bias, common effect
                W_bi_est[i,j] = 2
            elif graph.graph[i,j] == 2 and graph.graph[j,i] == 2: # indicates i o-o j
                W_bi_est[i,j] = 3

    return B_est, W_bi_est
