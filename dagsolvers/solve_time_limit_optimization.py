"""PPT Method G: one continuous solve with explicit checkpoints."""

import numpy as np
from gurobipy import GRB

from dagsolvers import solve_milp_clique_core as core


class TimeLimitOptimizationMethod(core.CliqueMethod):
    family_name = "time_limit_optimization"
    _defaults = [5, 60, 120, 300, 600, 1200, 1800, 2700,
                 3600, 5400, 7200]

    def __init__(self, cfg):
        super().__init__(cfg)
        if self.variant != "G":
            raise ValueError(f"time_limit_optimization expects G, got {self.variant!r}")

    def initialize_model(self, model):
        values = list(getattr(self.cfg, "checkpoint_times", [])) or self._defaults
        model._checkpoint_times = sorted(float(value) for value in values)
        model._checkpoint_rows = []
        model._next_checkpoint_index = 0

    @staticmethod
    def _callback_time(model):
        return (model._cycle_detection_seconds + model._cycle_submission_seconds
                + model._clique_detection_seconds + model._clique_submission_seconds)

    def on_mip(self, model):
        runtime = float(model.cbGet(GRB.Callback.RUNTIME))
        while (model._next_checkpoint_index < len(model._checkpoint_times)
               and runtime >= model._checkpoint_times[model._next_checkpoint_index]):
            target = model._checkpoint_times[model._next_checkpoint_index]
            incumbent = float(model.cbGet(GRB.Callback.MIP_OBJBST))
            bound = float(model.cbGet(GRB.Callback.MIP_OBJBND))
            gap = (abs(incumbent - bound) / max(abs(incumbent), 1e-12)
                   if np.isfinite(incumbent) and np.isfinite(bound) else None)
            snapshot = model._best_accepted_snapshot
            model._checkpoint_rows.append({
                "checkpoint_target_seconds": target,
                "observed_runtime_seconds": runtime,
                "best_incumbent": incumbent, "best_bound": bound, "gap": gap,
                "explored_nodes": float(model.cbGet(GRB.Callback.MIP_NODCNT)),
                "open_nodes": float(model.cbGet(GRB.Callback.MIP_NODLFT)),
                "lp_iterations": float(model.cbGet(GRB.Callback.MIP_ITRCNT)),
                "solution_count": int(model.cbGet(GRB.Callback.MIP_SOLCNT)),
                "cycle_lazy_cuts": model._cycle_lazy_count,
                "clique_lazy_cuts": model._clique_lazy_count,
                "clique_user_cuts": model._clique_user_count,
                "callback_time": self._callback_time(model),
                "best_accepted_objective": (
                    snapshot["objective"] if snapshot else None),
                "best_accepted_edges": snapshot["edges"] if snapshot else None,
                "best_accepted_weights": snapshot["weights"] if snapshot else None,
                "best_accepted_nnz": snapshot["nnz"] if snapshot else None,
                "best_accepted_shd": snapshot["shd"] if snapshot else None,
                "best_accepted_f1": snapshot["f1"] if snapshot else None,
            })
            model._next_checkpoint_index += 1

    def finalize(self, model):
        runtime = float(model.Runtime)
        while (model._next_checkpoint_index < len(model._checkpoint_times)
               and runtime >= model._checkpoint_times[model._next_checkpoint_index]):
            target = model._checkpoint_times[model._next_checkpoint_index]
            snapshot = model._best_accepted_snapshot
            has_solution = int(model.SolCount) > 0
            model._checkpoint_rows.append({
                "checkpoint_target_seconds": target,
                "observed_runtime_seconds": runtime,
                "best_incumbent": float(model.ObjVal) if has_solution else None,
                "best_bound": float(model.ObjBound),
                "gap": float(model.MIPGap) if has_solution else None,
                "explored_nodes": float(model.NodeCount), "open_nodes": None,
                "lp_iterations": float(model.IterCount),
                "solution_count": int(model.SolCount),
                "cycle_lazy_cuts": model._cycle_lazy_count,
                "clique_lazy_cuts": model._clique_lazy_count,
                "clique_user_cuts": model._clique_user_count,
                "callback_time": self._callback_time(model),
                "best_accepted_objective": (
                    snapshot["objective"] if snapshot else None),
                "best_accepted_edges": snapshot["edges"] if snapshot else None,
                "best_accepted_weights": snapshot["weights"] if snapshot else None,
                "best_accepted_nnz": snapshot["nnz"] if snapshot else None,
                "best_accepted_shd": snapshot["shd"] if snapshot else None,
                "best_accepted_f1": snapshot["f1"] if snapshot else None,
            })
            model._next_checkpoint_index += 1

    def summary_fields(self, model):
        return {"checkpoints": model._checkpoint_rows}


def solve(*args, **kwargs):
    cfg = kwargs.get("cfg")
    kwargs["method"] = TimeLimitOptimizationMethod(cfg)
    return core.solve(*args, **kwargs)
