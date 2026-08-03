import os
import numpy as np

def solve_nts_notears(X, Y, p, cfg):
    import torch
    from dagsolvers.solvers.nts_notears.nts_notears import train_NTS_NOTEARS, NTS_NOTEARS

    torch.set_default_dtype(torch.double)
    #np.set_printoptions(precision=3)

    number_of_lags = p
    n, s0 = X.shape
    d = s0

    variable_names_no_time = ['X{}'.format(j) for j in range(1, d + 1)]
    #variable_names = make_variable_names_with_time_steps(number_of_lags, variable_names_no_time)

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print('\nUsing device: {}\n'.format(device))

    w_threshold = 0.3

    prior_knowledge = None

    model = NTS_NOTEARS(dims=[d, 10, 1], bias=True, number_of_lags=number_of_lags,
                        prior_knowledge=prior_knowledge, variable_names_no_time=variable_names_no_time)


    W_est_full = train_NTS_NOTEARS(model, X, device=device, lambda1=cfg.lambda1, lambda2=cfg.lambda2,
                                   w_threshold=w_threshold, h_tol=1e-60, verbose=1)

    W_est = W_est_full[p * d:, -d:]

    A_est = []
    for i in range(p):
        A_est.append(W_est_full[i * d:(i + 1) * d, -d:])
    A_est.reverse()

    return W_est, A_est

