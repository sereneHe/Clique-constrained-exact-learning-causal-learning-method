"""PPT Method D: fractional clique separation with MIPNODE/cbCut."""

import itertools
import time
from collections import defaultdict

import gurobipy as gp
import networkx as nx
import numpy as np
from gurobipy import GRB

from dagsolvers import solve_milp_clique_core as core


def _candidate(y, nodes):
    nodes = tuple(sorted(nodes))
    pairs = list(itertools.combinations(nodes, 2))
    lhs = sum(y[i, j] for i, j in pairs)
    rhs = len(pairs) - 1
    violation = float(lhs - rhs)
    return {"nodes": nodes, "pairs": pairs, "rhs": rhs,
            "violation": violation,
            "efficiency": violation / max(len(pairs), 1)}


class FractionalSeparationMethod(core.CliqueMethod):
    family_name = "fractional_separation"

    def __init__(self, cfg):
        super().__init__(cfg)
        if self.variant not in {"D1", "D2", "D3", "D4", "D5"}:
            raise ValueError(f"fractional_separation expects D1--D5, got {self.variant!r}")

    def requires_precrush(self):
        return self.variant != "D1"

    def initialize_model(self, model):
        model._enable_fractional_clique_cuts = self.variant != "D1"
        model._fractional_root_only = self.variant in {"D2", "D3"}
        model._root_max_cuts_per_round = int(
            getattr(self.cfg, "root_max_cuts_per_round", 20))
        model._nonroot_max_cuts_per_callback = int(
            getattr(self.cfg, "nonroot_max_cuts_per_callback", 5))
        model._nonroot_separation_frequency = max(
            1, int(getattr(self.cfg, "nonroot_separation_frequency", 10)))
        model._fractional_violation_tolerance = float(
            getattr(self.cfg, "fractional_violation_tolerance", 1e-6))
        model._fractional_greedy_starts = int(
            getattr(self.cfg, "fractional_greedy_starts", 10))
        model._dense_history_min_hits = int(
            getattr(self.cfg, "dense_history_min_hits", 2))
        model._fractional_clique_cut_keys = set()
        model._fractional_candidates_detected = 0
        model._fractional_separation_seconds = 0.0
        model._dense_history_hits = defaultdict(int)
        model._fractional_callbacks_checked = 0
        model._fractional_callbacks_skipped = 0
        model._fractional_zero_candidate_rounds = 0
        model._fractional_disabled_after_zero_rounds = False
        model._fractional_max_zero_rounds = max(
            0, int(getattr(self.cfg, "fractional_max_zero_rounds", 3)))
        model._fractional_time_budget = max(
            0.0, float(getattr(
                self.cfg, "fractional_separation_time_budget", 0.02)))

    @staticmethod
    def _mass(edge_values, d):
        y = np.zeros((d, d), dtype=float)
        for i, j in edge_values.keys():
            y[i, j] = float(edge_values[i, j])
        return y + y.T

    @staticmethod
    def _exact(model, y, region=None, deadline=None):
        universe = tuple(range(model._d) if region is None else sorted(region))
        size = model._max_clique_size + 1
        found = []
        if len(universe) >= size:
            for nodes in itertools.combinations(universe, size):
                if deadline is not None and time.perf_counter() >= deadline:
                    break
                item = _candidate(y, nodes)
                if item["violation"] > model._fractional_violation_tolerance:
                    found.append(item)
        return found

    @staticmethod
    def _greedy(model, y, region=None, deadline=None):
        universe = tuple(range(model._d) if region is None else sorted(region))
        target = model._max_clique_size + 1
        if len(universe) < target:
            return []
        degrees = {i: sum(y[i, j] for j in universe if j != i)
                   for i in universe}
        starts = sorted(universe, key=lambda i: (-degrees[i], i))[
            :model._fractional_greedy_starts]
        found = {}
        for start in starts:
            if deadline is not None and time.perf_counter() >= deadline:
                break
            selected, remaining = [start], set(universe) - {start}
            while len(selected) < target and remaining:
                nxt = max(remaining,
                          key=lambda v: (sum(y[v, u] for u in selected), -v))
                selected.append(nxt)
                remaining.remove(nxt)
            improved = True
            while improved:
                if deadline is not None and time.perf_counter() >= deadline:
                    break
                improved = False
                current = _candidate(y, selected)
                for old in list(selected):
                    for new in sorted(set(universe) - set(selected)):
                        if (deadline is not None
                                and time.perf_counter() >= deadline):
                            break
                        trial = [v for v in selected if v != old] + [new]
                        item = _candidate(y, trial)
                        if item["violation"] > current["violation"] + 1e-12:
                            selected, improved = trial, True
                            break
                    if improved:
                        break
            item = _candidate(y, selected)
            if item["violation"] > model._fractional_violation_tolerance:
                found[item["nodes"]] = item
        return list(found.values())

    def _select(self, model, y, node_count, deadline=None):
        if self.variant == "D3":
            return self._greedy(model, y, deadline=deadline)
        if self.variant == "D4":
            return (self._exact(model, y, deadline=deadline) if node_count == 0
                    else self._greedy(model, y, deadline=deadline))
        if self.variant == "D5" and node_count != 0:
            found = {}
            for nodes, hits in model._dense_history_hits.items():
                if hits < model._dense_history_min_hits:
                    continue
                for item in self._greedy(
                        model, y, region=nodes, deadline=deadline):
                    found[item["nodes"]] = item
            return list(found.values())
        return self._exact(model, y, deadline=deadline)

    def on_mipnode(self, model):
        if self.variant == "D1":
            return
        if model.cbGet(GRB.Callback.MIPNODE_STATUS) != GRB.OPTIMAL:
            return
        node_count = int(model.cbGet(GRB.Callback.MIPNODE_NODCNT))
        if model._fractional_root_only and node_count != 0:
            model._fractional_callbacks_skipped += 1
            return
        if node_count and node_count % model._nonroot_separation_frequency:
            model._fractional_callbacks_skipped += 1
            return
        if model._fractional_disabled_after_zero_rounds:
            model._fractional_callbacks_skipped += 1
            return
        model._fractional_callbacks_checked += 1
        values = model.cbGetNodeRel(model._edges_vars)
        y = self._mass(values, model._d)
        started = time.perf_counter()
        deadline = (started + model._fractional_time_budget
                    if model._fractional_time_budget > 0 else None)
        candidates = sorted(self._select(model, y, node_count, deadline),
                            key=lambda item: item["violation"], reverse=True)
        model._fractional_candidates_detected += len(candidates)
        separation_elapsed = time.perf_counter() - started
        model._fractional_separation_seconds += separation_elapsed
        if candidates:
            model._fractional_zero_candidate_rounds = 0
        else:
            model._fractional_zero_candidate_rounds += 1
            if ((model._fractional_root_only or node_count > 0)
                    and model._fractional_max_zero_rounds > 0
                    and model._fractional_zero_candidate_rounds
                    >= model._fractional_max_zero_rounds):
                model._fractional_disabled_after_zero_rounds = True
        limit = (model._root_max_cuts_per_round if node_count == 0
                 else model._nonroot_max_cuts_per_callback)
        added = 0
        for item in candidates:
            if (model._fractional_time_budget > 0
                    and time.perf_counter() - started
                    >= model._fractional_time_budget):
                break
            key = tuple(item["nodes"])
            if key in model._fractional_clique_cut_keys:
                continue
            model.cbCut(gp.quicksum(
                model._edges_vars[i, j] + model._edges_vars[j, i]
                for i, j in item["pairs"]) <= item["rhs"])
            model._fractional_clique_cut_keys.add(key)
            model._clique_user_count += 1
            added += 1
            if limit > 0 and added >= limit:
                break

    def on_mipsol(self, model, selected_edges, edge_values, weight_values,
                  lag_edge_values, lag_weight_values, objective):
        skeleton = nx.Graph()
        skeleton.add_nodes_from(range(model._d))
        skeleton.add_edges_from((min(i, j), max(i, j))
                                for i, j in selected_edges)
        for clique in nx.find_cliques(skeleton):
            if len(clique) > model._max_clique_size:
                model._dense_history_hits[tuple(sorted(clique))] += 1
        return super().on_mipsol(
            model, selected_edges, edge_values, weight_values,
            lag_edge_values, lag_weight_values, objective)

    def summary_fields(self, model):
        return {
            "fractional_candidates_detected": model._fractional_candidates_detected,
            "fractional_user_cuts": model._clique_user_count,
            "fractional_separation_seconds": model._fractional_separation_seconds,
            "unique_fractional_cuts": len(model._fractional_clique_cut_keys),
            "fractional_callbacks_checked": model._fractional_callbacks_checked,
            "fractional_callbacks_skipped": model._fractional_callbacks_skipped,
            "zero_candidate_rounds": model._fractional_zero_candidate_rounds,
            "disabled_after_zero_rounds": (
                model._fractional_disabled_after_zero_rounds),
            "separation_time_budget": model._fractional_time_budget,
        }


def solve(*args, **kwargs):
    cfg = kwargs.get("cfg")
    kwargs["method"] = FractionalSeparationMethod(cfg)
    return core.solve(*args, **kwargs)
