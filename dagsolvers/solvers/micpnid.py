'''
Date: 2023/6/19
Author: Tong Xu
Mixed integer convex programming with perspective strengthening + outer approximation.
'''

# import packages
import gurobipy as gp
from gurobipy import GRB
import timeit
import scipy
import cvxpy as cp

# from utils import *
import numpy as np
import pandas as pd
import networkx as nx


def optimize(data, moral, lam, tau=0, timelimit=50, verbose=1):
    """

    Solve a mixed integer convex programming problem with perspective strengthening and outer approximation to estimate
    a Bayesian network.

    :param data: n by p data matrix.
    :param moral: list of edges in the moral graph (superstructure)
    :param lam: sparsity parameter lambda
    :param tau: early stopping parameter tau
    :param timelimit: set the time limit of gurobi to be timelimit * p (seconds)
    :param verbose: output the log of gurobi if verbose = 1
    :return:
        RGAP: relative optimality gap of optimization problem
        B: the B matrix representing a Bayesian network
        run_time: run time of solving the problem
    """

    n, p = data.shape
    # l = 12 * np.log(p) / n  # sparsity penalty parameter

    E = [(i, j) for i in range(p) for j in range(p) if i != j]  # off diagonal edge sets
    list_edges = []
    for edge in moral:
        list_edges.append((edge[0] - 1, edge[1] - 1))
        list_edges.append((edge[1] - 1, edge[0] - 1))

    ## Moral Graph
    G_moral = nx.Graph()
    for i in range(p):
        G_moral.add_node(i)
    G_moral.add_edges_from(list_edges)

    non_edges = list(set(E) - set(list_edges))
    # Sigma_hat = data.values.T @ data.values / n
    Sigma_hat = np.cov(data.T)

    ############################## Find Delta and Mu ########################################

    # Find the smallest possible \mu such that Sigma_hat + \mu I be PD and stable.
    min_eig = np.min(scipy.linalg.eigh(Sigma_hat, eigvals_only=True))
    if min_eig < 0:
        pmu = np.abs(min_eig)  # due to numerical instability. This is the minimum value for \mu.
    else:
        pmu = 0

    # Find delta using SDP
    Lam = cp.Variable(p)
    # The operator >> denotes matrix inequality.

    constraints = [Sigma_hat + pmu * np.identity(p) - cp.diag(Lam) >> 0] + [Lam[i] >= 0 for i in range(p)]

    prob = cp.Problem(cp.Maximize(cp.sum(Lam)), constraints)
    prob.solve() # solver=cp.CVXOPT

    # Print results
    Delta = Lam.value
    Delta[Delta < 0] = 0  # Due to possible numerical instability

    ################################# PARAMETERS OF THE MODEL ################################

    m = gp.Model()
    # Create variables
    # Continuous variables

    S_var = {}
    for j, k in list_edges:
        S_var[j, k] = m.addVar(vtype=GRB.CONTINUOUS, name="s_%s_%s" % (j, k))
    for i in range(p):
        S_var[i, i] = m.addVar(vtype=GRB.CONTINUOUS, name="s_%s_%s" % (i, i))
    Gamma = {}
    for i in range(p):
        for j in range(p):
            if i == j:
                Gamma[i, j] = m.addVar(lb=1e-5, vtype=GRB.CONTINUOUS, name="Gamma%s%s" % (i, j))
            else:
                Gamma[i, j] = m.addVar(lb=-GRB.INFINITY, ub=GRB.INFINITY, vtype=GRB.CONTINUOUS, name="Gamma%s%s" % (i, j))

    psi = m.addMVar((p, 1), lb=1, ub=p, vtype=GRB.CONTINUOUS, name='psi')

    # Integer variables
    g = {}
    for i in range(p):
        for j in range(p):
            g[i, j] = m.addVar(vtype=GRB.BINARY, name="g%s%s" % (i, j))

    # Variables for outer approximation
    T = {}
    for i in range(p):
        T[i] = m.addVar(lb=-10, ub=100, vtype=GRB.CONTINUOUS, name="T%s" % i)
        # This gives Gamma[i,i] a range about [0.0001, 100]

    m._T = T
    m._Gamma = Gamma
    m._g = g

    # define the callback function
    def logarithmic_callback(model, where):
        if where == gp.GRB.Callback.MIPSOL:
            # Get the value of Gamma
            Gamma_val = model.cbGetSolution(model._Gamma)
            for i in range(p):
                model.cbLazy(model._T[i] >= -2 * np.log(Gamma_val[i, i]) - 2 / Gamma_val[i, i] * (
                        model._Gamma[i, i] - Gamma_val[i, i]))

    Q = Sigma_hat - np.diag(Delta) + pmu * np.identity(p)
    min_eig = np.min(scipy.linalg.eigh(Q, eigvals_only=True))
    if min_eig <= 0:
        epsilon = np.abs(min_eig) + 0.0000001  # due to numerical instability. We epsilon = min_eig + 0.0000001
    else:
        epsilon = 0

    D = np.diag(Delta) - pmu * np.identity(p) - epsilon * np.identity(p)
    Q = Sigma_hat - D

    # Set objective
    log_term = 0
    for i in range(p):
        log_term += T[i]

    trace = gp.QuadExpr()
    for k in range(p):
        for i in range(p):
            for j in range(p):
                trace += Gamma[j, k] * Gamma[j, i] * Q[i, k]

    perspective_bigM = gp.LinExpr()
    perspective = gp.LinExpr()
    for i in range(p):
        for j in range(p):
            perspective_bigM += Gamma[j, i]*Gamma[j, i]*D[i, i]

    for j in range(p):
        perspective += D[j, j]*gp.quicksum(S_var[k, j] for k in G_moral.neighbors(j))
        perspective += D[j, j]*S_var[j, j]

    penalty = gp.LinExpr()
    for i, j in E:
        penalty += lam*g[i, j]

    m.setObjective(log_term + trace + perspective_bigM + penalty, GRB.MINIMIZE)

    # solve the problem without constraints to get big_M
    m.Params.lazyConstraints = 1
    m.Params.OutputFlag = verbose
    m.optimize(logarithmic_callback)
    m.update()

    big_M = 0
    for j, k in list_edges:
        big_M = max(big_M, abs(Gamma[j, k].x))

    M = 2*big_M

    m.setObjective(log_term + trace + perspective + penalty, GRB.MINIMIZE)

    m.addConstrs(Gamma[i, i] <= M for i in range(p))
    m.addConstrs(Gamma[j, k] <= M*g[j, k] for j, k in list_edges)
    m.addConstrs(Gamma[j, k] >= -M*g[j, k] for j, k in list_edges)
    m.addConstrs(1-p+p*g[j, k] <= psi[k] - psi[j] for j, k in list_edges)

    m.addConstrs(Gamma[j, k] == 0 for j, k in non_edges)  # Use moral structure
    m.addConstrs(g[j, k] == 0 for j, k in non_edges)  # Use moral structure
    m.update()

    # Conic constraints
    for k, j in list_edges:
        m.addConstr(S_var[k, j]*g[k, j] >= Gamma[k, j]*Gamma[k, j])
        m.addConstr(S_var[k, j] <= M*M*g[k, j])
    for i in range(p):
        m.addConstr(S_var[i, i] >= Gamma[i, i]*Gamma[i, i])
        m.addConstr(S_var[i, i] <= M * M)


    # Solve
    m.Params.TimeLimit = timelimit*p
    m.Params.lazyConstraints = 1
    m.Params.OutputFlag = verbose
    if tau > 0:
        m.Params.MIPGapAbs = tau
    start = timeit.default_timer()
    m.optimize(logarithmic_callback)
    end = timeit.default_timer()

    # Extract solutions
    Gamma_ij = [var.X for var in m.getVars() if "Gamma" in var.VarName]
    Gamma_opt = np.reshape(Gamma_ij, (p, p))
    D_half = np.diag(np.diag(Gamma_opt))
    B = np.eye(p) - Gamma_opt.T@np.linalg.inv(D_half)
    B[abs(B) <= 1e-6] = 0
    run_time = end - start
    RGAP = m.MIPGAP

    return RGAP, B, Gamma_opt.T, m.ObjVal, run_time


