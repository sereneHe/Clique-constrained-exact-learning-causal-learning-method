"""PPT Method B: controlled addition of minimal (k+1) clique cuts."""

import itertools
from collections import defaultdict

from dagsolvers import solve_milp_clique_core as core


def _candidate(nodes, edge_values):
    nodes = tuple(sorted(nodes))
    pairs = list(itertools.combinations(nodes, 2))
    lhs = sum(float(edge_values[i, j]) + float(edge_values[j, i])
              for i, j in pairs)
    rhs = len(pairs) - 1
    violation = float(lhs - rhs)
    return {"nodes": nodes, "pairs": pairs, "rhs": rhs,
            "violation": violation,
            "efficiency": violation / max(len(pairs), 1)}


class ControlledCutAdditionMethod(core.CliqueMethod):
    family_name = "controlled_cut_addition"

    def __init__(self, cfg):
        super().__init__(cfg)
        if self.variant not in {"B1", "B2", "B3", "B4", "B5", "B6"}:
            raise ValueError(
                "controlled_cut_addition expects B1--B6, got "
                f"{self.variant!r}")

    def initialize_model(self, model):
        model._controlled_candidate_hits = defaultdict(int)
        model._controlled_selected_hits = defaultdict(int)
        model._controlled_similarity_rejections = 0
        model._controlled_max_jaccard = float(
            getattr(self.cfg, "max_cut_jaccard_similarity", 0.8))

    @staticmethod
    def _jaccard(left, right):
        left, right = set(left), set(right)
        return len(left & right) / max(len(left | right), 1)

    def integer_clique_candidates(self, model, selected_edges, edge_values):
        maximals = core._maximal_cliques(
            selected_edges, model._d, model._max_clique_size)
        k = model._max_clique_size
        minimal_sets = sorted({
            tuple(nodes) for maximal in maximals
            for nodes in itertools.combinations(sorted(maximal), k + 1)
        })
        candidates = [_candidate(nodes, edge_values) for nodes in minimal_sets]
        for item in candidates:
            key = item["nodes"]
            model._controlled_candidate_hits[key] += 1
            item["history_hits"] = model._controlled_candidate_hits[key]
            # Integer violations often tie. Efficiency + recurrence makes B3
            # genuinely different from arbitrary first-candidate selection.
            item["score"] = (item["efficiency"]
                             + 1e-3 * item["history_hits"])
        if self.variant == "B1":
            selected = candidates[:1]
        elif self.variant == "B2":
            selected = candidates
        elif self.variant == "B6":
            # Original most-violated baseline. Integer MIPSOL candidates often
            # tie, so node order provides a deterministic tie-break only.
            selected = sorted(candidates, key=lambda item: (
                -item["violation"], item["nodes"]))[:1]
        elif self.variant == "B3":
            selected = sorted(candidates, key=lambda item: (
                -item["score"], -item["violation"], item["nodes"]))[:1]
        else:
            ranked = sorted(candidates, key=lambda item: (
                -item["score"], -item["violation"], item["nodes"]))
            selected = []
            for item in ranked:
                if any(self._jaccard(item["nodes"], other["nodes"])
                       > model._controlled_max_jaccard
                       for other in selected):
                    model._controlled_similarity_rejections += 1
                    continue
                selected.append(item)
                if len(selected) >= model._clique_top_k:
                    break
        for item in selected:
            model._controlled_selected_hits[item["nodes"]] += 1
        return selected

    def summary_fields(self, model):
        return {
            "selection_policy": {
                "B1": "first_minimal_k_plus_1",
                "B2": "all_k_plus_1",
                "B3": "efficiency_history_scored",
                "B4": "top_k_scored_jaccard_diverse",
                "B5": "top_k_scored_jaccard_diverse_deduplicated",
                "B6": "original_most_violated",
            }[self.variant],
            "callback_cut_cap": model._max_clique_cuts_per_callback,
            "deduplicate": model._deduplicate_clique_cuts,
            "unique_candidates_seen": len(model._controlled_candidate_hits),
            "unique_candidates_selected": len(model._controlled_selected_hits),
            "similarity_rejections": model._controlled_similarity_rejections,
            "max_jaccard_similarity": model._controlled_max_jaccard,
        }


def solve(*args, **kwargs):
    cfg = kwargs.get("cfg")
    kwargs["method"] = ControlledCutAdditionMethod(cfg)
    return core.solve(*args, **kwargs)
