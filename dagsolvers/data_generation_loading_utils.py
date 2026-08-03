import random
from os.path import join
from pathlib import Path
import networkx as nx
import numpy as np
from omegaconf import DictConfig

from dagsolvers import sachs_utils, krebs_utils, admg_generators
from dagsolvers.dagsolver_utils import ExDagDataException
from notears import utils


REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_categorical_bn_benchmark(cfg: DictConfig):
    """Load a fixed categorical BN sample and its reference DAG.

    The stored CSV contains integer state codes.  Different experiment seeds
    select deterministic subsets of the same public-network sample so the
    solver methods see exactly the same rows for a given seed.
    """
    name = _normalized_problem_name(cfg.problem.name)
    data_dir = Path(cfg.problem.get('data_path', REPO_ROOT / 'datasets' / name))
    if not data_dir.is_absolute():
        data_dir = REPO_ROOT / data_dir

    samples_path = data_dir / 'samples_seed2027_n5000.csv'
    adjacency_path = data_dir / 'adjacency.csv'
    variables_path = data_dir / 'variables.txt'
    for path in (samples_path, adjacency_path, variables_path):
        if not path.exists():
            raise ExDagDataException(f'Missing {name} benchmark file: {path}')

    import pandas as pd

    frame = pd.read_csv(samples_path)
    variables = [line.strip() for line in variables_path.read_text().splitlines() if line.strip()]
    if list(frame.columns) != variables:
        raise ExDagDataException(f'{name} sample columns do not match variables.txt')

    adjacency = pd.read_csv(adjacency_path, index_col=0).loc[variables, variables].to_numpy(dtype=float)
    requested = int(cfg.problem.get('number_of_samples', len(frame)))
    if requested <= 0 or requested > len(frame):
        raise ExDagDataException(
            f'{name}.number_of_samples must be in [1, {len(frame)}], got {requested}'
        )
    rng = np.random.default_rng(int(cfg.problem.get('seed', 0)))
    rows = rng.permutation(len(frame))[:requested]
    X = frame.iloc[rows].to_numpy(dtype=float)
    return X, adjacency, variables


def _maybe_load_static_npz(cfg: DictConfig):
    # Static .npz fixtures are intentionally ignored so every experiment
    # regenerates data from cfg.problem.seed and the current generator logic.
    return None

def normalize_data(X, Y):
    mean = np.mean(X, axis=0)
    std = np.std(X, axis=0)
    X = X - mean
    X = X / std

    for i, _ in enumerate(Y):
        Y[i] = Y[i] - mean
        Y[i] = Y[i] / std

    return X, Y


def _normalized_problem_name(name):
    return str(name).strip().lower().replace('-', '_')


def _problem_lag_order(cfg: DictConfig):
    try:
        return int(cfg.problem.get('p', 0) or 0)
    except (TypeError, ValueError):
        return 0


def _base_graph_type_for_problem(normalized_graph_type):
    if normalized_graph_type.startswith('cliquefree_'):
        return normalized_graph_type.replace('cliquefree_', '')
    return normalized_graph_type


def _use_dynamic_generation(graph_type, normalized_graph_type, cfg: DictConfig):
    if graph_type == 'dynamic':
        return True
    return _problem_lag_order(cfg) > 0 and _base_graph_type_for_problem(normalized_graph_type) in {'er', 'sf'}


def _simulate_static_problem(cfg: DictConfig, run, graph_type, normalized_graph_type, tabu_edges):
    d = cfg.problem.number_of_variables
    n = cfg.problem.number_of_samples
    edge_ratio = cfg.problem.get('intra_edge_ratio', cfg.problem.get('edge_ratio'))
    s0 = edge_ratio * d if edge_ratio is not None else None
    sem_type = cfg.problem.sem_type
    noise_scale = cfg.problem.noise_scale
    noise_scale_variance = cfg.problem.get('noise_scale_variance', None)
    if noise_scale_variance is not None:
        noise_scale = [random.uniform(noise_scale - noise_scale_variance, noise_scale + noise_scale_variance) for _ in range(d)]
    cached = _maybe_load_static_npz(cfg)
    if cached is not None:
        npz_path, W_true, B_true, X = cached
        if run is not None:
            try:
                run.log_text(str(npz_path), 'cached_dataset.txt')
            except Exception:
                pass
        Y = []
        A_true = []
        B_lags_true = []
        W_bi_true = None
        B_bi_true = None
        intra_nodes = [f'node_{i}' for i in range(X.shape[1])]
        inter_nodes = []
        return W_true, W_bi_true, B_true, B_bi_true, A_true, B_lags_true, X, Y, tabu_edges, intra_nodes, inter_nodes

    base_graph_type = _base_graph_type_for_problem(normalized_graph_type).upper()
    clique_limit = None
    if normalized_graph_type.startswith('cliquefree_'):
        clique_limit = int(cfg.problem.get('clique_limit', 5))
        if run is not None:
            run.log_param('clique_limit', clique_limit)
    if run is not None and edge_ratio is not None:
        run.log_param('effective_edge_ratio', edge_ratio)
    try:
        B_true = utils.simulate_dag(d, s0, base_graph_type)
        if clique_limit is not None:
            B_true = _break_large_cliques(B_true, clique_limit)
    except Exception as e:
        error_prefix = 'clique-free samples' if clique_limit is not None else 'samples'
        if run is not None:
            run.log_text(f'Error: Cannot generate {error_prefix} data. Exception: {e}', 'error.txt')
        raise ExDagDataException(e)

    if cfg.problem.get('only_01', False):
        W_true = B_true
    elif cfg.problem.get('only_positive', False):
        W_true = utils.simulate_parameter(B_true, w_ranges=((0.5, 2.0),))
    else:
        W_true = utils.simulate_parameter(B_true)
    X = utils.simulate_linear_sem(
        W_true,
        n,
        sem_type,
        noise_scale=noise_scale,
        internal_normalization=cfg.problem.get('internal_normalization', False),
    )
    Y = []
    A_true = []
    B_lags_true = []
    W_bi_true = None
    B_bi_true = None
    return W_true, W_bi_true, B_true, B_bi_true, A_true, B_lags_true, X, Y, tabu_edges, None, None


def _simulate_dynamic_problem(cfg: DictConfig, run, graph_type, normalized_graph_type):
    p = _problem_lag_order(cfg)
    d = cfg.problem.number_of_variables
    n = cfg.problem.number_of_samples
    degree_intra = cfg.problem.intra_edge_ratio * 2
    degree_inter = cfg.problem.inter_edge_ratio * 2
    w_max_inter = cfg.problem.w_max_inter
    w_min_inter = cfg.problem.w_min_inter
    w_decay = cfg.problem.w_decay
    if p == 0:
        degree_inter = 0

    if graph_type == 'dynamic':
        variant = cfg.problem.graph_type_intra
    else:
        variant = _base_graph_type_for_problem(normalized_graph_type)

    if variant == 'er':
        graph_type_intra = 'erdos-renyi'
    elif variant == 'sf':
        graph_type_intra = 'barabasi-albert'
    else:
        raise ExDagDataException(f"Unknown intra-slice graph type '{variant}'")

    graph_type_inter = cfg.problem.get('graph_type_inter', 'er')
    if graph_type_inter == 'er':
        graph_type_inter = 'erdos-renyi'

    clique_limit = None
    max_attempts = 100
    if normalized_graph_type.startswith('cliquefree_'):
        clique_limit = int(cfg.problem.get('clique_limit', 5))
        if run is not None:
            run.log_param('clique_limit', clique_limit)

    try:
        generator = cfg.problem.generator
        noise_scale = cfg.problem.noise_scale
        noise_scale_variance = cfg.problem.get('noise_scale_variance', None)
        if noise_scale_variance is not None:
            noise_scale_vector = [random.uniform(noise_scale - noise_scale_variance, noise_scale + noise_scale_variance) for _ in range(d)]
        else:
            noise_scale_vector = [noise_scale] * d
        from structure.data_generators import gen_stationary_dyn_net_and_df
        for attempt in range(max_attempts):
            g, df, intra_nodes, inter_nodes = gen_stationary_dyn_net_and_df(
                num_nodes=d,
                n_samples=n,
                p=p,
                degree_intra=degree_intra,
                degree_inter=degree_inter,
                graph_type_intra=graph_type_intra,
                graph_type_inter=graph_type_inter,
                w_max_intra=cfg.problem.w_max_intra,
                w_min_intra=cfg.problem.w_min_intra,
                w_min_inter=w_min_inter,
                w_max_inter=w_max_inter,
                w_decay=w_decay,
                noise_scale=noise_scale_vector,
                max_data_gen_trials=1000,
                generator=generator,
            )
            if clique_limit is None:
                break
            intra_adjacency = nx.to_numpy_array(g, nodelist=intra_nodes)
            intra_binary = (intra_adjacency != 0).astype(int)
            if _max_undirected_clique_size(intra_binary, limit=clique_limit + 1) <= clique_limit:
                break
        else:
            raise ExDagDataException(
                f'Could not generate a dynamic {normalized_graph_type} graph with clique size <= {clique_limit} '
                f'after {max_attempts} attempts'
            )
    except Exception as e:
        if run is not None:
            run.log_text(f'Error: Cannot generate samples data. Exception: {e}', 'error.txt')
            run.log_metric('infeasible', True)
        raise ExDagDataException(e)

    W_true = nx.to_numpy_array(g, nodelist=intra_nodes)
    B_true = (W_true != 0).astype(int)
    a_mat = nx.to_numpy_array(g, nodelist=intra_nodes + inter_nodes)[len(intra_nodes):, :len(intra_nodes)]
    df_x = df[intra_nodes]
    X = df_x.to_numpy()
    W_bi_true = None
    B_bi_true = None

    Y = []
    A_true = []
    B_lags_true = []
    for lag in range(1, p + 1):
        lag_cols = [c for c in inter_nodes if f'_lag{lag}' in c]
        df_x_lag = df[lag_cols]
        Y_lag = df_x_lag.to_numpy()
        Y.append(Y_lag)

        idxs = [f'_lag{lag}' in c for c in inter_nodes]
        a_mat_lag = a_mat[idxs, :]
        b_mat_lag = (a_mat_lag != 0).astype(int)
        A_true.append(a_mat_lag)
        B_lags_true.append(b_mat_lag)

    return W_true, W_bi_true, B_true, B_bi_true, A_true, B_lags_true, X, Y, [], intra_nodes, inter_nodes


def _max_undirected_clique_size(adjacency_matrix, limit=None):
    skeleton = nx.from_numpy_array((np.asarray(adjacency_matrix) != 0).astype(int))
    max_size = 0
    for clique in nx.find_cliques(skeleton):
        clique_size = len(clique)
        if clique_size > max_size:
            max_size = clique_size
            if limit is not None and max_size >= limit:
                return max_size
    return max_size


def _turan_max_edges(num_nodes, clique_limit):
    # Maximum edges in a K_clique_limit-free graph on num_nodes vertices.
    if clique_limit is None or clique_limit <= 1:
        return 0
    parts = clique_limit - 1
    base = num_nodes // parts
    remainder = num_nodes % parts
    sizes = [base + 1] * remainder + [base] * (parts - remainder)
    return num_nodes * (num_nodes - 1) // 2 - sum(size * (size - 1) // 2 for size in sizes)


def _choose_edge_to_break_clique(B_work, clique):
    clique = list(clique)
    subgraph = nx.DiGraph(B_work).subgraph(clique).copy()
    if subgraph.number_of_edges() > 0 and nx.is_directed_acyclic_graph(subgraph):
        path = nx.dag_longest_path(subgraph)
        if len(path) >= 2:
            mid = len(path) // 2
            u, v = path[mid - 1], path[mid]
            if B_work[u, v] != 0:
                return (u, v), len(path)
            if B_work[v, u] != 0:
                return (v, u), len(path)

    candidate_edges = []
    for idx, u in enumerate(clique):
        for v in clique[idx + 1 :]:
            if B_work[u, v] != 0:
                candidate_edges.append((u, v))
            elif B_work[v, u] != 0:
                candidate_edges.append((v, u))
    if candidate_edges:
        return random.choice(candidate_edges), 0
    return None, 0


def _break_large_cliques(B_true, clique_limit, max_iterations=1000):
    B_work = np.array(B_true, copy=True)
    for _attempt in range(max_iterations):
        large_cliques = [
            list(candidate)
            for candidate in nx.find_cliques(nx.from_numpy_array((B_work != 0).astype(int)))
            if len(candidate) > clique_limit
        ]
        if not large_cliques:
            return B_work

        best_edge = None
        best_path_len = 0
        for clique in large_cliques:
            edge, path_len = _choose_edge_to_break_clique(B_work, clique)
            if edge is None:
                continue
            if path_len > best_path_len:
                best_path_len = path_len
                best_edge = edge

        if best_edge is None:
            break

        u, v = best_edge
        B_work[u, v] = 0

    raise ExDagDataException(f'Could not break cliques down to size < {clique_limit} after {max_iterations} edge removals')


def _simulate_dag_with_clique_limit(d, s0, graph_type, clique_limit=None, max_attempts=1000):
    for _attempt in range(max_attempts):
        B_true = utils.simulate_dag(d, s0, graph_type)
        if clique_limit is None:
            return B_true
        if _max_undirected_clique_size(B_true, limit=clique_limit + 1) <= clique_limit:
            return B_true
    raise ExDagDataException(
        f'Could not generate a {graph_type} DAG with clique size <= {clique_limit} after {max_attempts} attempts'
    )

def load_problem(cfg: DictConfig, run):
    graph_type = cfg.problem.name
    normalized_graph_type = _normalized_problem_name(graph_type)
    #run.log_param('problem', graph_type)
    tabu_edges = []
    intra_nodes = None
    inter_nodes = None #TODO: all problems should define this
    if graph_type == 'cds':
        from dagsolvers import cds_utils
        W_true, B_true, A_true, B_lags_true, X, Y, intra_nodes, inter_nodes, tabu_edges = cds_utils.load_data(cfg.problem.n, cfg.problem.granularity, cfg.problem.p, cfg.problem.data_path)
        W_bi_true = np.zeros_like(W_true)
        B_bi_true = np.zeros_like(B_true)
    elif graph_type == 'codiet':
        from dagsolvers import codiet_utils
        W_true, B_true, A_true, B_lags_true, X, Y, intra_nodes, inter_nodes, tabu_edges = codiet_utils.load_data(cfg.problem)
        W_bi_true = np.zeros_like(W_true)
        B_bi_true = np.zeros_like(B_true)
    elif graph_type == 'krebs':
        p = cfg.problem.p
        measurements = cfg.problem.measurements
        variant = cfg.problem.variant
        #run.log_param('measurements', measurements)
        #run.log_param('variant', variant)
        W_true, B_true, A_true, B_lags_true, X, Y, X_lag, intra_nodes, inter_nodes = krebs_utils.load_data(variant, measurements, p, cfg.problem.data_path)
        W_bi_true = None
        B_bi_true = None
        #n, d = X.shape

    elif graph_type == 'Sachs':
        variant = cfg.problem.variant
        #run.log_param('variant', variant)
        #normalize = cfg.problem.get('normalize')
        #run.log_param('normalize', normalize)
        X, B_true, W_true = sachs_utils.load_data(variant, False, cfg.problem.data_path)
        # n, d = X.shape
        # p = 0
        Y = []
        A_true = []
        B_lags_true = []
        W_bi_true = None
        B_bi_true = None

    elif graph_type == 'bnlearn' or graph_type == 'nips2023':
        #run.log_param('variant', cfg.problem.variant)
        if graph_type == 'bnlearn':
            n = cfg.problem.get('number_of_samples')
            # normalize = cfg.problem.get('normalize', False)
            # run.log_param('normalize', normalize)
            from dagsolvers import bnlearn_utils
            X, W_true = bnlearn_utils.load_dataset(cfg.problem.variant, n=n, normalize=False)
        elif graph_type == 'nips2023':
            from dagsolvers import nips_comp_utils
            X, W_true = nips_comp_utils.load_dataset(cfg.problem.variant, cfg.problem.data_path)
        else:
            assert False
        B_true = W_true
        # n, d = X.shape
        # p = 0
        Y = []
        A_true = []
        B_lags_true = []
        W_bi_true = None
        B_bi_true = None

    elif normalized_graph_type in {'child', 'insurance', 'alarm'}:
        X, W_true, intra_nodes = _load_categorical_bn_benchmark(cfg)
        B_true = (W_true != 0).astype(int)
        Y = []
        A_true = []
        B_lags_true = []
        W_bi_true = None
        B_bi_true = None

    elif graph_type == 'dynamic' or normalized_graph_type in {'er', 'sf', 'path', 'pathperm', 'g2', 'cliquefree_er', 'cliquefree_sf'}:
        if _use_dynamic_generation(graph_type, normalized_graph_type, cfg):
            W_true, W_bi_true, B_true, B_bi_true, A_true, B_lags_true, X, Y, tabu_edges, intra_nodes, inter_nodes = _simulate_dynamic_problem(
                cfg, run, graph_type, normalized_graph_type
            )
        else:
            W_true, W_bi_true, B_true, B_bi_true, A_true, B_lags_true, X, Y, tabu_edges, intra_nodes, inter_nodes = _simulate_static_problem(
                cfg, run, graph_type, normalized_graph_type, tabu_edges
            )

    elif graph_type == 'ermag':
        d = cfg.problem.number_of_variables
        n = cfg.problem.number_of_samples
        edge_ratio = cfg.problem.get('edge_ratio', 1)
        run.log_param('edge_ratio', edge_ratio)
        s0 = edge_ratio * d
        sem_type = cfg.problem.sem_type
        noise_scale = cfg.problem.get('noise_scale', 1.0)
        tabu_edges_ratio = cfg.problem.get('tabu_edges_ratio', 0.2)
        hidden_vertices_ratio = cfg.problem.get('hidden_vertices_ratio', 0.2)
        run.log_param('sem_type', sem_type)
        run.log_param('noise_scale', noise_scale)
        try:
            B_true = utils.simulate_dag(d, s0, "ER")
        except Exception as e:
            run.log_text(f'Error: Cannot generate samples data. Exception: {e}', 'error.txt')
            run.log_metric('infeasible', True)
            raise ExDagDataException(e)

        if cfg.problem.get('only_01', False):
            W_true = B_true
        elif cfg.problem.get('only_positive', False):
            W_true = utils.simulate_parameter(B_true, w_ranges=((0.5, 2.0),))
        else:
            W_true = utils.simulate_parameter(B_true)
        X = utils.simulate_linear_sem(W_true, n, sem_type, noise_scale=noise_scale)
        Y = []
        A_true = []
        B_lags_true = []


        # p = 0

        new_d = int(d * (1-hidden_vertices_ratio))
        indices = np.random.choice(range(d), size=new_d, replace=False)
        d = new_d
        X = X[:, indices]
        W_true = W_true[np.ix_(indices, indices)]
        B_true = B_true[np.ix_(indices, indices)]
        B_bi_true = np.zeros_like(B_true)
        for i in range(d):
            for j in range(i):
                if W_true[i, j] == 0.0 and W_true[j, i] == 0.0:
                    if np.random.rand() < tabu_edges_ratio:
                        tabu_edges.append((i, j))
                        B_bi_true[i, j] = 1.0
                        B_bi_true[j, i] = 1.0 # Maybe dubious.

        W_bi_true = np.copy(B_bi_true)

    elif graph_type == 'bowfree_admg':
        B_true, B_bi_true, tabu_edges, X = admg_generators.generate_graph_and_samples(cfg.problem.number_of_variables,cfg.problem.pdir, cfg.problem.pbidir, cfg.problem.max_in_arrows, cfg.problem.number_of_samples, cfg.problem.enforce_mag)
        W_true = B_true
        W_bi_true = B_bi_true
        Y = []
        A_true = []
        B_lags_true = []

    elif graph_type == 'admissions':
        import pandas as pd
        from sklearn.preprocessing import LabelEncoder
        file_path = cfg.problem.data_path
        df = pd.read_csv(file_path, sep=';')
        encoder = LabelEncoder()
        for col in ['gender', 'admit']:
            df[col] = encoder.fit_transform(df[col])
        #del df['gender']
        #df['gender'] = df['gender']
        #df['admit'] = 2 * df['admit']
        df = pd.get_dummies(df, columns=['department'], prefix='D', dtype=int)
        # for col in df.columns:
        #     if 'department' in col:
        #         df[col] = df[col] * 0.5
        # print(df.to_string())

        X = df.to_numpy()
        intra_nodes = df.columns.tolist()

        W_true = np.zeros((X.shape[1], X.shape[1]))
        B_true = np.zeros((X.shape[1], X.shape[1]))
        A_true = []
        B_lags_true = []
        Y = []
        W_bi_true = np.zeros((X.shape[1], X.shape[1]))
        B_bi_true = np.zeros((X.shape[1], X.shape[1]))
        tabu_edges = [(0,1),(1,0)]
    
    elif graph_type == 'load_from_file':
        assert False, 'implement me'

    else:
        assert False, 'unknown problem'
        
    # Generating default node names.
    if intra_nodes is None:
        intra_nodes = [f'node_{i}' for i in range(len(X[0]))]
    if inter_nodes is None:
        inter_nodes = [f'node_{i}_lag_{lag}' for lag in range(1, cfg.problem.get('p', 0) + 1) for i in range(len(X[0]))]
    
    return W_true, W_bi_true, B_true, B_bi_true, A_true, B_lags_true, X, Y, tabu_edges, intra_nodes, inter_nodes
