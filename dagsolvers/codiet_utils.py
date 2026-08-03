from os.path import join
import os
import re

import numpy as np


def unify_names(name):
    name = name.lower()
    name = re.sub(" ", "-", name)
    name = re.sub("--", "-", name)
    name = re.sub("-/-", "/", name)
    name = name.replace(".", "-")
    name = re.sub("_", "-", name)
    return name


def load_data(cfg):
    import networkx as nx
    import polars as pl
    SOURCE_DIR = cfg.data_path # '/Users/pavel/0_code/0_causal/codiet_data'

    G = nx.read_graphml(join(SOURCE_DIR, cfg.knowledge_graph_filename))
    #G = nx.relabel_nodes(G, lambda x: unify_names(x)) # !!! this may need to be readded

    #df = pd.read_feather(join(SOURCE_DIR, "features.feather"))
    df = pl.read_ipc(join(SOURCE_DIR, cfg.data_filename))
    #df = df.fillna(0)
    df = df.fill_null(0)
    df = df.select(pl.selectors.numeric())
    if cfg.scale_data == 'mean':
        df = df.with_columns(pl.selectors.numeric() / pl.selectors.numeric().abs().mean())
    elif cfg.scale_data == 'max':
        df = df.with_columns(pl.selectors.numeric() / pl.selectors.numeric().abs().max())
    elif cfg.scale_data == 'quantile09':
        #df = df / df.abs().quantile(0.95)
        df = df.with_columns(
            pl.selectors.numeric() / pl.selectors.numeric().abs().quantile(0.95))
        # df = df.replace("NaN", 0)
        # df = df.astype(float).fillna(0)
        # df = df.fillna(0)
    df = df.with_columns([
        pl.when(pl.col(c).is_infinite()).then(0).otherwise(pl.col(c)).alias(c)
        for c in df.columns
    ])
    df = df.fill_null(0)
    df = df.fill_nan(0)

    if len(df) > 1:
        df = df.select([
            col for col in df.columns if df[col].n_unique() > 1
        ])
    #df = df.to_pandas()
    df_abs = df.with_columns(pl.selectors.numeric().abs())
    overall_max = df_abs.max().select(pl.max_horizontal(pl.all())).item()
    print(overall_max)
    #print(df.abs().max().max())
    print('recommended max weight')
    df_abs_mean = df_abs.mean()
    max_of_means = df_abs_mean.select(pl.max_horizontal(pl.all())).item()
    min_of_means = df_abs_mean.select(pl.min_horizontal(pl.all())).item()
    if min_of_means > 0:
        print(max_of_means / min_of_means)

    #print(df.abs().mean().max()/df.abs().mean().min())


    # Remove non-numeric columns!
    #df = df.select_dtypes(include=["number"])
    features = cfg.get('features')
    if features is not None:
        df = df.select(features)


    # df = df.dropna(axis=1, how="any")
    # df = df.dropna(axis=0, how="any")

    n = cfg.get('n')
    if n is not None:
        df = df.sample(n=n, seed=42, shuffle=True)
        #df = df.sample(n=n, random_state=42)  # keeping only 2k samples to fit into memory ...


    #df = df / df.abs().max()

    print(f"Shape: {df.shape}")
    print(df.head())
    #print(f"Forbidden edges: {H.number_of_edges()} on {H.number_of_nodes()} vertices")

    # zero one normalization and intercept term - did not work well

        #df = df.loc[:, df.nunique() > 1]
    # df = (df - df.mean(numeric_only=True)) / df.std(numeric_only=True)
    # df["intercept"] = 1.0

    print(df.head())
    col_to_idx = {col: idx for idx, col in enumerate(df.columns)}
    intra_nodes = list(df.columns)
    # print(intra_nodes)
    # print(G.nodes)
    # select only relevatn columns and forbid those non
    H = G.subgraph(intra_nodes).copy()
    print(f"Subgraph size: {H.number_of_edges()}")
    H = nx.complement(H)

    print("Done loading")
    print(f"Nodes: {H.nodes}")

    tabu_edges = list((col_to_idx[s],col_to_idx[e]) for (s,e) in H.edges())


    X = df.to_numpy()

    n, d = X.shape

    # W_est, _, _, stats, m = solve(df, forbidden_edges=H, forbid_both=True, lambda1=0, loss_type='l1', reg_type='l1',
    #                               w_threshold=-np.inf, B_ref=None, mode='all_cycles', weights_bound=1e10)
    W_true = np.zeros((d, d))  # TODO: get the ground truth
    A_true = []
    B_lags_true = []
    Y = []
    inter_nodes = None
    return W_true, W_true, A_true, B_lags_true, X, Y, intra_nodes, inter_nodes, tabu_edges