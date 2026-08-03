import os

import numpy as np
import pandas as pd
from os.path import join


from structure.transformers import DynamicDataTransformer


def read_graph(graph_file):
    with open(graph_file, "r") as file:
        lines = file.readlines()
    groundtruth = [tuple(line.strip().split()) for line in lines]
    return set(groundtruth)

def create_adj_matrix(vertices, edges, p):
    A = np.zeros((len(vertices), len(vertices)))
    A_inter = [np.zeros((len(vertices), len(vertices))) for _ in range(p)]
    for row_idx, row in enumerate(vertices):
        for col_idx, column in enumerate(vertices):
            if (f'{row}_lag0', f'{column}_lag0') in edges:
                A[row_idx, col_idx] = 1
            for layer in range(p):
                if (f'{row}_lag{layer+1}', f'{column}_lag0') in edges:
                    A_inter[layer][row_idx, col_idx] = 1
    assert len(edges) == A.sum() + sum(A_i.sum() for A_i in A_inter)
    return A, A_inter


def load_data(variant, measurements, p, path):
    data_dir = join(path,variant)
    files_list = [entry.name for entry in os.scandir(data_dir) if entry.is_file()]
    files_list.sort()
    #files_list = join(path, f'{variant}.txt')

    ground_truth_file = join(path,f'groundtruth-{variant}.txt')
    #with open(files_list, 'r') as file:
    #    lines = file.readlines()
    files = [join(data_dir, line.strip()) for line in files_list]
    #files = files_list
    data = [pd.read_table(file, header=None, index_col=0).transpose() for file in files[:measurements]]
    # variables = data[0].columns
    # variables = [f'{v}'.strip() for v in variables]
    # intra_nodes = [f'{v}_lag0' for v in variables]
    # inter_nodes = [f'{v}_lag1' for v in variables]
    # #p = 1

    df = DynamicDataTransformer(p=p).fit_transform(data, return_df=True)
    variables = df.columns
    intra_nodes = [v for v in variables if '_lag0' in v]
    inter_nodes = [v for v in variables if '_lag0' not in v]
    vertices = [n.replace('_lag0','') for n in intra_nodes]

    df_x = df[intra_nodes]
    X = df_x.to_numpy()
    df_x_lag = df[inter_nodes]
    X_lag = df_x_lag.to_numpy() # for dynotears

    Y = []
    for lag in range(1, p + 1):
        lag_cols = [c for c in inter_nodes if f'_lag{lag}' in c]
        df_x_lag = df[lag_cols]
        Y_lag = df_x_lag.to_numpy()
        Y.append(Y_lag)

    #X, Xlags = DynamicDataTransformer(p=p).fit_transform(data, return_df=False)

    gts = read_graph(ground_truth_file)
    A, A_inter = create_adj_matrix(vertices, gts, p)

    return A, A, A_inter, A_inter, X, Y, X_lag, intra_nodes, inter_nodes


