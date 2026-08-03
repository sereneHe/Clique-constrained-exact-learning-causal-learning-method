"""PPT Method C: repair a rejected incumbent and submit a heuristic."""

import itertools
import json
import os
import time
from collections import defaultdict

import networkx as nx
import numpy as np

from dagsolvers import solve_milp_clique_core as core


class RepairIncumbentMethod(core.CliqueMethod):
    family_name = "repair_incumbent"
    _modes = {"C1": "none", "C2": "greedy_delete",
              "C3": "local_ls", "C4": "local_ridge",
              "C5": "local_ridge", "C6": "local_ridge"}

    def __init__(self, cfg):
        super().__init__(cfg)
        if self.variant not in self._modes:
            raise ValueError(f"repair_incumbent expects C1--C6, got {self.variant!r}")

    def initialize_model(self, model):
        model._incumbent_repair_mode = self._modes[self.variant]
        model._repair_ridge_alpha = float(
            getattr(self.cfg, "repair_ridge_alpha", 1e-3))
        model._repair_refit_solver = str(
            getattr(self.cfg, "repair_refit_solver", "auto")).lower()
        model._repair_deletion_score = str(
            getattr(self.cfg, "repair_deletion_score", "violation_loss")).lower()
        model._repair_violation_weight = float(
            getattr(self.cfg, "repair_violation_weight", 1.0))
        model._repair_loss_weight = float(
            getattr(self.cfg, "repair_loss_weight", 1.0))
        model._repair_max_retries = int(
            getattr(self.cfg, "repair_max_retries", 2))
        model._repair_metrics = {
            "attempts": 0, "submitted": 0, "matched_accepted": 0,
            "failed": 0, "edges_removed": 0,
            "columns_refitted": 0, "time": 0.0,
            "validation_failures": 0, "retry_attempts": 0,
            "cbuse_accepted": 0, "cbuse_rejected": 0,
            "cbuse_deferred": 0,
            "matched_improved_incumbent": 0,
        }
        model._repair_failure_reasons = defaultdict(int)
        model._repair_submitted_supports = set()
        model._repair_objective_degradations = []
        model._repair_violation_edge_hits = defaultdict(int)
        model._repair_best_accepted_support = set()
        model._repair_removed_records = []
        model._repair_cache_loaded_cycle = 0
        model._repair_cache_loaded_clique = 0
        model._repair_cache_saved_cycle = 0
        model._repair_cache_saved_clique = 0
        model._repair_cut_cache_mode = str(
            getattr(self.cfg, "repair_cut_cache_mode", "off")).lower()
        model._repair_cut_cache_path = self._cache_path(model)
        if self.variant == "C6" and model._repair_cut_cache_mode in {
                "read", "read_write"}:
            self._load_valid_cut_cache(model)

    def _cache_path(self, model):
        directory = str(getattr(self.cfg, "repair_cut_cache_dir", "repair_cut_cache"))
        metadata = dict(getattr(self.cfg, "experiment_metadata", {}) or {})
        seed = metadata.get("seed", "unknown")
        return os.path.join(
            directory,
            f"valid_cuts_d{model._d}_k{model._max_clique_size}_seed{seed}.json")

    @staticmethod
    def _load_valid_cut_cache(model):
        path = model._repair_cut_cache_path
        if not os.path.exists(path):
            return
        with open(path) as handle:
            payload = json.load(handle)
        if (int(payload.get("d", -1)) != model._d
                or int(payload.get("max_clique_size", -1))
                != model._max_clique_size):
            return
        for raw_cycle in payload.get("cycle_cuts", []):
            edges = tuple(sorted((int(i), int(j)) for i, j in raw_cycle))
            if not edges or edges in model._added_cycle_cut_keys:
                continue
            model.addConstr(
                sum(model._edges_vars[i, j] for i, j in edges)
                <= len(edges) - 1)
            model._added_cycle_cut_keys.add(edges)
            model._repair_cache_loaded_cycle += 1
        for raw_clique in payload.get("clique_cuts", []):
            clique = tuple(sorted(int(node) for node in raw_clique))
            if (len(clique) <= model._max_clique_size
                    or clique in model._added_clique_cut_keys):
                continue
            pairs = list(itertools.combinations(clique, 2))
            model.addConstr(sum(
                model._edges_vars[i, j] + model._edges_vars[j, i]
                for i, j in pairs) <= len(pairs) - 1)
            model._added_clique_cut_keys.add(clique)
            model._repair_cache_loaded_clique += 1

    @staticmethod
    def _save_valid_cut_cache(model):
        path = model._repair_cut_cache_path
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        payload = {
            "d": model._d,
            "max_clique_size": model._max_clique_size,
            "cycle_cuts": [[list(edge) for edge in cycle]
                           for cycle in sorted(model._added_cycle_cut_keys)],
            "clique_cuts": [list(clique)
                            for clique in sorted(model._added_clique_cut_keys)],
        }
        temporary = path + f".tmp.{os.getpid()}"
        with open(temporary, "w") as handle:
            json.dump(payload, handle, indent=2)
        os.replace(temporary, path)
        model._repair_cache_saved_cycle = len(payload["cycle_cuts"])
        model._repair_cache_saved_clique = len(payload["clique_cuts"])

    @staticmethod
    def _deletion_loss(model, edge, weights, support, lag_weight_values):
        """Exact data-fit SSE change if one contemporaneous edge is removed."""
        source, target = edge
        prediction = sum(
            model._X[:, parent] * float(weights[parent, target])
            for parent, child in support if child == target)
        for lag_index, lag_data in enumerate(model._Y):
            prediction = prediction + lag_data @ np.asarray([
                float(lag_weight_values[lag_index][i, target])
                for i in range(model._d)])
        residual = model._X[:, target] - prediction
        removed_contribution = model._X[:, source] * float(weights[edge])
        new_residual = residual + removed_contribution
        return float((new_residual @ new_residual - residual @ residual)
                     / len(model._X))

    def _choose_edge(self, model, choices, weights, support,
                     lag_weight_values):
        losses = {
            edge: self._deletion_loss(
                model, edge, weights, support, lag_weight_values)
            for edge in choices}
        if model._repair_deletion_score == "weight_only":
            edge = min(choices, key=lambda item: abs(float(weights[item])))
            return edge, {"loss_delta": losses[edge], "score": None}
        best_support = model._repair_best_accepted_support
        scale = max(1e-12, max(abs(value) for value in losses.values()))
        def priority(edge):
            history = model._repair_violation_edge_hits[edge]
            protected = 1 if edge in best_support else 0
            score = (model._repair_violation_weight * (1.0 + history)
                     - model._repair_loss_weight * losses[edge] / scale
                     - 2.0 * protected)
            return score, -abs(float(weights[edge])), edge
        edge = max(choices, key=priority)
        return edge, {
            "loss_delta": losses[edge],
            "violation_hits": model._repair_violation_edge_hits[edge],
            "score": priority(edge)[0],
        }

    def _repair_support(self, model, selected_edges, weights,
                        lag_weight_values):
        support, removed, decisions = set(selected_edges), [], []
        while True:
            directed = nx.DiGraph()
            directed.add_nodes_from(range(model._d))
            directed.add_edges_from(support)
            try:
                cycle = nx.find_cycle(directed, orientation="original")
            except nx.NetworkXNoCycle:
                cycle = []
            if cycle:
                choices = [(u, v) for u, v, *_ in cycle]
                edge, details = self._choose_edge(
                    model, choices, weights, support, lag_weight_values)
                support.remove(edge)
                removed.append(edge)
                decisions.append({"reason": "cycle", "edge": list(edge),
                                  **details})
                continue
            skeleton = nx.Graph()
            skeleton.add_nodes_from(range(model._d))
            skeleton.add_edges_from((min(i, j), max(i, j)) for i, j in support)
            violated = [tuple(clique) for clique in nx.find_cliques(skeleton)
                        if len(clique) > model._max_clique_size]
            if not violated:
                return support, removed, decisions
            clique = max(violated, key=len)
            choices = [(i, j) for i, j in support
                       if i in clique and j in clique]
            if not choices:
                return None, removed, decisions
            edge, details = self._choose_edge(
                model, choices, weights, support, lag_weight_values)
            support.remove(edge)
            removed.append(edge)
            decisions.append({"reason": "clique", "edge": list(edge),
                              "clique": list(clique), **details})

    @staticmethod
    def _refit(model, support, original_weights, mode, affected,
               lag_weight_values):
        repaired = {key: (float(original_weights[key]) if key in support else 0.0)
                    for key in model._edges_weights.keys()}
        if mode not in {"local_ls", "local_ridge"}:
            return repaired
        alpha = model._repair_ridge_alpha if mode == "local_ridge" else 0.0
        for target in affected:
            parents = sorted(i for i, j in support if j == target)
            for source in range(model._d):
                if source != target:
                    repaired[source, target] = 0.0
            if not parents:
                continue
            design = model._X[:, parents]
            response = model._X[:, target].copy()
            for lag_index, lag_data in enumerate(model._Y):
                response -= lag_data @ np.asarray([
                    float(lag_weight_values[lag_index][i, target])
                    for i in range(model._d)])
            gram = design.T @ design + alpha * np.eye(len(parents))
            solver = model._repair_refit_solver
            try:
                if solver == "qr" or (solver == "auto" and alpha == 0.0):
                    if alpha > 0.0:
                        augmented_x = np.vstack(
                            [design, np.sqrt(alpha) * np.eye(len(parents))])
                        augmented_y = np.concatenate(
                            [response, np.zeros(len(parents))])
                    else:
                        augmented_x, augmented_y = design, response
                    q, r = np.linalg.qr(augmented_x, mode="reduced")
                    beta = np.linalg.solve(r, q.T @ augmented_y)
                else:
                    beta = np.linalg.solve(gram, design.T @ response)
            except np.linalg.LinAlgError:
                beta = np.linalg.lstsq(design, response, rcond=None)[0]
            for parent, coefficient in zip(parents, beta):
                bound = model._edge_specific_bounds.get(
                    (parent, target), model._global_big_m)
                repaired[parent, target] = float(
                    np.clip(coefficient, -bound, bound))
        return repaired

    @staticmethod
    def _validate_repair(model, support, repaired, lag_edge_values,
                         lag_weight_values, tolerance=1e-7):
        """Validate every structural/linking constraint affected by repair."""
        errors = []
        graph = nx.DiGraph()
        graph.add_nodes_from(range(model._d))
        graph.add_edges_from(support)
        if not nx.is_directed_acyclic_graph(graph):
            errors.append("cycle")
        skeleton = nx.Graph()
        skeleton.add_nodes_from(range(model._d))
        skeleton.add_edges_from((min(i, j), max(i, j)) for i, j in support)
        max_size = max((len(c) for c in nx.find_cliques(skeleton)), default=0)
        if max_size > model._max_clique_size:
            errors.append("clique")
        if any((j, i) in support for i, j in support):
            errors.append("antiparallel")
        for edge, value in repaired.items():
            bound = model._edge_specific_bounds.get(edge, model._global_big_m)
            selected = edge in support
            if abs(float(value)) > bound + tolerance:
                errors.append(f"weight_bound:{edge}")
            if not selected and abs(float(value)) > tolerance:
                errors.append(f"weight_without_edge:{edge}")
        for edge_values, weight_values in zip(
                lag_edge_values, lag_weight_values):
            for edge, value in weight_values.items():
                bound = model._global_big_m
                if abs(float(value)) > bound * float(edge_values[edge]) + tolerance:
                    errors.append(f"lag_link:{edge}")
        return {"valid": not errors, "errors": errors,
                "max_clique_size": max_size}

    def on_rejected(self, model, selected_edges, edge_values, weight_values,
                    lag_edge_values, lag_weight_values, objective):
        mode = model._incumbent_repair_mode
        if mode == "none":
            return
        started = time.perf_counter()
        model._repair_metrics["attempts"] += 1
        support, removed, decisions = self._repair_support(
            model, selected_edges, weight_values, lag_weight_values)
        if support is None or not removed:
            model._repair_metrics["failed"] += 1
            model._repair_failure_reasons["no_repairable_support"] += 1
            model._repair_metrics["time"] += time.perf_counter() - started
            return
        original_support = set(selected_edges)
        record = {
            "mipsol_id": model._mipsol_count,
            "deletion_decisions": decisions,
            "attempts": [],
        }
        cbuse_result = None
        submission_status = "not_submitted"
        repaired = None
        for retry in range(model._repair_max_retries + 1):
            affected = {j for _, j in removed}
            original_parents = {
                str(target): sorted(i for i, j in original_support
                                    if j == target)
                for target in affected}
            repaired_parents = {
                str(target): sorted(i for i, j in support if j == target)
                for target in affected}
            repaired = self._refit(
                model, support, weight_values, mode, affected,
                lag_weight_values)
            validation = self._validate_repair(
                model, support, repaired, lag_edge_values, lag_weight_values)
            attempt = {
                "retry": retry,
                "removed_edges": [list(edge) for edge in removed],
                "affected_targets": sorted(affected),
                "original_parents": original_parents,
                "repaired_parents": repaired_parents,
                "validation": validation,
            }
            record["attempts"].append(attempt)
            if not validation["valid"]:
                model._repair_metrics["validation_failures"] += 1
                for error in validation["errors"]:
                    model._repair_failure_reasons[error.split(":", 1)[0]] += 1
                cbuse_result = None
            else:
                model.cbSetSolution(
                    list(model._edges_vars.values()),
                    [1.0 if key in support else 0.0
                     for key in model._edges_vars.keys()])
                model.cbSetSolution(
                    list(model._edges_weights.values()),
                    [repaired[key] for key in model._edges_weights.keys()])
                for variables, values in zip(
                        model._lag_edges_vars, lag_edge_values):
                    model.cbSetSolution(
                        list(variables.values()),
                        [float(values[key]) for key in variables.keys()])
                for variables, values in zip(
                        model._lag_edges_weights, lag_weight_values):
                    model.cbSetSolution(
                        list(variables.values()),
                        [float(values[key]) for key in variables.keys()])
                cbuse_result = float(model.cbUseSolution())
                attempt["cbuse_result"] = cbuse_result
                # on_rejected is called from MIPSOL.  Gurobi documents that
                # cbUseSolution stores the proposed solution for later in
                # this callback context and therefore returns GRB.INFINITY;
                # that value is not a rejection.  Actual later acceptance is
                # matched by support in on_accepted().
                attempt["cbuse_immediate"] = False
                attempt["cbuse_status"] = "deferred"
                model._repair_metrics["cbuse_deferred"] += 1
                submission_status = "deferred"
                break
            if retry >= model._repair_max_retries or not support:
                break
            # Explicit fallback: remove one additional loss-aware edge, refit
            # its target column, validate again, and resubmit.
            fallback, details = self._choose_edge(
                model, list(support), weight_values, support,
                lag_weight_values)
            support.remove(fallback)
            removed.append(fallback)
            decision = {"reason": "repair_retry", "edge": list(fallback),
                        **details}
            decisions.append(decision)
            model._repair_metrics["retry_attempts"] += 1
        record["final_cbuse_result"] = cbuse_result
        record["submission_status"] = submission_status
        record["success"] = submission_status in {"accepted", "deferred"}
        model._repair_removed_records.append(record)
        if not record["success"]:
            model._repair_metrics["failed"] += 1
            model._repair_failure_reasons["submission_not_reached"] += 1
            model._repair_metrics["time"] += time.perf_counter() - started
            return
        support_key = tuple(sorted(support))
        model._repair_submitted_supports.add(support_key)
        model._repair_metrics["submitted"] += 1
        model._repair_metrics["edges_removed"] += len(removed)
        if mode != "greedy_delete":
            model._repair_metrics["columns_refitted"] += len(affected)
        residual = model._X - model._X @ np.asarray([
            [repaired.get((i, j), 0.0) for j in range(model._d)]
            for i in range(model._d)])
        for lag_index, lag_data in enumerate(model._Y):
            lag_matrix = np.asarray([
                [float(lag_weight_values[lag_index][i, j])
                 for j in range(model._d)] for i in range(model._d)])
            residual -= lag_data @ lag_matrix
        approximate_objective = float(np.sum(residual ** 2) / len(model._X))
        model._repair_objective_degradations.append(
            approximate_objective - float(objective))
        model._repair_metrics["time"] += time.perf_counter() - started

    def on_accepted(self, model, selected_edges, objective):
        model._repair_best_accepted_support = set(selected_edges)
        support_key = tuple(sorted(selected_edges))
        if support_key in model._repair_submitted_supports:
            model._repair_metrics["matched_accepted"] += 1
            if objective < model._best_accepted_objective - 1e-9:
                model._repair_metrics["matched_improved_incumbent"] += 1
            model._repair_submitted_supports.discard(support_key)

    def on_mipsol(self, model, selected_edges, edge_values, weight_values,
                  lag_edge_values, lag_weight_values, objective):
        if self.variant == "C5":
            for cycle in core.find_cycles(selected_edges, "all_cycles"):
                edges, _ = core._cycle_edges_and_key(cycle)
                for edge in edges:
                    model._repair_violation_edge_hits[edge] += 1
            skeleton = nx.Graph()
            skeleton.add_nodes_from(range(model._d))
            skeleton.add_edges_from((min(i, j), max(i, j))
                                    for i, j in selected_edges)
            selected = set(selected_edges)
            for clique in nx.find_cliques(skeleton):
                if len(clique) <= model._max_clique_size:
                    continue
                for i, j in selected:
                    if i in clique and j in clique:
                        model._repair_violation_edge_hits[i, j] += 1
        return super().on_mipsol(
            model, selected_edges, edge_values, weight_values,
            lag_edge_values, lag_weight_values, objective)

    def finalize(self, model):
        if self.variant == "C6" and model._repair_cut_cache_mode in {
                "write", "read_write"}:
            self._save_valid_cut_cache(model)

    def summary_fields(self, model):
        submitted = model._repair_metrics["submitted"]
        signed_changes = model._repair_objective_degradations
        positive_degradations = [value for value in signed_changes if value > 0]
        return {
            "repair_config": {
                "mode": model._incumbent_repair_mode,
                "deletion_score": model._repair_deletion_score,
                "violation_weight": model._repair_violation_weight,
                "loss_weight": model._repair_loss_weight,
                "refit_solver": model._repair_refit_solver,
                "ridge_alpha": model._repair_ridge_alpha,
                "max_retries": model._repair_max_retries,
            },
            "repair_metrics": dict(model._repair_metrics),
            "repair_failure_reasons": dict(model._repair_failure_reasons),
            "repair_success_rate": (
                model._repair_metrics["matched_accepted"] / submitted
                if submitted else None),
            "repair_incumbent_improvement_rate": (
                model._repair_metrics["matched_improved_incumbent"] / submitted
                if submitted else None),
            "mean_objective_degradation": (
                float(np.mean(positive_degradations))
                if positive_degradations else 0.0),
            "mean_signed_objective_change": (
                float(np.mean(signed_changes)) if signed_changes else None),
            "repair_objective_improvement_fraction": (
                sum(value < 0 for value in signed_changes) / len(signed_changes)
                if signed_changes else None),
            "repair_records": model._repair_removed_records,
            "trajectory_violation_edge_count": len(
                model._repair_violation_edge_hits),
            "valid_cut_cache": {
                "mode": model._repair_cut_cache_mode,
                "path": model._repair_cut_cache_path,
                "loaded_cycle": model._repair_cache_loaded_cycle,
                "loaded_clique": model._repair_cache_loaded_clique,
                "saved_cycle": model._repair_cache_saved_cycle,
                "saved_clique": model._repair_cache_saved_clique,
            },
        }


def solve(*args, **kwargs):
    cfg = kwargs.get("cfg")
    kwargs["method"] = RepairIncumbentMethod(cfg)
    return core.solve(*args, **kwargs)
