import numpy as np


def floyd_warshall(adj):
    n = len(adj)
    dist = np.full((n, n), np.inf)

    # initialize the edges from the adj. matrix - inf where adj is zero, 1 otherwise
    dist[adj > 0.5] = 1
    np.fill_diagonal(dist, 0)

    for k in range(n):  # k is the midpoint of SP
        for i in range(n):
            for j in range(n):
                pathlen = dist[i][k] + dist[k][j]
                if dist[i][j] > pathlen:
                    dist[i][j] = pathlen

    return dist


def trace_f_w(dist, adj, u, v):
    if dist[u][v] == np.inf:
        return []

    n = len(dist)
    marked = np.full((n, n), False)
    edges = []
    if adj[u][v] == 1:
        edges.append((u, v))
    stack = []
    marked[u, v] = True
    stack.append((u, v))

    while stack:
        i, j = stack.pop()
        for k in range(n):
            if dist[i][k] + dist[k][j] != np.inf:  # a path goes through k
                for s, t in [(i, k), (k, j)]:
                    if not marked[s][t]:  # make sure not to include duplicates
                        marked[s][t] = True
                        if adj[s][t] == 1:  # direct edge, add it to the list
                            edges.append((s, t))
                        stack.append((s, t))  # a path, recurse
    return edges


def inducing_path_dfs(dist, adj, s, u, possible_endpoints, path, visited, only_one_dir=True, mode="shortest_cycle"):
    # dist = FW distances, adj = bidirect adjacency, u curr point, s where we started, path = current path
    if len(possible_endpoints) == 0:  # no possible enpoint, how can an inducing path exist?
        return []

    paths = []
    # we need to test for endpoint of the inducing path
    if len(path) > 2:
        visited[u] |= possible_endpoints # do not replicate work searching for failed goals
        if u in possible_endpoints:
            if u < s or not only_one_dir:  # optimization - report only one direction
                paths.append(path)

    # nest further
    n = len(dist)
    for v in range(n):
        if adj[u][v] > 0.5:  # iterate neighbors
            if v not in path:  # make sure we do not cycle or use edge we came from
                v_endpoints = possible_endpoints if dist[v][s] != np.inf else possible_endpoints & set(np.where(dist[v][:] < np.inf)[0])  # exists a path to v?
                v_endpoints -= visited[v]
                paths_after_v = inducing_path_dfs(dist, adj, s, v, v_endpoints, path + [v], visited, only_one_dir=only_one_dir, mode=mode)
                paths.extend(paths_after_v)

                if len(paths) > 1 and mode != "all_cycles":
                    return paths

        # check for the last hop going v -> u (len path cond is redundant)
        if len(path) > 2 and dist[v][u] == 1 and v in possible_endpoints:
            if v < s or not only_one_dir:
                paths.append(path)

    return paths


def inducing_paths(dist, adjbi, mode="shortest_cycle", only_one_dir=True):
    targets = []
    for end in range(dist.shape[1]):
        for start in range(dist.shape[0]):
            if start != end and np.isfinite(dist[start][end]):
                targets.append(end)
                break
    targets = set(targets)

    paths = []
    for v in targets:
        visited = [set() for _ in range(len(dist))]
        v_targets = targets if not only_one_dir else {t for t in targets if t < v}
        paths.extend(inducing_path_dfs(dist, adjbi, v, v, v_targets, [v], visited, mode=mode, only_one_dir=only_one_dir))
        # special case - we start with directed edge v -> u
        for u in range(len(dist)):
            if dist[v][u] == 1:
                paths.extend(inducing_path_dfs(dist, adjbi, v, u, v_targets, [v, u], visited, mode=mode, only_one_dir=only_one_dir))
        if len(paths) > 1 and mode != "all_cycles":
            return paths
    return paths


def check_for_inducing_path(adj, adjbi, fwdist):
    #fwdist = floyd_warshall(adj)
    paths = inducing_paths(fwdist, adjbi)
    retval = []  # list of tuples of lists (directed, bidirected)
    for path in paths:
        s = path[0]
        t = path[-1]
        biedges = [(path[i], path[i + 1]) for i in range(1, len(path) - 2)]
        diredges = []

        # first and last edge special cases
        if adj[path[0]][path[1]] == 1: diredges.append((path[0], path[1]))
        else: biedges.append((path[0], path[1]))
        if adj[path[-1]][path[-2]] == 1: diredges.append((path[-1], path[-2]))
        else: biedges.append((path[-1], path[-2]))

        for v in path[1:-1]:
            diredges.extend(trace_f_w(fwdist, adj, v, s))
            diredges.extend(trace_f_w(fwdist, adj, v, t))
        retval.append((diredges, biedges))
    return retval


def check_for_almost_directed_cycles(adj, adjbi, fwdist):
    # we look over all bi-directed edges and check whether there is path from one endpoint to the other
    n = len(adj)
    retval = []
    for u in range(n):
        for v in range(n):  # no need to check the other direction as the adjbi is symmetric -> both uv an vu are tested
            if adjbi[u][v] and fwdist[u][v] != np.inf:  # biedge uv and path uv
                diredges = trace_f_w(fwdist, adj, u, v)
                retval.append((diredges, [(u, v)]))
    return retval
