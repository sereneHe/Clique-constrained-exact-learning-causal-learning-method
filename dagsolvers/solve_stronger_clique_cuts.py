"""PPT Method F: compare maximal and stronger (k+1) clique lazy cuts."""

import itertools

from dagsolvers import solve_milp_clique_core as core


def _candidate(nodes, edge_values):
    nodes = tuple(sorted(nodes))
    pairs = list(itertools.combinations(nodes, 2))
    lhs = sum(float(edge_values[i, j]) + float(edge_values[j, i])
              for i, j in pairs)
    rhs = len(pairs) - 1
    return {"nodes": nodes, "pairs": pairs, "rhs": rhs,
            "violation": float(lhs - rhs),
            "efficiency": float((lhs - rhs) / max(len(pairs), 1))}


class StrongerCliqueCutsMethod(core.CliqueMethod):
    family_name = "stronger_clique_cuts"

    def __init__(self, cfg):
        super().__init__(cfg)
        if self.variant not in {"F1", "F2", "F3", "F4"}:
            raise ValueError(f"stronger_clique_cuts expects F1--F4, got {self.variant!r}")

    def integer_clique_candidates(self, model, selected_edges, edge_values):
        maximals = core._maximal_cliques(
            selected_edges, model._d, model._max_clique_size)
        if self.variant == "F1":
            node_sets = sorted(maximals, key=lambda nodes: (-len(nodes), nodes))
        else:
            k = model._max_clique_size
            node_sets = sorted({
                tuple(nodes) for maximal in maximals
                for nodes in itertools.combinations(sorted(maximal), k + 1)
            })
        candidates = [_candidate(nodes, edge_values) for nodes in node_sets]
        if self.variant == "F2":
            # "First" means the deterministic lexicographically first
            # minimal (k+1) set, independent of its violation ranking.
            return candidates[:1]
        candidates.sort(key=lambda item: (
            -item["violation"], -item["efficiency"], item["nodes"]))
        if self.variant == "F3":
            return candidates[:model._clique_top_k]
        return candidates

    def summary_fields(self, model):
        return {"cut_formulation": {
            "F1": "maximal_clique",
            "F2": "first_k_plus_1",
            "F3": "top_k_k_plus_1",
            "F4": "all_unique_k_plus_1",
        }[self.variant]}


def solve(*args, **kwargs):
    cfg = kwargs.get("cfg")
    kwargs["method"] = StrongerCliqueCutsMethod(cfg)
    return core.solve(*args, **kwargs)
