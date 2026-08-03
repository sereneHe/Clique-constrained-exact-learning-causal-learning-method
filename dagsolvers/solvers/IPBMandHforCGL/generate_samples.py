# To run, type:
# python3 generate_samples.py graph_file_name sample_file_name sample_size [data_directory]
# It reads and writes files in '../Instances/data/'

#from pgmpy.factors.discrete import State
#from pgmpy.models.BayesianModel import BayesianModel
#from pgmpy.sampling import BayesianModelSampling
#from pgmpy.factors.discrete import TabularCPD
#from pgmpy.estimators import K2Score, BdeuScore, BicScore
import pandas as pd
import numpy as np
from scipy.special import comb
from utils import compute_local_BiCScore, simulate_sem, compute_local_BiCScore_gauss, \
    compute_BiC_c_component, score_write_to_file, compute_BiC_c_comps_sets, check_connected_component,\
    find_bi_connected_node, has_cycle_in_c_comp
import networkx as nx
import itertools
import pickle
from typing import Sequence, Iterable
import sys

def read_graph_from_file(filename):
    """ Reads a graph from a file

    The following is an example of an input file:

    n_nodes n_directed n_bidirected
    4 3 2
    directed
    0 2
    2 3
    3 1
    bidirected
    0 1
    0 3

    """

    file = open(filename, 'r')
    data = file.readlines()
    file.close()

    # line 0 contains the heading: n_nodes n_directed n_bidirected
    line = data[1] # line 1 contains the values of n_nodes n_directed n_bidirected
    sline = line.strip('\n').split(' ')
    nnodes = int(sline[0])
    ndir = int(sline[1])
    nbidir = int(sline[2])

    D = [[0]*nnodes for i in range(nnodes)]
    B = [[0]*nnodes for i in range(nnodes)]

    # line 2 contains the heading: directed
    # the following lines contain the directed edges
    for nline in range(3,3+ndir):
        line = data[nline]
        sline = line.strip('\n').split(' ')
        tail = int(sline[0])
        head = int(sline[1])
        D[tail][head] = 1

    # line 3+ndir contains the heading: bidirected
    # the following lines contain the bidirected edges
    start = 3+ndir+1
    for nline in range(start,start+nbidir):
        line = data[nline]
        sline = line.strip('\n').split(' ')
        tail = int(sline[0])
        head = int(sline[1])
        B[tail][head] = 1
        B[head][tail] = 1

    graph = {}
    graph[0] = D
    graph[1] = B
    return graph


def gererate_bidirected_graph_Bhattacharya_fig1c():
    # generate ADMG in Figure 1(c) of Bhattacharya's paper

    D = [[0, 0, 1, 0],
         [0, 0, 0, 0],
         [0, 0, 0, 1],
         [0, 1, 0, 0]]

    B = [[0, 1, 0, 1],
         [1, 0, 0, 0],
         [0, 0, 0, 0],
         [1, 0, 0, 0]]

    graph = {}
    graph[0] = D
    graph[1] = B
    return graph

def simulate_sem_multivariate_gaussian(
        D: Iterable[Sequence[int]],
        B: Iterable[Sequence[int]],
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

def simulate_sem_multivariate_gaussian_(
        D: Iterable[Sequence[int]],
        B: Iterable[Sequence[int]],
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


def main():
#    np.random.seed(12345)
    data_directory = '../Instances/data/'
    graph_file_name = '' #'graph_bhattacharya_fig1c.txt'
    sample_file_name = '' #'sample_bhattacharya_fig1c.txt'
    if len(sys.argv) > 1:
        graph_file_name = sys.argv[1]
    if len(sys.argv) > 2:
        sample_file_name = sys.argv[2]
    sample_size = 1000
    if len(sys.argv) > 3:
        sample_size = int(sys.argv[3])
    if len(sys.argv) > 4:
        data_directory = sys.argv[4]
    random_seed = 12345
    if len(sys.argv) > 5:
        random_seed = int(sys.argv[5])
    np.random.seed(random_seed)
    delta_beta_file_name = data_directory + 'delta_beta_' + graph_file_name
    graph_file_name = data_directory + graph_file_name
    sample_file_name = data_directory + sample_file_name
        
#    graph = gererate_bidirected_graph_Bhattacharya_fig1c()
    graph = read_graph_from_file(graph_file_name)
    data, delta, beta = simulate_sem_multivariate_gaussian(graph[0], graph[1], sample_size)
#    data = simulate_sem_multivariate_gaussian(graph[0], graph[1], sample_size)
    data = data[:,:,0]

    nrows,ncols = data.shape
    wrt = ''
    for i in range(nrows):
        for j in range(ncols-1):
            wrt = wrt + str(data[i][j]) + ' '
        wrt = wrt + str(data[i][ncols-1]) + '\n'
    f = open(sample_file_name,"w")
    f.write(wrt)
    f.close()

    wrt = 'nnodes\n'
    wrt = wrt + str(ncols) + '\n'
    wrt = wrt + 'delta\n'
    for i in range(ncols):
        for j in range(ncols-1):
            wrt = wrt + str(delta[i][j]) + ' '
        wrt = wrt + str(delta[i][ncols-1]) + '\n'
    wrt = wrt + 'beta\n'
    for i in range(ncols):
        for j in range(ncols-1):
            wrt = wrt + str(beta[i][j]) + ' '
        wrt = wrt + str(beta[i][ncols-1]) + '\n'
    f = open(delta_beta_file_name,"w")
    f.write(wrt)
    f.close()

    

if __name__ == "__main__":

    main()
