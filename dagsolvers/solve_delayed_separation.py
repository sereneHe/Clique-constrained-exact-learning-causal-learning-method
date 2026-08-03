"""PPT Method A: delayed cycle/clique separation."""

import time
import itertools
from collections import defaultdict

import networkx as nx

from dagsolvers import solve_milp_clique_core as core


class DelayedSeparationMethod(core.CliqueMethod):
    family_name = "delayed_separation"

    def __init__(self, cfg):
        super().__init__(cfg)
        if self.variant != "A":
            raise ValueError(f"delayed_separation expects A, got {self.variant!r}")

    def initialize_model(self, model):
        model._separation_order = "cycle_first"
        model._delayed_second_separation = True
        model._callback_mode = "first_cycle"
        model._clique_callback_mode = "first_clique"
        model._max_cycle_cuts_per_callback = 1
        model._max_clique_cuts_per_callback = 1
        model._deduplicate_cycle_cuts = True
        model._deduplicate_clique_cuts = True
        model._skeleton_hits = defaultdict(int)
        model._dense_region_hits = defaultdict(int)
        model._delayed_skeleton_cycle_keys = defaultdict(set)
        model._delayed_violation_counts = defaultdict(int)
        model._delayed_classification_seconds = 0.0
        model._delayed_first_cycle_cuts = 0
        model._delayed_recurrence_escalations = 0
        model._delayed_clique_only_or_dag_dense_cuts = 0
        model._max_skeleton_hits = 0
        model._dense_escalation_hits = max(
            1, int(getattr(self.cfg, "dense_escalation_hits", 2)))
        model._clique_separation_time_budget = max(
            0.0, float(getattr(self.cfg, "clique_separation_time_budget", 0.1)))
        model._delayed_escalation_reasons = defaultdict(int)

    @staticmethod
    def _record_dense_history(model, selected_edges):
        signature = tuple(sorted({
            (min(i, j), max(i, j)) for i, j in selected_edges if i != j
        }))
        model._skeleton_hits[signature] += 1
        hits = model._skeleton_hits[signature]
        model._max_skeleton_hits = max(model._max_skeleton_hits, hits)
        graph = nx.Graph()
        graph.add_nodes_from(range(model._d))
        graph.add_edges_from(signature)
        started = time.perf_counter()
        violated = []
        for clique in nx.find_cliques(graph):
            if len(clique) > model._max_clique_size:
                violated.append(tuple(sorted(clique)))
                # Record every canonical minimal (k+1) dense region. Taking
                # only one prefix would hide other recurring regions inside a
                # larger maximal clique.
                for region in itertools.combinations(
                        sorted(clique), model._max_clique_size + 1):
                    model._dense_region_hits[tuple(region)] += 1
            if (model._clique_separation_time_budget > 0
                    and time.perf_counter() - started
                    >= model._clique_separation_time_budget):
                break
        return signature, hits, violated

    def on_mipsol(self, model, selected_edges, edge_values, weight_values,
                  lag_edge_values, lag_weight_values, objective):
        started = time.perf_counter()
        signature, skeleton_hits, violated_cliques = self._record_dense_history(
            model, selected_edges)
        cycles = core.find_cycles(selected_edges, "all_cycles")
        records = [(*core._cycle_edges_and_key(cycle), cycle)
                   for cycle in cycles]
        seen = model._delayed_skeleton_cycle_keys[signature]
        seen_before = len(seen)
        unseen = [record for record in records if record[1] not in seen]
        cycle_violation = bool(cycles)
        clique_violation = bool(violated_cliques)
        if cycle_violation and clique_violation:
            violation_class = "both"
        elif cycle_violation:
            violation_class = "cycle_only"
        elif clique_violation:
            violation_class = "clique_only"
        else:
            violation_class = "neither"
        model._delayed_violation_counts[violation_class] += 1
        different_cycle_recurrence = bool(seen and unseen)
        dense_hits = max((model._dense_region_hits[tuple(region)]
            for clique in violated_cliques
            for region in itertools.combinations(
                sorted(clique), model._max_clique_size + 1)), default=0)
        model._delayed_classification_seconds += time.perf_counter() - started

        cycle_added = clique_added = False
        action = "accept"
        if cycle_violation:
            recurrence_ready = (
                skeleton_hits >= model._dense_escalation_hits
                or dense_hits >= model._dense_escalation_hits)
            if clique_violation and recurrence_ready:
                clique_added = core._add_clique_cuts(
                    model, selected_edges, edge_values)
                if clique_added:
                    model._delayed_recurrence_escalations += 1
                    reason = ("different_cycle" if different_cycle_recurrence
                              else "dense_region_hits")
                    model._delayed_escalation_reasons[reason] += 1
                    action = "repeat_skeleton_add_clique"
            else:
                chosen = unseen[0] if unseen else records[0]
                cycle_added = core._add_cycle_cuts(
                    model, selected_edges, cycles_override=[chosen[2]])
                if cycle_added:
                    seen.add(chosen[1])
                    model._delayed_first_cycle_cuts += 1
                    action = "first_add_cycle_store_skeleton"
        elif clique_violation:
            clique_added = core._add_clique_cuts(
                model, selected_edges, edge_values)
            if clique_added:
                model._delayed_clique_only_or_dag_dense_cuts += 1
                action = "clique_only_or_dag_dense_add_clique"

        core._callback_log(
            model, "method_a_delayed_separation",
            mipsol_id=model._mipsol_count, violation_class=violation_class,
            skeleton_hits=skeleton_hits, previously_seen_cycles=seen_before,
            dense_region_hits=dense_hits,
            different_cycle_recurrence=int(different_cycle_recurrence),
            action=action)
        return cycle_added, clique_added

    def summary_fields(self, model):
        return {
            "violation_counts": dict(model._delayed_violation_counts),
            "classification_seconds": model._delayed_classification_seconds,
            "first_cycle_cuts": model._delayed_first_cycle_cuts,
            "recurrent_skeleton_clique_escalations": (
                model._delayed_recurrence_escalations),
            "clique_only_or_dag_dense_cuts": (
                model._delayed_clique_only_or_dag_dense_cuts),
            "unique_skeletons": len(model._skeleton_hits),
            "max_skeleton_hits": model._max_skeleton_hits,
            "dense_escalation_threshold": model._dense_escalation_hits,
            "unique_dense_regions": len(model._dense_region_hits),
            "dense_region_hit_histogram": dict(sorted(
                __import__("collections").Counter(
                    model._dense_region_hits.values()).items())),
            "escalation_reasons": dict(model._delayed_escalation_reasons),
        }


def solve(*args, **kwargs):
    cfg = kwargs.get("cfg")
    kwargs["method"] = DelayedSeparationMethod(cfg)
    return core.solve(*args, **kwargs)
