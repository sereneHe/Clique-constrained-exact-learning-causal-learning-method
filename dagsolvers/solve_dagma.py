from omegaconf import DictConfig


def solve_dagma(X, cfg: DictConfig):
    from dagma.linear import DagmaLinear
    model = DagmaLinear(loss_type=cfg.loss_type) # create a linear model with least squares loss
    W_est = model.fit(X, lambda1=cfg.lambda1)
    return W_est
