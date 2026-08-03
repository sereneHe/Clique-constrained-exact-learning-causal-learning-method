import numpy as np
import networkx as nx
from omegaconf import DictConfig

from notears import utils



def solve(X, cfg: DictConfig):
    from pygobnilp.gobnilp import Gobnilp
    m = Gobnilp()
    m.params.TimeLimit = cfg.time_limit
    m.learn(X,data_type=cfg.data_type,score=cfg.score,  palim=cfg.palim, gurobi_output=True, verbose=5, plot=False) # BGe, GaussianL0, GaussianBIC, GaussianAIC,
    bn = m.learned_bn

    am = nx.adjacency_matrix(bn, sorted(bn.nodes()))

    W_est = am.todense()
    return W_est


if __name__ == '__main__':
    utils.set_random_seed(1)

    #n, d, s0, graph_type, sem_type = 100, 23, 20, 'ER', 'gauss' #20
    n, d, s0, graph_type, sem_type = 3000, 3, 20, 'PATHPERM', 'gauss' #20
    B_true = utils.simulate_dag(d, s0, graph_type)
    W_true = utils.simulate_parameter(B_true)
    np.savetxt('W_true.csv', W_true, delimiter=',')

    X = utils.simulate_linear_sem(W_true, n, sem_type, noise_scale=50)
    np.savetxt('X.csv', X, delimiter=',')
    #X = np.loadtxt('X.csv', delimiter=',')

    W_est = solve(X)

    assert utils.is_dag(W_est)
    np.savetxt('W_est_gobnilp.csv', W_est, delimiter=',')
    # acc = utils.count_accuracy(B_true, W_est != 0)
    # print(acc)
