import numpy as np
from scipy.special import expit as sigmoid
import igraph as ig
import random

from notears.linear import notears_linear



if __name__ == '__main__':
    from notears import utils
    utils.set_random_seed(3)

    n, d, s0, graph_type, sem_type = 2, 2, 20, 'PATH', 'gauss'
    B_true = utils.simulate_dag(d, s0, graph_type)
    W_true = utils.simulate_parameter(B_true)
    #np.savetxt('W_true.csv', W_true, delimiter=',')
    #W_true = np.loadtxt('W_true.csv', delimiter=',')

    X = utils.simulate_linear_sem(W_true, n, sem_type)
    np.savetxt('X.csv', X, delimiter=',')
    #X = np.loadtxt('X.csv', delimiter=',')

    W_est = notears_linear(X, lambda1=0.1, loss_type='l2')
    assert utils.is_dag(W_est)
    np.savetxt('W_est.csv', W_est, delimiter=',')
    acc = utils.count_accuracy(B_true, W_est != 0)
    print(acc)
