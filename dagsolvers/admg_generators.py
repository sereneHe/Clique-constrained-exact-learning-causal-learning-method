import random
import numpy as np
import networkx as nx

from dagsolvers.magseparation import check_for_inducing_path, check_for_almost_directed_cycles, floyd_warshall

def generate_random_mag(nnodes, pdir, pbidir, max_in_arrows=None):
   while True:
       D, B = generate_random_bow_free_graph(nnodes, pdir, pbidir, max_in_arrows=max_in_arrows)
       fwdist = floyd_warshall(D)
       if check_for_almost_directed_cycles(D, B, fwdist):
           continue
       if check_for_inducing_path(D, B, fwdist):
           continue
       return D, B

def generate_random_bow_free_graph(nnodes, pdir, pbidir, max_in_arrows=None):
    D = [[0]*nnodes for i in range(nnodes)]
    B = [[0]*nnodes for i in range(nnodes)]

    for i in range(nnodes-1):
        for j in range(i+1, nnodes):
            if random.random() < pdir:
                D[i][j] = 1
            elif random.random() < pbidir:
                B[i][j] = 1
                B[j][i] = 1

    if max_in_arrows is not None:
        D, B = remove_edges_until_max_in_arrows(D, B, max_in_arrows)
    return np.array(D), np.array(B)


def remove_edges_until_max_in_arrows(D, B, max_in_arrows):
    # max_in_arrows is the maximum number of arrows pointing to each node

    nnodes = len(D)

    for j in range(nnodes):
        dipar = []
        bipar = []
        for i in range(nnodes):
            if D[i][j] == 1:
                dipar.append(i)
            if B[i][j] == 1:
                bipar.append(i)

        n_in_edges = len(dipar)+len(bipar)
        while n_in_edges > max_in_arrows:
            index = random.randint(0, n_in_edges-1)
            if index < len(dipar):
                D[dipar[index]][j] = 0
                dipar.pop(index)
            else:
                index -= len(dipar)
                B[bipar[index]][j] = 0
                B[j][bipar[index]] = 0
                bipar.pop(index)
            n_in_edges -= 1

    return D, B

def simulate_sem_multivariate_gaussian(
        D,
        B,
        n: int) -> np.ndarray:
    """Simulate samples from SEM with specified type of noise.

    Args:
        D: adjacency matrix of directed edges
        B: adjacency matrix of bidirected edges
        n: number of samples

    Returns:
        X: [n,d] sample matrix
    """
    G = nx.DiGraph(np.array(D))
    W = nx.to_numpy_array(G)
    d = W.shape[0]
    x_dims = 1
    X = np.zeros([n, d, x_dims])
    ordered_vertices = list(nx.topological_sort(G))
    assert len(ordered_vertices) == d
    delta = np.zeros([d, d])
    beta = np.zeros([d, d])
    # graph_bhattacharya_fig1c.txt: delta[i][j] in [-2.0,-0.5] union [0.5,2.0]
    # graph_6nodes.txt: delta[i][j] in [-0.5,-0.2] union [0.2,0.5]
    low = 0.5 #0.2
    #    low = 0.1
    high = 2.0 #0.5
    #    high = 0.5
    #    high = 0.9 # this is an attempt to lower the values of delta
    #    low = 0.4
    #    high = 0.8
    diff = high-low
    for i in range(d):
        for j in range(d):
            if D[i][j] > 0:
                delta[i][j] = np.random.uniform(-diff, diff)
                if delta[i][j] < 0.0:
                    delta[i][j] -= low
                else:
                    delta[i][j] += low
    # sample_bhattacharya_fig1c.txt: beta[i][j] in [-0.7,-0.4] union [0.4,0.7]
    # graph_6nodes.txt: beta[i][j]=0.0
    low = 1.0 #0.4
    high = 2.0 #0.7
    #    low = 0.2
    #    high = 0.6
    diff = high-low
    #    """
    for i in range(d-1):
        for j in range(i+1, d):
            if B[i][j] > 0:
                beta[i][j] = np.random.uniform(-diff, diff)
                if beta[i][j] < 0.0:
                    beta[i][j] -= low
                else:
                    beta[i][j] += low
                beta[j][i] = beta[i][j]
    #    """
    # beta[i][j] in [-1.2,-0.7] union [0.7,1.2] minus or plus sum(beta[i][j]) where j != i
    # sample_bhattacharya_fig1c.txt: beta[i][i] in [0.7,1.2]
    # graph_6nodes.txt: beta[i][i] in [0.1,0.4]
    low = 0.7 #0.1
    high = 1.2 #0.4
    #    low = 0.6 #0.1
    #    high = 0.9 #0.4
    #    diff = high-low
    for i in range(d):
        sum = 0.0
        for j in range(d):
            if i != j:
                sum += abs(beta[i][j])
        #        beta[i][i] = np.random.uniform(-diff, diff)
        beta[i][i] = np.random.uniform(low, high)
        # --------------------------------
        # this part ensures that beta[i][i] > sum but not by much
        """
        if abs(beta[i][i]) + low > sum:
            sum = 0.0
        else:
            temp1 = 1.01 * sum
            temp2 = sum + abs(beta[i][i]) + low
            temp = min(temp1, temp2)
            sum = temp - abs(beta[i][i]) - low
        """
        # --------------------------------
        if beta[i][i] < 0.0:
            beta[i][i] -= (low + sum)
        else:
            beta[i][i] += (low + sum)
    # sample multivariate normal distribution (each column corresponds to the samples of epsilon_i)
    epsilon = np.random.multivariate_normal([0]*d,beta,n)
    for j in ordered_vertices:
        parents = list(G.predecessors(j))
        eta = X[:, parents, 0].dot(delta[parents, j])
        X[:, j, 0] = eta + epsilon[:,j]

    #    return X
    return X, delta, beta


def generate_graph_and_samples(nnodes, pdir, pbidir, max_in_arrows, sample_size, enforce_mag):
    if enforce_mag:
        graph_d, graph_b = generate_random_mag(nnodes, pdir, pbidir, max_in_arrows)
    else:
        graph_d, graph_b = generate_random_bow_free_graph(nnodes, pdir, pbidir, max_in_arrows)
    tabu_edges = []
    for i in range(graph_b.shape[0]):
        for j in range(graph_b.shape[1]):
            if graph_b[i][j] > 0:
                tabu_edges.append((i, j))
    data, delta, beta = simulate_sem_multivariate_gaussian(graph_d, graph_b , sample_size)
    data = data[:,:,0]
    return graph_d, graph_b, tabu_edges, data
