import numpy as np
from omegaconf import DictConfig


def solve_ipbm(X, cfg: DictConfig):
    # Code for the paper "Integer Programming Based Methods and Heuristics for Causal Graph Learning
    # Sanjeeb Dash, Joao Goncalves, Tian Gao
    from dagsolvers.solvers.IPBMandHforCGL.test_latent_scores import generate_scores_bidirect
    from dagsolvers.solvers.IPBMandHforCGL.learn import BNSLlvInst


    observed_data = X
    num_sample, num_var = observed_data.shape


    c_size = cfg.c_size # 2
    if c_size is None:
        c_size = num_var
    single_parent_size = cfg.single_parent_size # 3
    if single_parent_size is None:
        single_parent_size = num_var - 1
    other_c_parent_size = cfg.other_c_parent_size # 1
    if other_c_parent_size is None:
        other_c_parent_size = num_var - 1
    #file_name = '../Instances/data/score_' + dataset[:-4]
    #print(file_name)


    scores = generate_scores_bidirect(observed_data,
                                      single_c_parent_size = single_parent_size,
                                      other_c_parent_size = other_c_parent_size,
                                      c_size = c_size,
                                      file_name = None)

    inst = BNSLlvInst('instance', None, None, cfg.heuristics, cfg.cuts, cfg.time_limit, cfg.bowfree, cfg.arid)
    inst.set_data(observed_data, scores)
    inst.Initialize(prune=True,dag=True)
    inst.Solve_with_cb()

    D, B = inst.get_graph()

    Wbi_est = np.zeros((len(B),len(B)))
    W_est = np.zeros((len(D),len(D)))

    for i in range(len(D)):
        for j in range(len(D[i])):
            if D[i][j] == 1: # i -> j
                W_est[i][j] = 1

    for i in range(len(B)):
        for j in range(len(B[i])):
            if B[i][j] == 1: # i -> j
                Wbi_est[i][j] = 1


    return W_est, Wbi_est
