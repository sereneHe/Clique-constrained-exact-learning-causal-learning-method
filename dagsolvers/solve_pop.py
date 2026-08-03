import gurobipy as gp
import numpy as np
from gurobipy import GRB



def solve_pop(X, lambda1, loss_type):
    n, d = X.shape
    m = gp.Model()
    V = {}  # v constraints
    W = {} # Je v cost funkci
    for v1 in range(d):
        for v2 in range(d):
            for power in range(1, d + 1):
                V[power, v1, v2] = m.addVar(vtype=GRB.CONTINUOUS, name=f'w2{v1}->{v2}_power_{d}')
                if power == 1:
                    W[v1, v2] = m.addVar(lb=float('-inf'),vtype=GRB.CONTINUOUS, name=f'weight{v1}->{v2}')
                    m.addConstr(W[v1, v2] ** 2 == V[1, v1, v2])

    for v1 in range(d):
        for v2 in range(d):
            for power in range(1, d + 1):
                if (power % 2) == 0:
                    m.addConstr(V[power, v1, v2] == gp.quicksum(V[power//2, v1, k] * V[power//2, k, v2] for k in range(d)))
                else:
                    if power > 1:
                        m.addConstr(V[power, v1, v2] == gp.quicksum(V[((power-1)//2)+1, v1, k] * V[(power-1)//2, k, v2] for k in range(d)))

    #for v in range(d):
    for power in range(1, d + 1):
        m.addConstr(gp.quicksum(V[power,k,k] for k in range(d)) == 0)

    if loss_type == 'l2':

        reg2 = gp.quicksum(V.values())
        m.setObjective(gp.quicksum((X[i,j] - gp.quicksum(X[i, k] * W[k, j] for k in range(d) if k != j))**2 for i in range(n) for j in range(d)) + lambda1 * reg2, GRB.MINIMIZE)
        print(m.getObjective().getValue())
    elif loss_type == 'l1':
        pass

    m._W = W
    m.optimize()


    W_vals = m.getAttr('x', W)

    W_est = np.zeros((d,d))
    for v1 in range(d):
        for v2 in range(d):
            W_est[v1, v2] = W_vals[v1, v2]


    assert utils.is_dag(W_est)
    m.dispose()
    gp.disposeDefaultEnv()
    return W_est


if __name__ == '__main__':
    from notears import utils
    utils.set_random_seed(1)

    n, d, s0, graph_type, sem_type = 30, 7, 20, 'ER', 'gauss' # 7 funguje, 25
    #n, d, s0, graph_type, sem_type = 10, 2, 20, 'PATH', 'gauss' # 7 funguje, 25
    B_true = utils.simulate_dag(d, s0, graph_type)
    W_true = utils.simulate_parameter(B_true)
    np.savetxt('W_true.csv', W_true, delimiter=',')
    #W_true = np.loadtxt('W_true.csv', delimiter=',')

    X = utils.simulate_linear_sem(W_true, n, sem_type, noise_scale=1)
    xcol = X[:,1] / X[:,0]
    x1avg = X[:,0].sum()/n
    x2avg = X[:,1].sum()/n
    print('debug')
    print(x2avg/x1avg)

    xrat = (X[:,1]/X[:,0]).sum()/n
    print(xrat)

    np.savetxt('X.csv', X, delimiter=',')
    #X = np.loadtxt('X.csv', delimiter=',')

    W_est = solve_pop(X, lambda1=0, loss_type='l2') # lambda1=0.0009
    assert utils.is_dag(W_est)
    np.savetxt('W_est_milp.csv', W_est, delimiter=',')
    acc = utils.count_accuracy(B_true, W_est != 0)
    print(acc)
