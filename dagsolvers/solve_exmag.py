import gurobipy as gp
import numpy as np
from gurobipy import GRB
from notears import utils

from dagsolvers.dagsolver_utils import find_minimal_dag_threshold, tupledict_to_np_matrix
from dagsolvers.metrics_utils import apply_threshold, find_optimal_threshold_for_shd
from dagsolvers.magseparation import floyd_warshall, check_for_inducing_path, check_for_almost_directed_cycles


def find_cycles(edges, mode):
    vertices = set(e[0] for e in edges)
    vertices.update(e[1] for e in edges)

    visited = set()
    on_stack = set()
    parent = {}
    stack = []
    shortest_cycle = None
    found_cycles = []
    number_of_cycles = 0

    for root in vertices:
        if root in visited:
            continue
        stack.append(root)
        while stack:
            v = stack[-1]
            if v not in visited:
                visited.add(v)
                on_stack.add(v)
            else:
                if v in on_stack:
                    on_stack.remove(v)
                # else:
                #     print('DEBUG')
                stack.pop()

            neighbors = [e[1] for e in edges if e[0] == v]
            for neighbor in neighbors:
                if neighbor not in visited:
                    stack.append(neighbor)
                    parent[neighbor] = v
                elif neighbor in on_stack:
                    number_of_cycles += 1
                    # Found a cycle
                    cycle = [neighbor, v]  # Back edge
                    p = parent[v]
                    while p != neighbor:
                        cycle.append(p)
                        p = parent[p]
                    # print(cycle)
                    # return cycle # return the first found cycle
                    found_cycles.append(cycle)
                    if shortest_cycle is None or len(shortest_cycle) > len(cycle):
                        shortest_cycle = cycle

    # print(f'number of cycles: {number_of_cycles}')
    if mode == 'shortest_cycle':
        if shortest_cycle is not None:
            return [shortest_cycle]
        else:
            return []
    elif mode == 'all_cycles':
        return found_cycles
    else:
        assert False, f'Invalid mode{mode}'


def extract_adj_matrix(edges_vals, weights_vals, d):
    W = np.zeros((d, d))
    for v1 in range(d):
        for v2 in range(d):
            if v1 != v2:
                if edges_vals[v1, v2] > 0.5:
                    W[v1, v2] = weights_vals[(v1, v2)]
    return W


def check_for_mag(model, where):
    if where == GRB.Callback.MESSAGE:
        pass
        # edges_vals = model.cbGetSolution(model._edges_vars)
        # weights_vals = model.cbGetSolution(model._edges_weights)
        # W = extract_adj_matrix(edges_vals, weights_vals)
        # print(W)

    if where == GRB.Callback.MIPSOL:
        # print('CALLBACK')
        # make a list of edges selected in the solution
        constr_added = False
        edges_vals = model.cbGetSolution(model._edges_vars)
        edges_vals = tupledict_to_np_matrix(edges_vals, model._d)
        biedges_vals = model.cbGetSolution(model._biedges_vars)
        biedges_vals = tupledict_to_np_matrix(biedges_vals, model._d)
        weights_vals = model.cbGetSolution(model._edges_weights)
        selected_edges = gp.tuplelist((i, j) for i, j in model._edges_vars.keys() if edges_vals[i, j] > 0.5)

        # find the shortest cycle in the selected edge list
        cycles = find_cycles(selected_edges, model._callback_mode)
        for cycle in cycles:
            edges_of_cycle = []
            for i in range(len(cycle) - 1):
                edges_of_cycle.append((cycle[i + 1], cycle[i]))
            edges_of_cycle.append((cycle[0], cycle[-1]))
            # callback_constraints[1] = callback_constraints[1] + 1
            # print('NEW CONSTRAINT')
            model._lazy_count += 1
            model.cbLazy(gp.quicksum(model._edges_vars[i, j] for i, j in edges_of_cycle)
                         <= len(edges_of_cycle) - 1)
            constr_added = True

        # find the almost directed cycles and inducing paths
        # TODO ajd and biadj might not work with model.cbGetSolution
        if len(cycles) == 0:
            fwdist = floyd_warshall(edges_vals)
            almost_directed_cycles = check_for_almost_directed_cycles(edges_vals, biedges_vals, fwdist)
            #print("almost directed")
            #print(almost_directed_cycles)
            inducing_paths = check_for_inducing_path(edges_vals, biedges_vals, fwdist)
            #print("inducing_paths")
            #print(inducing_paths)
            for lst in (almost_directed_cycles, inducing_paths):
                for directed_edges, bidirected_edges in lst:
                    model._lazy_count += 1
                    #print("lazy constraint")
                    model.cbLazy(gp.quicksum(model._edges_vars[i, j] for i, j in directed_edges) +
                                 gp.quicksum(model._biedges_vars[i, j] for i, j in bidirected_edges)
                                 <= len(directed_edges) + len(bidirected_edges) - 1)
                    #print(len(directed_edges) + len(bidirected_edges) - 1)
                    constr_added = True

        # Compute solving statistics
        rt = model.cbGet(GRB.Callback.RUNTIME)
        if not constr_added and model._B_ref is not None and (
                rt - model._last_time_stats > 60):  # Compute statistics every 60 seconds
            B_true = model._B_ref
            model._last_time_stats = rt
            W_sol = extract_adj_matrix(edges_vals, weights_vals, model._d)
            Wbi_sol = extract_adj_matrix(biedges_vals, weights_vals, model._d)
            dag_t, W_sol = find_minimal_dag_threshold(W_sol)  # TODO what is this?
            # W_sol = apply_threshold(W_sol, 0.3)
            default_threshold = 0.3
            W_t = apply_threshold(W_sol, default_threshold)
            shd = utils.count_accuracy(B_true, W_t != 0)['shd']
            objval = model.cbGet(GRB.Callback.MIPSOL_OBJ)

            best_t, best_shd = find_optimal_threshold_for_shd(B_true, W_sol, [], [], np.zeros_like(B_true), Wbi_sol)

            print(f't{default_threshold}_SHD: {shd} BEST_SHD: {best_shd} BEST_t: {best_t} OBJ: {objval} DAG_t: {dag_t}')
            model._stats.append((round(rt), shd, best_shd, best_t, objval, dag_t))


def solve(X, lambda1, loss_type, reg_type, w_threshold, tabu_edges={}, B_ref=None, mode='shortest_cycle',
          time_limit=300, robust=False, weights_bound=100.0, constraints_mode='weights'):
    """Tabu edges are a set of pairs of integers or column names in X."""
    n, d = X.shape

    # 'no-weights'
    # if loss_type == 'l2':
    #     X = X - np.mean(X, axis=0, keepdims=True)

    # convert tabu edges from variable names, just for the case,
    if not all(isinstance(item, int) for sublist in tabu_edges for item in sublist):
        name_to_index = {name: index for index, name in enumerate(X.columns)}
        tabu_edges = {(name_to_index[a], name_to_index[b]) for a, b in tabu_edges}
    tabu_matrix = np.zeros((d, d), dtype=bool)
    for i, j in tabu_edges:
        tabu_matrix[i, j] = True
        tabu_matrix[j, i] = True
    tabu_matrix = tabu_matrix.astype(int)

    print("tabu matrix")
    print(tabu_matrix)

    m = gp.Model()
    edges_vars = {}
    biedges_vars = {}
    edges_weights = {}

    for v1 in range(d):
        for v2 in range(d):
            if v1 != v2:
                edges_vars[v1, v2] = m.addVar(vtype=GRB.BINARY, name=f'{v1}->{v2}')
                biedges_vars[v1, v2] = m.addVar(vtype=GRB.BINARY, name=f'{v1}<->{v2}')
                edges_weights[v1, v2] = m.addVar(lb=float('-inf'), vtype=GRB.CONTINUOUS, name=f'weight{v1}->{v2}')

                if constraints_mode == 'no-weights':
                    m.addConstr(edges_weights[v1, v2] == (edges_vars[v1, v2] + biedges_vars[v1, v2]))
                else:
                    m.addConstr(edges_weights[v1, v2] <= weights_bound * (edges_vars[v1, v2] + biedges_vars[v1, v2]))
                    m.addConstr(-edges_weights[v1, v2] <= weights_bound * (edges_vars[v1, v2] + biedges_vars[v1, v2]))

                # either bi-directional edge, or normal, not both
                m.addConstr(edges_vars[v1, v2]  + biedges_vars[v1, v2] <= 1)
                # no directed edge where none should be
                m.addConstr(edges_vars[v1, v2] + tabu_matrix[v1, v2] <= 1)
                # bidirectional edge only if directed is forbidden
                m.addConstr(biedges_vars[v1, v2] <= tabu_matrix[v1, v2])

    for v1 in range(d):
        for v2 in range(v1):
            # no anti-parallel edges
            m.addConstr(edges_vars[v2, v1] + edges_vars[v1, v2] <= 1)

            # bidirectional edges need to be both uv and vu
            m.addConstr(biedges_vars[v1, v2] == biedges_vars[v2, v1])


    # no need to change criterion for MAG version
    robust_vars = {}
    quad_diff = {}
    if robust:
        for i in range(n):
            robust_vars[i] = m.addVar(vtype=GRB.BINARY, name=f's{i}')
            for j in range(d):
                quad_diff[i, j] = m.addVar(lb=float('-inf'), vtype=GRB.CONTINUOUS, name=f'q{i}-{j}')
        r = round(0.9 * n)
        m.addConstr(gp.quicksum(robust_vars[i] for i in range(n)) >= r)
        for i in range(n):
            for j in range(d):
                m.addConstr((X[i, j] - gp.quicksum(X[i, k] * edges_weights[k, j] for k in range(d) if k != j)) ** 2 ==
                            quad_diff[i, j])
        robust_objective = gp.quicksum(quad_diff[i, j] * robust_vars[i] for i in range(n) for j in range(d))
    # callback_constraints = {}
    # callback_constraints[1] = 0

    # regulazition
    if reg_type == 'l2':
        reg = gp.quicksum(w ** 2 for w in edges_weights.values())
    elif reg_type == 'l1':
        reg = gp.quicksum(w for w in edges_vars.values()) + gp.quicksum(w for w in biedges_vars.values())
    else:
        assert False

    # Cost function
    if loss_type == 'l2':
        if robust:
            m.setObjective(robust_objective + lambda1 * reg / d, GRB.MINIMIZE)
        else:
            m.setObjective(gp.quicksum(
                (X[i, j] - gp.quicksum(X[i, k] * edges_weights[k, j] for k in range(d) if k != j)) ** 2 for i in
                range(n) for j in range(d)) / n + lambda1 * reg / d, GRB.MINIMIZE)
            print(m.getObjective().getValue())
    elif loss_type == 'l1':
        abs_vars = {}
        for i in range(n):
            for j in range(d):
                abs_vars[i, j] = m.addVar(vtype=GRB.CONTINUOUS, name=f'abs{i}-{j})')
                m.addConstr((X[i, j] - gp.quicksum(X[i, k] * edges_weights[k, j] for k in range(d) if k != j)) <= abs_vars[i, j])
                m.addConstr(-(X[i, j] - gp.quicksum(X[i, k] * edges_weights[k, j] for k in range(d) if k != j)) <= abs_vars[i, j])

        abs_edges_weights = {}
        for v1 in range(d):
            for v2 in range(d):
                if v1 != v2:
                    abs_edges_weights[v1, v2] = m.addVar(vtype=GRB.CONTINUOUS, name=f'abs_weight{v1}->{v2}')
                    m.addConstr(edges_weights[v1, v2] <= abs_edges_weights[v1, v2])
                    m.addConstr(-edges_weights[v1, v2] <= abs_edges_weights[v1, v2])

        m.setObjective(gp.quicksum(abs_vars[i, j] for i in range(n) for j in range(d)) + lambda1 * reg, GRB.MINIMIZE)

    m.Params.lazyConstraints = 1
    m.Params.MIPGap = 0.1
    m.params.TimeLimit = time_limit
    m._edges_vars = edges_vars
    m._biedges_vars = biedges_vars
    m._edges_weights = edges_weights
    m._lazy_count = 0
    m._last_time_stats = 0
    m._B_ref = B_ref
    m._stats = []
    m._d = d
    m._callback_mode = mode
    m.optimize(check_for_mag)

    sol_count = m.getAttr(GRB.attr.SolCount)
    if sol_count == 0:
        return None, None, None, None, None

    gap = m.MIPGap
    lazy_count = m._lazy_count
    stats = m._stats

    # print(f'add constraints: {callback_constraints[1]}')

    edges_vals = tupledict_to_np_matrix(m.getAttr('x', edges_vars), d)
    biedges_vals = tupledict_to_np_matrix(m.getAttr('x', biedges_vars), d)
    weights_vals = m.getAttr('x', edges_weights)
    
    print(edges_vars)
    print(edges_vals)
    print(biedges_vars)
    print(biedges_vals)
    print(edges_weights)
    W = extract_adj_matrix(edges_vals, weights_vals, d)
    Wbi = extract_adj_matrix(biedges_vals, weights_vals, d)

    m.dispose()
    gp.disposeDefaultEnv()

    # threshold_func = np.vectorize(lambda x: (x if abs(x) > threshold else 0.0))
    # W_t = threshold_func(W)

    W[np.abs(W) < w_threshold] = 0
    Wbi[np.abs(Wbi) < w_threshold] = 0

    assert utils.is_dag(W)

    return W, Wbi, gap, lazy_count, stats


if __name__ == '__main__':
    from notears import utils

    utils.set_random_seed(1)

    n, d, s0, graph_type, sem_type = 2000, 10, 30, 'ER', 'gauss'
    # n, d, s0, graph_type, sem_type = 100, 3, 20, 'PATHPERM', 'gauss'  # 7 funguje, 25 GOBNILP COUNTER EXAMPL
    # n, d, s0, graph_type, sem_type = 10, 2, 20, 'PATH', 'gauss' # 7 funguje, 25
    B_true = utils.simulate_dag(d, s0, graph_type)
    W_true = utils.simulate_parameter(B_true)
    np.savetxt('W_true.csv', W_true, delimiter=',')
    # W_true = np.loadtxt('W_true.csv', delimiter=',')

    X = utils.simulate_linear_sem(W_true, n, sem_type, noise_scale=1)
    xcol = X[:, 1] / X[:, 0]
    x1avg = X[:, 0].sum() / n
    x2avg = X[:, 1].sum() / n
    print('debug')
    print(x2avg / x1avg)

    xrat = (X[:, 1] / X[:, 0]).sum() / n
    print(xrat)

    np.savetxt('X.csv', X, delimiter=',')
    # X = np.loadtxt('X.csv', delimiter=',')

    tabu_edges = []
    hidden_vertices_ratio = 0.2
    tabu_edges_ratio = 0.2
    new_d = int(d * (1 - hidden_vertices_ratio))
    indices = np.random.choice(range(d), size=new_d, replace=False)
    d = new_d
    X = X[:, indices]
    W_true = W_true[np.ix_(indices, indices)]
    for i in range(d):
        for j in range(i):
            if W_true[i, j] == 0.0 and W_true[j, i] == 0.0:
                if np.random.rand() < tabu_edges_ratio:
                    tabu_edges.append((i, j))

    W_est, W_bi, _, _, stats = solve(X, tabu_edges=tabu_edges, lambda1=0, loss_type='l2', reg_type='l1', w_threshold=0.1, B_ref=B_true,
                               mode='all_cycles')  # lambda1=0.0009
    assert utils.is_dag(W_est)
    np.savetxt('W_est_milp.csv', W_est, delimiter=',')
    acc = utils.count_accuracy(B_true, W_est != 0)
    print(stats)
    print(acc)
