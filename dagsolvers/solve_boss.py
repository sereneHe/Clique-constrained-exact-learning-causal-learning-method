from os.path import join, isfile
from os import listdir
import subprocess
import numpy as np
import json

def write_data(file_name, X, variable_names):
    header = '\t'.join(variable_names)
    np.savetxt(file_name, X, delimiter='\t', header=header, comments='')

def read_data(file_name, variable_names):
    d = len(variable_names)
    d_idx = {name: i for i, name in enumerate(variable_names)}
    with open(file_name) as f:
        W_est_json = json.load(f)
    edges = W_est_json['edgesSet']
    W_est = np.zeros((d,d))
    for edge in edges:
        from_idx = d_idx[edge['node1']['name']] # row index
        to_idx = d_idx[edge['node2']['name']] # column index
        if edge['endpoint1'] == 'TAIL' and edge['endpoint2'] == 'ARROW':
            W_est[from_idx, to_idx] = 1
        elif edge['endpoint1'] == 'TAIL' and edge['endpoint2'] == 'TAIL':
            W_est[from_idx, to_idx] = 1
            #W_est[to_idx, from_idx] = 1
        else:
            assert False

    return W_est


def solve_boss(X, work_dir, boss_cmd):
    _, d = X.shape
    variable_names = [f'v{rnd_var_index}' for rnd_var_index in range(d)]
    write_data(join(work_dir, 'dataset.txt'), X, variable_names)
    ret = subprocess.run(boss_cmd.split(' '), cwd=work_dir)
    assert ret.returncode == 0

    output_files = [f for f in listdir(work_dir) if isfile(join(work_dir, f)) and f.startswith('boss_') and f.endswith('_graph.json')]
    assert len(output_files) == 1
    W_est = read_data(join(work_dir, output_files[0]), variable_names)

    return W_est
