"""Configurable clique separation formulation and candidate selection."""

import itertools
import os
from collections import defaultdict

from dagsolvers import solve_milp_clique_core as core


def _env_bool(name, default):
    value = os.environ.get(name)
    if value is None:
        return default
    if value.lower() in {"1", "true", "yes", "on"}:
        return True
    if value.lower() in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be true or false, got {value!r}")


def _candidate(nodes, edge_values):
    nodes = tuple(sorted(nodes))
    pairs = list(itertools.combinations(nodes, 2))
    lhs = sum(float(edge_values[i, j]) + float(edge_values[j, i])
              for i, j in pairs)
    rhs = len(pairs) - 1
    violation = float(lhs - rhs)
    return {
        "nodes": nodes, "pairs": pairs, "rhs": rhs,
        "violation": violation,
        "efficiency": violation / max(len(pairs), 1),
    }


class CliqueSeparationOptionsMethod(core.CliqueMethod):
    family_name = "clique_separation_options"

    def __init__(self, cfg):
        super().__init__(cfg)
        self.formulation = os.environ.get(
            "CLIQUE_SEPERATION_FORMULATION", "k_plus_1").lower()
        self.selection = os.environ.get(
            "CLIQUE_SEPERATION_SELECTION", "first").lower()
        valid_formulations = {"maximal", "k_plus_1"}
        valid_selections = {
            "first", "all", "most_violated", "history",
            "top_k", "top_k_diverse",
        }
        if self.formulation not in valid_formulations:
            raise ValueError(
                "CLIQUE_SEPERATION_FORMULATION must be maximal or k_plus_1; got "
                f"{self.formulation!r}")
        if self.selection not in valid_selections:
            raise ValueError(
                "invalid CLIQUE_SEPERATION_SELECTION: " f"{self.selection!r}")
        self.variant = f"{self.formulation}_{self.selection}".upper()

    def initialize_model(self, model):
        model._clique_option_candidate_hits = defaultdict(int)
        model._clique_option_selected_hits = defaultdict(int)
        model._clique_option_similarity_rejections = 0
        model._controlled_max_jaccard = float(os.environ.get(
            "CLIQUE_SEPERATION_MAX_JACCARD",
            getattr(self.cfg, "max_cut_jaccard_similarity", 0.8)))
        model._clique_top_k = int(os.environ.get(
            "CLIQUE_SEPERATION_TOP_K", model._clique_top_k))
        model._deduplicate_clique_cuts = _env_bool(
            "CLIQUE_SEPERATION_DEDUP", model._deduplicate_clique_cuts)

    @staticmethod
    def _jaccard(left, right):
        left, right = set(left), set(right)
        return len(left & right) / max(len(left | right), 1)

    def integer_clique_candidates(self, model, selected_edges, edge_values):
        maximals = core._maximal_cliques(
            selected_edges, model._d, model._max_clique_size)
        if self.formulation == "maximal":
            node_sets = sorted(maximals, key=lambda nodes: (-len(nodes), nodes))
        else:
            k = model._max_clique_size
            node_sets = sorted({
                tuple(nodes) for maximal in maximals
                for nodes in itertools.combinations(sorted(maximal), k + 1)
            })

        candidates = [_candidate(nodes, edge_values) for nodes in node_sets]
        for item in candidates:
            key = item["nodes"]
            model._clique_option_candidate_hits[key] += 1
            item["history_hits"] = model._clique_option_candidate_hits[key]
            item["score"] = item["efficiency"] + 1e-3 * item["history_hits"]

        ranked = sorted(candidates, key=lambda item: (
            -item["violation"], -item["efficiency"], item["nodes"]))
        if self.selection == "first":
            chosen = candidates[:1]
        elif self.selection == "all":
            chosen = candidates
        elif self.selection == "most_violated":
            chosen = ranked[:1]
        elif self.selection == "history":
            chosen = sorted(candidates, key=lambda item: (
                -item["score"], -item["violation"], item["nodes"]))[:1]
        elif self.selection == "top_k":
            chosen = ranked[:model._clique_top_k]
        else:
            history_ranked = sorted(candidates, key=lambda item: (
                -item["score"], -item["violation"], item["nodes"]))
            chosen = []
            for item in history_ranked:
                if any(self._jaccard(item["nodes"], other["nodes"])
                       > model._controlled_max_jaccard for other in chosen):
                    model._clique_option_similarity_rejections += 1
                    continue
                chosen.append(item)
                if len(chosen) >= model._clique_top_k:
                    break

        for item in chosen:
            model._clique_option_selected_hits[item["nodes"]] += 1
        return chosen

    def summary_fields(self, model):
        return {
            "clique_separation_formulation": self.formulation,
            "clique_separation_selection": self.selection,
            "clique_separation_top_k": model._clique_top_k,
            "clique_separation_deduplicate": model._deduplicate_clique_cuts,
            "max_jaccard_similarity": model._controlled_max_jaccard,
            "unique_candidates_seen": len(model._clique_option_candidate_hits),
            "unique_candidates_selected": len(model._clique_option_selected_hits),
            "similarity_rejections": model._clique_option_similarity_rejections,
        }


def solve(*args, **kwargs):
    cfg = kwargs.get("cfg")
    kwargs["method"] = CliqueSeparationOptionsMethod(cfg)
    return core.solve(*args, **kwargs)
