import numpy as np
from omegaconf import DictConfig

from dagsolvers.solvers.IP4AncADMG.test_latent_scores import generate_scores_bidirect


def solve_ip4ancadmg(X, cfg: DictConfig):
    # Code for the paper "Integer Programming for Causal Structure Learning in the Presence of Latent Variables" (https://proceedings.mlr.press/v139/chen21c.html

    from dagsolvers.solvers.IP4AncADMG.LearnLatent import BNSLlvInst


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

    inst = BNSLlvInst('instance')
    inst.set_data(observed_data, scores)
    inst.Initialize(prune=True,dag=True, max_time=cfg.time_limit)
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
