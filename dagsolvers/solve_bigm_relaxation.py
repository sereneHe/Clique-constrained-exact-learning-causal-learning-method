"""PPT Method E: scalar and edge-specific Big-M relaxations."""

import numpy as np

from dagsolvers import solve_milp_clique_core as core


class BigMRelaxationMethod(core.CliqueMethod):
    family_name = "bigm_relaxation"
    _scalar = {
        "E1": 10.0,
        "E6": 15.0,
        "E2": 20.0,
        "E7": 25.0,
        "E3": 50.0,
        "E4": 100.0,
    }

    def __init__(self, cfg):
        super().__init__(cfg)
        if self.variant not in {"E1", "E2", "E3", "E4", "E5", "E6", "E7"}:
            raise ValueError(
                "bigm_relaxation expects E1--E7, got "
                f"{self.variant!r}")

    def prepare_big_m(self, X, Y, global_bound):
        bound = self._scalar.get(self.variant, float(global_bound))
        d = X.shape[1]
        fallback = {(i, j): bound for i in range(d) for j in range(d) if i != j}
        if self.variant != "E5":
            return bound, "scalar", fallback, {
                "mode": "scalar", "fallback_count": 0,
            }
        if str(getattr(self.cfg, "loss_type", "l2")) != "l2" or bool(
                getattr(self.cfg, "robust", False)):
            return bound, "edge_specific", fallback, {
                "mode": "edge_specific", "fallback_count": len(fallback),
                "fallback_reason": "requires non-robust l2",
            }
        safety = float(getattr(self.cfg, "edge_specific_safety_factor", 1.01))
        condition_limit = float(
            getattr(self.cfg, "edge_specific_condition_limit", 1e10))
        zero_sse = float(np.sum(X ** 2))
        bounds = dict(fallback)
        fallback_count, condition_numbers = 0, []
        for target in range(d):
            contemporaneous = [i for i in range(d) if i != target]
            blocks = [X[:, contemporaneous]] + list(Y)
            design = np.concatenate(blocks, axis=1)
            gram = design.T @ design
            condition = float(np.linalg.cond(gram)) if gram.size else float("inf")
            condition_numbers.append(condition)
            if not np.isfinite(condition) or condition > condition_limit:
                fallback_count += len(contemporaneous)
                continue
            try:
                inverse = np.linalg.inv(gram)
                beta = inverse @ design.T @ X[:, target]
            except np.linalg.LinAlgError:
                fallback_count += len(contemporaneous)
                continue
            residual = X[:, target] - design @ beta
            radius_squared = max(zero_sse - float(residual @ residual), 0.0)
            for position, source in enumerate(contemporaneous):
                candidate = abs(float(beta[position])) + np.sqrt(max(
                    radius_squared * float(inverse[position, position]), 0.0))
                bounds[source, target] = min(
                    bound, max(1e-6, safety * candidate))
        values = np.asarray(list(bounds.values()), dtype=float)
        return bound, "edge_specific", bounds, {
            "mode": "edge_specific", "fallback_count": fallback_count,
            "min": float(np.min(values)),
            "p25": float(np.quantile(values, .25)),
            "median": float(np.median(values)),
            "p75": float(np.quantile(values, .75)),
            "max": float(np.max(values)),
            "max_condition_number": max(condition_numbers, default=None),
        }

    def initialize_model(self, model):
        model._big_m_candidate_count = 0
        model._big_m_near_bound_count = 0
        model._big_m_max_observed_ratio = 0.0
        model._big_m_small_x_large_w_count = 0
        model._big_m_saturation_tolerance = float(
            getattr(self.cfg, "big_m_saturation_tolerance", 0.98))

    def on_mipsol(self, model, selected_edges, edge_values, weight_values,
                  lag_edge_values, lag_weight_values, objective):
        model._big_m_candidate_count += 1
        for edge, value in weight_values.items():
            bound = model._edge_specific_bounds.get(edge, model._global_big_m)
            ratio = abs(float(value)) / max(float(bound), 1e-12)
            model._big_m_max_observed_ratio = max(
                model._big_m_max_observed_ratio, ratio)
            if edge_values[edge] > 0.5 and ratio >= model._big_m_saturation_tolerance:
                model._big_m_near_bound_count += 1
            if edge_values[edge] <= 0.1 and abs(float(value)) >= 0.5:
                model._big_m_small_x_large_w_count += 1
        return super().on_mipsol(
            model, selected_edges, edge_values, weight_values,
            lag_edge_values, lag_weight_values, objective)

    def summary_fields(self, model):
        return {"big_m_mode": model._big_m_mode,
                "weights_bound": model._global_big_m,
                "edge_bound_summary": model._edge_bound_summary,
                "candidate_count": model._big_m_candidate_count,
                "near_bound_count": model._big_m_near_bound_count,
                "max_observed_bound_ratio": model._big_m_max_observed_ratio,
                "small_x_large_w_count": model._big_m_small_x_large_w_count,
                "bound_safety_warning": bool(
                    model._big_m_near_bound_count > 0),
                "saturation_tolerance": model._big_m_saturation_tolerance}


def solve(*args, **kwargs):
    cfg = kwargs.get("cfg")
    kwargs["method"] = BigMRelaxationMethod(cfg)
    return core.solve(*args, **kwargs)
